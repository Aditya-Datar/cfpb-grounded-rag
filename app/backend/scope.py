"""Scope check: is this complaint covered by Regulations E, F, V, Z or the FCRA at all?

Gagan's H5 detector (docs/tasks/results/gagan.md): a logistic regression on
retrieval-confidence features from BM25 and mpnet dense scores, fit on the dev
half of the gold set, with the F1-maximising threshold from the dev half. On the
held-out half it reached AUROC 0.740 [0.625, 0.851], recall 0.846 and precision
0.440 for NONE, i.e. 1.27 wrong referrals per correct one. So the app treats a
flag as a prompt for the officer (refer, or draft anyway), never as an automatic
rejection.

The fitted model is plain numbers in artifacts/scope_model.json (no pickle),
written by app/backend/train_scope.py.
"""
import json
import math
from pathlib import Path

import numpy as np

from app.backend.config import ARTIFACTS

FEATURES = ["bm25_top", "bm25_margin", "bm25_top_z", "bm25_top5_mean",
            "dense_top", "dense_margin", "dense_top_z", "dense_top5_mean", "n_words"]
MODEL_PATH = ARTIFACTS / "scope_model.json"


def _rank_sections(chunks: list[dict], scores: np.ndarray) -> list[float]:
    seen, out = set(), []
    for i in np.argsort(-scores, kind="stable"):
        sec = chunks[i]["section"]
        if sec not in seen:
            seen.add(sec)
            out.append(float(scores[i]))
            if len(out) == 5:
                break
    return out


def _signals(chunks: list[dict], row: np.ndarray, prefix: str) -> dict[str, float]:
    """Same definitions as scripts/run_retrieval.py features()."""
    secs = _rank_sections(chunks, row)
    return {f"{prefix}_top": secs[0], f"{prefix}_margin": secs[0] - secs[1],
            f"{prefix}_top_z": (secs[0] - row.mean()) / (row.std() or 1.0),
            f"{prefix}_top5_mean": float(np.mean(secs))}


def features(chunks: list[dict], bm25_row: np.ndarray, dense_row: np.ndarray, n_words: int) -> dict[str, float]:
    return {**_signals(chunks, bm25_row, "bm25"), **_signals(chunks, dense_row, "dense"), "n_words": float(n_words)}


class ScopeModel:
    def __init__(self, spec: dict):
        self.spec = spec
        self.mean = np.array(spec["scaler_mean"])
        self.scale = np.array(spec["scaler_scale"])
        self.coef = np.array(spec["coef"])
        self.intercept = float(spec["intercept"])
        self.threshold = float(spec["threshold"])

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> "ScopeModel | None":
        return cls(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def score(self, feats: dict[str, float]) -> dict:
        x = (np.array([feats[f] for f in FEATURES]) - self.mean) / self.scale
        z = float(x @ self.coef + self.intercept)
        p = 1 / (1 + math.exp(-z))
        return {"prob_out_of_scope": p, "threshold": self.threshold, "out_of_scope": p >= self.threshold,
                "features": {k: round(v, 4) for k, v in feats.items()}, "model": self.spec["name"]}
