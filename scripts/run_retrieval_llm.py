"""Retrieval v2: a large retrieval embedder plus LLM listwise reranking, chosen on the dev half only.

    python scripts/run_retrieval_llm.py

Post-H1 experiment (2026-11-19), following run_retrieval_improve.py. Components:

1. First stage. Dense scores from `nvidia/nemotron-3.5-embed-8b` (NVIDIA API,
   input_type query/passage) or from mpnet (H1), each optionally fused with BM25
   (alpha), plus the classifier's regulation prior (+b, as in
   run_retrieval_improve.py).
2. LLM listwise reranking (RankGPT-style, Sun et al. 2023). The top K sections of
   the first stage are shown to an LLM with their citation, heading and the best
   matching passage; it returns the five that most directly govern the complaint,
   best first. Final ranking: the LLM's five, then the rest in first-stage order.

Selection (dev half only, metrics.half == 0): the first stage by dev MRR over
the embedder x alpha x b grid; then rerank K in {0, 10, 20, 30} by dev MRR on top
of it (ties -> smaller K). The chosen pipeline is reported ONCE on the report
half against the H1 hybrid baseline and the 2026-11-19 prior-only result, with
paired bootstrap CIs. Every API response is cached under
outputs/retrieval/llm_cache, so reruns are free.

Writes results/retrieval_llm.json and outputs/retrieval/llm/ranked.parquet.
"""
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_retrieval import boot_ci, paired_gain  # noqa: E402

from cfpb.annotation import load_items  # noqa: E402
from cfpb.config import OUTPUT_DIR, PRODUCT_TO_REGULATION  # noqa: E402
from cfpb.generate.nemotron import api_key  # noqa: E402
from cfpb.pipeline.corpus import _regulation_of  # noqa: E402
from cfpb.retrieval.bm25 import DEFAULT_CHUNKS_PATH, BM25Retriever, load_chunks  # noqa: E402
from cfpb.retrieval.dense import DenseRetriever, HybridRetriever, minmax  # noqa: E402
from cfpb.retrieval.metrics import half, rank_of, retrieval_metrics  # noqa: E402

EMBED_MODEL = "nvidia/nemotron-3.5-embed-8b"
RERANK_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
BASE = "https://integrate.api.nvidia.com/v1"
CACHE = OUTPUT_DIR / "retrieval" / "llm_cache"
ALPHAS = [1.0, 0.9, 0.8, 0.7, 0.5]
B_GRID = [0.0, 0.1, 0.2, 0.3, 0.5]
K_GRID = [0, 10, 20, 30]
MODES = ["nothink", "think32k"]
N_BOOT = 10000

RERANK_PROMPT = """You are a compliance analyst at a US financial company. A consumer complaint is below, followed by candidate sections of federal consumer-finance law: Regulation E (12 CFR 1005, electronic fund transfers), Regulation Z (12 CFR 1026, truth in lending), Regulation V (12 CFR 1022, fair credit reporting), Regulation F (12 CFR 1006, debt collection) and the Fair Credit Reporting Act (15 U.S.C. 1681 et seq.).

Pick the five candidate sections that most directly govern the company's obligations on the complaint's main issue, best first. Prefer the operative section that sets the duty (for example, error resolution or dispute procedures) over definitions, scope or general provisions.

Complaint:
{complaint}

Candidate sections:
{candidates}

Answer with JSON only, for example {{"ranking": ["C3", "C1", "C7", "C2", "C5"]}}."""

_session = requests.Session()


def _post(path: str, body: dict, timeout: int = 300, retries: int = 8) -> dict:
    key = hashlib.sha1(json.dumps([path, body], sort_keys=True).encode()).hexdigest()
    f = CACHE / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
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


def embed(texts: list[str], input_type: str) -> np.ndarray:
    # One text per request: the hosted endpoint returns HTTP 500 for batches of longer passages (2026-11-19).
    # Long inputs also fail intermittently despite truncate=END, so fall back to shorter word cuts.
    def one(t):
        for n in (1000, 400, 200):
            try:
                return _post("/embeddings", {"model": EMBED_MODEL, "input": [t if len(t.split()) <= n else " ".join(t.split()[:n])],
                                             "input_type": input_type, "encoding_format": "float",
                                             "truncate": "END"}, retries=4)["data"][0]["embedding"]
            except RuntimeError:
                print(f"  embedding failed at {n} words; retrying shorter", flush=True)
        raise RuntimeError("embedding failed at every length")
    with ThreadPoolExecutor(8) as ex:
        out = list(ex.map(one, texts))
    print(f"  embedded {len(texts)} {input_type}", flush=True)
    e = np.asarray(out, dtype="float32")
    return e / np.linalg.norm(e, axis=1, keepdims=True)


def section_order(order: np.ndarray, chunks: list[dict]) -> list[tuple[str, int]]:
    """Sections in order of their best chunk, with that chunk's index."""
    seen, out = set(), []
    for i in order:
        s = chunks[i]["section"]
        if s not in seen:
            seen.add(s)
            out.append((s, int(i)))
    return out


def label(chunk: dict) -> str:
    sec = chunk["section"]
    return f"15 U.S.C. {sec}" if chunk.get("regulation") == "FCRA" else f"12 CFR {sec}"


def llm_rerank(complaint: str, cands: list[tuple[str, int]], chunks: list[dict], mode: str) -> list[str]:
    lines = []
    for n, (sec, j) in enumerate(cands, 1):
        words = (chunks[j]["text"] or "").split()
        lines.append(f"C{n}. {label(chunks[j])}, {chunks[j]['heading']}\n   Passage: {' '.join(words[:90])}")
    text = " ".join(complaint.split()[:900])
    body = {"model": RERANK_MODEL, "temperature": 0,
            "messages": [{"role": "user", "content": RERANK_PROMPT.format(complaint=text, candidates="\n".join(lines))}]}
    # The first run (max_tokens 8192, thinking on) spent the whole budget reasoning on 327 of 381 calls and
    # returned no answer, so thinking is either off or given 32k tokens; the mode is chosen on dev.
    if mode == "nothink":
        body |= {"max_tokens": 1024, "chat_template_kwargs": {"enable_thinking": False}}
    else:
        body |= {"max_tokens": 32768}
    msg = _post("/chat/completions", body)["choices"][0]["message"]
    content = re.sub(r"<think>.*?</think>", "", msg.get("content") or "", flags=re.S)
    ids = re.findall(r"C(\d+)", content.split("ranking")[-1] if "ranking" in content else content)
    picked = []
    for x in ids:
        k = int(x) - 1
        if 0 <= k < len(cands) and cands[k][0] not in picked:
            picked.append(cands[k][0])
    return picked[:5]


def main() -> None:
    items = load_items()[["complaint_id", "narrative_clean"]]
    gold = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str)
    df = items.merge(gold[["complaint_id", "gold_regulation", "gold_section"]], on="complaint_id", validate="1:1")
    df = df[df["gold_regulation"] != "NONE"].reset_index(drop=True)
    dev = (df["complaint_id"].map(half) == 0).to_numpy()
    texts = df["narrative_clean"].tolist()
    print(f"{len(df)} in-scope: dev {dev.sum()}, report {(~dev).sum()}", flush=True)

    chunks = load_chunks(DEFAULT_CHUNKS_PATH, include_fcra=True)
    reg = np.array([_regulation_of(c["section"]) for c in chunks])
    bm25 = BM25Retriever(chunks)
    B = np.vstack([bm25.scores(t) for t in texts])
    dense = {"mpnet": DenseRetriever(chunks).scores_batch(texts)}
    E_c = embed([c.get("embed_text") or c["text"] for c in chunks], "passage")
    E_q = embed(texts, "query")
    dense["nv-embed-8b"] = (E_q @ E_c.T).astype(float)

    from cfpb.pipeline.core import load_classifier
    clf = load_classifier(require=True)
    prior = np.zeros_like(B)
    for i, t in enumerate(texts):
        cand = PRODUCT_TO_REGULATION.get(clf.classify(t).product.label)
        allowed = {"V", "FCRA"} if cand == "V" else ({cand} if cand else set())
        if allowed:
            prior[i] = np.isin(reg, list(allowed)).astype(float)

    def first_stage(emb: str, alpha: float, b: float) -> np.ndarray:
        return np.vstack([HybridRetriever.combine(B[i], dense[emb][i], alpha) for i in range(len(df))]) + b * prior

    def ranks(S: np.ndarray, reranked: list[list[str]] | None = None) -> list:
        out = []
        for i in range(len(df)):
            secs = [s for s, _ in section_order(np.argsort(-S[i], kind="stable"), chunks)]
            if reranked is not None:
                top = reranked[i]
                secs = top + [s for s in secs if s not in top]
            out.append(rank_of(df["gold_section"][i], secs))
        return out

    def dev_metrics(r):
        return retrieval_metrics([x for x, d in zip(r, dev) if d])

    # Stage 1 selection.
    tuning = []
    for emb in dense:
        for a in ALPHAS:
            for b in B_GRID:
                m = dev_metrics(ranks(first_stage(emb, a, b)))
                tuning.append({"embedder": emb, "alpha": a, "b": b, "dev_mrr": m["mrr"], "dev_hit@1": m["hit@1"],
                               "dev_hit@5": m["hit@5"], "dev_hit@10": m["hit@10"], "dev_hit@30": None})
    best1 = max(tuning, key=lambda t: (round(t["dev_mrr"], 6), -t["b"], t["alpha"]))
    print("stage 1 chosen on dev:", best1, flush=True)
    S1 = first_stage(best1["embedder"], best1["alpha"], best1["b"])

    # Stage 2: LLM rerank of the top K sections (all complaints, K = 30 superset is NOT reused: each K is its own call).
    reranked: dict[tuple, list[list[str]]] = {}
    for mode in MODES:
        for K in K_GRID[1:]:
            def one(i, K=K, mode=mode):
                cands = section_order(np.argsort(-S1[i], kind="stable"), chunks)[:K]
                return llm_rerank(texts[i], cands, chunks, mode)
            with ThreadPoolExecutor(3) as ex:
                reranked[(mode, K)] = list(ex.map(one, range(len(df))))
            print(f"reranked {mode} K={K}; empty answers: {sum(not r for r in reranked[(mode, K)])}", flush=True)
    m0 = dev_metrics(ranks(S1))
    rr_tuning = [{"mode": None, "K": 0, "dev_mrr": m0["mrr"], "dev_hit@1": m0["hit@1"], "dev_hit@5": m0["hit@5"]}]
    for (mode, K), rr in reranked.items():
        m = dev_metrics(ranks(S1, rr))
        rr_tuning.append({"mode": mode, "K": K, "dev_mrr": m["mrr"], "dev_hit@1": m["hit@1"], "dev_hit@5": m["hit@5"],
                          "empty_answers": sum(not r for r in rr)})
    # Ties -> no rerank, then thinking off (cheaper), then smaller K.
    best2 = max(rr_tuning, key=lambda t: (round(t["dev_mrr"], 6), t["K"] == 0, t["mode"] == "nothink", -t["K"]))
    print("rerank chosen on dev:", best2, flush=True)

    base = ranks(first_stage("mpnet", 0.8, 0.0))
    prior_only = ranks(first_stage("mpnet", 0.8, 0.3))
    stage1 = ranks(S1)
    final = ranks(S1, reranked.get((best2["mode"], best2["K"])))
    rep = ~dev

    def sel(r):
        return [x for x, m in zip(r, rep) if m]

    def block(r, vs=None):
        out = retrieval_metrics(sel(r)) | {"ci95": boot_ci(sel(r), N_BOOT)}
        if vs is not None:
            out["gain_vs_h1_hybrid"] = paired_gain(sel(r), sel(base), N_BOOT)
            out["gain_vs_prior_only"] = paired_gain(sel(r), sel(prior_only), N_BOOT)
        return out

    res = {
        "embedder": EMBED_MODEL, "reranker": RERANK_MODEL, "rerank_prompt": RERANK_PROMPT,
        "selection": "stage 1 by max dev MRR (ties: smaller b, larger alpha); then rerank mode and K by max dev MRR (ties: no rerank, thinking off, smaller K)",
        "stage1_chosen": best1, "rerank_chosen": best2, "dev_stage1_tuning": tuning, "dev_rerank_tuning": rr_tuning,
        "report_half": {"h1_hybrid_mpnet": block(base), "prior_only_2026_11_19": block(prior_only, True),
                        "stage1_chosen": block(stage1, True), "final": block(final, True)},
        "per_regulation_report_half": {},
    }
    for g in sorted(df["gold_regulation"].unique()):
        mask = rep & (df["gold_regulation"] == g).to_numpy()
        res["per_regulation_report_half"][g] = {
            "n": int(mask.sum()),
            "h1_hybrid_hit@5": retrieval_metrics([x for x, m in zip(base, mask) if m])["hit@5"],
            "final_hit@1": retrieval_metrics([x for x, m in zip(final, mask) if m])["hit@1"],
            "final_hit@5": retrieval_metrics([x for x, m in zip(final, mask) if m])["hit@5"]}
    (ROOT / "results" / "retrieval_llm.json").write_text(json.dumps(res, indent=2), encoding="utf-8")

    rows = []
    for i in range(len(df)):
        secs = section_order(np.argsort(-S1[i], kind="stable"), chunks)
        top = reranked.get((best2["mode"], best2["K"]), [[]] * len(df))[i]
        best_chunk = dict(secs)
        ordered = top + [s for s, _ in secs if s not in top]
        rows += [{"complaint_id": df["complaint_id"][i], "retriever": "nv-embed-8b+bm25+prior+llm-rerank",
                  "corpus": "regulation+statute", "rank": k + 1, "section": s, "score": float(10 - k),
                  "chunk_id": chunks[best_chunk[s]]["chunk_id"]} for k, s in enumerate(ordered[:10])]
    out = OUTPUT_DIR / "retrieval" / "llm"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out / "ranked.parquet", index=False)
    for k, m in res["report_half"].items():
        print(f"report {k:24s} n={m['n']} hit@1={m['hit@1']:.3f} hit@5={m['hit@5']:.3f} hit@10={m['hit@10']:.3f} "
              f"mrr={m['mrr']:.3f}" + (f"  gain vs H1 hit@5 {m['gain_vs_h1_hybrid']['hit@5']}" if "gain_vs_h1_hybrid" in m else ""))


if __name__ == "__main__":
    main()
