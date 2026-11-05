"""Build the files for the ChatGPT cross-check of the annotation (Annotator B).

    python scripts/make_chatgpt_package.py

Writes annotation/chatgpt_package/generated/ (git-ignored, regenerable):
    01_INSTRUCTIONS.md          rubric; conventions copied from the annotator skill
    02_complaints.md            all annotation items (sample + top-up), WITHOUT labels
    03_regulation_sections.md   valid section list (Regs E/F/V/Z + FCRA)
    04_reg_E_1005.md ... 07_reg_Z_1026.md   full rule text per regulation
    08_FCRA_1681.md             full FCRA statute text
    09_claude_labels.md         Annotator A's labels, uploaded ONLY in step 2
"""
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.annotation import load_items  # noqa: E402
from cfpb.config import PROCESSED_DIR, ROOT  # noqa: E402

PKG = ROOT / "annotation" / "chatgpt_package"
OUT = PKG / "generated"
SKILL = ROOT / ".claude" / "skills" / "regulation-annotator" / "SKILL.md"
CLAUDE_LABELS = ROOT / "annotation" / "llm_labels_claude-opus-5-5.jsonl"
NAMES = {"E": ("1005", "Regulation E (Electronic Fund Transfers)"),
         "F": ("1006", "Regulation F (Debt Collection Practices)"),
         "V": ("1022", "Regulation V (Fair Credit Reporting)"),
         "Z": ("1026", "Regulation Z (Truth in Lending)")}


def section_key(sec: str):
    """Sort 1026.5 < 1026.13 and 1681 < 1681a < 1681c < 1681c-1."""
    head, _, tail = sec.partition(".")
    return (head, float(tail)) if tail else (sec, 0.0)


def write_text_file(path: Path, title: str, df: pd.DataFrame, note: str) -> None:
    out = [f"# {title}", "", note, ""]
    for sec in sorted(df["section"].drop_duplicates(), key=section_key):
        sdf = df[df["section"] == sec]
        out += [f"## {sdf['heading'].iloc[0]}", ""] + list(sdf["text"]) + [""]
    path.write_text("\n".join(out), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    items = load_items()

    # 01: instructions with conventions copied from the skill (single source of truth)
    skill = SKILL.read_text(encoding="utf-8")
    conv = skill.split("## Labelling conventions", 1)[1].split("\n## Output", 1)[0]
    conv = conv.split("\n", 1)[1].strip()
    template = (PKG / "01_INSTRUCTIONS.template.md").read_text(encoding="utf-8")
    (OUT / "01_INSTRUCTIONS.md").write_text(
        template.replace("__CONVENTIONS__", conv).replace("__N_ITEMS__", str(len(items))), encoding="utf-8")

    # 02: complaints, blind (no regulation_candidate, no labels)
    lines = [f"# Complaints to label ({len(items)})", "",
             "CFPB consumer complaints, cleaned. [REDACTED] and [DATE] are privacy masks.",
             "Product/issue are what the consumer selected when filing.", ""]
    for _, r in items.iterrows():
        lines += [f"## Item {r['item']} | complaint_id {r['complaint_id']}",
                  f"- product: {r['product']} | sub_product: {r['sub_product']}",
                  f"- issue: {r['issue']} | sub_issue: {r['sub_issue']}",
                  f"- company: {r['company']}", "", r["narrative_clean"], ""]
    (OUT / "02_complaints.md").write_text("\n".join(lines), encoding="utf-8")

    # 03: section list
    shutil.copy(ROOT / "annotation" / "regulation_sections.md", OUT / "03_regulation_sections.md")

    # 04-08: full rule and statute text
    chunks = pd.read_parquet(PROCESSED_DIR / "reg_chunks.parquet")
    rule = chunks[chunks["kind"] == "regulation"]
    for n, (reg, (part, name)) in enumerate(NAMES.items(), start=4):
        write_text_file(OUT / f"0{n}_reg_{reg}_{part}.md",
                        f"{name}, 12 CFR Part {part} - rule text (eCFR as of 2026-10-13)",
                        rule[rule["regulation"] == reg],
                        "Official Interpretations (Supplement I) are not included.")
    write_text_file(OUT / "08_FCRA_1681.md",
                    "Fair Credit Reporting Act, 15 U.S.C. 1681-1681x (U.S. Code 2024 edition)",
                    chunks[chunks["kind"] == "statute"],
                    "Statutory text only; editorial and amendment notes omitted. Cite sections as e.g. 1681i.")

    # 09: Annotator A labels, compact, for step 2 only
    labels = [json.loads(line) for line in CLAUDE_LABELS.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    item_of = dict(zip(items["complaint_id"], items["item"]))
    out = ["# Annotator A labels (Claude, regulation-annotator skill)", "",
           "UPLOAD ONLY IN STEP 2, after your own blind labels are finished.", ""]
    for r in sorted(labels, key=lambda r: item_of[r["complaint_id"]]):
        ref = r["gold_paragraph"] or r["gold_section"] or ""
        out += [f"## Item {item_of[r['complaint_id']]} | complaint_id {r['complaint_id']}",
                f"- label: {r['gold_regulation']} {ref} | confidence {r['confidence']} "
                f"| runner-up {r['runner_up_section']}",
                f"- main grievance: {r['main_grievance']}",
                f"- evidence quote: {r['evidence_quote']}",
                f"- governing law if NONE: {r['governing_law_if_none']}",
                f"- rationale: {r['rationale']}", ""]
    (OUT / "09_claude_labels.md").write_text("\n".join(out), encoding="utf-8")

    for stale in ["08_claude_labels.md"]:  # file name used before the FCRA was added
        (OUT / stale).unlink(missing_ok=True)
    for f in sorted(OUT.iterdir()):
        print(f"{f.name:32s} {f.stat().st_size / 1e3:8.0f} KB")


if __name__ == "__main__":
    main()
