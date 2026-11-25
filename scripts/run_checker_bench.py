"""Benchmark grounding checkers on the 150 checker-label pairs (EXPERIMENT_LOG E12c).

    .venv/Scripts/python.exe scripts/run_checker_bench.py --kinds factcg minicheck

Same premises as the NLI checker (the corpus text of each pair's premise_chunk_ids).
For each checker: balanced accuracy at 0.5, AUROC, cutoff chosen on set 1 and tested on
set 2 (the H4 protocol), and 5-fold CV x20 over all 150 (cutoff tuned inside each fold);
DeBERTa NLI (stored scores) gets the same treatment. Also the paired set-2 bootstrap
difference in BA (checker at its set-1 cutoff minus NLI at T). Scores are cached in
outputs/checker_bench/<kind>.json. Writes results/checker_bench.json.
"""
import argparse
import ast
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from run_checker_calibration import ba, load  # noqa: E402

from cfpb.pipeline.corpus import load_corpus  # noqa: E402
from cfpb.verify.grounding import GroundingVerifier  # noqa: E402

T = 0.99658203125
CACHE = ROOT / "outputs" / "checker_bench"


def ids(x):
    return list(x) if not isinstance(x, str) else ast.literal_eval(x)


def best_cut(y, p):
    cands = np.unique(np.concatenate([p, [0.5, T]]))
    return float(max(cands, key=lambda t: (ba(y, (p >= t).astype(int)), -abs(t - 0.5))))


def evaluate(both, s1, s2, col, rng):
    t = best_cut(s1.y.to_numpy(), s1[col].to_numpy())
    cv = []
    for _ in range(20):
        folds = rng.permutation(len(both)) % 5
        pred = np.zeros(len(both), int)
        for f in range(5):
            tr, te = both[folds != f], both[folds == f]
            pred[folds == f] = (te[col].to_numpy() >= best_cut(tr.y.to_numpy(), tr[col].to_numpy())).astype(int)
        cv.append(ba(both.y, pred))
    return {"BA@0.5_set1": ba(s1.y, s1[col] >= 0.5), "BA@0.5_set2": ba(s2.y, s2[col] >= 0.5),
            "AUROC_set1": float(roc_auc_score(s1.y, s1[col])), "AUROC_set2": float(roc_auc_score(s2.y, s2[col])),
            "cut_set1": t, "BA_set1_at_cut": ba(s1.y, s1[col] >= t), "BA_set2_at_cut": ba(s2.y, s2[col] >= t),
            "unsupported_recall_set2_at_cut": float((s2[col][s2.y == 0] < t).mean()),
            "cv150_BA_mean": float(np.mean(cv)), "cv150_BA_sd": float(np.std(cv))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kinds", nargs="+", default=["factcg", "minicheck"])
    ap.add_argument("--with-ultra", action="store_true", help="also score mean(checker, Ultra judge)")
    ap.add_argument("--out", default="results/checker_bench.json")
    args = ap.parse_args()
    s1, s2 = load(""), load("_v2")
    both = pd.concat([s1, s2], ignore_index=True)
    corpus = load_corpus([str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")])
    CACHE.mkdir(parents=True, exist_ok=True)
    for kind in args.kinds:
        f = CACHE / f"{kind}.json"
        cache = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        v = GroundingVerifier(kind)
        for n, r in enumerate(both.itertuples()):
            if r.pair_id not in cache:
                cache[r.pair_id] = v.score([corpus.get(c).text for c in ids(r.premise_chunk_ids)], r.sentence)[0]
                if n % 10 == 0:
                    f.write_text(json.dumps(cache), encoding="utf-8")
                    print(f"{kind}: {len(cache)}/{len(both)}", flush=True)
        f.write_text(json.dumps(cache), encoding="utf-8")
        for d in (both, s1, s2):
            d[kind] = d["pair_id"].map(cache)
    rng = np.random.default_rng(0)
    out = {"n": [len(s1), len(s2)], "checkers": {"nli": evaluate(both, s1, s2, "entail", rng)}}
    for kind in args.kinds:
        out["checkers"][kind] = evaluate(both, s1, s2, kind, rng)
        t = out["checkers"][kind]["cut_set1"]
        a = (s2[kind].to_numpy() >= t).astype(int)
        b = (s2["entail"].to_numpy() >= T).astype(int)
        y = s2.y.to_numpy()
        boots = []
        for _ in range(10000):
            i = rng.integers(0, len(y), len(y))
            boots.append(ba(y[i], a[i]) - ba(y[i], b[i]))
        out["checkers"][kind]["set2_BA_minus_NLI_T"] = {"diff": ba(y, a) - ba(y, b),
                                                          "ci95": [float(np.percentile(boots, 2.5)),
                                                                   float(np.percentile(boots, 97.5))]}
    # pairing with the Ultra judge (E12b/E15): mean(checker, Ultra), against the current mean(DeBERTa, Ultra)
    if args.with_ultra:
        ult = pd.concat([pd.read_parquet(ROOT / "outputs" / f"checker_scored{t}.parquet") for t in ("_v1", "_v2")])
        ult = dict(zip(ult.pair_id, ult.ultra))
        for d in (both, s1, s2):
            d["ultra"] = d["pair_id"].map(ult)
            d["nli+ultra"] = (d["entail"] + d["ultra"]) / 2
        out["checkers"]["nli+ultra"] = evaluate(both, s1, s2, "nli+ultra", rng)
        ref_t = out["checkers"]["nli+ultra"]["cut_set1"]
        for kind in args.kinds:
            col = f"{kind}+ultra"
            for d in (both, s1, s2):
                d[col] = (d[kind] + d["ultra"]) / 2
            m = out["checkers"][col] = evaluate(both, s1, s2, col, rng)
            a = (s2[col].to_numpy() >= m["cut_set1"]).astype(int)
            b = (s2["nli+ultra"].to_numpy() >= ref_t).astype(int)
            y = s2.y.to_numpy()
            boots = []
            for _ in range(10000):
                i = rng.integers(0, len(y), len(y))
                boots.append(ba(y[i], a[i]) - ba(y[i], b[i]))
            m["set2_BA_minus_nli+ultra"] = {"diff": ba(y, a) - ba(y, b),
                                            "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]}
    # simple ensemble: mean of the available probabilities, cutoff tuned the same way
    if len(args.kinds) > 1:
        for d in (both, s1, s2):
            d["mean_new"] = d[args.kinds].mean(axis=1)
        out["checkers"]["mean(" + "+".join(args.kinds) + ")"] = evaluate(both, s1, s2, "mean_new", rng)
    (ROOT / args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k, m in out["checkers"].items():
        extra = m.get("set2_BA_minus_NLI_T") or m.get("set2_BA_minus_nli+ultra")
        print(f"{k:28s} AUROC {m['AUROC_set1']:.3f}/{m['AUROC_set2']:.3f}  BA@0.5 {m['BA@0.5_set1']:.3f}/{m['BA@0.5_set2']:.3f}"
              f"  cut {m['cut_set1']:.4f} -> set2 BA {m['BA_set2_at_cut']:.3f} (unsup recall {m['unsupported_recall_set2_at_cut']:.2f})"
              f"  CV150 {m['cv150_BA_mean']:.3f}" + (f"  vs {'DeBERTa+Ultra' if k.endswith('+ultra') else 'NLI@T'} {extra['diff']:+.3f} [{extra['ci95'][0]:+.3f}, {extra['ci95'][1]:+.3f}]" if extra else ""))


if __name__ == "__main__":
    main()
