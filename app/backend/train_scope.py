"""Fit the scope (NONE) detector for the app and write app/backend/artifacts/scope_model.json.

    python -m app.backend.train_scope

Same setup as scripts/run_abstention.py (Gagan's H5 run): features from BM25 and
all-mpnet-base-v2 over the corpus with the FCRA, logistic regression on standardised
features fit on the dev half (metrics.half == 0), threshold maximising F1 on the dev
half. Prints the report-half AUROC so it can be checked against
results/abstention_mpnet.json (0.740, threshold 0.386).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from app.backend.scope import FEATURES, MODEL_PATH, features  # noqa: E402
from cfpb.annotation import load_items  # noqa: E402
from cfpb.retrieval.bm25 import DEFAULT_CHUNKS_PATH, BM25Retriever, load_chunks  # noqa: E402
from cfpb.retrieval.dense import DEFAULT_MODEL, DenseRetriever  # noqa: E402
from cfpb.retrieval.metrics import half  # noqa: E402


def main() -> None:
    from run_abstention import best_threshold
    items = load_items()[["complaint_id", "narrative_clean"]]
    gold = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str)[["complaint_id", "gold_regulation"]]
    df = items.merge(gold, on="complaint_id", validate="1:1")
    chunks = load_chunks(DEFAULT_CHUNKS_PATH, include_fcra=True)
    bm25, dense = BM25Retriever(chunks), DenseRetriever(chunks, DEFAULT_MODEL)
    texts = df["narrative_clean"].tolist()
    S_b = np.vstack([bm25.scores(t) for t in texts])
    S_d = dense.scores_batch(texts)
    X = np.array([[f[k] for k in FEATURES] for f in
                  (features(chunks, b, d, len(t.split())) for b, d, t in zip(S_b, S_d, texts))])
    y = (df["gold_regulation"] == "NONE").to_numpy()
    dev = (df["complaint_id"].map(half) == 0).to_numpy()

    m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000)).fit(X[dev], y[dev])
    p = m.predict_proba(X)[:, 1]
    t = float(best_threshold(y[dev], p[dev]))
    rep = ~dev
    flag = p[rep] >= t
    spec = {"name": "h5-logreg-mpnet-v1", "features": FEATURES,
            "scaler_mean": m[0].mean_.tolist(), "scaler_scale": m[0].scale_.tolist(),
            "coef": m[-1].coef_[0].tolist(), "intercept": float(m[-1].intercept_[0]), "threshold": t,
            "dense_model": DEFAULT_MODEL, "corpus": "chunks.jsonl with FCRA",
            "report_half": {"n": int(rep.sum()), "n_none": int(y[rep].sum()),
                            "auroc": float(roc_auc_score(y[rep], p[rep])),
                            "true_flags": int((flag & y[rep]).sum()), "false_flags": int((flag & ~y[rep]).sum())},
            "source": "docs/tasks/results/gagan.md; fit on gold dev half (metrics.half == 0)"}
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(json.dumps({k: spec[k] for k in ("threshold", "report_half")}, indent=2))
    print("wrote", MODEL_PATH)


if __name__ == "__main__":
    main()
