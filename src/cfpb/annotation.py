"""Annotation item sets: the stratified sample (120) plus the in-scope top-up.

Why a top-up (2026-10-15): of the 120 stratified items, only 12 E, 22 F and 7 Z
were in scope after labelling, against a target of about 30 per regulation.
The top-up draws extra items from the issue types most likely to be governed by
Regs E, F and Z. Like the splits, it is hash-ordered, so it never changes when
other rows change. It excludes the classifier test set and the original sample.
"""
import pandas as pd

from cfpb.config import PROCESSED_DIR
from cfpb.data.split import stable_uniform

# Per target regulation: (products, sub_issues, number to draw).
TOPUP_PLAN = {
    "E": (["Checking or savings account", "Prepaid card",
           "Money transfer, virtual currency, or money service"],
          ["Transaction was not authorized", "Problem using a debit or ATM card", "Banking errors",
           "Money was taken from your account on the wrong day or for the wrong amount",
           "Charged for a purchase or transfer you did not make with the card",
           "Card company isn't resolving a dispute about a purchase or transfer"], 30),
    "Z": (["Credit card"],
          ["Credit card company isn't resolving a dispute about a purchase on your statement",
           "Card was charged for something you did not purchase with the card",
           "Card opened without my consent or knowledge", "Problem during payment process",
           "Problem with fees", "Charged too much interest"], 36),
    "F": (["Debt collection"],
          ["Didn't receive enough information to verify debt", "Didn't receive notice of right to dispute",
           "Frequent or repeated calls", "You told them to stop contacting you, but they keep trying",
           "Threatened to sue you for very old debt"], 12),
}
COLS = ["complaint_id", "regulation_candidate", "product", "sub_product", "issue", "sub_issue",
        "company", "narrative_clean"]


def make_topup(narr: pd.DataFrame, exclude_ids: set[str]) -> pd.DataFrame:
    pool = narr[~narr["complaint_id"].isin(exclude_ids)]
    pool = pool.assign(_u=stable_uniform(pool["complaint_id"], "topup"))
    parts = []
    for reg, (products, sub_issues, n) in TOPUP_PLAN.items():
        cand = pool[pool["product"].isin(products) & pool["sub_issue"].isin(sub_issues)]
        # Round-robin across sub-issues so one issue type does not dominate.
        cand = cand.sort_values("_u")
        cand = cand.assign(_rank=cand.groupby("sub_issue").cumcount()).sort_values(["_rank", "_u"])
        parts.append(cand.head(n).assign(regulation_candidate=reg))
    out = pd.concat(parts)[COLS].reset_index(drop=True)
    for c in ["gold_regulation", "gold_section", "gold_paragraph", "annotator", "confidence", "notes"]:
        out[c] = ""
    return out


def load_items() -> pd.DataFrame:
    """All annotation items with a stable 1-based `item` number: sample 1-120, then top-up."""
    sample = pd.read_csv(PROCESSED_DIR / "annotation_sample.csv", dtype=str, keep_default_na=False)
    frames = [sample.assign(subset="sample")]
    topup_path = PROCESSED_DIR / "annotation_topup.csv"
    if topup_path.exists():
        frames.append(pd.read_csv(topup_path, dtype=str, keep_default_na=False).assign(subset="topup"))
    items = pd.concat(frames, ignore_index=True)
    items.insert(0, "item", range(1, len(items) + 1))
    return items
