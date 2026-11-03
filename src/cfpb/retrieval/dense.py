"""Dense and hybrid retrievers over the regulation chunks (H1).

DenseRetriever: Sentence-Transformers embeddings (default all-mpnet-base-v2, the
model the chunker was sized for) with cosine similarity, searched exhaustively
with FAISS (IndexFlatIP over normalised vectors) or plain numpy if FAISS is
missing. The corpus is only ~3k chunks, so exact search is fast.

HybridRetriever: per query, min-max normalise the BM25 and dense scores over all
chunks and combine them as alpha * dense + (1 - alpha) * bm25. alpha is tuned on
a fixed half of the gold complaints (scripts/run_retrieval.py), never on the
half we report.

All retrievers expose the same interface as BM25Retriever:
    scores(query) -> np.ndarray over chunks
    retrieve(query, k) -> [{"chunk_id", "score"}]
    ranked_sections(query) -> [(section, best score)], deduplicated
"""
import hashlib
import json
from pathlib import Path

import numpy as np

from cfpb.config import OUTPUT_DIR

DEFAULT_MODEL = "sentence-transformers/all-mpnet-base-v2"
EMB_CACHE = OUTPUT_DIR / "retrieval" / "embeddings"


def rank_sections(chunks: list[dict], scores: np.ndarray) -> list[tuple[str, float]]:
    """Sections ranked by their best chunk, keeping the first occurrence of each."""
    seen, out = set(), []
    for i in np.argsort(-scores, kind="stable"):
        sec = chunks[i]["section"]
        if sec not in seen:
            seen.add(sec)
            out.append((sec, float(scores[i])))
    return out


class _RankMixin:
    chunks: list[dict]

    def scores(self, query: str) -> np.ndarray:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def retrieve(self, query: str, k: int = 10) -> list[dict]:
        s = self.scores(query)
        order = np.argsort(-s, kind="stable")[:k]
        return [{"chunk_id": self.chunks[i]["chunk_id"], "score": float(s[i])} for i in order]

    def ranked_sections(self, query: str) -> list[tuple[str, float]]:
        return rank_sections(self.chunks, self.scores(query))


class DenseRetriever(_RankMixin):
    def __init__(self, chunks: list[dict], model_name: str = DEFAULT_MODEL, field: str = "embed_text",
                 batch_size: int = 64, device: str | None = None, cache_dir: Path | None = EMB_CACHE):
        from sentence_transformers import SentenceTransformer  # deferred: heavy import
        self.chunks, self.model_name, self.field = chunks, model_name, field
        self.model = SentenceTransformer(model_name, device=device)
        self.batch_size = batch_size
        self.emb = self._chunk_embeddings(cache_dir)
        try:
            import faiss
            self.index = faiss.IndexFlatIP(self.emb.shape[1])
            self.index.add(self.emb)
        except ImportError:
            self.index = None

    def _chunk_embeddings(self, cache_dir: Path | None) -> np.ndarray:
        texts = [c.get(self.field) or c["text"] for c in self.chunks]
        key = hashlib.sha1(json.dumps([self.model_name, texts]).encode()).hexdigest()[:16]
        path = cache_dir / f"{key}.npy" if cache_dir else None
        if path is not None and path.exists():
            return np.load(path)
        emb = self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                                show_progress_bar=True, convert_to_numpy=True).astype("float32")
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, emb)
        return emb

    def encode_queries(self, queries: list[str]) -> np.ndarray:
        return self.model.encode(queries, batch_size=self.batch_size, normalize_embeddings=True,
                                 convert_to_numpy=True).astype("float32")

    def scores_batch(self, queries: list[str]) -> np.ndarray:
        """(n_queries, n_chunks) cosine similarities, exhaustive."""
        q = self.encode_queries(queries)
        if self.index is None:
            return (q @ self.emb.T).astype(float)
        sims, idx = self.index.search(q, len(self.chunks))
        out = np.empty_like(sims, dtype=float)
        np.put_along_axis(out, idx, sims, axis=1)
        return out

    def scores(self, query: str) -> np.ndarray:
        return self.scores_batch([query])[0]


def minmax(x: np.ndarray) -> np.ndarray:
    lo, hi = float(x.min()), float(x.max())
    return np.zeros_like(x, dtype=float) if hi == lo else (x - lo) / (hi - lo)


class HybridRetriever(_RankMixin):
    """alpha * minmax(dense) + (1 - alpha) * minmax(bm25). Both retrievers must index the same chunks."""

    def __init__(self, bm25, dense, alpha: float = 0.5):
        assert [c["chunk_id"] for c in bm25.chunks] == [c["chunk_id"] for c in dense.chunks]
        self.bm25, self.dense, self.alpha = bm25, dense, alpha
        self.chunks = bm25.chunks

    def scores(self, query: str) -> np.ndarray:
        return self.combine(self.bm25.scores(query), self.dense.scores(query), self.alpha)

    @staticmethod
    def combine(bm25_scores: np.ndarray, dense_scores: np.ndarray, alpha: float) -> np.ndarray:
        return alpha * minmax(dense_scores) + (1 - alpha) * minmax(bm25_scores)
