"""Retrieval improvements over the H1 winner (hybrid mpnet, alpha 0.8), chosen on the dev half only.

    python scripts/run_retrieval_improve.py [--rerankers cross-encoder/ms-marco-MiniLM-L-6-v2 BAAI/bge-reranker-base]

Post-H1 experiment (2026-11-18). Two additions, both pre-specified before any
report-half number was looked at:

1. Regulation prior. The DistilBERT product prediction maps to a usual regulation
   (config.PRODUCT_TO_REGULATION; V also admits the FCRA). Chunks from that
   regulation get +b on the min-max-normalised score. b = 0 is no prior; a large
   b is a hard filter.
2. Cross-encoder reranking. The top N chunks (after the prior) are re-scored by a
   cross-encoder reading complaint and chunk together; final score
   (1 - w) * minmax(first stage) + w * minmax(cross-encoder) + b * prior.

Selection: every (reranker, w, b) in the grid is scored by MRR on the dev half
(metrics.half == 0, in-scope); the best, ties broken toward the simpler setting,
is then reported ONCE on the report half with bootstrap CIs and the paired gain
over the unchanged hybrid baseline. Writes results/retrieval_improved.json and
outputs/retrieval/improved/ranked.parquet (top 10 chunks per complaint).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_retrieval import boot_ci, paired_gain  # noqa: E402

from cfpb.annotation import load_items  # noqa: E402
from cfpb.config import OUTPUT_DIR, PRODUCT_TO_REGULATION  # noqa: E402
from cfpb.pipeline.corpus import _regulation_of  # noqa: E402
from cfpb.retrieval.bm25 import DEFAULT_CHUNKS_PATH, BM25Retriever, load_chunks  # noqa: E402
from cfpb.retrieval.dense import DenseRetriever, HybridRetriever, minmax  # noqa: E402
from cfpb.retrieval.metrics import half, rank_of, retrieval_metrics  # noqa: E402

ALPHA = 0.8          # H1 winner (docs/tasks/results/ishani.md)
TOP_N = 50           # candidates re-scored by the cross-encoder
W_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]
B_GRID = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 2.0]   # 2.0 acts as a hard filter


def section_ranks(order: np.ndarray, chunks: list[dict], gold: str) -> int | None:
    seen, secs = set(), []
    for i in order:
        s = chunks[i]["section"]
        if s not in seen:
            seen.add(s)
            secs.append(s)
    return rank_of(gold, secs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rerankers", nargs="+",
                    default=["cross-encoder/ms-marco-MiniLM-L-6-v2", "BAAI/bge-reranker-base"])
    ap.add_argument("--n-boot", type=int, default=10000)
    args = ap.parse_args()

    items = load_items()[["complaint_id", "narrative_clean"]]
    gold = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str)
    df = items.merge(gold[["complaint_id", "gold_regulation", "gold_section"]], on="complaint_id", validate="1:1")
    df = df[df["gold_regulation"] != "NONE"].reset_index(drop=True)          # in-scope only
    dev = (df["complaint_id"].map(half) == 0).to_numpy()
    texts = df["narrative_clean"].tolist()
    print(f"{len(df)} in-scope complaints: dev {dev.sum()}, report {(~dev).sum()}", flush=True)

    chunks = load_chunks(DEFAULT_CHUNKS_PATH, include_fcra=True)
    reg = np.array([_regulation_of(c["section"]) for c in chunks])
    bm25, dense = BM25Retriever(chunks), DenseRetriever(chunks)
    S_d = dense.scores_batch(texts)
    S = np.vstack([minmax(HybridRetriever.combine(bm25.scores(t), d, ALPHA)) for t, d in zip(texts, S_d)])

    # Regulation prior from the classifier's product prediction.
    from cfpb.pipeline.core import load_classifier
    clf = load_classifier(require=True)
    prior = np.zeros_like(S)
    predicted = []
    for i, t in enumerate(texts):
        cand = PRODUCT_TO_REGULATION.get(clf.classify(t).product.label)
        allowed = {"V", "FCRA"} if cand == "V" else ({cand} if cand else set())
        predicted.append(cand)
        if allowed:
            prior[i] = np.isin(reg, list(allowed)).astype(float)
    prior_right = np.mean([p is not None and (p == g or (p == "V" and g == "FCRA"))
                           for p, g in zip(predicted, df["gold_regulation"])])
    print(f"classifier's regulation matches gold for {prior_right:.1%} of in-scope complaints", flush=True)

    # Cross-encoder scores for the top-N candidates of the widest pool (b = 0 and every b share most of it,
    # so score the union of candidates over the b grid).
    pools = [np.unique(np.concatenate([np.argsort(-(S[i] + b * prior[i]), kind="stable")[:TOP_N] for b in B_GRID]))
             for i in range(len(df))]
    from sentence_transformers import CrossEncoder
    ce_scores: dict[str, list[np.ndarray]] = {}
    for name in args.rerankers:
        ce = CrossEncoder(name, max_length=512)
        out = []
        for i, pool in enumerate(pools):
            out.append(np.asarray(ce.predict([(texts[i], chunks[j].get("embed_text") or chunks[j]["text"]) for j in pool],
                                             batch_size=32, show_progress_bar=False), dtype=float))
        ce_scores[name] = out
        print("scored", name, flush=True)

    def order_for(i: int, name: str | None, w: float, b: float) -> np.ndarray:
        first = S[i] + b * prior[i]
        order = np.argsort(-first, kind="stable")
        if name and w > 0:
            pool = order[:TOP_N]
            pos = {j: k for k, j in enumerate(pools[i])}
            ce = minmax(ce_scores[name][i][[pos[j] for j in pool]])
            comb = (1 - w) * minmax(S[i][pool]) + w * ce + b * prior[i][pool]
            order = np.concatenate([pool[np.argsort(-comb, kind="stable")], order[TOP_N:]])
        return order

    def ranks_for(name: str | None, w: float, b: float) -> list:
        return [section_ranks(order_for(i, name, w, b), chunks, df["gold_section"][i]) for i in range(len(df))]

    grid = []
    for b in B_GRID:
        grid.append((None, 0.0, b))
        for name in args.rerankers:
            for w in W_GRID[1:]:
                grid.append((name, w, b))
    tuning = []
    for name, w, b in grid:
        r = ranks_for(name, w, b)
        m = retrieval_metrics([x for x, d in zip(r, dev) if d])
        tuning.append({"reranker": name, "w": w, "b": b, "dev_mrr": m["mrr"], "dev_hit@1": m["hit@1"], "dev_hit@5": m["hit@5"]})
    # Best dev MRR; ties -> no reranker, then smaller w, then smaller b.
    best = max(tuning, key=lambda t: (round(t["dev_mrr"], 6), t["reranker"] is None, -t["w"], -t["b"]))
    print("chosen on dev:", best, flush=True)

    base = ranks_for(None, 0.0, 0.0)
    chosen = ranks_for(best["reranker"], best["w"], best["b"])
    prior_only = ranks_for(None, 0.0, max((t for t in tuning if t["reranker"] is None), key=lambda t: (round(t["dev_mrr"], 6), -t["b"]))["b"])

    def block(ranks, mask):
        sel = [x for x, m in zip(ranks, mask) if m]
        return retrieval_metrics(sel) | {"ci95": boot_ci(sel, args.n_boot)}

    rep = ~dev
    res = {"baseline": "hybrid mpnet alpha 0.8, with FCRA (H1 winner)", "top_n": TOP_N, "grid": {"w": W_GRID, "b": B_GRID,
           "rerankers": args.rerankers}, "selection": "max dev-half MRR; ties toward no reranker, smaller w, smaller b",
           "classifier_regulation_matches_gold": prior_right, "chosen": best, "dev_tuning": tuning,
           "report_half": {
               "baseline": block(base, rep),
               "chosen": block(chosen, rep) | {"gain_vs_baseline": paired_gain([x for x, m in zip(chosen, rep) if m],
                                                                                [x for x, m in zip(base, rep) if m], args.n_boot)},
               "prior_only": block(prior_only, rep) | {"gain_vs_baseline": paired_gain([x for x, m in zip(prior_only, rep) if m],
                                                                                       [x for x, m in zip(base, rep) if m], args.n_boot)}}}
    (ROOT / "results" / "retrieval_improved.json").write_text(json.dumps(res, indent=2), encoding="utf-8")

    rows = []
    for i in range(len(df)):
        order = order_for(i, best["reranker"], best["w"], best["b"])[:10]
        rows += [{"complaint_id": df["complaint_id"][i], "retriever": "improved", "corpus": "regulation+statute",
                  "rank": k + 1, "chunk_id": chunks[j]["chunk_id"], "section": chunks[j]["section"],
                  "score": float(10 - k)}  # rank-based score; the combined score is not on one scale across pools
                 for k, j in enumerate(order)]
    out = OUTPUT_DIR / "retrieval" / "improved"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out / "ranked.parquet", index=False)
    for k in ("baseline", "chosen", "prior_only"):
        m = res["report_half"][k]
        print(f"report half {k:10s} n={m['n']} hit@1={m['hit@1']:.3f} hit@5={m['hit@5']:.3f} mrr={m['mrr']:.3f}"
              + (f"  gain hit@5 {m['gain_vs_baseline']['hit@5']}" if "gain_vs_baseline" in m else ""))


if __name__ == "__main__":
    main()
