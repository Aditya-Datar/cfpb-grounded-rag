"""Stage 4: sentence-level NLI verifier (CLAUDE.md Sec. 3, docs/INTERFACES.md Sec. 5).

Follows SummaC (Laban et al., 2022): each generated sentence is a hypothesis,
checked against premise blocks taken from the passages it cites (or all the
context if it cites nothing). A sentence's score is its best block:

    entail_prob     = max over blocks of P(entailment | block, sentence)
    contradict_prob = P(contradiction) on that same block
    label           = supported if entail_prob >= threshold, else unsupported

Blocks are windows of at most `max_premise_tokens` tokens (stride overlapping)
so that block + sentence fit the model's 512-token input. The threshold is
tuned on the checker validation set (scripts/benchmark_checker.py).
"""
from functools import cached_property

from cfpb.pipeline.schema import SUPPORTED, UNSUPPORTED, Draft, RetrievedChunk, SentenceCheck, Verification

DEFAULT_MODEL = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"


class NLIVerifier:
    is_stub = False

    def __init__(self, model_name: str = DEFAULT_MODEL, threshold: float = 0.5,
                 max_premise_tokens: int = 400, stride: int = 300, batch_size: int = 8,
                 device: str | None = None):
        self.model_name, self.threshold = model_name, threshold
        self.max_premise_tokens, self.stride, self.batch_size = max_premise_tokens, stride, batch_size
        self._device = device

    @cached_property
    def _model(self):
        import torch  # deferred: slow import, only needed when scoring
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModelForSequenceClassification.from_pretrained(self.model_name).eval()
        device = self._device or ("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        label2id = {k.lower(): v for k, v in model.config.label2id.items()}
        return tok, model, device, label2id["entailment"], label2id["contradiction"]

    def blocks(self, premise: str) -> list[str]:
        """Split a premise into overlapping token windows, returned as text spans."""
        tok = self._model[0]
        enc = tok(premise, add_special_tokens=False, return_offsets_mapping=True)
        offsets = enc["offset_mapping"]
        if len(offsets) <= self.max_premise_tokens:
            return [premise]
        out = []
        for start in range(0, len(offsets), self.stride):
            window = offsets[start:start + self.max_premise_tokens]
            out.append(premise[window[0][0]:window[-1][1]])
            if start + self.max_premise_tokens >= len(offsets):
                break
        return out

    def pair_probs(self, premises: list[str], hypotheses: list[str]) -> list[tuple[float, float]]:
        """(entail, contradict) probability for each (premise, hypothesis) pair."""
        import torch
        tok, model, device, ent, con = self._model
        out = []
        for i in range(0, len(premises), self.batch_size):
            enc = tok(premises[i:i + self.batch_size], hypotheses[i:i + self.batch_size],
                      truncation="only_first", max_length=512, padding=True, return_tensors="pt").to(device)
            with torch.no_grad():
                probs = model(**enc).logits.softmax(-1).cpu()
            out += [(float(p[ent]), float(p[con])) for p in probs]
        return out

    def score(self, premises: list[str], sentence: str) -> tuple[float, float]:
        """Best block over all premise texts: (entail_prob, contradict_prob)."""
        blocks = [b for p in premises for b in self.blocks(p)]
        if not blocks:
            return 0.0, 0.0
        return max(self.pair_probs(blocks, [sentence] * len(blocks)), key=lambda ec: ec[0])

    def verify(self, draft: Draft, context: list[RetrievedChunk]) -> Verification:
        by_id = {c.chunk_id: c for c in context}
        all_ids = [c.chunk_id for c in context]
        checks = []
        for i, (sentence, cited) in enumerate(zip(draft.sentences, draft.cited_chunk_ids)):
            premise_ids = [cid for cid in cited if cid in by_id] or all_ids
            entail, contradict = self.score([by_id[cid].text for cid in premise_ids], sentence)
            label = SUPPORTED if entail >= self.threshold else UNSUPPORTED
            checks.append(SentenceCheck(i, sentence, premise_ids, entail, contradict, label))
        return Verification(checks, verifier=f"nli:{self.model_name}", threshold=self.threshold)
