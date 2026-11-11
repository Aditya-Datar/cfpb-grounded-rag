"""BM25 sparse retriever over the regulation chunks (Pair B baseline, sparse floor).

Indexes `embed_text` of each chunk and returns chunk ids with BM25 scores.
Tokens are lowercase alphanumeric runs; stopword removal is optional and off by default.
"""
import json
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from cfpb.config import ROOT

DEFAULT_CHUNKS_PATH = ROOT / "chunking" / "data" / "processed" / "chunks.jsonl"
_TOKEN = re.compile(r"[a-z0-9]+")


def load_chunks(path: Path = DEFAULT_CHUNKS_PATH, include_fcra: bool = True) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f if line.strip()]
    if not include_fcra:
        chunks = [c for c in chunks if c["regulation"] != "FCRA"]
    return chunks


def tokenize(text: str, stopwords: frozenset[str] = frozenset()) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in stopwords]


class BM25Retriever:
    def __init__(self, chunks: list[dict], stopwords: frozenset[str] = frozenset(),
                 k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.stopwords = stopwords
        self.index = BM25Okapi([tokenize(c["embed_text"], stopwords) for c in chunks], k1=k1, b=b)

    def scores(self, query: str) -> np.ndarray:
        return np.asarray(self.index.get_scores(tokenize(query, self.stopwords)), dtype=float)

    def retrieve(self, query: str, k: int = 10) -> list[dict]:
        """Top-k chunks as dicts(chunk_id, score), best first (INTERFACES.md Sec. 2)."""
        s = self.scores(query)
        order = np.argsort(-s, kind="stable")[:k]
        return [{"chunk_id": self.chunks[i]["chunk_id"], "score": float(s[i])} for i in order]

    def ranked_sections(self, query: str) -> list[tuple[str, float]]:
        """Sections ranked by their best chunk, keeping the first occurrence of each."""
        s = self.scores(query)
        seen, out = set(), []
        for i in np.argsort(-s, kind="stable"):
            sec = self.chunks[i]["section"]
            if sec not in seen:
                seen.add(sec)
                out.append((sec, float(s[i])))
        return out
