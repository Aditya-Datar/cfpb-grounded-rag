"""Dataset profiling: label distribution, narrative coverage, length, redaction."""
import json
from pathlib import Path

import pandas as pd

from cfpb.config import PRODUCT_TO_REGULATION


def profile(df: pd.DataFrame) -> dict:
    has_narr = df["narrative"].notna() & (df["narrative"].str.strip() != "")
    report = {
        "n_rows": int(len(df)),
        "date_min": df["date_received"].min(),
        "date_max": df["date_received"].max(),
        "n_with_narrative": int(has_narr.sum()),
        "product_counts": df["product"].value_counts().to_dict(),
        "n_issues": int(df["issue"].nunique()),
        "top_issues": df["issue"].value_counts().head(25).to_dict(),
        "regulation_candidate_counts": (
            df["product"].map(PRODUCT_TO_REGULATION).fillna("none")
            .value_counts().to_dict()),
        "submitted_via": df["submitted_via"].value_counts().to_dict(),
    }
    if "n_words" in df:
        report["narrative_words"] = df["n_words"].describe().round(1).to_dict()
        report["redaction_density"] = df["redaction_density"].describe().round(3).to_dict()
    return report


def write_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
