"""Validate LLM annotation files before they are used.

    python scripts/check_llm_labels.py annotation/llm_labels_claude-opus-5-5.jsonl

Checks every line: required fields present; complaint_id is in
annotation_sample.csv; regulation is one of E/F/V/Z/NONE; gold_section exists in
the corpus and matches the regulation; gold_paragraph starts with gold_section;
evidence_quote appears verbatim (whitespace-insensitive) in that section's
regulation or interpretation text; NONE labels name the governing law.
Exits non-zero if any label is invalid.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.annotation import load_items  # noqa: E402
from cfpb.config import PROCESSED_DIR  # noqa: E402

REQUIRED = ["complaint_id", "annotator", "date", "main_grievance", "gold_regulation",
            "gold_section", "confidence", "evidence_quote", "rationale"]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def main() -> None:
    path = Path(sys.argv[1])
    chunks = pd.read_parquet(PROCESSED_DIR / "reg_chunks.parquet")
    sample_ids = set(load_items()["complaint_id"])
    sec_reg = chunks[chunks["kind"].isin(["regulation", "statute"])].groupby("section")["regulation"].first()
    sec_text = chunks.groupby("section")["text"].apply(lambda t: norm(" ".join(t)))
    problems, seen, n = [], set(), 0
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        n += 1
        r = json.loads(line)
        err = [f"missing {k}" for k in REQUIRED if k not in r]
        cid, reg, sec = r.get("complaint_id"), r.get("gold_regulation"), r.get("gold_section")
        if cid not in sample_ids:
            err.append("complaint_id not in the annotation items (sample + top-up)")
        if cid in seen:
            err.append("duplicate complaint_id")
        seen.add(cid)
        if reg not in {"E", "F", "V", "Z", "FCRA", "NONE"}:
            err.append(f"bad regulation {reg}")
        if reg == "NONE":
            if sec:
                err.append("NONE label has a section")
            if not r.get("governing_law_if_none"):
                err.append("NONE label without governing_law_if_none")
        else:
            if sec not in sec_reg.index:
                err.append(f"section {sec} not in corpus")
            elif sec_reg[sec] != reg:
                err.append(f"section {sec} belongs to Reg {sec_reg[sec]}, not {reg}")
            par = r.get("gold_paragraph")
            if par and not par.startswith(sec + "("):
                err.append(f"paragraph {par} not under {sec}")
            q = norm(r.get("evidence_quote"))
            if not q:
                err.append("missing evidence_quote")
            elif sec in sec_text.index and q not in sec_text[sec]:
                err.append("evidence_quote not verbatim in section text")
        if r.get("confidence") not in (1, 2, 3):
            err.append("confidence must be 1, 2 or 3")
        if err:
            problems.append((i, cid, err))
    for i, cid, err in problems:
        print(f"line {i} ({cid}): " + "; ".join(err))
    print(f"{n} labels checked, {len(problems)} invalid, "
          f"{len(sample_ids - seen)} of {len(sample_ids)} annotation items not yet labelled")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
