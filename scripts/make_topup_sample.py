"""Draw the in-scope annotation top-up (see cfpb/annotation.py for why and how).

    python scripts/make_topup_sample.py

Writes data/processed/annotation_topup.csv (git-ignored) and
annotation/annotation_topup_ids.txt (committed, so the draw is auditable).
Deterministic: same data, same items.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.annotation import make_topup  # noqa: E402
from cfpb.config import PROCESSED_DIR, ROOT  # noqa: E402


def main() -> None:
    narr = pd.read_parquet(PROCESSED_DIR / "narratives_clean.parquet")
    test_ids = set(pd.read_parquet(PROCESSED_DIR / "test.parquet", columns=["complaint_id"])["complaint_id"])
    sample_ids = set(pd.read_csv(PROCESSED_DIR / "annotation_sample.csv", dtype=str)["complaint_id"])
    topup = make_topup(narr, test_ids | sample_ids)
    topup.to_csv(PROCESSED_DIR / "annotation_topup.csv", index=False)
    (ROOT / "annotation" / "annotation_topup_ids.txt").write_text(
        "\n".join(f"{r.complaint_id}\t{r.regulation_candidate}\t{r.sub_issue}" for r in topup.itertuples()) + "\n",
        encoding="utf-8")
    print(topup.groupby(["regulation_candidate", "sub_issue"]).size().to_string())
    print(f"\n{len(topup)} top-up items written")


if __name__ == "__main__":
    main()
