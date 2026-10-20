import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.generate.nemotron import NemotronGenerator, split_sentences  # noqa: E402
from cfpb.pipeline.schema import SUPPORTED, UNSUPPORTED, Draft, RetrievedChunk  # noqa: E402
from cfpb.verify.nli import NLIVerifier  # noqa: E402


def _chunk(i, text="text"):
    return RetrievedChunk(i, f"c{i}", 1.0, "E", "1005.11", f"1005.11({i})", "Heading", text, "url")


CTX = [_chunk(1), _chunk(2)]


def test_split_moves_tags_and_maps_citations():
    s, c = split_sentences("The bank must investigate within 10 business days. [P1] It must also "
                           "send results [P1][P2]. Under 12 CFR 1005.11(c), see U.S.C. 1681 rules [P2].", CTX)
    assert s == ["The bank must investigate within 10 business days.", "It must also send results.",
                 "Under 12 CFR 1005.11(c), see U.S.C. 1681 rules."]
    assert c == [["c1"], ["c1", "c2"], ["c2"]]


def test_split_handles_none_out_of_range_and_think_blocks():
    s, c = split_sentences("<think>plan</think>The passages do not address this [NONE]. Other [P9].", CTX)
    assert s == ["The passages do not address this.", "Other."] and c == [[], []]


def test_generate_uses_cache_and_never_calls_twice(tmp_path, monkeypatch):
    gen = NemotronGenerator(cache_dir=tmp_path)
    calls = []

    def fake_call(messages):
        calls.append(messages)
        return {"choices": [{"message": {"content": "Investigate promptly [P1]."}}]}

    monkeypatch.setattr(gen, "_call", fake_call)
    d1 = gen.generate("my complaint", CTX)
    d2 = gen.generate("my complaint", CTX)
    assert len(calls) == 1 and d1 == d2
    assert d1.sentences == ["Investigate promptly."] and d1.cited_chunk_ids == [["c1"]]
    assert "[P2]" in calls[0][1]["content"] and "12 CFR 1005.11(2)" in calls[0][1]["content"]


def test_verifier_uses_cited_premises_else_all_context(monkeypatch):
    v = NLIVerifier(threshold=0.5)
    seen = []

    def fake_score(premises, sentence):
        seen.append(premises)
        return (0.9, 0.0) if "good" in sentence else (0.1, 0.8)

    monkeypatch.setattr(v, "score", fake_score)
    ctx = [_chunk(1, "alpha"), _chunk(2, "beta")]
    draft = Draft("", ["good one", "bad one"], [["c2"], []], ["c1", "c2"], "m", "p", False)
    out = v.verify(draft, ctx)
    assert seen == [["beta"], ["alpha", "beta"]]
    assert [c.label for c in out.checks] == [SUPPORTED, UNSUPPORTED]
    assert out.checks[1].premise_chunk_ids == ["c1", "c2"]
