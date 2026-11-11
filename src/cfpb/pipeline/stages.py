"""Stage interfaces, the real classifier adapter, and placeholder stubs.

Each stage is any object with the method below (duck-typed via Protocol).
Pairs B and C implement theirs to these signatures and pass them to
`Pipeline`; nothing else in the pipeline or the demo has to change.

    Classifier.classify(narrative_clean)            -> Classification
    Retriever.retrieve(narrative_clean, k)          -> Retrieval
    Generator.generate(narrative_clean, context)    -> Draft
    Verifier.verify(draft, context)                 -> Verification

Inputs are already cleaned (cfpb.data.clean.clean_narrative). Stubs set
`is_stub = True`; the pipeline reports them in `PipelineResult.stubbed_stages`
so the demo can label placeholder output.
"""
from pathlib import Path
from typing import Protocol

from cfpb.config import PRODUCT_TO_REGULATION
from cfpb.pipeline.schema import (UNCHECKED, Classification, Draft, LabelPrediction, Retrieval,
                                  RetrievedChunk, SentenceCheck, Verification)


class Classifier(Protocol):
    def classify(self, narrative_clean: str) -> Classification: ...


class Retriever(Protocol):
    def retrieve(self, narrative_clean: str, k: int) -> Retrieval: ...


class Generator(Protocol):
    def generate(self, narrative_clean: str, context: list[RetrievedChunk]) -> Draft: ...


class Verifier(Protocol):
    def verify(self, draft: Draft, context: list[RetrievedChunk]) -> Verification: ...


def citation(chunk: RetrievedChunk) -> str:
    """Human-readable citation, e.g. '12 CFR 1005.11(c)' or '15 U.S.C. 1681i(a)(1)'."""
    ref = chunk.paragraph or chunk.section
    return f"15 U.S.C. {ref}" if chunk.regulation == "FCRA" else f"12 CFR {ref}"


# ---------------------------------------------------------------- real stages

class DistilBertClassifier:
    """Stage 1 using the trained models (CLAUDE_PROGRESS.md Sec. 7, v2 baseline).
    Needs torch and transformers (requirements-classifier.txt) and the `best/`
    folders from Drive `Dataset/outputs/classifier/<label>/best/`."""
    is_stub = False

    def __init__(self, product_dir, issue_dir=None, top_k: int = 3):
        from cfpb.classify.predict import ComplaintClassifier  # torch import is slow; defer it
        self.top_k = top_k
        self.product = ComplaintClassifier(product_dir)
        self.issue = ComplaintClassifier(issue_dir) if issue_dir else None
        self.source = f"distilbert:{Path(product_dir).parent.name}" + (
            f"+{Path(issue_dir).parent.name}" if issue_dir else "")

    def _one(self, clf, text: str) -> LabelPrediction:
        row = clf.predict([text], clean=False, top_k=self.top_k).iloc[0]
        return LabelPrediction(row["label"], float(row["prob"]),
                               [(label, float(p)) for label, p in row["top_k"]])

    def classify(self, narrative_clean: str) -> Classification:
        product = self._one(self.product, narrative_clean)
        issue = self._one(self.issue, narrative_clean) if self.issue else None
        return Classification(product, issue, PRODUCT_TO_REGULATION.get(product.label), self.source)


# ---------------------------------------------------------------------- stubs

STUB_PRODUCT = "Checking or savings account"


class StubClassifier:
    """Fixed answer, for running the pipeline without model weights."""
    is_stub = True

    def classify(self, narrative_clean: str) -> Classification:
        return Classification(
            product=LabelPrediction(STUB_PRODUCT, 0.0, [(STUB_PRODUCT, 0.0)]),
            issue=None,
            candidate_regulation=PRODUCT_TO_REGULATION[STUB_PRODUCT],
            source="stub",
        )


class StubRetriever:
    """Returns k placeholder chunks (Pair B replaces this). `abstain=True`
    exercises the NONE path, which returns no chunks."""
    is_stub = True

    def __init__(self, abstain: bool = False):
        self.abstain = abstain

    def retrieve(self, narrative_clean: str, k: int) -> Retrieval:
        chunks = [] if self.abstain else [
            RetrievedChunk(
                rank=i + 1, chunk_id=f"STUB:{i + 1}", score=1.0 / (i + 1),
                regulation="E", section="1005.11", paragraph=f"1005.11(stub-{i + 1})",
                heading="[stub] Placeholder chunk",
                text="[stub] Retrieval is not built yet. Real chunks will carry "
                     "the regulation text here.",
                source_url="https://www.ecfr.gov/current/title-12/part-1005/section-1005.11",
            ) for i in range(k)]
        return Retrieval(chunks, abstain_score=1.0 if self.abstain else 0.0,
                         abstained=self.abstain, retriever="stub", corpus="stub")


class StubGenerator:
    """Template draft citing the top chunk, no LLM call (Pair C replaces this)."""
    is_stub = True

    def generate(self, narrative_clean: str, context: list[RetrievedChunk]) -> Draft:
        top = context[0]
        sentences = [
            "[stub draft] Thank you for your complaint.",
            f"[stub draft] Your complaint appears to be governed by {citation(top)}.",
            "[stub draft] A compliance officer will review it.",
        ]
        return Draft(
            response=" ".join(sentences), sentences=sentences,
            cited_chunk_ids=[[], [top.chunk_id], []],
            context_chunk_ids=[c.chunk_id for c in context],
            model="stub", prompt_version="stub", is_referral=False,
        )


class StubVerifier:
    """Marks every sentence `unchecked` (Pair C replaces this). Premises follow
    INTERFACES.md Sec. 5: the cited chunks, or all context if none are cited."""
    is_stub = True

    def verify(self, draft: Draft, context: list[RetrievedChunk]) -> Verification:
        all_ids = [c.chunk_id for c in context]
        checks = [SentenceCheck(i, s, cited or all_ids, None, None, UNCHECKED)
                  for i, (s, cited) in enumerate(zip(draft.sentences, draft.cited_chunk_ids))]
        return Verification(checks, verifier="stub", threshold=None)
