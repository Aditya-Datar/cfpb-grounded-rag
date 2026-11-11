"""Agreement between two annotation files (JSONL, one label per complaint).

    python scripts/compare_annotators.py annotation/llm_labels_claude-opus-5-5.jsonl \
        annotation/llm_labels_chatgpt.jsonl [--review annotation/chatgpt_review.jsonl]

Prints Cohen's kappa and raw agreement at regulation level (E/F/V/Z/NONE) and
section level (section, or NONE), a confusion table, and writes the
disagreements to annotation/disagreements.md for human adjudication.
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

sys.stdout.reconfigure(encoding="utf-8")


def load(path: Path) -> pd.DataFrame:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    df = pd.DataFrame(rows).drop_duplicates("complaint_id", keep="last").set_index("complaint_id")
    df["section_label"] = df["gold_section"].fillna("NONE").where(df["gold_regulation"] != "NONE", "NONE")
    return df


def label(r: pd.Series) -> str:
    """'Z 1026.13(a)(4)' style label; NaN/None fields are skipped."""
    ref = next((r.get(k) for k in ("gold_paragraph", "gold_section")
                if isinstance(r.get(k), str) and r.get(k)), "")
    return f"{r['gold_regulation']} {ref}".strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    ap.add_argument("--review", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("annotation/disagreements.md"))
    args = ap.parse_args()

    a, b = load(args.a), load(args.b)
    ids = a.index.intersection(b.index)
    print(f"A: {len(a)} labels, B: {len(b)} labels, compared: {len(ids)}")
    for level, col in [("regulation", "gold_regulation"), ("section", "section_label")]:
        ya, yb = a.loc[ids, col], b.loc[ids, col]
        print(f"{level:10s} agreement {(ya == yb).mean():.3f}  Cohen's kappa {cohen_kappa_score(ya, yb):.3f}")
    print("\nregulation confusion (rows = A, cols = B):")
    print(pd.crosstab(a.loc[ids, "gold_regulation"], b.loc[ids, "gold_regulation"], margins=True))

    review = {}
    if args.review and args.review.exists():
        for line in args.review.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                review[r["complaint_id"]] = r
    dis = [cid for cid in ids if a.loc[cid, "section_label"] != b.loc[cid, "section_label"]]
    lines = [f"# Annotator disagreements ({len(dis)} of {len(ids)})", "",
             f"A = `{args.a.name}`, B = `{args.b.name}`. A human adjudicator records the final label.", ""]
    for cid in dis:
        ra, rb = a.loc[cid], b.loc[cid]
        lines += [f"## {cid}",
                  f"- **A:** {label(ra)} (conf {ra['confidence']}): {ra['rationale']}",
                  f"- **B:** {label(rb)} (conf {rb['confidence']}): {rb['rationale']}"]
        if cid in review:
            rv = review[cid]
            lines.append(f"- **B's review:** prefers {rv.get('preferred')} -> {rv.get('preferred_label')}: "
                         f"{rv.get('reason')}")
        lines += ["- **Final (human):** ", ""]
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{len(dis)} disagreements written to {args.out}")


if __name__ == "__main__":
    main()
