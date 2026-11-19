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
from run_retrieval import boot_ci, paired_gain, retrieval_metrics  # noqa: E402


DEFAULT_TAG = "struct1400"
TAGS = ["struct1400", "struct700", "struct2800", "fixed200", "section"]
RETRIEVERS = ["bm25", "dense", "hybrid"]


def ranks_path(tag: str, no_fcra: bool) -> Path:
    suffix = "_no_fcra" if no_fcra else ""
    return ROOT / "outputs" / "retrieval" / f"ranks_{tag}{suffix}.parquet"


def load_report_ranks(tag: str, no_fcra: bool, non_fcra_only: bool = False) -> pd.DataFrame:
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
    mask = (frame["gold_regulation"] != "NONE") & (~frame["dev_half"].astype(bool))
    if non_fcra_only:
        mask &= frame["gold_regulation"] != "FCRA"
    report = frame.loc[
        mask,
        ["complaint_id", *[f"rank_{name}" for name in RETRIEVERS]],
    ].copy()
    if report["complaint_id"].duplicated().any():
        raise ValueError(f"{path} contains duplicate complaint IDs")
    return report.set_index("complaint_id").sort_index()


def rank_list(frame: pd.DataFrame, retriever: str) -> list:
    return frame[f"rank_{retriever}"].replace({np.nan: None}).tolist()


def summarize(frame: pd.DataFrame) -> dict:
    result = {}
    for name in RETRIEVERS:
        ranks = rank_list(frame, name)
        result[name] = retrieval_metrics(ranks) | {"ci95": boot_ci(ranks, n_boot=10000, seed=0)}
    return result


def compare(default: pd.DataFrame, alternative: pd.DataFrame) -> dict:
    joined = default.join(alternative, lsuffix="_default", rsuffix="_alternative", how="inner")
    if len(joined) != len(default) or len(joined) != len(alternative):
        raise ValueError("chunkings do not contain the same report-half complaints")

    result = {"n": len(joined), "paired_difference": {}}
    for name in RETRIEVERS:
        base = rank_list(joined.rename(columns={f"rank_{name}_default": f"rank_{name}"}), name)
        ranks = rank_list(joined.rename(columns={f"rank_{name}_alternative": f"rank_{name}"}), name)
        result["paired_difference"][name] = paired_gain(ranks, base, n_boot=10000, seed=0)
    return result


def compare_fcra_scope() -> dict:
    """Compare struct1400 with and without FCRA on the same non-FCRA items."""
    with_fcra = load_report_ranks(DEFAULT_TAG, no_fcra=False, non_fcra_only=True)
    without_fcra = load_report_ranks(DEFAULT_TAG, no_fcra=True, non_fcra_only=True)
    joined = without_fcra.join(with_fcra, lsuffix="_without", rsuffix="_with", how="inner")
    if len(joined) != len(with_fcra) or len(joined) != len(without_fcra):
        raise ValueError("with- and without-FCRA ranks do not contain the same non-FCRA complaints")

    differences = {}
    for name in RETRIEVERS:
        without = joined[f"rank_{name}_without"].replace({np.nan: None}).tolist()
        with_ = joined[f"rank_{name}_with"].replace({np.nan: None}).tolist()
        differences[name] = paired_gain(with_, without, n_boot=10000, seed=0)
    return {
        "population": "gold_regulation not in {NONE, FCRA} and dev_half == False",
        "n": len(joined),
        "with_fcra": summarize(with_fcra),
        "without_fcra": summarize(without_fcra),
        "paired_difference_with_minus_without": differences,
    }


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
        "fcra_scope": compare_fcra_scope(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
