import sys
import types
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.retrieval.dense import DenseRetriever, HybridRetriever, minmax, rank_sections  # noqa: E402
from cfpb.verify.llm_judge import parse  # noqa: E402

CHUNKS = [{"chunk_id": "a1", "section": "1005.11", "embed_text": "error resolution investigate"},
          {"chunk_id": "a2", "section": "1005.11", "embed_text": "provisional credit error"},
          {"chunk_id": "b1", "section": "1006.6", "embed_text": "debt collector calls"},
          {"chunk_id": "c1", "section": "1026.13", "embed_text": "billing error credit card"}]
VOCAB = ["error", "credit", "debt", "collector", "calls", "billing", "card", "investigate"]


class FakeST:
    """Bag-of-words 'embedding' so the tests need no model download."""
    def __init__(self, name, device=None):
        pass

    def encode(self, texts, normalize_embeddings=True, **kw):
        v = np.array([[t.lower().split().count(w) for w in VOCAB] for t in texts], dtype="float32") + 1e-3
        return v / np.linalg.norm(v, axis=1, keepdims=True)


@pytest.fixture
def dense(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeST))
    return DenseRetriever(CHUNKS, "fake", cache_dir=None)


def test_rank_sections_dedupes_keeping_best_chunk():
    assert rank_sections(CHUNKS, np.array([0.2, 0.9, 0.5, 0.1])) == [("1005.11", 0.9), ("1006.6", 0.5), ("1026.13", 0.1)]


def test_minmax_constant_vector_is_zero():
    assert minmax(np.array([3.0, 3.0])).tolist() == [0.0, 0.0]
    assert minmax(np.array([1.0, 3.0, 2.0])).tolist() == [0.0, 1.0, 0.5]


def test_dense_ranks_by_cosine_and_batch_matches_single(dense):
    assert dense.retrieve("debt collector calls", k=1)[0]["chunk_id"] == "b1"
    assert dense.ranked_sections("billing error card")[0][0] == "1026.13"
    batch = dense.scores_batch(["debt calls", "billing card"])
    assert np.allclose(batch[1], dense.scores("billing card"))


def test_dense_numpy_fallback_matches_faiss(dense):
    q = "provisional credit error"
    with_index = dense.scores(q)
    dense.index = None
    assert np.allclose(with_index, dense.scores(q), atol=1e-5)


def test_hybrid_alpha_endpoints(dense):
    class FakeBM25:
        chunks = CHUNKS

        def scores(self, q):
            return np.array([0.0, 0.0, 0.0, 5.0])  # always prefers c1
    h0, h1 = HybridRetriever(FakeBM25(), dense, 0.0), HybridRetriever(FakeBM25(), dense, 1.0)
    assert h0.retrieve("debt collector calls", 1)[0]["chunk_id"] == "c1"   # pure BM25
    assert h1.retrieve("debt collector calls", 1)[0]["chunk_id"] == "b1"   # pure dense


def test_judge_parse():
    assert parse('```json\n{"label": "Supported", "support_probability": 85}\n```') == ("supported", 0.85)
    assert parse('<think>hmm "label": "supported"</think>{"label": "unsupported", "support_probability": 140}') == ("unsupported", 1.0)
    assert parse("no json here") == (None, None)
