"""One complaint in, one full result out: classify, retrieve, draft, verify.

The Streamlit demo imports this directly (team decision 2026-10-18: no
separate API). Build the pipeline once per server process:

    import streamlit as st
    from cfpb.pipeline import load_pipeline

    @st.cache_resource
    def get_pipeline():
        return load_pipeline()

    result = get_pipeline().analyze(narrative)   # PipelineResult
    result.to_dict()                             # plain dict

Stages that are not built yet run as stubs, listed in result.stubbed_stages.
Batch evaluation (precision@k, the retrieved-vs-oracle gap) does not go
through here; it reads and writes the Parquet formats in docs/INTERFACES.md.
"""
import logging
import time
from pathlib import Path

from cfpb.config import OUTPUT_DIR
from cfpb.data.clean import clean_narrative
from cfpb.pipeline.schema import Draft, PipelineResult, Verification
from cfpb.pipeline.stages import (Classifier, DistilBertClassifier, Generator, Retriever,
                                  StubClassifier, StubGenerator, StubRetriever, StubVerifier,
                                  Verifier)

log = logging.getLogger(__name__)

DEFAULT_PRODUCT_MODEL = OUTPUT_DIR / "classifier" / "product" / "best"
DEFAULT_ISSUE_MODEL = OUTPUT_DIR / "classifier" / "issue" / "best"

# Drafted instead of a cited response when the retriever abstains
# (INTERFACES.md Sec. 7). Fixed text, so abstentions cost no LLM call.
REFERRAL_SENTENCES = [
    "This complaint appears to fall outside Regulations E, F, V and Z and the "
    "Fair Credit Reporting Act.",
    "No governing section was found in the corpus, so no response has been drafted.",
    "Escalate to compliance for review.",
]


def referral_draft() -> Draft:
    return Draft(response=" ".join(REFERRAL_SENTENCES), sentences=list(REFERRAL_SENTENCES),
                 cited_chunk_ids=[[] for _ in REFERRAL_SENTENCES], context_chunk_ids=[],
                 model="none", prompt_version="referral-v1", is_referral=True)


class Pipeline:
    def __init__(self, classifier: Classifier, retriever: Retriever,
                 generator: Generator, verifier: Verifier, k: int = 5):
        self.classifier, self.retriever = classifier, retriever
        self.generator, self.verifier = generator, verifier
        self.k = k

    def _stubbed(self, retriever, abstained: bool = False) -> list[str]:
        stages = {"classify": self.classifier, "retrieve": retriever}
        if not abstained:  # a referral never calls the generator or verifier
            stages |= {"generate": self.generator, "verify": self.verifier}
        return [name for name, s in stages.items() if getattr(s, "is_stub", False)]

    @property
    def stubbed_stages(self) -> list[str]:
        return self._stubbed(self.retriever)

    def analyze(self, narrative: str, k: int | None = None,
                retriever: Retriever | None = None) -> PipelineResult:
        """Run all four stages on one raw complaint narrative. `retriever`
        overrides the pipeline's for this call only, e.g. an oracle bound to a
        gold complaint (corpus.OracleRetriever.for_complaint). Raises
        ValueError if nothing is left after cleaning."""
        clean = clean_narrative(narrative)
        if not clean:
            raise ValueError("Complaint text is empty.")
        retriever = retriever or self.retriever
        timings: dict[str, float] = {}

        def timed(name, fn, *args):
            t0 = time.perf_counter()
            out = fn(*args)
            timings[name] = round((time.perf_counter() - t0) * 1000, 1)
            return out

        classification = timed("classify", self.classifier.classify, clean)
        retrieval = timed("retrieve", retriever.retrieve, clean, k or self.k)
        if retrieval.abstained:
            draft = referral_draft()
            verification = Verification([], verifier="skipped (referral)", threshold=None)
        else:
            draft = timed("generate", self.generator.generate, clean, retrieval.chunks)
            verification = timed("verify", self.verifier.verify, draft, retrieval.chunks)
        return PipelineResult(narrative, clean, classification, retrieval, draft,
                              verification, self._stubbed(retriever, retrieval.abstained), timings)


def load_classifier(product_dir=DEFAULT_PRODUCT_MODEL, issue_dir=DEFAULT_ISSUE_MODEL,
                    require: bool = False) -> Classifier:
    """The trained DistilBERT models if available, else the stub (with a
    warning). `require=True` raises instead of falling back. The issue model
    is optional."""
    product_dir = Path(product_dir)
    issue_dir = Path(issue_dir) if issue_dir else None
    try:
        if not product_dir.is_dir():
            raise FileNotFoundError(f"No product model at {product_dir}")
        return DistilBertClassifier(product_dir, issue_dir if issue_dir and issue_dir.is_dir() else None)
    except (FileNotFoundError, ImportError) as e:
        if require:
            raise
        log.warning("Classifier falls back to the stub: %s", e)
        return StubClassifier()


def load_retriever(require: bool = False) -> Retriever:
    """Pair B's BM25 baseline (cfpb.retrieval.bm25, branch retrieval-bm25) over
    their chunks.jsonl if both are present, else the stub (with a warning).

    No abstention threshold: the top BM25 score does not separate NONE
    complaints (AUROC 0.43, CLAUDE_PROGRESS.md 2026-10-19 BM25 entry), so this
    retriever never abstains. `require=True` raises instead of falling back."""
    from cfpb.pipeline.corpus import PAIR_B_CORPUS, Corpus
    from cfpb.pipeline.retrievers import FunctionRetriever
    try:
        from cfpb.retrieval.bm25 import BM25Retriever, load_chunks  # branch retrieval-bm25
        if not PAIR_B_CORPUS.exists():
            raise FileNotFoundError(f"No Pair B corpus at {PAIR_B_CORPUS}")
        bm25 = BM25Retriever(load_chunks(PAIR_B_CORPUS))
        return FunctionRetriever(bm25.retrieve, Corpus.load(PAIR_B_CORPUS), name="bm25")
    except (FileNotFoundError, ImportError) as e:
        if require:
            raise
        log.warning("Retriever falls back to the stub: %s", e)
        return StubRetriever()


def load_pipeline(product_dir=DEFAULT_PRODUCT_MODEL, issue_dir=DEFAULT_ISSUE_MODEL,
                  require_models: bool = False, k: int = 5,
                  require_retriever: bool = False) -> Pipeline:
    """Default pipeline: real stages where they exist, stubs elsewhere.
    `require_models` / `require_retriever` raise instead of falling back to
    the stub classifier / retriever."""
    return Pipeline(
        classifier=load_classifier(product_dir, issue_dir, require=require_models),
        retriever=load_retriever(require=require_retriever),
        generator=StubGenerator(),
        verifier=StubVerifier(),
        k=k,
    )
