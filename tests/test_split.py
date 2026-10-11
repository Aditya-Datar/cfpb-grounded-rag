import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.config import PRODUCT_TO_REGULATION  # noqa: E402
from cfpb.data.split import annotation_sample, make_splits  # noqa: E402

PRODUCTS = [p for p, r in PRODUCT_TO_REGULATION.items() if r]


def _frame(n: int) -> pd.DataFrame:
    return pd.DataFrame({
        "complaint_id": [str(10_000 + i) for i in range(n)],
        "product": [PRODUCTS[i % len(PRODUCTS)] for i in range(n)],
        "sub_product": "s", "issue": "i", "sub_issue": "", "company": "c",
        "narrative_clean": [f"text {i}" for i in range(n)],
    })


def _membership(splits):
    return {cid: name for name, part in splits.items() for cid in part["complaint_id"]}


def test_splits_partition_rows_roughly_80_10_10():
    df = _frame(20_000)
    s = make_splits(df)
    assert sum(len(p) for p in s.values()) == len(df)
    assert set(_membership(s)) == set(df["complaint_id"])
    assert 0.78 < len(s["train"]) / len(df) < 0.82
    assert 0.08 < len(s["test"]) / len(df) < 0.12


def test_removing_rows_does_not_reshuffle_others():
    df = _frame(20_000)
    before = _membership(make_splits(df))
    dropped = df.sample(250, random_state=0)
    after = _membership(make_splits(df.drop(dropped.index)))
    moved = [cid for cid, name in after.items() if before[cid] != name]
    assert moved == []


def test_cap_is_stable_and_respected():
    df = _frame(20_000)
    s = make_splits(df, max_per_class=500)
    total = pd.concat(s.values())
    assert total["product"].value_counts().max() == 500
    again = pd.concat(make_splits(df.iloc[::-1], max_per_class=500).values())
    assert set(total["complaint_id"]) == set(again["complaint_id"])  # row order irrelevant


def test_annotation_sample_stable_and_balanced():
    df = _frame(5_000)
    a = annotation_sample(df)
    assert a["regulation_candidate"].value_counts().to_dict() == {r: 30 for r in "EFVZ"}
    b = annotation_sample(df.drop(df.sample(100, random_state=1).index))
    kept = set(a["complaint_id"]) & set(b["complaint_id"])
    assert len(kept) >= 110  # only rows that were dropped (or displaced by them) change
