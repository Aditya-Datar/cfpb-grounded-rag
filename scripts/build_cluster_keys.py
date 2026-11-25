"""Write the cluster keys for cluster-based scoring (docs/CLUSTER_SCORING_PROTOCOL.md, Sec. 5).

    .venv/Scripts/python.exe scripts/build_cluster_keys.py

One key per distinct (CFPB issue, gold section) over the attribution complaints
(annotation/attribution_ids.txt). Reads ONLY the gold labels and the complaint
metadata (product, sub-product, issue, sub-issue, company); never drafts, rankings,
run outputs or results. Writes annotation/cluster_keys.jsonl.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cfpb.annotation import load_items  # noqa: E402


def key_id(issue: str, section: str) -> str:
    return f"{section}|{re.sub(r'[^a-z0-9]+', '-', issue.lower()).strip('-')}"


def main() -> None:
    ids = [l.strip() for l in open(ROOT / "annotation" / "attribution_ids.txt", encoding="utf-8") if l.strip()]
    gold = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str).set_index("complaint_id")
    meta = load_items().set_index("complaint_id")[["product", "sub_product", "issue", "sub_issue", "company"]]
    df = meta.loc[ids].join(gold.loc[ids, ["gold_regulation", "gold_section", "gold_paragraph"]])
    rows = []
    for (issue, sec), g in df.groupby(["issue", "gold_section"], sort=True):
        rows.append({"key": key_id(issue, sec), "issue": issue, "gold_section": sec,
                     "gold_regulation": g["gold_regulation"].iloc[0],
                     "gold_paragraphs": sorted(g["gold_paragraph"].dropna().unique().tolist()),
                     "products": sorted(g["product"].dropna().unique().tolist()),
                     "sub_products": sorted(g["sub_product"].dropna().unique().tolist()),
                     "sub_issues": sorted(g["sub_issue"].dropna().unique().tolist()),
                     "companies": sorted(g["company"].dropna().unique().tolist()),
                     "n_complaints": len(g), "complaint_ids": sorted(g.index.tolist())})
    out = ROOT / "annotation" / "cluster_keys.jsonl"
    out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {out}: {len(rows)} keys over {len(df)} complaints")


if __name__ == "__main__":
    main()
