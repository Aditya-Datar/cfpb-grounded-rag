import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.pipeline import Pipeline, load_classifier, load_pipeline  # noqa: E402
from cfpb.pipeline.schema import (SUPPORTED, UNCHECKED, UNSUPPORTED, Retrieval,  # noqa: E402
                                  RetrievedChunk, SentenceCheck, Verification)
from cfpb.pipeline.stages import (StubClassifier, StubGenerator, StubRetriever,  # noqa: E402
                                  StubVerifier, citation)

NARRATIVE = ("On XX/XX/2025 my bank denied my claim for an unauthorized debit of "
             "{$250.00} from account XXXX without sending any documents.")


def _stub_pipeline(abstain=False, k=3):
    return Pipeline(StubClassifier(), StubRetriever(abstain=abstain), StubGenerator(),
                    StubVerifier(), k=k)


def test_end_to_end_with_stubs():
    r = _stub_pipeline().analyze(NARRATIVE)
    assert r.narrative == NARRATIVE
    assert r.narrative_clean == ("On [DATE] my bank denied my claim for an unauthorized debit "
                                 "of $250.00 from account [REDACTED] without sending any documents.")
    assert [c.rank for c in r.retrieval.chunks] == [1, 2, 3]
    assert len(r.draft.sentences) == len(r.draft.cited_chunk_ids) == len(r.verification.checks)
    assert r.draft.context_chunk_ids == [c.chunk_id for c in r.retrieval.chunks]
    assert all(c.label == UNCHECKED for c in r.verification.checks)
    assert r.stubbed_stages == ["classify", "retrieve", "generate", "verify"]
    assert set(r.timings_ms) == {"classify", "retrieve", "generate", "verify"}


def test_k_override():
    assert len(_stub_pipeline(k=3).analyze(NARRATIVE, k=7).retrieval.chunks) == 7


def test_verifier_premise_is_cited_chunks_else_all_context():
    r = _stub_pipeline().analyze(NARRATIVE)
    all_ids = [c.chunk_id for c in r.retrieval.chunks]
    for check, cited in zip(r.verification.checks, r.draft.cited_chunk_ids):
        assert check.premise_chunk_ids == (cited or all_ids)


def test_abstention_drafts_referral_without_generation_or_verification():
    class MustNotRun:
        is_stub = True

        def generate(self, *a):
            raise AssertionError("generator called on abstention")

        def verify(self, *a):
            raise AssertionError("verifier called on abstention")

    pipe = Pipeline(StubClassifier(), StubRetriever(abstain=True), MustNotRun(), MustNotRun())
    r = pipe.analyze(NARRATIVE)
    assert r.retrieval.abstained and r.retrieval.chunks == []
    assert r.draft.is_referral and r.draft.context_chunk_ids == []
    assert all(c == [] for c in r.draft.cited_chunk_ids)
    assert r.verification.checks == []
    assert "generate" not in r.timings_ms
    assert r.stubbed_stages == ["classify", "retrieve"]  # the referral itself is not a stub


@pytest.mark.parametrize("text", ["", "   ", None])
def test_empty_input_rejected(text):
    with pytest.raises(ValueError):
        _stub_pipeline().analyze(text)


def test_to_dict_is_json_serialisable_and_counts_labels():
    r = _stub_pipeline().analyze(NARRATIVE)
    r.verification = Verification([SentenceCheck(0, "a", [], 0.9, 0.0, SUPPORTED),
                                   SentenceCheck(1, "b", [], 0.1, 0.8, UNSUPPORTED),
                                   SentenceCheck(2, "c", [], None, None, UNCHECKED)], "test", 0.5)
    d = json.loads(json.dumps(r.to_dict()))
    assert d["verification"]["n_supported"] == 1
    assert d["verification"]["n_flagged"] == 1
    assert d["classification"]["product"]["label"] == "Checking or savings account"


def test_real_stage_can_replace_a_stub():
    class FixedRetriever:  # no is_stub attribute: counts as real
        def retrieve(self, text, k):
            chunk = RetrievedChunk(1, "S:1681i(a)(1)", 0.8, "FCRA", "1681i", "1681i(a)(1)",
                                   "§ 1681i", "text", "https://example.org")
            return Retrieval([chunk], 0.2, False, "fixed", "test")

    pipe = Pipeline(StubClassifier(), FixedRetriever(), StubGenerator(), StubVerifier())
    r = pipe.analyze(NARRATIVE)
    assert "retrieve" not in r.stubbed_stages
    assert "15 U.S.C. 1681i(a)(1)" in r.draft.response


def test_citation_format():
    def chunk(reg, sec, para):
        return RetrievedChunk(1, "x", 1.0, reg, sec, para, "", "", "")
    assert citation(chunk("E", "1005.11", "1005.11(c)")) == "12 CFR 1005.11(c)"
    assert citation(chunk("FCRA", "1681i", "")) == "15 U.S.C. 1681i"


def test_missing_model_falls_back_to_stub_or_raises(tmp_path):
    missing = tmp_path / "no_model"
    assert isinstance(load_classifier(missing, None), StubClassifier)
    with pytest.raises(FileNotFoundError):
        load_classifier(missing, None, require=True)
    assert "classify" in load_pipeline(missing, None).stubbed_stages


def test_batch_tables_follow_interfaces(tmp_path):
    from cfpb.pipeline.batch import to_frames
    results = {"1": _stub_pipeline(k=2).analyze(NARRATIVE),
               "2": _stub_pipeline(abstain=True).analyze(NARRATIVE)}
    f = to_frames(results, "retrieved")
    assert list(f["classification"].complaint_id) == ["1", "2"]
    ranked = f["ranked"]
    assert list(ranked[ranked.complaint_id == "1"]["rank"]) == [1, 2]
    assert ranked[ranked.complaint_id == "2"].abstained.tolist() == [True]  # one row, no chunk
    assert f["responses"].is_referral.tolist() == [False, True]
    assert set(f["sentences"].complaint_id) == {"1"}  # referrals are not verified
    for name, df in f.items():  # nested list columns must survive Parquet
        df.to_parquet(tmp_path / f"{name}.parquet", index=False)
