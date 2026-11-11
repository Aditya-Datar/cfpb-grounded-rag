"""Retriever comparison for H1: BM25 vs dense vs hybrid (docs/tasks/ishani.md).

    python scripts/run_retrieval.py                                   # mpnet, with and without FCRA
    python scripts/run_retrieval.py --model BAAI/bge-base-en-v1.5 \
        --query-prefix "Represent this sentence for searching relevant passages: " --tag bge
    python scripts/run_retrieval.py --chunks path/to/other_chunks.jsonl --tag chunks-v2   # chunking ablation

Gold: annotation/gold_final.jsonl, in-scope items only for ranking metrics. The hybrid
weight alpha is chosen on the dev half (metrics.half == 0, by MRR) and every retriever is
reported on the other half, so the hybrid is not scored on the items it was tuned on.
All-item numbers are included for reference only.

Writes (per corpus variant, name = <retriever>[_<tag>][_no_fcra]):
    outputs/retrieval/<name>/ranked.parquet   top 10 chunks per gold complaint, for
                                              run_pipeline_batch.py --retriever precomputed
    outputs/retrieval/features<_tag><_no_fcra>.parquet   per-complaint score features (H5)
    outputs/retrieval/ranks<_tag><_no_fcra>.parquet      gold-section rank per complaint and retriever
    results/retrieval_<tag>.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.annotation import load_items  # noqa: E402
from cfpb.config import OUTPUT_DIR, ROOT  # noqa: E402
from cfpb.retrieval.bm25 import DEFAULT_CHUNKS_PATH, BM25Retriever, load_chunks  # noqa: E402
from cfpb.retrieval.dense import DEFAULT_MODEL, DenseRetriever, HybridRetriever, rank_sections  # noqa: E402
from cfpb.retrieval.metrics import half, rank_of, retrieval_metrics  # noqa: E402

GOLD_PATH = ROOT / "annotation" / "gold_final.jsonl"
REGS = ["E", "F", "Z", "FCRA", "V"]
ALPHAS = [round(a, 2) for a in np.arange(0, 1.01, 0.1)]


def boot_ci(ranks: list, n_boot: int, seed: int = 0) -> dict:
    """95% bootstrap CIs over complaints for hit@1/5/10 and MRR."""
    r = np.array([np.inf if x is None else x for x in ranks], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(r), (n_boot, len(r)))
    out = {}
    for name, f in [("hit@1", lambda a: (a <= 1).mean(-1)), ("hit@5", lambda a: (a <= 5).mean(-1)),
                    ("hit@10", lambda a: (a <= 10).mean(-1)), ("mrr", lambda a: (1 / a).mean(-1))]:
        b = f(r[idx])
        out[name] = [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]
    return out


def paired_gain(ranks: list, base: list, n_boot: int, seed: int = 0) -> dict:
    """Mean per-complaint gain over the baseline, with a paired bootstrap 95% CI."""
    a = np.array([np.inf if x is None else x for x in ranks], dtype=float)
    b = np.array([np.inf if x is None else x for x in base], dtype=float)
    idx = np.random.default_rng(seed).integers(0, len(a), (n_boot, len(a)))
    out = {}
    for name, d in [("hit@5", (a <= 5).astype(float) - (b <= 5)), ("mrr", 1 / a - 1 / b)]:
        bs = d[idx].mean(-1)
        out[name] = {"mean": float(d.mean()), "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}
    return out


def ranks_for(chunks, S: np.ndarray, gold_sections) -> list:
    return [rank_of(g, [s for s, _ in rank_sections(chunks, row)]) if isinstance(g, str) else None
            for row, g in zip(S, gold_sections)]


def features(chunks, S: np.ndarray, prefix: str) -> dict:
    """Per-complaint confidence signals from a score matrix (used by run_abstention.py)."""
    feats = {f"{prefix}_top": [], f"{prefix}_margin": [], f"{prefix}_top_z": [], f"{prefix}_top5_mean": []}
    for row in S:
        secs = [v for _, v in rank_sections(chunks, row)[:5]]
        feats[f"{prefix}_top"].append(secs[0])
        feats[f"{prefix}_margin"].append(secs[0] - secs[1])
        feats[f"{prefix}_top_z"].append((secs[0] - row.mean()) / (row.std() or 1.0))
        feats[f"{prefix}_top5_mean"].append(float(np.mean(secs)))
    return feats


def write_ranked(chunks, S: np.ndarray, ids, retriever: str, corpus: str, name: str, k: int = 10) -> Path:
    rows = []
    for cid, row in zip(ids, S):
        for i, j in enumerate(np.argsort(-row, kind="stable")[:k]):
            rows.append({"complaint_id": cid, "retriever": retriever, "corpus": corpus, "rank": i + 1,
                         "chunk_id": chunks[j]["chunk_id"], "section": chunks[j]["section"], "score": float(row[j])})
    out = OUTPUT_DIR / "retrieval" / name / "ranked.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out, index=False)
    return out


def run(df: pd.DataFrame, args, include_fcra: bool) -> dict:
    chunks = load_chunks(args.chunks, include_fcra=include_fcra)
    corpus = "regulation+statute" if include_fcra else "regulation"
    suffix = (f"_{args.tag}" if args.tag else "") + ("" if include_fcra else "_no_fcra")
    queries = [args.query_prefix + q for q in df["narrative_clean"]]

    bm25 = BM25Retriever(chunks)
    S_bm25 = np.vstack([bm25.scores(q) for q in df["narrative_clean"]])
    dense = DenseRetriever(chunks, args.model, device=args.device, batch_size=args.batch_size)
    S_dense = dense.scores_batch(queries)

    gold = df["gold_section"].tolist()
    ins = (df["gold_regulation"] != "NONE").to_numpy()
    dev = (df["complaint_id"].map(half) == 0).to_numpy()

    # alpha on the dev half by MRR (ties -> smaller alpha, i.e. closer to BM25).
    tune = {}
    for a in ALPHAS:
        S = np.vstack([HybridRetriever.combine(b, d, a) for b, d in zip(S_bm25[ins & dev], S_dense[ins & dev])])
        tune[a] = retrieval_metrics(ranks_for(chunks, S, np.array(gold, dtype=object)[ins & dev]))["mrr"]
    alpha = max(ALPHAS, key=lambda a: (tune[a], -a))
    S_hyb = np.vstack([HybridRetriever.combine(b, d, alpha) for b, d in zip(S_bm25, S_dense)])

    mats = {"bm25": S_bm25, "dense": S_dense, "hybrid": S_hyb}
    ranks = {n: ranks_for(chunks, S, gold) for n, S in mats.items()}
    for n, S in mats.items():
        write_ranked(chunks, S, df["complaint_id"], n if n == "bm25" else f"{n}:{args.model}", corpus, n + suffix)

    feat = pd.DataFrame({"complaint_id": df["complaint_id"], "gold_regulation": df["gold_regulation"],
                         "dev_half": dev, "n_words": df["narrative_clean"].str.split().str.len(),
                         **features(chunks, S_bm25, "bm25"), **features(chunks, S_dense, "dense")})
    feat.to_parquet(OUTPUT_DIR / "retrieval" / f"features{suffix}.parquet", index=False)
    # Gold-section rank over the full ranking (NaN = NONE item), for paired comparisons across runs.
    pd.DataFrame({"complaint_id": df["complaint_id"], "gold_regulation": df["gold_regulation"], "dev_half": dev,
                  **{f"rank_{n}": [np.nan if r is None else r for r in ranks[n]] for n in mats}}
                 ).to_parquet(OUTPUT_DIR / "retrieval" / f"ranks{suffix}.parquet", index=False)

    def block(mask) -> dict:
        sel = lambda r: [x for x, m in zip(r, mask) if m]  # noqa: E731
        res = {}
        for n in mats:
            res[n] = retrieval_metrics(sel(ranks[n])) | {"ci95": boot_ci(sel(ranks[n]), args.n_boot)}
            if n != "bm25":
                res[n]["gain_vs_bm25"] = paired_gain(sel(ranks[n]), sel(ranks["bm25"]), args.n_boot)
        return res

    regs = df["gold_regulation"].to_numpy()
    out = {"n_chunks": len(chunks), "hybrid_alpha": alpha, "alpha_tuning_dev_mrr": tune,
           "report_half": block(ins & ~dev), "all_in_scope": block(ins),
           "by_regulation_all": {g: {n: retrieval_metrics([r for r, x in zip(ranks[n], regs) if x == g])
                                     for n in mats} for g in REGS if (regs == g).any()}}
    if not include_fcra:
        out["non_fcra_report_half"] = block(ins & ~dev & (regs != "FCRA"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--query-prefix", default="", help="instruction prefix some models need (e5, bge)")
    ap.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS_PATH)
    ap.add_argument("--tag", default="", help="suffix for output names, e.g. bge or chunks-v2")
    ap.add_argument("--device", default=None, help="cuda / cpu; default: auto")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--n-boot", type=int, default=10000)
    ap.add_argument("--fcra", choices=["both", "with", "without"], default="both")
    args = ap.parse_args()

    items = load_items()[["complaint_id", "narrative_clean"]]
    gold = pd.read_json(GOLD_PATH, lines=True, dtype=str)[["complaint_id", "gold_regulation", "gold_section"]]
    gold["gold_section"] = gold["gold_section"].where(gold["gold_regulation"] != "NONE")
    df = items.merge(gold, on="complaint_id", how="inner", validate="1:1")
    assert len(df) == len(gold), "every gold item needs a query narrative"

    results = {"dense_model": args.model, "query_prefix": args.query_prefix, "chunks": str(args.chunks),
               "hybrid": "alpha*minmax(dense) + (1-alpha)*minmax(bm25) per query; alpha by dev-half MRR",
               "split": "metrics.half(complaint_id)==0 is dev, ==1 is report"}
    if args.fcra in ("both", "with"):
        results["with_fcra"] = run(df, args, True)
    if args.fcra in ("both", "without"):
        results["without_fcra"] = run(df, args, False)
    out = ROOT / "results" / f"retrieval_{args.tag or 'dense_hybrid'}.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    for k in ("with_fcra", "without_fcra"):
        if k in results:
            print(k, "alpha =", results[k]["hybrid_alpha"])
            for n, m in results[k]["report_half"].items():
                print(f"  {n:7s} n={m['n']} hit@1={m['hit@1']:.3f} hit@5={m['hit@5']:.3f} "
                      f"hit@10={m['hit@10']:.3f} mrr={m['mrr']:.3f}")
    print("wrote", out)


if __name__ == "__main__":
    main()
