"""Fingerprint the data splits so every teammate trains and tests on the SAME rows.

    python scripts/check_splits.py            # compare local splits to data_fingerprint.json
    python scripts/check_splits.py --write    # record the current splits (do this only
                                              # when the team agrees to change the data)

The fingerprint has, per split: row count, a SHA-1 of the sorted
complaint_ids (same rows?), and a SHA-1 of the cleaned narratives in
complaint_id order (same text?). The text hash catches stale files made by
an older cleaner, which keep the same rows. If anything differs, results are
not comparable with the team's.
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
    tables = {split: pd.read_parquet(data_dir / f"{split}.parquet",
                                     columns=["complaint_id", "narrative_clean"])
              for split in ("train", "val", "test")}
    tables["annotation_sample"] = pd.read_csv(data_dir / "annotation_sample.csv", dtype=str,
                                              keep_default_na=False,
                                              usecols=["complaint_id", "narrative_clean"])
    for name, df in tables.items():
        df = df.astype(str).sort_values("complaint_id")
        fp[name] = {"rows": len(df),
                    "sha1": hashlib.sha1("\n".join(df["complaint_id"]).encode()).hexdigest(),
                    "text_sha1": hashlib.sha1("\x1e".join(df["narrative_clean"]).encode()).hexdigest()}
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
