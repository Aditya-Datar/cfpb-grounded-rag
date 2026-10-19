"""Adapters that plug a retrieval team's output into the pipeline.

The retrieval interface in docs/INTERFACES.md Sec. 2 is deliberately small:
a function `retrieve(query, k) -> [{"chunk_id", "score"}, ...]` for live use,
and `outputs/retrieval/<run>/ranked.parquet` for batch runs. The pipeline
needs chunk text and citations as well, so these adapters look each chunk_id
up in a Corpus (the one the retriever indexed):

    bm25 = FunctionRetriever(my_bm25.retrieve, corpus, name="bm25", min_top_score=5.0)
    pipe = Pipeline(classifier, bm25, generator, verifier)

    ranked = PrecomputedRetriever("outputs/retrieval/bm25/ranked.parquet", corpus)
    pipe.analyze(text, retriever=ranked.for_complaint("23571192"))

Abstention (INTERFACES.md Sec. 7): with `min_top_score`, a complaint whose
best score is below it abstains. abstain_score is the negated top score, so
higher means more likely out of scope. A ranked.parquet with an `abstained`
column uses that column instead. Abstaining results keep their ranked chunks
(for evaluation); the pipeline still drafts a referral.
"""
from pathlib import Path
from typing import Callable

import pandas as pd

from cfpb.pipeline.corpus import Corpus
from cfpb.pipeline.schema import Retrieval


def _retrieval(ranked: list[tuple[str, float]], corpus: Corpus, name: str, corpus_label: str,
               min_top_score: float | None, abstained: bool | None = None) -> Retrieval:
    chunks = []
    for i, (chunk_id, score) in enumerate(ranked):
        try:
            chunk = corpus.get(chunk_id)
        except KeyError:
            raise KeyError(f"chunk_id {chunk_id!r} from {name} is not in corpus {corpus.name}; "
                           "load the corpus the retriever indexed") from None
        chunks.append(chunk.ranked(i + 1, float(score)))
    top = chunks[0].score if chunks else None
    if abstained is None:
        abstained = min_top_score is not None and (top is None or top < min_top_score)
    abstain_score = float("inf") if top is None else -top
    return Retrieval(chunks, abstain_score, bool(abstained), name, corpus_label)


class FunctionRetriever:
    """Live retriever from a function with the INTERFACES.md Sec. 2 signature."""
    is_stub = False

    def __init__(self, fn: Callable[[str, int], list[dict]], corpus: Corpus, name: str,
                 min_top_score: float | None = None):
        self.fn, self.corpus, self.name = fn, corpus, name
        self.min_top_score = min_top_score

    def retrieve(self, narrative_clean: str, k: int) -> Retrieval:
        ranked = [(r["chunk_id"], r["score"]) for r in self.fn(narrative_clean, k)][:k]
        return _retrieval(ranked, self.corpus, self.name, self.corpus.name, self.min_top_score)


class PrecomputedRetriever:
    """Rankings from a ranked.parquet (complaint_id, retriever, corpus, rank,
    chunk_id, score; optional abstained). Bind a complaint, as with the oracle."""
    is_stub = False

    def __init__(self, ranked_path, corpus: Corpus, min_top_score: float | None = None):
        df = pd.read_parquet(Path(ranked_path))
        missing = {"complaint_id", "rank", "chunk_id", "score"} - set(df.columns)
        if missing:
            raise ValueError(f"{ranked_path} lacks columns {sorted(missing)} (INTERFACES.md Sec. 2)")
        df["complaint_id"] = df["complaint_id"].astype(str)
        self.corpus, self.min_top_score = corpus, min_top_score
        self.name = str(df["retriever"].iloc[0]) if "retriever" in df and len(df) else Path(ranked_path).parent.name
        self.corpus_label = str(df["corpus"].iloc[0]) if "corpus" in df and len(df) else corpus.name
        self._ranked: dict[str, list[tuple[str, float]]] = {}
        self._abstained: dict[str, bool] = {}
        for cid, g in df.groupby("complaint_id", sort=False):
            g = g[g["chunk_id"].notna()].sort_values("rank")
            self._ranked[cid] = list(zip(g["chunk_id"].astype(str), g["score"].astype(float)))
        if "abstained" in df:
            self._abstained = df.groupby("complaint_id")["abstained"].any().astype(bool).to_dict()

    @property
    def complaint_ids(self) -> list[str]:
        return list(self._ranked)

    def for_complaint(self, complaint_id: str) -> "_BoundPrecomputed":
        if complaint_id not in self._ranked:
            raise KeyError(f"Complaint {complaint_id} has no ranking in this file")
        return _BoundPrecomputed(self, complaint_id)


class _BoundPrecomputed:
    is_stub = False

    def __init__(self, source: PrecomputedRetriever, complaint_id: str):
        self.source, self.complaint_id = source, complaint_id

    def retrieve(self, narrative_clean: str, k: int) -> Retrieval:
        s = self.source
        return _retrieval(s._ranked[self.complaint_id][:k], s.corpus, s.name, s.corpus_label,
                          s.min_top_score, s._abstained.get(self.complaint_id))
