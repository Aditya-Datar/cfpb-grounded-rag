"""Classifier splits and the stratified annotation sample.

Every random choice here is a hash of (seed, purpose, complaint_id), not a
shuffle of the whole table. A complaint therefore always lands in the same
split and keeps the same sampling rank, however many other rows are added or
removed. With a table-wide shuffle, dropping 248 rows (the 2026-10-10 cleaner
fix) moved 93% of the test set to other splits.
"""
import hashlib

import numpy as np
import pandas as pd

from cfpb.config import PRODUCT_TO_REGULATION, RANDOM_SEED


def stable_uniform(ids: pd.Series, purpose: str, seed: int = RANDOM_SEED) -> np.ndarray:
    """Deterministic pseudo-random number in [0, 1) per id. Different
    purposes ("split", "cap", "annotate") give independent draws."""
    return np.array([int(hashlib.sha1(f"{seed}:{purpose}:{i}".encode()).hexdigest()[:15], 16) / 16**15
                     for i in ids.astype(str)])


def make_splits(df: pd.DataFrame, label_col: str = "product",
                val_frac: float = 0.1, test_frac: float = 0.1,
                max_per_class: int | None = None) -> dict[str, pd.DataFrame]:
    """Train/val/test split by hashed complaint_id. Expects df already deduped
    on text_hash (clean.filter_narratives) so duplicates cannot leak.

    Each complaint's bucket depends only on its own id, so proportions per
    class are approximately (not exactly) 80/10/10; with the smallest class at
    ~1.8k rows that is close enough. max_per_class caps dominant classes
    (credit reporting) by keeping the rows with the lowest "cap" hash, which
    is also stable. Evaluation uses macro-F1 anyway.
    """
    df = df.assign(_cap=stable_uniform(df["complaint_id"], "cap"),
                   _split=stable_uniform(df["complaint_id"], "split"))
    if max_per_class:
        df = df.sort_values("_cap", kind="stable").groupby(label_col).head(max_per_class)
    bucket = np.where(df["_split"] < 1 - val_frac - test_frac, "train",
                      np.where(df["_split"] < 1 - test_frac, "val", "test"))
    # Classes too small to evaluate (<10 rows) go to train only.
    counts = df[label_col].value_counts()
    bucket[df[label_col].isin(counts[counts < 10].index).to_numpy()] = "train"
    df = df.drop(columns=["_cap", "_split"])
    return {name: df[bucket == name].sort_values("complaint_id").reset_index(drop=True)
            for name in ("train", "val", "test")}


def annotation_sample(df: pd.DataFrame, per_regulation: int = 30,
                      exclude_ids: set[str] | None = None) -> pd.DataFrame:
    """Stratified sample for the gold retrieval set (~30 per regulation,
    CLAUDE.md Sec. 4-5), with empty columns for annotators to fill in.
    Pass exclude_ids (e.g. the classifier test set) to keep sets disjoint."""
    df = df.assign(regulation_candidate=df["product"].map(PRODUCT_TO_REGULATION))
    df = df[df["regulation_candidate"].notna()]
    if exclude_ids:
        df = df[~df["complaint_id"].isin(exclude_ids)]
    # Round-robin across products within each regulation so e.g. Reg Z is
    # not all mortgages: order rows by a stable hash, rank them within their
    # product, take the lowest ranks first.
    df = df.assign(_u=stable_uniform(df["complaint_id"], "annotate")).sort_values("_u")
    df = df.assign(_rank=df.groupby("product").cumcount()).sort_values(["_rank", "_u"])
    out = df.groupby("regulation_candidate").head(per_regulation).reset_index(drop=True)
    cols = ["complaint_id", "regulation_candidate", "product", "sub_product",
            "issue", "sub_issue", "company", "narrative_clean"]
    out = out[cols]
    # Filled in by annotators, per the rubric.
    for c in ["gold_regulation", "gold_section", "gold_paragraph",
              "annotator", "confidence", "notes"]:
        out[c] = ""
    return out
