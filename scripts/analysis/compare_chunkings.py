"""Compare chunking ablations against the struct1400 baseline.

The retrieval jobs write one ranks parquet per chunking and corpus scope.  This
script aligns those files by complaint_id before calculating paired hit@5 and
MRR differences on the held-out, in-scope report half.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from run_retrieval import paired_gain  # noqa: E402


DEFAULT_TAG = "struct1400"
TAGS = ["struct1400", "struct700", "struct2800", "fixed200", "section"]
RETRIEVERS = ["bm25", "dense", "hybrid"]


def ranks_path(tag: str, no_fcra: bool) -> Path:
    suffix = "_no_fcra" if no_fcra else ""
    return ROOT / "outputs" / "retrieval" / f"ranks_{tag}{suffix}.parquet"


def load_report_ranks(tag: str, no_fcra: bool) -> pd.DataFrame:
    path = ranks_path(tag, no_fcra)
    if not path.exists():
        raise FileNotFoundError(f"missing retrieval ranks: {path}")
    frame = pd.read_parquet(path)
    required = {"complaint_id", "gold_regulation", "dev_half", *(
        f"rank_{name}" for name in RETRIEVERS
    )}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path} is missing columns: {sorted(missing)}")
    report = frame.loc[
        (frame["gold_regulation"] != "NONE") & (~frame["dev_half"].astype(bool)),
        ["complaint_id", *[f"rank_{name}" for name in RETRIEVERS]],
    ].copy()
    if report["complaint_id"].duplicated().any():
        raise ValueError(f"{path} contains duplicate complaint IDs")
    return report.set_index("complaint_id").sort_index()


def compare(default: pd.DataFrame, alternative: pd.DataFrame) -> dict:
    joined = default.join(alternative, lsuffix="_default", rsuffix="_alternative", how="inner")
    if len(joined) != len(default) or len(joined) != len(alternative):
        raise ValueError("chunkings do not contain the same report-half complaints")

    result = {"n": len(joined), "paired_difference": {}}
    for name in RETRIEVERS:
        base = joined[f"rank_{name}_default"].replace({np.nan: None}).tolist()
        ranks = joined[f"rank_{name}_alternative"].replace({np.nan: None}).tolist()
        result["paired_difference"][name] = paired_gain(ranks, base, n_boot=10000, seed=0)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "ablation_chunking.json")
    parser.add_argument("--with-fcra", action="store_true", help="compare ranks including FCRA")
    parser.add_argument("--tags", nargs="+", default=TAGS)
    args = parser.parse_args()
    if DEFAULT_TAG not in args.tags:
        raise ValueError("the baseline struct1400 must be included")

    no_fcra = not args.with_fcra
    baseline = load_report_ranks(DEFAULT_TAG, no_fcra)
    comparisons = {}
    for tag in args.tags:
        if tag == DEFAULT_TAG:
            continue
        comparisons[tag] = compare(baseline, load_report_ranks(tag, no_fcra))

    output = {
        "baseline": DEFAULT_TAG,
        "corpus": "regulation" if no_fcra else "regulation+statute",
        "split": "gold_regulation != NONE and dev_half == False",
        "bootstrap": {"n_resamples": 10000, "seed": 0},
        "comparisons": comparisons,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
