"""Replay saved full-run outputs (outputs/pipeline_runs/full-*) in the demo.

The full attribution runs on CARC already drafted (Nemotron) and checked (NLI)
every gold complaint, in both conditions. Loading those tables lets the demo
show real drafts and per-sentence labels on a laptop CPU, with no API call and
no NLI model. Labels are recomputed from the stored entailment scores, so the
page can switch between the run threshold and a frozen cutoff (supported iff
entail_prob >= cutoff, as in attribution_pilot.py report --tau).
"""
from dataclasses import replace
from pathlib import Path

import pandas as pd

from cfpb.pipeline.corpus import Corpus
from cfpb.pipeline.retrievers import PrecomputedRetriever
from cfpb.pipeline.schema import (SUPPORTED, UNSUPPORTED, Draft, PipelineResult, SentenceCheck,
                                  Verification)

ORACLE_RUN = "full-oracle-nli"
REQUIRED = ("ranked.parquet", "responses.parquet", "sentences.parquet")


def full_runs(runs_dir: Path) -> list[str]:
    """Names of complete full-* run folders, oracle excluded (it is the shared counterpart)."""
    return sorted(p.name for p in runs_dir.glob("full-*")
                  if p.name != ORACLE_RUN and all((p / f).exists() for f in REQUIRED))


class ReplayRun:
    """One saved run folder: rankings, drafts and per-sentence NLI scores."""

    def __init__(self, path: Path, corpus: Corpus):
        self.path = Path(path)
        self.retriever = PrecomputedRetriever(self.path / "ranked.parquet", corpus)
        responses = pd.read_parquet(self.path / "responses.parquet")
        responses["complaint_id"] = responses["complaint_id"].astype(str)
        self.responses = {r.complaint_id: r for r in responses.itertuples(index=False)}
        sentences = pd.read_parquet(self.path / "sentences.parquet")
        sentences["complaint_id"] = sentences["complaint_id"].astype(str)
        self.sentences = {cid: g.sort_values("sentence_idx") for cid, g in sentences.groupby("complaint_id")}
        self.verifier = str(sentences["verifier"].iloc[0]) if len(sentences) else "none"
        self.run_threshold = float(sentences["threshold"].iloc[0]) if len(sentences) else None
        self.model = str(responses["model"].iloc[0]) if len(responses) else "unknown"

    @property
    def complaint_ids(self) -> set[str]:
        return set(self.responses)

    def result(self, base: PipelineResult, complaint_id: str, k: int, cutoff: float) -> PipelineResult:
        """`base` supplies the narrative and classification (run live); retrieval,
        draft and verification come from the saved run, labelled at `cutoff`."""
        r = self.responses[complaint_id]
        draft = Draft(response=r.response, sentences=list(r.sentences),
                      cited_chunk_ids=[list(c) for c in r.cited_chunk_ids],
                      context_chunk_ids=list(r.context_chunk_ids), model=r.model,
                      prompt_version=r.prompt_version, is_referral=bool(r.is_referral))
        rows = self.sentences.get(complaint_id, pd.DataFrame())
        checks = [SentenceCheck(int(s.sentence_idx), s.sentence, list(s.premise_chunk_ids),
                                float(s.entail_prob), float(s.contradict_prob),
                                SUPPORTED if s.entail_prob >= cutoff else UNSUPPORTED)
                  for s in rows.itertuples(index=False)]
        verification = Verification(checks, verifier=self.verifier, threshold=cutoff)
        retrieval = self.retriever.for_complaint(complaint_id).retrieve(base.narrative_clean, k)
        stubbed = [s for s in base.stubbed_stages if s == "classify"]
        return replace(base, retrieval=retrieval, draft=draft, verification=verification,
                       stubbed_stages=stubbed, timings_ms={"classify": base.timings_ms.get("classify", 0.0)})
