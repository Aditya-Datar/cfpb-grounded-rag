"""Does a bigger reranker pick the governing section better? Dev half only.

    .venv/Scripts/python.exe scripts/run_reranker_swap.py [--half 0] [--models lightning mistral super ultra kimi minimax]

Same first stage (Nemotron embed 8B + BM25, alpha 0.8, regulation prior b 0.2 from the
classifier), same K = 10 candidate sections, same RERANK_PROMPT as the shipped reranker
(src/cfpb/retrieval/llm_rerank.py). Only the reranking model changes:
  lightning  nvidia/nemotron-3.5-lightning-30b-a3b   (shipped; thinking, 32k tokens)
  mistral    mistralai/mistral-large-4-1t-a52b       (reasoning_effort low; default effort ~3 min/call)
  super      nvidia/nemotron-3.5-super-vl-120b-a12b  (thinking, 32k tokens; also the drafter)
Scored by hit@1 / hit@3 / hit@5 / MRR of the gold section over in-scope complaints of
the chosen half (half 0 = dev, as in scripts/run_retrieval_llm.py). Responses are cached.
Writes results/reranker_swap_half{H}.json.
"""
import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cfpb.annotation import load_items  # noqa: E402
from cfpb.retrieval.llm_rerank import RERANK_K, RERANK_PROMPT, LLMRerankRetriever, _label, post, section_order  # noqa: E402
from cfpb.retrieval.metrics import half  # noqa: E402

MODELS = {
    "lightning": ("nvidia/nemotron-3.5-lightning-30b-a3b", {"max_tokens": 32768}),
    "mistral": ("mistralai/mistral-large-4-1t-a52b", {"max_tokens": 4096, "reasoning_effort": "low"}),
    "super": ("nvidia/nemotron-3.5-super-vl-120b-a12b", {"max_tokens": 32768}),
    "ultra": ("nvidia/nemotron-3-ultra-550b-a55b", {"max_tokens": 32768}),
    "kimi": ("moonshotai/kimi-k3.1-pro", {"max_tokens": 32768}),
    "minimax": ("minimaxai/minimax-m3.1-flash", {"max_tokens": 32768}),
    # Evaluation only: GPT through the Codex CLI on Aditya's ChatGPT Edu login (cfpb.verify.codex_client).
    "gpt": ("codex:gpt-5.6-sol", {}),
}
from cfpb.retrieval.llm_rerank import CODEX_CACHE, codex_post  # noqa: E402,F401  (moved to the module 2026-11-23)


# Variant "rubric": the team's section-choice conventions (annotation/ANNOTATION_GUIDE.md and the
# regulation-annotator skill), stated as guidance. The gold labels were made with these same conventions,
# so a gain from this variant partly reflects matching the labelling rubric; disclose that if used.
from cfpb.retrieval.llm_rerank import RUBRIC  # noqa: E402,F401  (moved to the module 2026-11-22; same text)


def rerank(model: str, extra: dict, complaint: str, cands, chunks, words_per: int = 90, rubric: bool = False) -> list[str]:
    lines = []
    for n, (sec, j) in enumerate(cands, 1):
        words = (chunks[j]["text"] or "").split()
        lines.append(f"C{n}. {_label(chunks[j])}, {chunks[j]['heading']}\n   Passage: {' '.join(words[:words_per])}")
    text = " ".join(complaint.split()[:900])
    prompt = RERANK_PROMPT.format(complaint=text, candidates="\n".join(lines))
    if rubric:
        prompt = prompt.replace("\n\nComplaint:\n", "\n" + RUBRIC + "\nComplaint:\n", 1)
    body = {"model": model, "temperature": 0, **extra, "messages": [{"role": "user", "content": prompt}]}
    try:
        if model.startswith("codex:"):
            msg = codex_post(model, prompt)["choices"][0]["message"]
        else:
            msg = post("/chat/completions", body)["choices"][0]["message"]
    except Exception:
        return []
    content = re.sub(r"<think>.*?</think>", "", msg.get("content") or "", flags=re.S)
    ids = re.findall(r"C(\d+)", content.split("ranking")[-1] if "ranking" in content else content)
    picked = []
    for x in ids:
        k = int(x) - 1
        if 0 <= k < len(cands) and cands[k][0] not in picked:
            picked.append(cands[k][0])
    return picked[:5]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--half", type=int, default=0)
    ap.add_argument("--models", nargs="+", default=list(MODELS))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--K", type=int, default=RERANK_K)
    ap.add_argument("--words", type=int, default=90)
    ap.add_argument("--rubric", action="store_true")
    args = ap.parse_args()
    tag = "" if (args.K, args.words, args.rubric) == (RERANK_K, 90, False) else         f"|K{args.K}-w{args.words}" + ("-rubric" if args.rubric else "")

    from cfpb.config import PRODUCT_TO_REGULATION
    from cfpb.pipeline.core import load_classifier
    from cfpb.retrieval.bm25 import DEFAULT_CHUNKS_PATH, BM25Retriever, load_chunks

    chunks = load_chunks(DEFAULT_CHUNKS_PATH, include_fcra=True)
    bm25 = BM25Retriever(chunks)
    items = load_items()[["complaint_id", "narrative_clean"]]
    gold = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str)
    df = items.merge(gold[["complaint_id", "gold_regulation", "gold_section"]], on="complaint_id", validate="1:1")
    df = df[(df["gold_regulation"] != "NONE") & (df["complaint_id"].map(half) == args.half)].reset_index(drop=True)
    clf = load_classifier(require=True)
    r = LLMRerankRetriever(chunks, bm25)
    cands = []
    for t in df["narrative_clean"]:
        s = r.first_stage(t, PRODUCT_TO_REGULATION.get(clf.classify(t).product.label))
        cands.append(section_order(np.argsort(-s, kind="stable"), chunks))
    print(f"{len(df)} in-scope complaints in half {args.half}", flush=True)

    out = {"half": args.half, "n": len(df), "K": RERANK_K, "prompt": "RERANK_PROMPT (unchanged)", "models": {}}
    for name in args.models:
        model, extra = MODELS[name]

        def one(i):
            return rerank(model, extra, df["narrative_clean"][i], cands[i][:args.K], chunks, args.words, args.rubric)

        with ThreadPoolExecutor(args.workers) as ex:
            tops = list(ex.map(one, range(len(df))))
        ranks = []
        for i, top in enumerate(tops):
            order = top + [s for s, _ in cands[i] if s not in top]
            g = df["gold_section"][i]
            ranks.append(order.index(g) + 1 if g in order else None)
        m = {f"hit@{k}": float(np.mean([x is not None and x <= k for x in ranks])) for k in (1, 3, 5)}
        m["mrr"] = float(np.mean([1 / x if x else 0 for x in ranks]))
        m["empty_answers"] = sum(not t for t in tops)
        m["model"], m["settings"] = model, extra
        m["K"], m["words_per_passage"], m["rubric"] = args.K, args.words, args.rubric
        out["models"][name + tag] = m
        print(f"{name + tag:24s} {model:42s} hit@1 {m['hit@1']:.3f} hit@3 {m['hit@3']:.3f} hit@5 {m['hit@5']:.3f} "
              f"MRR {m['mrr']:.3f} empty {m['empty_answers']}", flush=True)
    fs = [next((k + 1 for k, (s, _) in enumerate(c) if s == g), None) for c, g in zip(cands, df["gold_section"])]
    out["first_stage_hit@1"] = float(np.mean([x == 1 for x in fs]))
    out["first_stage_hit@10"] = float(np.mean([x is not None and x <= 10 for x in fs]))
    path = ROOT / "results" / f"reranker_swap_half{args.half}.json"
    if path.exists():  # merge with models scored by earlier runs
        old = json.loads(path.read_text(encoding="utf-8"))
        out["models"] = {**old.get("models", {}), **out["models"]}
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
