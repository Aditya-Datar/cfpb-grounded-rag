"""Result types passed between pipeline stages and returned to the demo.

Field names follow docs/INTERFACES.md (Secs. 1, 2, 4, 5, 7), restricted to
what one complaint at a time needs. The batch Parquet outputs stay the
evaluation format; these dataclasses are the in-memory, per-request form.
Every result has to_dict() so the demo (or a JSON API later) can use plain
dicts.
"""
from dataclasses import asdict, dataclass, field

NONE_LABEL = "NONE"  # abstention outcome, INTERFACES.md Sec. 7

# Verification labels. "unchecked" is only produced by the stub verifier, so a
# demo can never show a stubbed check as "supported".
SUPPORTED, UNSUPPORTED, UNCHECKED = "supported", "unsupported", "unchecked"


@dataclass
class LabelPrediction:
    label: str
    prob: float
    top_k: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class Classification:
    """Stage 1. `issue` is None when only the product model is loaded."""
    product: LabelPrediction
    issue: LabelPrediction | None
    candidate_regulation: str | None  # config.PRODUCT_TO_REGULATION heuristic, not a label
    source: str                       # e.g. "distilbert:<model_dir>" or "stub"


@dataclass
class RetrievedChunk:
    """One ranked chunk. Carries the text so the demo and the generator do not
    need a second corpus lookup."""
    rank: int
    chunk_id: str
    score: float
    regulation: str   # E, F, V, Z, FCRA
    section: str      # e.g. 1005.11 or 1681i
    paragraph: str
    heading: str
    text: str
    source_url: str


@dataclass
class Retrieval:
    """Stage 2. `abstained` is True when abstain_score passed the threshold,
    i.e. no in-scope section governs the complaint."""
    chunks: list[RetrievedChunk]
    abstain_score: float
    abstained: bool
    retriever: str
    corpus: str


@dataclass
class Draft:
    """Stage 3. `sentences` and `cited_chunk_ids` are aligned (one list of
    cited chunk ids per sentence, empty if the sentence cites nothing)."""
    response: str
    sentences: list[str]
    cited_chunk_ids: list[list[str]]
    context_chunk_ids: list[str]
    model: str
    prompt_version: str
    is_referral: bool  # True when drafted for an abstention (cites nothing)


@dataclass
class SentenceCheck:
    """Stage 4, one per draft sentence."""
    sentence_idx: int
    sentence: str
    premise_chunk_ids: list[str]
    entail_prob: float | None
    contradict_prob: float | None
    label: str  # SUPPORTED, UNSUPPORTED, or UNCHECKED


@dataclass
class Verification:
    checks: list[SentenceCheck]
    verifier: str
    threshold: float | None

    @property
    def n_supported(self) -> int:
        return sum(c.label == SUPPORTED for c in self.checks)

    @property
    def n_flagged(self) -> int:
        return sum(c.label == UNSUPPORTED for c in self.checks)


@dataclass
class PipelineResult:
    narrative: str        # as submitted
    narrative_clean: str  # what the models saw
    classification: Classification
    retrieval: Retrieval
    draft: Draft
    verification: Verification
    stubbed_stages: list[str]          # stages answered by a placeholder, shown in the demo
    timings_ms: dict[str, float]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["verification"]["n_supported"] = self.verification.n_supported
        d["verification"]["n_flagged"] = self.verification.n_flagged
        return d
