"""No-rule (NONE) detection for H5 (docs/tasks/gagan.md).

    python scripts/run_retrieval.py                       # first: writes the feature files
    python scripts/run_abstention.py [--features outputs/retrieval/features.parquet] [--tag mpnet]

Positive class = gold_regulation == NONE (the complaint has no governing section in
the corpus, so the pipeline should refer it instead of drafting). Every signal is
oriented so that higher means "more likely NONE" (low retrieval confidence).

Single signals: each feature column. Combined: logistic regression on all features,
standardised, fit on the dev half (metrics.half == 0) and scored on the report half;
also 5-fold stratified CV repeated 20 times over all items, for a less noisy AUROC.
Thresholds for P/R/F1 are tuned on the dev half (max F1) and applied to the report half.
Baseline to beat: top BM25 score, AUROC 0.43 (CLAUDE_PROGRESS.md, BM25 entry).

Writes results/abstention<_tag>.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.config import OUTPUT_DIR, ROOT  # noqa: E402
from cfpb.retrieval.metrics import prf  # noqa: E402

# Higher raw value = more confident retrieval, so NONE-score = -value. n_words is
# left unsigned: the regression learns its direction; as a single signal it is reported both ways.
CONFIDENCE = ["bm25_top", "bm25_margin", "bm25_top_z", "bm25_top5_mean",
              "dense_top", "dense_margin", "dense_top_z", "dense_top5_mean"]


def auroc_ci(y: np.ndarray, s: np.ndarray, n_boot: int, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            boots.append(roc_auc_score(y[i], s[i]))
    return {"auroc": float(roc_auc_score(y, s)),
            "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]}


def best_threshold(y: np.ndarray, s: np.ndarray) -> float:
    """Threshold on s (predict NONE when s >= t) maximising F1."""
    return max(np.unique(s), key=lambda t: prf(y, s >= t)["f1"])


def evaluate(y, s, dev, n_boot) -> dict:
    t = best_threshold(y[dev], s[dev])
    return {"report_half": auroc_ci(y[~dev], s[~dev], n_boot), "all": auroc_ci(y, s, n_boot),
            "threshold_tuned_on_dev": float(t),
            "prf_dev": prf(y[dev], s[dev] >= t), "prf_report": prf(y[~dev], s[~dev] >= t)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", type=Path, default=OUTPUT_DIR / "retrieval" / "features.parquet")
    ap.add_argument("--tag", default="")
    ap.add_argument("--n-boot", type=int, default=2000)
    args = ap.parse_args()

    df = pd.read_parquet(args.features)
    y = (df["gold_regulation"] == "NONE").to_numpy()
    dev = df["dev_half"].to_numpy().astype(bool)
    cols = [c for c in CONFIDENCE if c in df] + ["n_words"]
    X = df[cols].to_numpy(dtype=float)

    singles = {c: evaluate(y, -df[c].to_numpy(dtype=float), dev, args.n_boot) for c in cols if c != "n_words"}
    singles["n_words (longer = NONE)"] = evaluate(y, df["n_words"].to_numpy(dtype=float), dev, args.n_boot)
    singles["n_words (shorter = NONE)"] = evaluate(y, -df["n_words"].to_numpy(dtype=float), dev, args.n_boot)

    model = lambda: make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000))  # noqa: E731
    m = model().fit(X[dev], y[dev])
    s_rep = m.predict_proba(X)[:, 1]
    logreg = evaluate(y, s_rep, dev, args.n_boot)
    logreg["note"] = "fit on dev half; 'all' and prf_dev include the training items, use report_half"
    logreg["coefficients_standardised"] = dict(zip(cols, map(float, m[-1].coef_[0])))

    cv = []
    for tr, te in RepeatedStratifiedKFold(n_splits=5, n_repeats=20, random_state=0).split(X, y):
        cv.append(roc_auc_score(y[te], model().fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]))
    logreg["cv_5fold_x20_auroc"] = {"mean": float(np.mean(cv)), "sd": float(np.std(cv)),
                                    "p2.5_p97.5": [float(np.percentile(cv, 2.5)), float(np.percentile(cv, 97.5))]}

    out = {"features_file": str(args.features), "n": int(len(y)), "n_none": int(y.sum()),
           "n_report_half": int((~dev).sum()), "positive_class": "gold_regulation == NONE",
           "single_signals": singles, "logistic_regression": logreg}
    path = ROOT / "results" / f"abstention{'_' + args.tag if args.tag else ''}.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    for name, r in singles.items():
        print(f"{name:28s} report AUROC {r['report_half']['auroc']:.3f} {np.round(r['report_half']['ci95'], 3)}")
    print(f"{'logistic regression':28s} report AUROC {logreg['report_half']['auroc']:.3f} "
          f"{np.round(logreg['report_half']['ci95'], 3)}; CV {logreg['cv_5fold_x20_auroc']['mean']:.3f}"
          f" +/- {logreg['cv_5fold_x20_auroc']['sd']:.3f}; F1 report {logreg['prf_report']['f1']:.3f}")
    print("wrote", path)


if __name__ == "__main__":
    main()
