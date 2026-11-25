"""Models and the analysis worker.

Models load once, in a background thread at startup, so the API answers at once
and /api/health reports what is ready. Analyses run one at a time on a worker
thread: each stage writes its output and the next stage name to the database,
so the case page can show progress while drafting (which takes minutes on the
NVIDIA API) runs.

Stages for a live analysis:
    classify   DistilBERT product and issue (stub if the weights are missing)
    retrieve   the configured retriever over the regulation corpus. Default "llm" (since 2026-11-22):
               Nemotron embeddings + BM25 + the classifier's regulation prior, then Nemotron Super with
               the rubric hints ranks the top 10 sections; the drafter gets up to 5 chunks of the
               top-ranked section (src/cfpb/retrieval/llm_rerank.py; docs/EXPERIMENT_LOG.md E1, E5, E9)
    scope      H5 logistic regression on BM25 + mpnet confidence (app/backend/scope.py);
               a flag stops here (status scope_review) unless the officer asked to draft anyway
    generate   Nemotron draft citing the retrieved passages (needs NVIDIA_API_KEY)
    verify     DeBERTa NLI + Nemotron Ultra judge (mean; CFPB_CHECKER), one score per sentence against the passages it cites, then verification
               gating: sentences below the cutoff go back to the drafter to be rewritten from the
               passage wording, and a rewrite is kept only if it scores higher (CFPB_GATING_ROUNDS,
               default 2; src/cfpb/generate/revise.py; EXPERIMENT_LOG E10)
"""
import logging
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import numpy as np

from app.backend import config
from app.backend.db import Analysis, Case, DraftVersion, Session, log_event, now
from app.backend.scope import ScopeModel, features

log = logging.getLogger("cfpb.app")
K = 5
SYSTEM = "system"


class Models:
    def __init__(self):
        self.ready = threading.Event()
        self.status: dict[str, str] = {"state": "loading"}
        self.error: str | None = None
        self.classifier = self.corpus = self.chunks = self.bm25 = self.dense = None
        self.scope = self.verifier = self.generator = self.llm_retriever = None

    def load(self, light: bool = False) -> None:
        """light=True skips the NLI model and the generator (used by the seeding script)."""
        try:
            from cfpb.pipeline.core import load_classifier
            from cfpb.pipeline.corpus import PAIR_B_CORPUS, Corpus
            from cfpb.retrieval.bm25 import BM25Retriever, load_chunks
            from cfpb.retrieval.dense import DenseRetriever

            self.status["classifier"] = "loading"
            self.classifier = load_classifier()
            self.status["classifier"] = "stub" if getattr(self.classifier, "is_stub", False) else self.classifier.source
            self.chunks = load_chunks(PAIR_B_CORPUS)
            self.corpus = Corpus.load(PAIR_B_CORPUS)
            self.bm25 = BM25Retriever(self.chunks)
            self.status["retriever"] = f"{config.RETRIEVER} over {len(self.chunks)} chunks"
            self.status["dense"] = "loading"
            self.dense = DenseRetriever(self.chunks)
            self.status["dense"] = self.dense.model_name
            if config.RETRIEVER == "llm" and not light:
                from cfpb.retrieval.llm_rerank import EMBED_MODEL, LLMRerankRetriever
                self.status["retriever"] = "loading Nemotron passage embeddings"
                self.llm_retriever = LLMRerankRetriever(self.chunks, self.bm25, model=config.RERANK_MODEL,
                                                        fallback=config.RERANK_FALLBACK)
                self.status["retriever"] = (f"{EMBED_MODEL} + BM25 + regulation prior, reranked by {config.RERANK_MODEL} "
                                            f"(fallback {config.RERANK_FALLBACK}) "
                                            f"over {len(self.chunks)} chunks")
            self.scope = ScopeModel.load()
            self.status["scope"] = self.scope.spec["name"] if self.scope else "missing (run app.backend.train_scope)"
            if light:
                self.status["state"] = "ready"
                return
            if config.LOAD_NLI:
                from cfpb.verify.nli import NLIVerifier
                self.status["verifier"] = "loading"
                if config.CHECKER == "ensemble":
                    from cfpb.verify.ensemble import EnsembleVerifier
                    self.verifier = EnsembleVerifier(NLIVerifier(), threshold=config.ENSEMBLE_CUTOFF)
                else:
                    self.verifier = NLIVerifier(threshold=config.NLI_CUTOFF)
                _ = self.verifier._model  # load weights now, not on the first request
                self.status["verifier"] = (self.verifier.model_name if config.CHECKER == "ensemble"
                                           else f"nli:{self.verifier.model_name}")
            else:
                self.status["verifier"] = "disabled (CFPB_LOAD_NLI=0)"
            if config.HAS_NVIDIA_KEY:
                from cfpb.generate.nemotron import NemotronGenerator
                self.generator = NemotronGenerator(model=config.GENERATOR_MODEL, max_tokens=config.GENERATOR_MAX_TOKENS,
                                                   timeout=config.GENERATOR_TIMEOUT)
                self.status["generator"] = config.GENERATOR_MODEL
            else:
                self.status["generator"] = "no NVIDIA_API_KEY: live drafting off"
            self.status["state"] = "ready"
        except Exception as e:  # keep the API up and say what failed
            self.error = f"{type(e).__name__}: {e}"
            self.status["state"] = "error"
            log.exception("model loading failed")
        finally:
            self.ready.set()

    # ---- stage helpers
    def score_rows(self, text: str) -> tuple[np.ndarray, np.ndarray]:
        return self.bm25.scores(text), self.dense.scores(text)

    def ranking(self, bm25_row: np.ndarray, dense_row: np.ndarray) -> np.ndarray:
        if config.RETRIEVER == "dense":
            return dense_row
        if config.RETRIEVER == "hybrid":
            from cfpb.retrieval.dense import HybridRetriever
            return HybridRetriever.combine(bm25_row, dense_row, config.HYBRID_ALPHA)
        return bm25_row

    def top_chunks(self, scores: np.ndarray, k: int = K) -> list:
        order = np.argsort(-scores, kind="stable")[:k]
        return [self.corpus.get(self.chunks[i]["chunk_id"]).ranked(r + 1, float(scores[i]))
                for r, i in enumerate(order)]

    def scope_for(self, text: str, bm25_row=None, dense_row=None) -> dict | None:
        if not self.scope:
            return None
        if bm25_row is None:
            bm25_row, dense_row = self.score_rows(text)
        return self.scope.score(features(self.chunks, bm25_row, dense_row, len(text.split())))

    def check(self, sentences: list[str], cited: list[list[str]], context: list) -> list[dict]:
        """NLI checks for given sentences against the analysis's passages."""
        from cfpb.pipeline.schema import Draft
        draft = Draft(response=" ".join(sentences), sentences=sentences, cited_chunk_ids=cited,
                      context_chunk_ids=[c.chunk_id for c in context], model="officer", prompt_version="edit",
                      is_referral=False)
        return self.with_parts([asdict(c) for c in self.verifier.verify(draft, context).checks])

    def with_parts(self, checks: list[dict]) -> list[dict]:
        """Add the two ensemble components (DeBERTa, Ultra) to each check, for display."""
        parts = getattr(self.verifier, "last_parts", None)
        if parts:
            for c in checks:
                if c["sentence"] in parts:
                    c["nli_prob"], c["ultra_prob"] = parts[c["sentence"]]
        return checks


MODELS = Models()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")


def start() -> None:
    threading.Thread(target=MODELS.load, name="model-loader", daemon=True).start()
    with Session() as s:  # analyses interrupted by a restart run again
        pending = s.query(Analysis).filter(Analysis.stage.notin_(["done", "failed"])).all()
        for a in pending:
            a.stage = "queued"
        s.commit()
        for a in pending:
            _executor.submit(run_analysis, a.id)


def enqueue(analysis_id: int) -> None:
    _executor.submit(run_analysis, analysis_id)


def chunk_dicts(chunks) -> list[dict]:
    from cfpb.pipeline.stages import citation
    return [{**asdict(c), "citation": citation(c)} for c in chunks]


def context_from(retrieval: dict) -> list:
    from cfpb.pipeline.schema import RetrievedChunk
    fields = RetrievedChunk.__dataclass_fields__
    return [RetrievedChunk(**{k: v for k, v in c.items() if k in fields}) for c in retrieval["chunks"]]


def draft_sentences(texts: list[str], cited: list[list[str]], checks: list[dict] | None,
                    gating: list[dict] | None = None) -> list[dict]:
    by_idx = {c["sentence_idx"]: c for c in checks or []}
    out = []
    for i, (t, c) in enumerate(zip(texts, cited)):
        chk = by_idx.get(i, {})
        row = {"text": t, "cited_chunk_ids": list(c), "premise_chunk_ids": chk.get("premise_chunk_ids", list(c)),
               "entail_prob": chk.get("entail_prob"), "contradict_prob": chk.get("contradict_prob"),
               "label": chk.get("label", "unchecked")}
        if chk.get("ultra_prob") is not None:
            row |= {"nli_prob": chk["nli_prob"], "ultra_prob": chk["ultra_prob"]}
        g = gating[i] if gating else None
        if g and g.get("original"):
            row |= {"original_text": g["original"], "gating_round": g["round"]}
        out.append(row)
    return out


def run_analysis(analysis_id: int) -> None:
    MODELS.ready.wait()
    with Session() as s:
        a = s.get(Analysis, analysis_id)
        case = s.get(Case, a.case_id)

        def stage(name: str) -> None:
            a.stage = name
            s.commit()

        try:
            if MODELS.error:
                raise RuntimeError(f"models failed to load: {MODELS.error}")
            from cfpb.data.clean import clean_narrative
            timings = {}
            t = now()

            def lap(name):
                nonlocal t
                timings[name] = round((now() - t).total_seconds() * 1000)
                t = now()

            case.status = "analyzing"
            stage("classify")
            clean = clean_narrative(case.narrative)
            if not clean:
                raise ValueError("The complaint text is empty after cleaning.")
            a.narrative_clean = clean
            a.classification = asdict(MODELS.classifier.classify(clean))
            lap("classify")

            stage("retrieve")
            bm25_row, dense_row = MODELS.score_rows(clean)
            if MODELS.llm_retriever is not None:
                from cfpb.retrieval.llm_rerank import top_section_chunks
                r = MODELS.llm_retriever.retrieve(clean, a.classification.get("candidate_regulation"))
                pos = {c["chunk_id"]: i for i, c in enumerate(MODELS.chunks)}
                fs = r["first_stage"]
                chunks = [c.ranked(n + 1, float(fs[pos[c.chunk_id]]) if c.chunk_id in pos else 0.0) for n, c in
                          enumerate(top_section_chunks(r["sections"][0], fs, MODELS.corpus, MODELS.chunks))]
                a.retrieval = {"retriever": "llm-rerank-top-section" if r["reranked"] else "llm-first-stage-top-section",
                               "corpus": MODELS.corpus.name, "chunks": chunk_dicts(chunks), "note": r["note"],
                               "sections": r["sections"], "reranker": r.get("reranker")}
            else:
                chunks = MODELS.top_chunks(MODELS.ranking(bm25_row, dense_row))
                a.retrieval = {"retriever": config.RETRIEVER, "corpus": MODELS.corpus.name, "chunks": chunk_dicts(chunks)}
            lap("retrieve")

            stage("scope")
            a.scope = MODELS.scope_for(clean, bm25_row, dense_row)
            lap("scope")
            if a.scope and a.scope["out_of_scope"] and not a.force_draft:
                a.timings_ms, a.finished_at = timings, now()
                case.status = "scope_review"
                log_event(s, case, SYSTEM, "scope_flag",
                          f"Likely outside the covered regulations (score {a.scope['prob_out_of_scope']:.2f} "
                          f">= {a.scope['threshold']:.2f}). No draft written.")
                stage("done")
                return

            stage("generate")
            if MODELS.generator is None:
                raise RuntimeError("Live drafting needs NVIDIA_API_KEY in .env.")
            draft = MODELS.generator.generate(clean, chunks)
            a.draft = asdict(draft)
            a.generator_model = draft.model
            lap("generate")

            stage("verify")
            checks, gating = [], None
            texts, cited = draft.sentences, draft.cited_chunk_ids
            if MODELS.verifier is not None:
                a.verifier, a.nli_cutoff = MODELS.status["verifier"], config.CHECK_CUTOFF
                if config.GATING_ROUNDS > 0:
                    from cfpb.generate.revise import REVISE_VERSION, gate_draft
                    stage("revise")
                    texts, cited, chk, gating = gate_draft(clean, draft, chunks, MODELS.generator, MODELS.verifier,
                                                           config.CHECK_CUTOFF, config.GATING_ROUNDS)
                    checks = MODELS.with_parts([asdict(c) for c in chk])
                    a.draft = a.draft | {"gating": {"rounds": config.GATING_ROUNDS, "prompt": REVISE_VERSION,
                                                    "per_sentence": gating}}
                else:
                    checks = MODELS.with_parts([asdict(c) for c in MODELS.verifier.verify(draft, chunks).checks])
            a.checks = checks
            lap("verify")

            version = len(case.drafts) + 1
            s.add(DraftVersion(case_id=case.id, analysis_id=a.id, version=version, author="AI draft",
                               sentences=draft_sentences(texts, cited, checks, gating)))
            a.timings_ms, a.finished_at = timings, now()
            case.status = "in_review"
            n_flag = sum(c["label"] == "unsupported" for c in checks)
            n_rev = sum(bool(g.get("original")) for g in gating or [])
            log_event(s, case, SYSTEM, "analysis_done",
                      f"Draft v{version}: {len(texts)} sentences, {n_flag} flagged"
                      + (f", {n_rev} rewritten by the checker loop." if gating is not None else "."))
            stage("done")
        except Exception as e:
            log.exception("analysis %s failed", analysis_id)
            s.rollback()
            a = s.get(Analysis, analysis_id)
            case = s.get(Case, a.case_id)
            a.stage, a.error, a.finished_at = "failed", f"{type(e).__name__}: {e}", now()
            case.status = "failed"
            log_event(s, case, SYSTEM, "analysis_failed", a.error)
            s.commit()
            log.debug(traceback.format_exc())
