"""Checker calibration without a new model (EXPERIMENT_LOG E12a).

    .venv/Scripts/python.exe scripts/run_checker_calibration.py

On the 150 human-labelled pairs (set 1: annotation/checker_set.jsonl + checker_gold.jsonl;
set 2: *_v2), compares rules for "supported" built from the stored DeBERTa score and the
share of sentence words found in the premise (lexical containment):
  nli        entail >= tau
  contain    overlap >= c
  nli|contain   entail >= tau OR overlap >= c   (near-verbatim sentences auto-pass)
Parameters are chosen on set 1 and tested on set 2 (the H4 protocol), and by 5-fold CV
repeated 20 times over all 150 pairs. Metric: balanced accuracy (supported vs unsupported).
Writes results/checker_calibration.json.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = 0.99658203125


def load(tag: str) -> pd.DataFrame:
    s = pd.read_json(ROOT / "annotation" / f"checker_set{tag}.jsonl", lines=True, dtype=str)
    g = pd.read_json(ROOT / "annotation" / f"checker_gold{tag}.jsonl", lines=True, dtype=str)
    d = s.merge(g[["pair_id", "gold_label"]], on="pair_id", validate="1:1")
    d["entail"] = d["checker_entail"].astype(float)
    d["y"] = (d["gold_label"] == "supported").astype(int)
    d["overlap"] = [overlap(a, b) for a, b in zip(d["sentence"], d["premise"])]
    d["set"] = tag or "_v1"
    return d


def overlap(sentence: str, premise: str) -> float:
    w = re.findall(r"[a-z0-9]+", sentence.lower())
    p = set(re.findall(r"[a-z0-9]+", premise.lower()))
    return sum(x in p for x in w) / max(1, len(w))


def ba(y, pred) -> float:
    y, pred = np.asarray(y), np.asarray(pred)
    tpr = (pred[y == 1] == 1).mean() if (y == 1).any() else np.nan
    tnr = (pred[y == 0] == 0).mean() if (y == 0).any() else np.nan
    return float(np.nanmean([tpr, tnr]))


TAUS = sorted(set([0.5, 0.9, 0.99, 0.995, T, 0.998, 0.999, 0.9995]))
CS = [0.8, 0.85, 0.9, 0.925, 0.95, 0.975, 1.01]  # 1.01 = never auto-pass


def rules():
    yield "nli", [(t, 1.01) for t in TAUS]
    yield "contain", [(1.01, c) for c in CS[:-1]]
    yield "nli|contain", [(t, c) for t in TAUS for c in CS]


def predict(d, t, c):
    return ((d["entail"] >= t) | (d["overlap"] >= c)).astype(int)


def best(d, grid):
    return max(grid, key=lambda tc: (ba(d["y"], predict(d, *tc)), -tc[0]))


def main() -> None:
    s1, s2 = load(""), load("_v2")
    both = pd.concat([s1, s2], ignore_index=True)
    out = {"n_set1": len(s1), "n_set2": len(s2), "pos_rate": [float(s1.y.mean()), float(s2.y.mean())], "rules": {}}
    print(f"set1 n {len(s1)} supported {s1.y.mean():.2f}; set2 n {len(s2)} supported {s2.y.mean():.2f}")
    print(f"baseline NLI@T: set1 BA {ba(s1.y, s1.entail >= T):.3f}  set2 BA {ba(s2.y, s2.entail >= T):.3f}")
    rng = np.random.default_rng(0)
    for name, grid in rules():
        t, c = best(s1, grid)
        test = ba(s2.y, predict(s2, t, c))
        cv = []
        for _ in range(20):
            folds = rng.permutation(len(both)) % 5
            pred = np.zeros(len(both), int)
            for f in range(5):
                tr, te = both[folds != f], both[folds == f]
                pred[folds == f] = predict(te, *best(tr, grid))
            cv.append(ba(both.y, pred))
        out["rules"][name] = {"chosen_on_set1": {"tau": t, "c": c}, "set1_BA": ba(s1.y, predict(s1, t, c)),
                              "set2_BA": test, "cv150_BA_mean": float(np.mean(cv)), "cv150_BA_sd": float(np.std(cv))}
        print(f"{name:12s} chosen tau {t:.6f} c {c:.3f} | set1 {ba(s1.y, predict(s1, t, c)):.3f}  set2 {test:.3f}"
              f"  | 5-fold CV over 150: {np.mean(cv):.3f} (sd {np.std(cv):.3f})")
    # how often are high-overlap sentences unsupported per the humans?
    for c in (0.9, 0.95):
        hi = both[both.overlap >= c]
        out[f"overlap>={c}"] = {"n": len(hi), "human_supported": float(hi.y.mean()) if len(hi) else None,
                                "nli_T_flagged": float((hi.entail < T).mean()) if len(hi) else None}
        print(f"overlap >= {c}: n {len(hi)}, humans say supported {hi.y.mean():.2f}, NLI@T flags {(hi.entail < T).mean():.2f}")
    (ROOT / "results" / "checker_calibration.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
