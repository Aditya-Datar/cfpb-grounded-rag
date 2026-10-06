"""Stage 0 data pipeline: raw CFPB CSV -> cleaned splits + annotation sample.

Usage (from repo root, venv active):
    python scripts/run_data_pipeline.py --csv data/raw/filtered_data.csv
    python scripts/run_data_pipeline.py --csv data/raw/filtered_data.csv \
        --narratives data/raw/complaints_with_narratives.csv

Outputs (all git-ignored):
    data/processed/complaints.parquet        all rows, selected columns
    outputs/profile_all.json                 profile of every complaint
    data/processed/narratives_clean.parquet  cleaned, filtered, deduped
    outputs/profile_narratives.json          profile of usable narratives
    data/processed/{train,val,test}.parquet  classifier splits (by product)
    data/processed/annotation_sample.csv     ~30 per regulation for gold labels
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.config import OUTPUT_DIR, PROCESSED_DIR  # noqa: E402
from cfpb.data.clean import add_clean_columns, filter_narratives  # noqa: E402
from cfpb.data.load import csv_to_parquet  # noqa: E402
from cfpb.data.profile import profile, write_report  # noqa: E402
from cfpb.data.split import annotation_sample, make_splits  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--narratives", type=Path, default=None,
                    help="CSV with 'Complaint ID' and 'Consumer complaint narrative' "
                         "to join in if --csv lacks narratives")
    ap.add_argument("--skip-ingest", action="store_true",
                    help="reuse data/processed/complaints.parquet")
    ap.add_argument("--min-words", type=int, default=20)
    ap.add_argument("--max-redaction", type=float, default=0.5)
    ap.add_argument("--max-per-class", type=int, default=20_000)
    ap.add_argument("--per-regulation", type=int, default=30)
    args = ap.parse_args()

    all_path = PROCESSED_DIR / "complaints.parquet"
    if not args.skip_ingest:
        print(f"[1/5] Ingesting {args.csv}")
        csv_to_parquet(args.csv, all_path, narratives_path=args.narratives)

    print("[2/5] Profiling all complaints")
    df = pd.read_parquet(all_path)
    report = profile(df)
    write_report(report, OUTPUT_DIR / "profile_all.json")
    print(f"  rows={report['n_rows']:,}  with narrative={report['n_with_narrative']:,}  "
          f"dates={report['date_min']}..{report['date_max']}")

    if report["n_with_narrative"] == 0:
        sys.exit("\nNo narratives found. Classification and retrieval need the "
                 "'Consumer complaint narrative' column.\nRe-export with that "
                 "column or pass --narratives. Structured profile written to "
                 "outputs/profile_all.json.")

    print("[3/5] Cleaning narratives")
    narr = df[df["narrative"].notna()].copy()
    del df
    narr = filter_narratives(add_clean_columns(narr), args.min_words, args.max_redaction)
    narr.to_parquet(PROCESSED_DIR / "narratives_clean.parquet", index=False)
    write_report(profile(narr), OUTPUT_DIR / "profile_narratives.json")
    print(f"  usable narratives after filter+dedupe: {len(narr):,}")

    print("[4/5] Classifier splits")
    splits = make_splits(narr, max_per_class=args.max_per_class)
    for name, part in splits.items():
        part.to_parquet(PROCESSED_DIR / f"{name}.parquet", index=False)
        print(f"  {name}: {len(part):,}")

    print("[5/5] Annotation sample")
    # Kept disjoint from the classifier test set so no complaint is both
    # a gold retrieval example and a classifier test example.
    sample = annotation_sample(narr, args.per_regulation,
                               exclude_ids=set(splits["test"]["complaint_id"]))
    sample.to_csv(PROCESSED_DIR / "annotation_sample.csv", index=False)
    print(sample["regulation_candidate"].value_counts().to_string())


if __name__ == "__main__":
    main()
