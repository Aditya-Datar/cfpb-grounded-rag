"""H1 supplementary analysis (Ishani). NOT part of the shared scripts; reads only their outputs.

1. Paired differences between every pair of retrievers (BM25, dense and hybrid for each model),
   report half, in-scope items, hit@5 and MRR. Same bootstrap as scripts/run_retrieval.py:
   10,000 percentile resamples over complaints, numpy default_rng(0), same item order, so the
   resamples are identical to the main script's. Self-check: reproduces gain_vs_bm25 in each JSON.
2. Hub chunk 12-1006-1006.34-c-4-i: how often each retriever puts it in its top 5 chunks.

Usage (repo root, venv active):  python ~/h1_supplement.py --tags mpnet bge e5 --out <json>
"""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

HUB = "12-1006-1006.34-c-4-i"
N_BOOT, SEED = 10000, 0


def diff_ci(a: np.ndarray, b: np.ndarray) -> dict:
    """a, b: gold-section ranks (inf = not found). Mean of a minus b, paired bootstrap 95% CI."""
    idx = np.random.default_rng(SEED).integers(0, len(a), (N_BOOT, len(a)))
    out = {}
    for name, d in [("hit@5", (a <= 5).astype(float) - (b <= 5)), ("mrr", 1 / a - 1 / b)]:
        bs = d[idx].mean(-1)
        lo, hi = float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))
        out[name] = {"mean": float(d.mean()), "ci95": [lo, hi], "excludes_zero": bool(lo > 0 or hi < 0)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="+", default=["mpnet", "bge", "e5"])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    root = Path.cwd()
    out = {"note": "SUPPLEMENTARY: computed by h1_supplement.py from the shared scripts' outputs, not by "
                   "scripts/run_retrieval.py. Differences are row minus column (a - b).",
           "bootstrap": f"{N_BOOT} percentile resamples over complaints, numpy default_rng({SEED})",
           "subset": "report half (metrics.half == 1), in-scope (gold_regulation != NONE)"}
    for corpus, sfx in [("with_fcra", ""), ("without_fcra", "_no_fcra")]:
        # ---- ranks of the gold section, one column per retriever
        merged = None
        for t in args.tags:
            r = pd.read_parquet(root / f"outputs/retrieval/ranks_{t}{sfx}.parquet")
            r = r.rename(columns={"rank_dense": f"dense_{t}", "rank_hybrid": f"hybrid_{t}", "rank_bm25": f"bm25@{t}"})
            merged = r if merged is None else merged.merge(
                r[["complaint_id", f"dense_{t}", f"hybrid_{t}", f"bm25@{t}"]], on="complaint_id", validate="1:1")
        first = merged.copy()  # keeps the row order of the first file, which is the main script's order
        bm_cols = [f"bm25@{t}" for t in args.tags]
        for c in bm_cols[1:]:  # BM25 is deterministic: must be identical in every run
            assert first[c].fillna(-1).equals(first[bm_cols[0]].fillna(-1)), f"BM25 ranks differ: {c}"
        first["bm25"] = first[bm_cols[0]]
        sel = first[(first["gold_regulation"] != "NONE") & (~first["dev_half"].astype(bool))]
        ret = ["bm25"] + [f"{k}_{t}" for t in args.tags for k in ("dense", "hybrid")]
        R = {n: sel[n].fillna(np.inf).to_numpy(dtype=float) for n in ret}

        # ---- self-check against the main script's paired gain over BM25
        for t in args.tags:
            js = json.loads((root / f"results/retrieval_{t}.json").read_text())[corpus]["report_half"]
            for k in ("dense", "hybrid"):
                mine = diff_ci(R[f"{k}_{t}"], R["bm25"])
                for m in ("hit@5", "mrr"):
                    ref = js[k]["gain_vs_bm25"][m]
                    assert np.isclose(mine[m]["mean"], ref["mean"]) and np.allclose(mine[m]["ci95"], ref["ci95"]), \
                        f"self-check failed {corpus} {k}_{t} {m}: {mine[m]} vs {ref}"

        pairs = {f"{a} - {b}": diff_ci(R[a], R[b]) for a, b in itertools.combinations(ret, 2)}

        # ---- hub chunk in the top 5 chunks (ranked.parquet holds the top 10 chunks per complaint)
        report_ids = set(sel["complaint_id"])
        all_ids = set(first["complaint_id"])
        hub = {}
        folders = {"bm25": f"bm25_{args.tags[0]}{sfx}"} | {
            f"{k}_{t}": f"{k}_{t}{sfx}" for t in args.tags for k in ("dense", "hybrid")}
        for n, folder in folders.items():
            rk = pd.read_parquet(root / f"outputs/retrieval/{folder}/ranked.parquet")
            hit_ids = set(rk[(rk["chunk_id"] == HUB) & (rk["rank"] <= 5)]["complaint_id"])
            hub[n] = {"report_half_in_scope": f"{len(hit_ids & report_ids)}/{len(report_ids)}",
                      "all_198": f"{len(hit_ids & all_ids)}/{len(all_ids)}"}
        out[corpus] = {"n_report_half": int(len(sel)), "paired_differences": pairs, "hub_chunk_top5": hub}

    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("self-checks passed; wrote", args.out)


if __name__ == "__main__":
    main()
