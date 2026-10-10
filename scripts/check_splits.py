"""Fingerprint the data splits so every teammate trains and tests on the SAME rows.

    python scripts/check_splits.py            # compare local splits to data_fingerprint.json
    python scripts/check_splits.py --write    # record the current splits (do this only
                                              # when the team agrees to change the data)

The fingerprint is a SHA-1 of the sorted complaint_ids in each split, plus
row counts. If it differs, results are not comparable with the team's.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.config import PROCESSED_DIR, ROOT  # noqa: E402

FINGERPRINT = ROOT / "data_fingerprint.json"


def fingerprint(data_dir: Path) -> dict:
    fp = {}
    for split in ("train", "val", "test"):
        ids = sorted(pd.read_parquet(data_dir / f"{split}.parquet", columns=["complaint_id"])
                     ["complaint_id"].astype(str))
        fp[split] = {"rows": len(ids),
                     "sha1": hashlib.sha1("\n".join(ids).encode()).hexdigest()}
    sample = pd.read_csv(data_dir / "annotation_sample.csv", dtype=str)["complaint_id"]
    fp["annotation_sample"] = {"rows": len(sample),
                               "sha1": hashlib.sha1("\n".join(sorted(sample)).encode()).hexdigest()}
    return fp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=PROCESSED_DIR)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    fp = fingerprint(args.data_dir)
    if args.write:
        FINGERPRINT.write_text(json.dumps(fp, indent=2) + "\n")
        print(f"Wrote {FINGERPRINT}")
        return
    expected = json.loads(FINGERPRINT.read_text())
    ok = True
    for k, v in expected.items():
        match = fp.get(k) == v
        ok &= match
        print(f"{k:18s} rows={fp.get(k, {}).get('rows')} {'OK' if match else 'MISMATCH'}")
    if not ok:
        sys.exit("Splits differ from the team's reference. Do not report these results as "
                 "comparable; rerun scripts/run_data_pipeline.py or get the team's split files.")
    print("All splits match the team reference.")


if __name__ == "__main__":
    main()
