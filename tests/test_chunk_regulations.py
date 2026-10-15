import json
import re
import sys
from pathlib import Path

CHUNKING = Path(__file__).resolve().parents[1] / "chunking"
sys.path.insert(0, str(CHUNKING))

from chunk_regulations import chunk_record, split_at_markers  # noqa: E402
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


def test_default_gives_same_chunks_for_1005_11():
    chunks = chunk_record(_real_record("1005.11"))
    assert [c["paragraph"] for c in chunks] == [
        "(a)", "(b)", "(c)(1)", "(c)(2)", "(c)(3)", "(c)(4)", "(d)", "(e)",
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
    for max_chars in (500, 2000):
        missing = []
        for record in _all_regulation_records():
            missing += _missing_parent_intros(record, chunk_record(record, max_chars=max_chars))
        assert missing == [], (max_chars, len(missing), missing[:5])
