import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "chunking"))

from chunk_regulations import chunk_record, split_at_markers  # noqa: E402

URL = "https://www.ecfr.gov/current/title-12/part-1005/section-1005.99"


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
