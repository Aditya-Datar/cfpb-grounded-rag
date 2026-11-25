"""Retrieval v2 for live use: Nemotron embeddings + BM25 + regulation prior, then LLM listwise rerank.

The settings are the ones chosen on the dev half by scripts/run_retrieval_llm.py
(results/retrieval_llm.json, 2026-11-19): embedder nvidia/nemotron-3.5-embed-8b
fused with BM25 at alpha 0.8, +0.2 for chunks of the regulation the classifier's
product points to (V also admits the FCRA), then an LLM picks the five sections that
govern the complaint from the top 10.

Live default since 2026-11-22 (docs/EXPERIMENT_LOG.md E5, E9): nvidia/nemotron-3.5-super-vl-120b-a12b
(thinking, max_tokens 32768) with the rubric hints (RUBRIC, the team's section-choice conventions;
disclose that the gold labels share them). The 2026-11-19 setting (Lightning, no rubric) is
rerank(..., model=LIGHTNING_MODEL, rubric=False). Request bodies match the experiments', so the
same on-disk cache (outputs/retrieval/llm_cache) serves both.

top_section_chunks() gives the drafter's context: up to 5 chunks of the top-ranked section, by
first-stage score (the "top1x5" layout, E1).

    r = LLMRerankRetriever(chunks, bm25)
    out = r.retrieve(text, candidate_regulation="E")   # {"sections", "chunk_idx", "scores", "reranked", "note", "first_stage"}

Needs NVIDIA_API_KEY. If the reranker fails, the first-stage order is returned
and "reranked" is False; if the embedder fails, the call raises.
"""
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests

from cfpb.config import OUTPUT_DIR
from cfpb.generate.nemotron import api_key
from cfpb.pipeline.corpus import _regulation_of
from cfpb.retrieval.dense import HybridRetriever

EMBED_MODEL = "nvidia/nemotron-3.5-embed-8b"
LIGHTNING_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
SUPER_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
GPT_MODEL = "codex:gpt-5.6-sol"  # GPT via the Codex CLI (cfpb.verify.codex_client); best dev reranker, E9
RERANK_MODEL = SUPER_MODEL  # module default; the app picks its model with CFPB_RERANK_MODEL
USE_RUBRIC = True
CODEX_CACHE = OUTPUT_DIR / "retrieval" / "codex_cache"  # shared with scripts/run_reranker_swap.py
ALPHA, PRIOR_B, RERANK_K = 0.8, 0.2, 10
BASE = "https://integrate.api.nvidia.com/v1"
CACHE = OUTPUT_DIR / "retrieval" / "llm_cache"
EMB_FILE = OUTPUT_DIR / "retrieval" / "embeddings" / "nemotron-3.5-embed-8b.npy"

RERANK_PROMPT = """You are a compliance analyst at a US financial company. A consumer complaint is below, followed by candidate sections of federal consumer-finance law: Regulation E (12 CFR 1005, electronic fund transfers), Regulation Z (12 CFR 1026, truth in lending), Regulation V (12 CFR 1022, fair credit reporting), Regulation F (12 CFR 1006, debt collection) and the Fair Credit Reporting Act (15 U.S.C. 1681 et seq.).

Pick the five candidate sections that most directly govern the company's obligations on the complaint's main issue, best first. Prefer the operative section that sets the duty (for example, error resolution or dispute procedures) over definitions, scope or general provisions.

Complaint:
{complaint}

Candidate sections:
{candidates}

Answer with JSON only, for example {{"ranking": ["C3", "C1", "C7", "C2", "C5"]}}."""

# Variant "rubric": the team's section-choice conventions (annotation/ANNOTATION_GUIDE.md and the
# regulation-annotator skill), stated as guidance. The gold labels were made with these same conventions,
# so a gain from this variant partly reflects matching the labelling rubric; disclose that if used.
RUBRIC = """
Guidance for choosing the governing section (pick the duty section for the consumer's MAIN grievance; ignore statutes the consumer cites):
- Credit reporting agency: dispute or reinvestigation -> 15 U.S.C. 1681i; identity-theft block or report -> 1681c-2; inquiry without permissible purpose -> 1681b; file accuracy with no dispute -> 1681e.
- Furnisher: dispute sent directly to it -> 12 CFR 1022.43; dispute relayed by a credit bureau -> 1681s-2(b); known-inaccurate data -> 1681s-2(a).
- Third-party debt collector or debt buyer: ignored a written validation request and kept collecting or reporting -> 1006.38; reported false or disputed data to bureaus -> 1006.18; reported before any contact -> 1006.30; no validation notice -> 1006.34; contact after a written cease request -> 1006.6; repeated calls or harassment -> 1006.14; misstated amount or status -> 1006.18; time-barred suit -> 1006.26.
- Credit card: unauthorized charge where the issuer investigated and denied the claim -> 1026.13; unauthorized use described without a dispute-handling grievance -> 1026.12; card opened without request -> 1026.12; goods not delivered or billing error dispute -> 1026.13; payment not credited -> 1026.10; late fee without a timely statement -> 1026.5; APR increase -> 1026.55; penalty fee size -> 1026.52; payment allocation -> 1026.53.
- Bank account, debit card, prepaid card: unauthorized or incorrect electronic transfer and the claim handling is the grievance -> 1005.11; liability for a loss only -> 1005.6; prepaid claim denied as late -> 1005.18.
- Mortgage closing costs above the estimate -> 1026.19.
"""

_session = requests.Session()


def post(path: str, body: dict, timeout: int = 300, retries: int = 8) -> dict:
    """POST to the NVIDIA API with an on-disk cache keyed by the request body."""
    key = hashlib.sha1(json.dumps([path, body], sort_keys=True).encode()).hexdigest()
    f = CACHE / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    err = ""
    for attempt in range(retries):
        try:
            r = _session.post(BASE + path, json=body, timeout=timeout,
                              headers={"Authorization": f"Bearer {api_key()}"})
            if r.status_code == 200:
                out = r.json()
                CACHE.mkdir(parents=True, exist_ok=True)
                f.write_text(json.dumps(out), encoding="utf-8")
                return out
            err = f"HTTP {r.status_code}: {r.text[:200]}"
        except requests.RequestException as e:
            err = repr(e)
        time.sleep(min(120, 2 ** attempt) * (3 if "429" in err else 1))
    raise RuntimeError(f"{path} failed after retries: {err}")


def embed_one(text: str, input_type: str) -> list[float]:
    # One text per request (batches return HTTP 500); long inputs also fail at times, so cut shorter on failure.
    for n in (1000, 400, 200):
        try:
            return post("/embeddings", {"model": EMBED_MODEL,
                                        "input": [text if len(text.split()) <= n else " ".join(text.split()[:n])],
                                        "input_type": input_type, "encoding_format": "float", "truncate": "END"},
                        retries=4)["data"][0]["embedding"]
        except RuntimeError:
            continue
    raise RuntimeError("embedding failed at every length")


def embed(texts: list[str], input_type: str, workers: int = 8) -> np.ndarray:
    with ThreadPoolExecutor(workers) as ex:
        e = np.asarray(list(ex.map(lambda t: embed_one(t, input_type), texts)), dtype="float32")
    return e / np.linalg.norm(e, axis=1, keepdims=True)


def section_order(order, chunks: list[dict]) -> list[tuple[str, int]]:
    """Sections in order of their best chunk, with that chunk's index."""
    seen, out = set(), []
    for i in order:
        s = chunks[i]["section"]
        if s not in seen:
            seen.add(s)
            out.append((s, int(i)))
    return out


def _label(chunk: dict) -> str:
    return f"15 U.S.C. {chunk['section']}" if chunk.get("regulation") == "FCRA" else f"12 CFR {chunk['section']}"


def codex_post(model: str, prompt: str) -> dict:
    """One rerank call through the Codex CLI, cached under the same key as the E5/E9 experiments."""
    from cfpb.verify.codex_client import CodexClient
    f = CODEX_CACHE / (hashlib.sha1(("rerank" + model + prompt).encode()).hexdigest() + ".json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    data = CodexClient(model.split(":", 1)[1])._call([{"role": "user", "content": prompt}])
    if (data["choices"][0]["message"].get("content") or "").strip():
        CODEX_CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data), encoding="utf-8")
    return data


def rerank(complaint: str, cands: list[tuple[str, int]], chunks: list[dict], mode: str = "think32k",
           model: str = RERANK_MODEL, rubric: bool = USE_RUBRIC) -> list[str]:
    """The LLM's five sections, best first (fewer if its answer is short or unparseable)."""
    lines = []
    for n, (sec, j) in enumerate(cands, 1):
        words = (chunks[j]["text"] or "").split()
        lines.append(f"C{n}. {_label(chunks[j])}, {chunks[j]['heading']}\n   Passage: {' '.join(words[:90])}")
    text = " ".join(complaint.split()[:900])
    prompt = RERANK_PROMPT.format(complaint=text, candidates="\n".join(lines))
    if rubric:
        prompt = prompt.replace("\n\nComplaint:\n", "\n" + RUBRIC + "\nComplaint:\n", 1)
    if model.startswith("codex:"):
        msg = codex_post(model, prompt)["choices"][0]["message"]
    else:
        body = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]}
        if mode == "nothink":
            body |= {"max_tokens": 1024, "chat_template_kwargs": {"enable_thinking": False}}
        else:
            body |= {"max_tokens": 32768}
        msg = post("/chat/completions", body)["choices"][0]["message"]
    content = re.sub(r"<think>.*?</think>", "", msg.get("content") or "", flags=re.S)
    ids = re.findall(r"C(\d+)", content.split("ranking")[-1] if "ranking" in content else content)
    picked = []
    for x in ids:
        k = int(x) - 1
        if 0 <= k < len(cands) and cands[k][0] not in picked:
            picked.append(cands[k][0])
    return picked[:5]


def top_section_chunks(section: str, first_stage: np.ndarray, corpus, chunks: list[dict], n: int = 5) -> list:
    """Drafter context (top1x5, E1): up to n rule chunks of `section`, best first-stage score first."""
    pos = {c["chunk_id"]: i for i, c in enumerate(chunks)}
    return sorted(corpus.section(section),
                  key=lambda c: -first_stage[pos[c.chunk_id]] if c.chunk_id in pos else np.inf)[:n]


class LLMRerankRetriever:
    def __init__(self, chunks: list[dict], bm25, model: str = RERANK_MODEL, fallback: str | None = None):
        self.chunks, self.bm25, self.model, self.fallback = chunks, bm25, model, fallback
        self.reg = np.array([_regulation_of(c["section"]) for c in chunks])
        texts = [c.get("embed_text") or c["text"] for c in chunks]
        key = hashlib.sha1(json.dumps([EMBED_MODEL, texts]).encode()).hexdigest()[:16]
        path = EMB_FILE.with_name(f"{EMB_FILE.stem}-{key}.npy")
        if path.exists():
            self.emb = np.load(path)
        else:
            self.emb = embed(texts, "passage")
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, self.emb)

    def first_stage(self, text: str, candidate_regulation: str | None) -> np.ndarray:
        q = embed([text], "query")[0]
        s = HybridRetriever.combine(self.bm25.scores(text), (self.emb @ q).astype(float), ALPHA)
        allowed = {"V", "FCRA"} if candidate_regulation == "V" else ({candidate_regulation} if candidate_regulation else set())
        if allowed:
            s = s + PRIOR_B * np.isin(self.reg, list(allowed)).astype(float)
        return s

    def retrieve(self, text: str, candidate_regulation: str | None, k: int = 5) -> dict:
        s = self.first_stage(text, candidate_regulation)
        secs = section_order(np.argsort(-s, kind="stable"), self.chunks)
        best = dict(secs)
        note, top, used = None, [], None
        for m in [self.model] + ([self.fallback] if self.fallback and self.fallback != self.model else []):
            try:
                top = rerank(text, secs[:RERANK_K], self.chunks, model=m)
                if top:
                    used = m
                    break
                note = f"{m} gave no usable answer"
            except Exception as e:  # try the fallback, then keep the case moving on the first-stage order
                note = f"{m} unavailable ({type(e).__name__})"
        if used and used != self.model:
            note = f"{note}; reranked by the fallback {used}"
        elif not used:
            note = f"{note}; first-stage order shown"
        ordered = top + [sec for sec, _ in secs if sec not in top]
        idx = [best[sec] for sec in ordered[:k]]
        return {"sections": ordered[:k], "chunk_idx": idx, "scores": [float(s[i]) for i in idx],
                "reranked": bool(top), "reranker": used, "note": note, "first_stage": s}
