import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.retrieval.bm25 import BM25Retriever, load_chunks, tokenize  # noqa: E402

CHUNKS = [
    {"chunk_id": "a1", "section": "1005.11", "regulation": "E", "embed_text": "error resolution unauthorized electronic transfer"},
    {"chunk_id": "a2", "section": "1005.11", "regulation": "E", "embed_text": "unauthorized transfer investigation error"},
    {"chunk_id": "b1", "section": "1006.18", "regulation": "F", "embed_text": "debt collector false representation harassment"},
    {"chunk_id": "c1", "section": "1681i", "regulation": "FCRA", "embed_text": "reinvestigation of disputed credit report information"},
]


def test_tokenize_lowercases_and_drops_punctuation_and_stopwords():
    assert tokenize("Section 1005.11(b)-Error!") == ["section", "1005", "11", "b", "error"]
    assert tokenize("the Error", frozenset({"the"})) == ["error"]


def test_retrieve_top_hit_and_order():
    r = BM25Retriever(CHUNKS)
    out = r.retrieve("debt collector harassment", k=2)
    assert out[0]["chunk_id"] == "b1" and len(out) == 2
    assert out[0]["score"] >= out[1]["score"]


def test_ranked_sections_dedupes_and_keeps_best_first():
    secs = BM25Retriever(CHUNKS).ranked_sections("unauthorized electronic transfer error")
    names = [s for s, _ in secs]
    assert names[0] == "1005.11" and len(names) == len(set(names)) == 3


def test_real_corpus_loads_with_and_without_fcra():
    full, no = load_chunks(), load_chunks(include_fcra=False)
    assert len(full) == 2954 and len(no) == 2629
    assert all(c["regulation"] != "FCRA" for c in no)


def test_metrics_and_threshold():
    import numpy as np
    from cfpb.retrieval.metrics import prf, rank_of, retrieval_metrics, tune_threshold

    assert rank_of("b", ["a", "b"]) == 2 and rank_of("z", ["a"]) is None
    m = retrieval_metrics([1, 3, None, 12])
    assert m["hit@1"] == 0.25 and m["hit@5"] == 0.5 and m["hit@10"] == 0.5
    assert m["precision@5"] == 0.1 and abs(m["mrr"] - (1 + 1 / 3 + 1 / 12) / 4) < 1e-12
    s, none = np.array([1.0, 2.0, 8.0, 9.0]), np.array([True, True, False, False])
    t = tune_threshold(s, none)
    assert prf(none, s <= t)["f1"] == 1.0
