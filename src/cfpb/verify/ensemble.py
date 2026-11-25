"""Ensemble checker: mean(DeBERTa NLI entailment, Nemotron Ultra judge support probability) (EXPERIMENT_LOG E12b).

    v = EnsembleVerifier()                     # loads DeBERTa lazily; Ultra through the NVIDIA API
    v.verify(draft, context)                   # same interface as NLIVerifier
    v.score(premises, sentence)                # (ensemble score, NLI contradiction prob)

A sentence is supported when the mean is >= CUT, the cutoff chosen on checker set 1
(results/checker_ultra_compare.json, "nli_or_ultra_avg"): set-2 balanced accuracy 0.829 vs 0.679
for DeBERTa alone at T. Same premises for both models (the cited chunks, or all context chunks when
a sentence cites none) and the judge-v1 prompt, exactly as scripts/rescore_ensemble.py scores the
pipeline runs, so app and evaluation agree. Ultra replies are cached (cfpb.verify.llm_judge);
an unreadable reply counts as 0 for Ultra, as in the evaluation.
"""
from concurrent.futures import ThreadPoolExecutor

from cfpb.pipeline.schema import SUPPORTED, UNSUPPORTED, Draft, RetrievedChunk, SentenceCheck, Verification
from cfpb.verify.llm_judge import LLMJudgeVerifier
from cfpb.verify.nli import NLIVerifier

ULTRA = "nvidia/nemotron-3-ultra-550b-a55b"
CUT = 0.9737792968749999  # results/checker_ultra_compare.json nli_or_ultra_avg.cut_set1


class EnsembleVerifier:
    is_stub = False

    def __init__(self, nli: NLIVerifier | None = None, judge_model: str = ULTRA, threshold: float = CUT,
                 workers: int = 4):
        self.nli = nli or NLIVerifier()
        self.judge = LLMJudgeVerifier(judge_model, min_interval=0.0)
        self.threshold, self.workers = threshold, workers
        self.model_name = f"mean({self.nli.model_name}, {judge_model})"
        self.last_parts: dict[str, tuple[float, float]] = {}  # sentence -> (nli, ultra), for display

    @property
    def _model(self):  # so callers can preload the DeBERTa weights as with NLIVerifier
        return self.nli._model

    def _ultra(self, premises: list[str], sentence: str) -> float:
        return self.judge.score(premises, sentence)[0]

    def score(self, premises: list[str], sentence: str) -> tuple[float, float]:
        with ThreadPoolExecutor(1) as ex:
            u = ex.submit(self._ultra, premises, sentence)  # API call overlaps the local NLI pass
            e, c = self.nli.score(premises, sentence)
            ult = u.result()
        self.last_parts[sentence] = (e, ult)
        return (e + ult) / 2, c

    def verify(self, draft: Draft, context: list[RetrievedChunk]) -> Verification:
        by_id = {c.chunk_id: c for c in context}
        all_ids = [c.chunk_id for c in context]
        pids = [[cid for cid in cited if cid in by_id] or all_ids for cited in draft.cited_chunk_ids]
        prem = [[by_id[cid].text for cid in p] for p in pids]
        with ThreadPoolExecutor(self.workers) as ex:
            futs = [ex.submit(self._ultra, p, s) for p, s in zip(prem, draft.sentences)]  # API calls in parallel
            nli = [self.nli.score(p, s) for p, s in zip(prem, draft.sentences)]           # while NLI runs locally
            ult = [f.result() for f in futs]
        checks = []
        for i, (sentence, (e, c), u) in enumerate(zip(draft.sentences, nli, ult)):
            self.last_parts[sentence] = (e, u)
            m = (e + u) / 2
            checks.append(SentenceCheck(i, sentence, pids[i], m, c, SUPPORTED if m >= self.threshold else UNSUPPORTED))
        return Verification(checks, verifier=self.model_name, threshold=self.threshold)
