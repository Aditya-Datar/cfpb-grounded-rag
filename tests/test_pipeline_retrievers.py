import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.pipeline import Pipeline  # noqa: E402
from cfpb.pipeline.batch import to_frames  # noqa: E402
from cfpb.pipeline.corpus import Corpus, OracleRetriever  # noqa: E402
from cfpb.pipeline.retrievers import FunctionRetriever, PrecomputedRetriever  # noqa: E402
from cfpb.pipeline.stages import StubClassifier, StubGenerator, StubVerifier  # noqa: E402

CHUNKING = [  # Pair B format
    dict(chunk_id="12-1005-1005.11-c-1", part="1005", section="1005.11", paragraph="(c)(1)",
         heading="Time limits", text="Ten business days.", source_url="u", content_type="regulation",
         regulation="E"),
    dict(chunk_id="12-1006-1006.34-a", part="1006", section="1006.34", paragraph="(a)",
         heading="Validation", text="Validation notice.", source_url="u", content_type="regulation",
         regulation="F"),
    # FCRA row appended with only the INTERFACES fields (Sec. 6.5.6 quick pass)
    dict(chunk_id="S:1681i(a)(1)", section="1681i", paragraph="1681i(a)(1)", heading="§ 1681i",
         text="Reinvestigation.", source_url="u"),
]
REG = [  # regulation-corpus format
    dict(chunk_id="R:1005.11(c)", regulation="E", part="1005", kind="regulation", section="1005.11",
         paragraph="1005.11(c)", heading="§ 1005.11", text="(c)", n_words=1, source_url="u"),
    dict(chunk_id="S:1681i(a)(2)", regulation="FCRA", part="1681", kind="statute", section="1681i",
         paragraph="1681i(a)(2)", heading="§ 1681i", text="(2)", n_words=1, source_url="u"),
]
TEXT = "The collector never sent me a validation notice."


@pytest.fixture
def chunking(tmp_path):
    path = tmp_path / "chunks.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in CHUNKING), encoding="utf-8")
    return Corpus.load(path)


@pytest.fixture
def reg_path(tmp_path):
    path = tmp_path / "reg_chunks.parquet"
    pd.DataFrame(REG).to_parquet(path)
    return path


def _pipe(retriever=None):
    return Pipeline(StubClassifier(), retriever, StubGenerator(), StubVerifier())


def test_rows_without_regulation_or_kind_are_inferred(chunking):
    c = chunking.get("S:1681i(a)(1)")
    assert (c.regulation, c.kind, c.paragraph) == ("FCRA", "statute", "1681i(a)(1)")


def test_load_kinds_filter_and_merge(chunking, reg_path):
    statute = Corpus.load(reg_path, kinds=("statute",))
    assert [c.chunk_id for c in statute.chunks] == ["S:1681i(a)(2)"]
    merged = Corpus.merge(chunking, statute)
    assert len(merged) == 4 and merged.name == "chunks.jsonl+reg_chunks.parquet[statute]"
    assert [c.chunk_id for c in merged.section("1681i")] == ["S:1681i(a)(1)", "S:1681i(a)(2)"]
    with pytest.raises(ValueError, match="duplicate"):
        Corpus.merge(chunking, chunking)


def test_function_retriever_through_pipeline(chunking):
    calls = []

    def bm25(query, k):  # INTERFACES.md Sec. 2 signature
        calls.append((query, k))
        return [{"chunk_id": "12-1006-1006.34-a", "score": 9.5},
                {"chunk_id": "12-1005-1005.11-c-1", "score": 2.0}]

    r = _pipe(FunctionRetriever(bm25, chunking, "bm25")).analyze(TEXT, k=1)
    assert calls == [(TEXT, 1)]
    assert [(c.chunk_id, c.rank, c.section) for c in r.retrieval.chunks] == [("12-1006-1006.34-a", 1, "1006.34")]
    assert r.retrieval.retriever == "bm25" and not r.retrieval.abstained
    assert "retrieve" not in r.stubbed_stages
    assert "12 CFR 1006.34(a)" in r.draft.response


def test_function_retriever_abstains_below_threshold(chunking):
    def weak(query, k):
        return [{"chunk_id": "12-1005-1005.11-c-1", "score": 1.5}]

    r = _pipe(FunctionRetriever(weak, chunking, "bm25", min_top_score=3.0)).analyze(TEXT)
    assert r.retrieval.abstained and r.retrieval.abstain_score == -1.5
    assert len(r.retrieval.chunks) == 1  # ranking kept for evaluation
    assert r.draft.is_referral

    empty = FunctionRetriever(lambda q, k: [], chunking, "bm25", min_top_score=3.0).retrieve(TEXT, 5)
    assert empty.abstained and math.isinf(empty.abstain_score)


def test_unknown_chunk_id_names_the_corpus(chunking):
    bad = FunctionRetriever(lambda q, k: [{"chunk_id": "R:9999.1(a)", "score": 1}], chunking, "bm25")
    with pytest.raises(KeyError, match="chunks.jsonl"):
        bad.retrieve(TEXT, 5)


def test_precomputed_reads_interfaces_ranked_file(chunking, tmp_path):
    path = tmp_path / "ranked.parquet"
    pd.DataFrame([  # deliberately out of rank order
        dict(complaint_id="7", retriever="bm25", corpus="chunks.jsonl", rank=2,
             chunk_id="12-1005-1005.11-c-1", score=3.0),
        dict(complaint_id="7", retriever="bm25", corpus="chunks.jsonl", rank=1,
             chunk_id="12-1006-1006.34-a", score=8.0),
        dict(complaint_id="8", retriever="bm25", corpus="chunks.jsonl", rank=1,
             chunk_id="S:1681i(a)(1)", score=1.0),
    ]).to_parquet(path)
    pre = PrecomputedRetriever(path, chunking, min_top_score=2.0)
    assert sorted(pre.complaint_ids) == ["7", "8"]
    r = _pipe().analyze(TEXT, retriever=pre.for_complaint("7"))
    assert [c.chunk_id for c in r.retrieval.chunks] == ["12-1006-1006.34-a", "12-1005-1005.11-c-1"]
    assert r.retrieval.retriever == "bm25" and r.retrieval.corpus == "chunks.jsonl"
    assert pre.for_complaint("8").retrieve(TEXT, 5).abstained  # 1.0 < 2.0
    with pytest.raises(KeyError):
        pre.for_complaint("9")


def test_precomputed_rejects_files_missing_columns(chunking, tmp_path):
    path = tmp_path / "bad.parquet"
    pd.DataFrame([dict(complaint_id="1", chunk_id="x")]).to_parquet(path)
    with pytest.raises(ValueError, match="score"):
        PrecomputedRetriever(path, chunking)


def test_batch_ranked_output_round_trips(reg_path, tmp_path):
    corpus = Corpus.load(reg_path)
    gold = {"1": dict(complaint_id="1", gold_regulation="E", gold_section="1005.11",
                      gold_paragraph="1005.11(c)"),
            "2": dict(complaint_id="2", gold_regulation="NONE", gold_section=None, gold_paragraph=None)}
    oracle = OracleRetriever(corpus, gold)
    pipe = _pipe()
    results = {cid: pipe.analyze(TEXT, retriever=oracle.for_complaint(cid)) for cid in gold}
    path = tmp_path / "ranked.parquet"
    to_frames(results, "oracle")["ranked"].to_parquet(path, index=False)
    pre = PrecomputedRetriever(path, corpus)
    assert [c.chunk_id for c in pre.for_complaint("1").retrieve(TEXT, 5).chunks] == ["R:1005.11(c)"]
    again = pre.for_complaint("2").retrieve(TEXT, 5)
    assert again.abstained and again.chunks == []  # abstained column honoured


def test_load_corpus_specs(chunking, reg_path, tmp_path):
    from cfpb.pipeline.corpus import load_corpus
    jsonl = tmp_path / "chunks.jsonl"  # written by the chunking fixture
    merged = load_corpus([str(jsonl), f"{reg_path}::statute"])
    assert len(merged) == 4 and merged.get("S:1681i(a)(2)").kind == "statute"
    assert len(load_corpus(reg_path)) == 2
    both = load_corpus([reg_path, reg_path], keep_first=True)  # lookup-only union
    assert len(both) == 2


def _fake_bm25_module(monkeypatch, seen):
    """Stand-in for cfpb.retrieval.bm25 (branch retrieval-bm25), same API."""
    import types
    mod = types.ModuleType("cfpb.retrieval.bm25")

    def load_chunks(path):
        seen["path"] = path
        return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]

    class BM25Retriever:
        def __init__(self, chunks):
            self.chunks = chunks

        def retrieve(self, query, k=10):
            return [{"chunk_id": c["chunk_id"], "score": float(10 - i)} for i, c in enumerate(self.chunks[:k])]

    mod.load_chunks, mod.BM25Retriever = load_chunks, BM25Retriever
    monkeypatch.setitem(sys.modules, "cfpb.retrieval", types.ModuleType("cfpb.retrieval"))
    monkeypatch.setitem(sys.modules, "cfpb.retrieval.bm25", mod)


def test_load_retriever_uses_bm25_when_present(tmp_path, monkeypatch):
    from cfpb.pipeline import corpus as corpus_mod
    from cfpb.pipeline.core import load_retriever
    path = tmp_path / "chunks.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in CHUNKING), encoding="utf-8")
    monkeypatch.setattr(corpus_mod, "PAIR_B_CORPUS", path)
    seen = {}
    _fake_bm25_module(monkeypatch, seen)
    retriever = load_retriever(require=True)
    assert seen["path"] == path and not getattr(retriever, "is_stub", False)
    r = _pipe(retriever).analyze(TEXT, k=2)
    assert r.retrieval.retriever == "bm25" and len(r.retrieval.chunks) == 2
    assert not r.retrieval.abstained  # no abstention threshold for BM25
    assert "retrieve" not in r.stubbed_stages


def test_load_retriever_falls_back_without_module_or_corpus(tmp_path, monkeypatch):
    from cfpb.pipeline import corpus as corpus_mod
    from cfpb.pipeline.core import load_retriever
    from cfpb.pipeline.stages import StubRetriever
    monkeypatch.setitem(sys.modules, "cfpb.retrieval.bm25", None)  # import fails
    assert isinstance(load_retriever(), StubRetriever)
    with pytest.raises(ImportError):
        load_retriever(require=True)
    _fake_bm25_module(monkeypatch, {})
    monkeypatch.setattr(corpus_mod, "PAIR_B_CORPUS", tmp_path / "missing.jsonl")
    assert isinstance(load_retriever(), StubRetriever)
    with pytest.raises(FileNotFoundError):
        load_retriever(require=True)
