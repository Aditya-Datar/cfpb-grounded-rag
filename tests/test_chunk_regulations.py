import hashlib
import json
import re
import sys
from pathlib import Path

CHUNKING = Path(__file__).resolve().parents[1] / "chunking"
ROOT = CHUNKING.parent
sys.path.insert(0, str(CHUNKING))

import chunk_regulations  # noqa: E402
from chunk_regulations import (  # noqa: E402
    DEFAULT_FCRA_PATH, DEFAULT_OUT_PATH, DEFAULT_SECTIONS_PATH, EMBED_MAX_TOKENS,
    chunk_record, heading_only, load_fcra_chunks, load_token_counter,
    split_at_markers,
)
from parse_regulations import SINGLE_RE, leading_markers  # noqa: E402

URL = "https://www.ecfr.gov/current/title-12/part-1005/section-1005.99"
SECTIONS = CHUNKING / "data/processed/sections.jsonl"


def _real_record(section):
    """A regulation record from the committed sections.jsonl."""
    with SECTIONS.open(encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            if record["section"] == section and record["content_type"] == "regulation":
                return record
    raise LookupError(section)


def _record(blocks):
    """A regulation record shaped like parse_regulations.py output."""
    full = []
    for i, (text, path, continuation, certain) in enumerate(blocks):
        full.append({
            "type": "paragraph", "text": text, "i": i, "path": path,
            "label": "".join(f"({p})" for p in path), "continuation": continuation,
            "path_certain": certain, "in_wrapper": False,
        })
    return {
        "record_id": "12:1005:SECTION:§ 1005.99", "part": "1005", "regulation": "E",
        "section": "1005.99", "heading": "§ 1005.99 Test section.",
        "section_heading": "Test section.", "content_type": "regulation",
        "source_url": URL, "blocks": full,
    }


def _long_record(certain=True):
    filler = "word " * 60
    return _record([
        ("(c) Time limits—(1) Ten-day period. " + filler, ["c", "1"], False, True),
        ("(2) Forty-five day period. " + filler, ["c", "2"], False, certain),
        ("(d) Other rules. " + filler, ["d"], False, True),
    ])


def test_split_fused_markers():
    assert split_at_markers("(c) Time limits—(1) Ten-day period.") == ["(c) Time limits—", "(1) Ten-day period."]


def test_marker_run_stays_together():
    assert split_at_markers("(a)(1) “Access device” means") == ["", "(a)(1) “Access device” means"]


def test_short_section_is_one_chunk():
    chunks = chunk_record(_record([
        ("Intro text:", [], True, True),
        ("(a) First.", ["a"], False, True),
        ("(b) Second.", ["b"], False, True),
    ]))
    assert len(chunks) == 1
    c = chunks[0]
    assert (c["chunk_id"], c["paragraph"], c["source_url"]) == ("12-1005-1005.99-all", "", URL)
    assert c["text"] == "§ 1005.99 Test section.\nIntro text:\n(a) First.\n(b) Second."


def test_first_seven_fields_match_team_format():
    chunk = chunk_record(_record([("(a) First.", ["a"], False, True)]))[0]
    assert list(chunk)[:7] == ["chunk_id", "part", "section", "paragraph", "heading", "text", "source_url"]


def test_long_section_splits_and_keeps_parent_intro():
    chunks = chunk_record(_long_record(), max_chars=400)
    assert [c["paragraph"] for c in chunks] == ["(c)(1)", "(c)(2)", "(d)"]
    c2 = chunks[1]
    assert c2["text"].startswith("§ 1005.99 Test section.\n(c) Time limits—\n(2) Forty-five day period.")
    assert c2["source_url"] == URL + "#p-1005.99(c)(2)"
    assert c2["chunk_id"] == "12-1005-1005.99-c-2"


def test_split_only_as_deep_as_needed():
    chunks = chunk_record(_long_record(), max_chars=700)
    assert [c["paragraph"] for c in chunks] == ["(c)", "(d)"]


def test_uncertain_path_is_flagged_and_unanchored():
    chunks = chunk_record(_long_record(certain=False), max_chars=400)
    c2 = chunks[1]
    assert c2["path_certain"] is False
    assert c2["source_url"] == URL
    assert chunks[0]["path_certain"] is True


def test_continuation_stays_with_previous_paragraph():
    chunks = chunk_record(_record([
        ("(a) Rule. " + "word " * 60, ["a"], False, True),
        ("More about (a).", ["a"], True, True),
        ("(b) Next. " + "word " * 60, ["b"], False, True),
    ]), max_chars=400)
    assert [c["paragraph"] for c in chunks] == ["(a)", "(b)"]
    assert chunks[0]["text"].endswith("More about (a).")


def test_1005_11_chunks_at_2000():
    chunks = chunk_record(_real_record("1005.11"), max_chars=2000)
    assert [c["paragraph"] for c in chunks] == [
        "(a)", "(b)", "(c)(1)", "(c)(2)", "(c)(3)", "(c)(4)", "(d)", "(e)",
    ]


def test_default_1400_chunks_for_1005_11():
    chunks = chunk_record(_real_record("1005.11"))
    assert [c["paragraph"] for c in chunks] == [
        "(a)", "(b)(1)", "(b)(2)", "(b)(3)", "(c)(1)", "(c)(2)(i)", "(c)(2)(ii)", "(c)(2)(iii)",
        "(c)(2)(iv)", "(c)(3)", "(c)(4)", "(d)(1)", "(d)(2)", "(e)",
    ]


def test_smaller_limit_gives_more_chunks_for_1005_11():
    record = _real_record("1005.11")
    assert len(chunk_record(record, max_chars=800)) > len(chunk_record(record, max_chars=2000))


def test_every_block_in_one_chunk_at_several_limits():
    record = _real_record("1005.11")
    block_texts = [b["text"] for b in record["blocks"]]
    for max_chars in (500, 800, 2000, 4000):
        # chunk_record raises if any text is lost or duplicated.
        chunks = chunk_record(record, max_chars=max_chars)
        for text in block_texts:
            # Fused blocks are split across parent and child, so check the tail.
            tail = text[-40:]
            assert any(tail in c["text"] for c in chunks), (max_chars, tail)


def test_split_period_form():
    assert split_at_markers("(b) Record retention. (1) Any person shall retain") == [
        "(b) Record retention. ", "(1) Any person shall retain",
    ]


def test_period_form_needs_a_list_start():
    # "(ii)" cannot start a list, so it is a cross-reference, not a new paragraph.
    assert split_at_markers("(2) Coverage. (ii) applies here") == ["(2) Coverage. (ii) applies here"]


def test_period_form_intro_reaches_every_child_chunk():
    filler = "word " * 60
    chunks = chunk_record(_record([
        ("(b) Record retention. (1) First rule. " + filler, ["b", "1"], False, True),
        ("(2) Second rule. " + filler, ["b", "2"], False, True),
    ]), max_chars=400)
    assert [c["paragraph"] for c in chunks] == ["(b)(1)", "(b)(2)"]
    assert all("\n(b) Record retention.\n" in c["text"] for c in chunks)


def test_real_period_form_1005_12():
    chunks = {c["paragraph"]: c for c in chunk_record(_real_record("1005.12"))}
    assert "(a) Relation to Truth in Lending." in chunks["(a)(2)"]["text"]


def _squash(s):
    return " ".join(s.split())


def _own_texts(record):
    """(paragraph path, text written directly under it), found without the chunker's code.

    The parser gives each block's markers; a marker's own words run up to where
    the next marker's "(x)" first appears in the text.
    """
    out = []
    for b in record["blocks"]:
        path, text = tuple(b["path"]), b["text"]
        markers = [] if b["continuation"] else leading_markers(text)[0]
        k = len(markers)
        if k < 2 or list(path[-k:]) != markers:
            out.append((path, text))
            continue
        start = 0
        for j in range(k):
            end = text.find(f"({markers[j + 1]})", start + 1) if j + 1 < k else len(text)
            words = SINGLE_RE.sub("", text[start:end]).strip()
            if words:
                out.append((path[: len(path) - k + 1 + j], text[start:end]))
            start = end if words or j + 1 == k else start
    return out


def _missing_parent_intros(record, chunks):
    """Chunks whose text lacks the words of one of their parent paragraphs."""
    own = _own_texts(record)
    missing = []
    for c in chunks:
        path = tuple(re.findall(r"\(([^)]+)\)", c["paragraph"]))
        text = _squash(c["text"])
        for parent, intro in own:
            if len(parent) < len(path) and path[: len(parent)] == parent and _squash(intro) not in text:
                missing.append((c["chunk_id"], intro[:60]))
    return missing


def _all_regulation_records():
    with SECTIONS.open(encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    return [r for r in records if r["content_type"] == "regulation" and not r["reserved"]]


def test_every_chunk_contains_all_parent_intros():
    for max_chars in (500, 1400, 2000):
        missing = []
        for record in _all_regulation_records():
            missing += _missing_parent_intros(record, chunk_record(record, max_chars=max_chars))
        assert missing == [], (max_chars, len(missing), missing[:5])


# ---- embed_text

# SHA-1 over every regulation chunk's chunk_id and text, all four parts, made by the
# code before embed_text existed (commit 8f7b9f2). embed_text must not change text.
TEXT_FINGERPRINTS = {
    1400: (2629, "6371522a5e6aecc4d0ca4cda18f51c8cab8ca0a0"),
    2000: (2104, "1d25c90a41431469359f81d56e6b07d6c0b48ad9"),
}


def _words(text):
    """Stand-in token counter for synthetic records: one token per word."""
    return len(text.split())


def test_embed_text_comes_right_after_the_seven_fields():
    chunk = chunk_record(_record([("(a) First.", ["a"], False, True)]), count_tokens=_words)[0]
    assert list(chunk)[7] == "embed_text"


def test_heading_only():
    assert heading_only("(2) Timing and content. Except as otherwise provided") == "(2) Timing and content."
    assert heading_only("(b) Pre-acquisition disclosure requirements—") == "(b) Pre-acquisition disclosure requirements—"
    # A period inside a section number is not the end of a heading.
    assert heading_only("(c) Rules in § 1026.20(d) apply. More text") == "(c) Rules in § 1026.20(d) apply."
    assert heading_only("(3) For each employee who is not licensed:") == "(3) For each employee who is not licensed:"


def test_embed_text_equals_text_when_short():
    chunk = chunk_record(_record([("(a) First.", ["a"], False, True)]), count_tokens=_words)[0]
    assert chunk["embed_text"] == chunk["text"]


def test_embed_text_shortens_parent_intros_when_too_long():
    chunks = chunk_record(_record([
        ("(c) Time limits. " + "intro " * 400, ["c"], False, True),
        ("(1) First rule.", ["c", "1"], False, True),
        ("(2) Second rule.", ["c", "2"], False, True),
    ]), max_chars=400, count_tokens=_words)
    c1 = chunks[0]
    assert c1["paragraph"] == "(c)(1)"
    assert c1["text"].startswith("§ 1005.99 Test section.\n(c) Time limits. intro intro")
    assert c1["embed_text"] == "§ 1005.99 Test section.\n(c) Time limits.\n(1) First rule."


def test_missing_tokenizers_package_gives_install_message():
    saved = sys.modules.get("tokenizers")
    sys.modules["tokenizers"] = None  # makes "from tokenizers import ..." raise ImportError
    load_token_counter.cache_clear()
    try:
        chunk_regulations.load_token_counter()
        raise AssertionError("expected SystemExit")
    except SystemExit as e:
        assert "pip install tokenizers" in str(e)
    finally:
        if saved is None:
            del sys.modules["tokenizers"]
        else:
            sys.modules["tokenizers"] = saved
        load_token_counter.cache_clear()


def test_text_unchanged_by_embed_text():
    records = _all_regulation_records()
    for max_chars, (n_expected, sha_expected) in TEXT_FINGERPRINTS.items():
        h, n = hashlib.sha1(), 0
        for record in records:
            for c in chunk_record(record, max_chars=max_chars):
                h.update((c["chunk_id"] + "\n" + c["text"] + "\n\0").encode("utf-8"))
                n += 1
        assert (n, h.hexdigest()) == (n_expected, sha_expected), max_chars


def test_embed_text_never_more_tokens_than_text():
    count = load_token_counter()
    for record in _all_regulation_records():
        for c in chunk_record(record):
            assert count(c["embed_text"]) <= count(c["text"]), c["chunk_id"]
            if count(c["text"]) <= EMBED_MAX_TOKENS:
                assert c["embed_text"] == c["text"], c["chunk_id"]


def test_fcra_is_ported_to_fixed_corpus_schema(tmp_path):
    html = """<html><body>
<!-- documentid:15_1681i usckey:x -->
<h3 class="section-head">&sect;1681i. Procedure in case of disputed accuracy</h3>
<!-- field-start:statute -->
<h4 class="subsection-head">(a) Reinvestigations of disputed information</h4>
<p class="statutory-body">The agency shall conduct a reasonable reinvestigation.</p>
<!-- field-end:statute -->
</body></html>"""
    path = tmp_path / "fcra.htm"
    path.write_text(html, encoding="utf-8")
    chunks = load_fcra_chunks(path, count_tokens=_words, fetch_missing=False)
    assert len(chunks) == 1
    c = chunks[0]
    assert list(c)[:8] == [
        "chunk_id", "part", "section", "paragraph", "heading", "text", "source_url", "embed_text",
    ]
    assert c["chunk_id"] == "15-fcra-1681i-a"
    assert c["part"] == "FCRA" and c["regulation"] == "FCRA"
    assert c["section"] == "1681i" and c["paragraph"] == "(a)"
    assert c["content_type"] == "statute" and c["path_certain"] is True
    assert c["text"].startswith("§1681i. Procedure in case of disputed accuracy")
    assert c["embed_text"] == c["text"]


def test_long_fcra_chunk_packs_at_html_block_boundaries(tmp_path):
    html = """<html><body>
<!-- documentid:15_1681i usckey:x -->
<h3 class="section-head">&sect;1681i. Procedure in case of disputed accuracy</h3>
<!-- field-start:statute -->
<h4 class="subsection-head">(a) Reinvestigations</h4>
<p class="statutory-body">First statutory block has enough words to be useful.</p>
<p class="statutory-body">Second statutory block must be kept intact.</p>
<!-- field-end:statute -->
</body></html>"""
    path = tmp_path / "fcra.htm"
    path.write_text(html, encoding="utf-8")
    chunks = load_fcra_chunks(path, max_chars=105, count_tokens=_words, fetch_missing=False)
    assert [c["chunk_id"] for c in chunks] == [
        "15-fcra-1681i-a-piece-1", "15-fcra-1681i-a-piece-2", "15-fcra-1681i-a-piece-3",
    ]
    assert all(c["text"].startswith("§1681i.") for c in chunks)
    joined = "\n".join(c["text"] for c in chunks)
    assert "First statutory block has enough words to be useful." in joined
    assert "Second statutory block must be kept intact." in joined


def test_fixed_corpus_includes_complete_model_safe_fcra():
    path = CHUNKING / "data/processed/chunks.jsonl"
    with path.open(encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]
    assert len(chunks) == 2954
    assert len({c["chunk_id"] for c in chunks}) == len(chunks)

    fcra = [c for c in chunks if c["regulation"] == "FCRA"]
    assert len(fcra) == 325
    assert len({c["section"] for c in fcra}) == 31
    count = load_token_counter()
    assert max(c["n_chars"] for c in fcra) <= 1400
    assert max(count(c["embed_text"]) for c in fcra) <= EMBED_MAX_TOKENS

    # Both annotators' FCRA evidence remains verbatim in the fixed corpus.
    by_section = {}
    for c in fcra:
        by_section.setdefault(c["section"], []).append(c["text"])
    for filename in ("llm_labels_claude-opus-5-5.jsonl", "llm_labels_chatgpt.jsonl"):
        with (ROOT / "annotation" / filename).open(encoding="utf-8") as f:
            labels = [json.loads(line) for line in f]
        for label in labels:
            if label["gold_regulation"] == "FCRA":
                assert label["evidence_quote"] in "\n".join(by_section[label["gold_section"]])


def test_default_input_and_output_paths_are_script_relative():
    assert DEFAULT_SECTIONS_PATH == CHUNKING / "data/processed/sections.jsonl"
    assert DEFAULT_OUT_PATH == CHUNKING / "data/processed/chunks.jsonl"
    assert DEFAULT_FCRA_PATH == ROOT / "data/raw/fcra/USCODE-2024-title15-chap41-subchapIII.htm"
