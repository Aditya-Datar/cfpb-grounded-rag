"""Section-level retrieval and abstention metrics (docs/INTERFACES.md Secs. 2 and 7)."""
import hashlib

import numpy as np

KS = (1, 5, 10)


def rank_of(gold: str, ranked_sections: list[str]) -> int | None:
    """1-based rank of the gold section in a section-deduplicated list, or None."""
    return ranked_sections.index(gold) + 1 if gold in ranked_sections else None


def retrieval_metrics(ranks: list[int | None]) -> dict:
    """hit@k = recall@k (one gold section per item), precision@k = hit@k / k, and MRR."""
    n = len(ranks)
    out: dict = {"n": n}
    for k in KS:
        hit = sum(r is not None and r <= k for r in ranks) / n if n else float("nan")
        out[f"hit@{k}"] = hit
        out[f"recall@{k}"] = hit
        out[f"precision@{k}"] = hit / k
    out["mrr"] = sum(1 / r for r in ranks if r) / n if n else float("nan")
    return out


def half(complaint_id: str, salt: str = "bm25-abstain") -> int:
    """Fixed 0/1 split of items by SHA-1, so threshold tuning and reporting are disjoint."""
    return int(hashlib.sha1(f"{salt}:{complaint_id}".encode()).hexdigest(), 16) % 2


def prf(abstain_true: np.ndarray, abstain_pred: np.ndarray) -> dict:
    tp = int((abstain_true & abstain_pred).sum())
    p = tp / abstain_pred.sum() if abstain_pred.sum() else 0.0
    r = tp / abstain_true.sum() if abstain_true.sum() else 0.0
    return {"precision": float(p), "recall": float(r), "f1": float(2 * p * r / (p + r)) if p + r else 0.0,
            "n": int(len(abstain_true)), "n_none": int(abstain_true.sum())}


def tune_threshold(top_scores: np.ndarray, is_none: np.ndarray) -> float:
    """Threshold maximizing abstention F1 when abstaining on top score < threshold."""
    best_t, best_f = float(top_scores.min()), -1.0
    for t in np.unique(top_scores):
        f = prf(is_none, top_scores <= t)["f1"]  # inclusive: abstain at or below t
        if f > best_f:
            best_t, best_f = float(t), f
    return best_t
