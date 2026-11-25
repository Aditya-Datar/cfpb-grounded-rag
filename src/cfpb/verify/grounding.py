"""Grounding checkers trained for LLM claims: FactCG-DeBERTa-L and MiniCheck-Flan-T5-L (EXPERIMENT_LOG E12).

Drop-in for NLIVerifier where gating needs it: `score(premises, sentence) -> (support_prob, 0.0)`
and `verify(draft, context)`. Input formats follow the authors' code (read 2026-11-22):

FactCG (Lei et al., NAACL 2025; github.com/derenlei/FactCG, factcg/utils.py + inference.py):
    INSTRUCTION_TEMPLATE with the premise chunk as text_a and the claim as text_b, max_length 2048,
    premise packed into chunks of <= 550 word tokens at sentence boundaries, softmax over the 2
    logits, index 1 = supported, max over chunks.
MiniCheck (Tang et al., EMNLP 2024; github.com/Liyan06/MiniCheck, minicheck/inference.py):
    "predict: " + chunk + "</s>" + claim, max_length 2048, chunks of <= 500 words at sentence
    boundaries, one decoder step from the pad token, softmax over token ids [3, 209] ("▁", "▁1"),
    index 1 = supported, max over chunks.
AlignScore-large (Zha et al., ACL 2023; github.com/yuh-zha/AlignScore, src/alignscore/inference.py +
model.py, read 2026-11-23): RoBERTa-large + linear heads on the pooler output; 'nli_sp' mode = softmax of
the 3-way head, class 0 ("aligned"); premise split into sentence groups of about 350 words, each
(group, claim sentence) pair tokenised with truncation 'only_first' to 512; score = mean over claim
sentences of the max over groups. Checkpoint yzha/AlignScore AlignScore-large.ckpt.
HHEM-2.1-open (Vectara; vectara/hallucination_evaluation_model, flan-t5-base): the model's own
predict(): prompt "<pad> Determine if the hypothesis is true given the premise?..." and softmax
index 1 = consistent. No chunking.
Bespoke-MiniCheck-7B (Bespoke Labs, via Ollama `bespoke-minicheck`): prompt "Document: ...\nClaim: ..."
answered Yes/No; score = P(Yes) / (P(Yes) + P(No)) from the first token's log-probabilities.
Deviation: the Ollama build is 4-bit quantised (the full bf16 model needs about 15.5 GB of RAM, this
machine has 16 GB), so its scores may differ slightly from the published model's.
Deviation: the authors split sentences with NLTK; this uses a regex splitter (NLTK is not installed).
Premises here are mostly under 500 words, so nearly all fit one chunk.
"""
import re
from functools import cached_property

from cfpb.pipeline.schema import SUPPORTED, UNSUPPORTED, SentenceCheck, Verification

FACTCG = "yaxili96/FactCG-DeBERTa-v3-Large"
MINICHECK = "lytang/MiniCheck-Flan-T5-Large"
FACTCG_TEMPLATE = ("{text_a}\n\nChoose your answer: based on the paragraph above can we conclude that \"{text_b}\"?"
                   "\n\nOPTIONS:\n- Yes\n- No\nI think the answer is ")
ALIGNSCORE = "yzha/AlignScore"
HHEM = "vectara/hallucination_evaluation_model"
BESPOKE = "bespoke-minicheck"
OLLAMA = "http://localhost:11434"
_SENT = re.compile(r"(?<=[.;:!?])\s+|\n+")


def chunk_words(text: str, max_words: int) -> list[str]:
    out, cur, n = [], [], 0
    for s in (x.strip() for x in _SENT.split(text)):
        if not s:
            continue
        w = len(s.split())
        if cur and n + w > max_words:
            out.append(" ".join(cur))
            cur, n = [], 0
        cur.append(s)
        n += w
    if cur:
        out.append(" ".join(cur))
    return out or [text]


class GroundingVerifier:
    is_stub = False

    def __init__(self, kind: str = "factcg", threshold: float = 0.5, batch_size: int = 4, device: str | None = None):
        assert kind in ("factcg", "minicheck", "alignscore", "hhem", "bespoke")
        self.kind, self.threshold, self.batch_size, self._device = kind, threshold, batch_size, device
        self.model_name = {"factcg": FACTCG, "minicheck": MINICHECK, "alignscore": ALIGNSCORE + ":AlignScore-large",
                           "hhem": HHEM, "bespoke": "ollama:" + BESPOKE}[kind]

    @cached_property
    def _model(self):
        import torch
        from transformers import (AutoConfig, AutoModelForSeq2SeqLM, AutoModelForSequenceClassification,
                                  AutoTokenizer)
        device = self._device or ("cuda" if torch.cuda.is_available() else "cpu")
        if self.kind == "alignscore":
            return self._load_alignscore(device)
        if self.kind == "hhem":
            model = AutoModelForSequenceClassification.from_pretrained(HHEM, trust_remote_code=True)  # code read 2026-11-23
            return None, model.eval().to(device), device
        if self.kind == "bespoke":
            return None, None, None
        tok = AutoTokenizer.from_pretrained(self.model_name, use_fast=True)
        if self.kind == "factcg":
            cfg = AutoConfig.from_pretrained(self.model_name, num_labels=2, finetuning_task="text-classification")
            cfg.problem_type = "single_label_classification"
            model = AutoModelForSequenceClassification.from_pretrained(self.model_name, config=cfg)
            tok.pad_token = tok.eos_token or tok.pad_token
        else:
            model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
        return tok, model.eval().to(device), device

    @staticmethod
    def _load_alignscore(device):
        import torch
        from huggingface_hub import hf_hub_download
        from transformers import AutoConfig, AutoTokenizer, RobertaModel
        ckpt = torch.load(hf_hub_download(ALIGNSCORE, "AlignScore-large.ckpt"), map_location="cpu", weights_only=True)
        sd = ckpt.get("state_dict", ckpt)
        base = RobertaModel(AutoConfig.from_pretrained("roberta-large"))
        missing, _ = base.load_state_dict({k[len("base_model."):]: v for k, v in sd.items() if k.startswith("base_model.")},
                                          strict=False)
        assert not [m for m in missing if "position_ids" not in m], missing
        tri = torch.nn.Linear(base.config.hidden_size, 3)
        tri.load_state_dict({"weight": sd["tri_layer.weight"], "bias": sd["tri_layer.bias"]})
        return AutoTokenizer.from_pretrained("roberta-large"), (base.eval().to(device), tri.eval().to(device)), device

    def _alignscore(self, premise: str, claim: str) -> float:
        import torch
        tok, (base, tri), device = self._model
        sents = [s for s in (x.strip() for x in _SENT.split(premise)) if s] or [""]
        n = len(premise.strip().split()) // 350 + 1
        n = max(len(sents) // n, 1)
        groups = [" ".join(sents[i:i + n]) for i in range(0, len(sents), n)]
        hyps = [s for s in (x.strip() for x in _SENT.split(claim)) if s] or [claim]
        pre = [g for g in groups for _ in hyps]
        hyp = [h for _ in groups for h in hyps]
        out = []
        for i in range(0, len(pre), 8):
            enc = tok(pre[i:i + 8], hyp[i:i + 8], truncation="only_first", padding="max_length", max_length=512,
                      return_tensors="pt").to(device)
            with torch.no_grad():
                out.append(tri(base(**enc).pooler_output).softmax(-1)[:, 0].cpu())
        return float(torch.cat(out).view(len(groups), len(hyps)).max(0).values.mean())

    def _bespoke(self, premise: str, claim: str) -> float:
        import json
        import math
        import urllib.request
        body = {"model": BESPOKE, "prompt": f"Document: {premise}\nClaim: {claim}", "stream": False,
                "options": {"temperature": 0, "num_predict": 1}, "logprobs": True, "top_logprobs": 10}
        req = urllib.request.Request(OLLAMA + "/api/generate", json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            d = json.loads(r.read())
        top = (d.get("logprobs") or [{}])[0].get("top_logprobs") or []
        p = {"yes": 0.0, "no": 0.0}
        for e in top:
            w = e["token"].strip().lower()
            if w in p:
                p[w] += math.exp(e["logprob"])
        if p["yes"] + p["no"] == 0:  # no log-probabilities: fall back to the answer itself
            return 1.0 if d.get("response", "").strip().lower().startswith("yes") else 0.0
        return p["yes"] / (p["yes"] + p["no"])

    def _probs(self, chunks: list[str], claim: str) -> list[float]:
        import torch
        tok, model, device = self._model
        out = []
        for i in range(0, len(chunks), self.batch_size):
            part = chunks[i:i + self.batch_size]
            if self.kind == "factcg":
                texts = [FACTCG_TEMPLATE.format(text_a=c, text_b=claim) for c in part]
                enc = tok(texts, max_length=2048, truncation=True, padding="longest", return_tensors="pt").to(device)
                with torch.no_grad():
                    p = model(**enc).logits.softmax(-1)[:, 1]
            else:
                texts = ["predict: " + tok.eos_token.join([c, claim]) for c in part]
                enc = tok(texts, max_length=2048, truncation=True, padding=True, return_tensors="pt").to(device)
                dec = torch.zeros((enc["input_ids"].size(0), 1), dtype=torch.long, device=device)
                with torch.no_grad():
                    logits = model(**enc, decoder_input_ids=dec).logits.squeeze(1)
                p = logits[:, torch.tensor([3, 209])].softmax(-1)[:, 1]
            out += [float(x) for x in p.cpu()]
        return out

    def score(self, premises: list[str], sentence: str) -> tuple[float, float]:
        if self.kind == "alignscore":
            return self._alignscore(" ".join(premises), sentence), 0.0
        if self.kind == "bespoke":
            return self._bespoke("\n\n".join(premises), sentence), 0.0
        if self.kind == "hhem":
            _, model, _ = self._model
            return float(model.predict([("\n\n".join(premises), sentence)])[0]), 0.0
        size = 550 if self.kind == "factcg" else 500
        chunks = [c for p in premises for c in chunk_words(p, size)]
        if not chunks:
            return 0.0, 0.0
        return max(self._probs(chunks, sentence)), 0.0

    def verify(self, draft, context) -> Verification:
        by_id = {c.chunk_id: c for c in context}
        all_ids = [c.chunk_id for c in context]
        checks = []
        for i, (sentence, cited) in enumerate(zip(draft.sentences, draft.cited_chunk_ids)):
            pids = [c for c in cited if c in by_id] or all_ids
            e, _ = self.score([by_id[c].text for c in pids], sentence)
            checks.append(SentenceCheck(i, sentence, pids, e, 0.0, SUPPORTED if e >= self.threshold else UNSUPPORTED))
        return Verification(checks, verifier=f"{self.kind}:{self.model_name}", threshold=self.threshold)
