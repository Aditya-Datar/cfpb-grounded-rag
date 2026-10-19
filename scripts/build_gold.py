"""Assemble the final gold labels from two annotators plus human adjudication.

    python scripts/build_gold.py --init      # write annotation/spot_check.md (20 agreed items to re-check)
    python scripts/build_gold.py             # build annotation/gold_final.jsonl

Inputs:
  annotation/llm_labels_claude-opus-5-5.jsonl (A), annotation/llm_labels_chatgpt.jsonl (B)
  annotation/disagreements.md   (scripts/compare_annotators.py; human fills "Final (human):")
  annotation/spot_check.md      (human fills "Check (human):")
A "Final" / "Check" entry may be:
  A or B            take that annotator's label
  OK                (spot check only) the agreed label stands
  <REG> <ref>       an explicit label, e.g. "E 1005.11(c)", "FCRA 1681i(a)(1)", "Z 1026.13", "NONE"
  initials in brackets at the end are recorded as the adjudicator, e.g. "B [AD]"
Items still undecided are reported, and the gold file is written only when none remain
(use --allow-pending to write the decided ones anyway).
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.data.split import stable_uniform  # noqa: E402

ANN = Path("annotation")
A_PATH, B_PATH = ANN / "llm_labels_claude-opus-5-5.jsonl", ANN / "llm_labels_chatgpt.jsonl"
DIS, SPOT, OUT = ANN / "disagreements.md", ANN / "spot_check.md", ANN / "gold_final.jsonl"
LABEL_RE = re.compile(r"^(E|F|V|Z|FCRA|NONE)\s*([0-9][0-9a-z.\-]*(?:\([^)]+\))*)?$")


def load(path: Path) -> dict:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["complaint_id"]: r for r in rows}


def key(r: dict) -> tuple:
    sec = r.get("gold_section") if r.get("gold_regulation") != "NONE" else None
    return (r.get("gold_regulation"), sec)


def as_label(r: dict) -> str:
    ref = r.get("gold_paragraph") or r.get("gold_section") or ""
    return f"{r['gold_regulation']} {ref}".strip()


def parse_label(text: str) -> dict | None:
    m = LABEL_RE.match(text.strip())
    if not m:
        return None
    reg, ref = m.group(1), m.group(2)
    if reg == "NONE":
        return {"gold_regulation": "NONE", "gold_section": None, "gold_paragraph": None}
    sec = re.match(r"[0-9][0-9a-z.\-]*", ref).group(0) if ref else None
    return {"gold_regulation": reg, "gold_section": sec, "gold_paragraph": ref if ref and "(" in ref else None}


def read_decisions(path: Path, field: str) -> dict:
    """complaint_id -> (decision text, adjudicator) from '## <id>' blocks."""
    out, cid = {}, None
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cid = line[3:].strip().split()[0]
        m = re.match(rf"- \*\*{field} \(human\):\*\*\s*(.*)$", line)
        if m and cid and m.group(1).strip():
            text = m.group(1).strip()
            who = re.search(r"\[([^\]]+)\]\s*$", text)
            out[cid] = (re.sub(r"\s*\[[^\]]+\]\s*$", "", text), who.group(1) if who else "")
    return out


def init_spot_check(a: dict, b: dict) -> None:
    agreed = [cid for cid in a if cid in b and key(a[cid]) == key(b[cid])]
    u = dict(zip(agreed, stable_uniform(pd.Series(agreed), "spotcheck")))
    pick = sorted(agreed, key=u.get)[:20]
    lines = ["# Human spot check: 20 items both annotators agreed on", "",
             "Read the complaint (`python scripts/reg_lookup.py --complaint <id>`) and the cited text.",
             "Write OK, or the correct label (e.g. `E 1005.11(c)`, `NONE`), after 'Check (human):',",
             "with your initials in brackets, e.g. `OK [AD]`.", ""]
    for cid in pick:
        r = a[cid]
        lines += [f"## {cid}", f"- **Agreed label:** {as_label(r)} (A conf {r['confidence']}, "
                  f"B conf {b[cid]['confidence']})", f"- **Main grievance (A):** {r['main_grievance']}",
                  f"- **Quote (A):** {r['evidence_quote']}", "- **Check (human):** ", ""]
    SPOT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {SPOT} ({len(pick)} items)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--allow-pending", action="store_true")
    args = ap.parse_args()
    a, b = load(A_PATH), load(B_PATH)
    if args.init:
        init_spot_check(a, b)
        return
    finals, spots = read_decisions(DIS, "Final"), read_decisions(SPOT, "Check")
    gold, pending, bad = [], [], []
    for cid in sorted(a):
        ra, rb = a[cid], b.get(cid)
        if rb is not None and key(ra) == key(rb):
            label, source, who = {k: ra.get(k) for k in ("gold_regulation", "gold_section", "gold_paragraph")}, "agreed", ""
            if cid in spots:
                text, who = spots[cid]
                if text.upper() != "OK":
                    label = parse_label(text) or bad.append((cid, text))
                    source = "spot_corrected"
                else:
                    source = "agreed_spot_checked"
        elif cid in finals:
            text, who = finals[cid]
            pick = {"A": ra, "B": rb}.get(text.upper())
            label = ({k: pick.get(k) for k in ("gold_regulation", "gold_section", "gold_paragraph")}
                     if pick else parse_label(text))
            if label is None:
                bad.append((cid, text))
                continue
            source = "adjudicated"
        else:
            pending.append(cid)
            continue
        if label:
            gold.append({"complaint_id": cid, **label, "source": source, "adjudicator": who,
                         "label_a": as_label(ra), "label_b": as_label(rb) if rb else None})
    for cid, text in bad:
        print(f"unparseable decision for {cid}: {text!r}")
    print(f"gold: {len(gold)} decided | pending human decision: {len(pending)} | unparseable: {len(bad)}")
    if (pending or bad) and not args.allow_pending:
        sys.exit("Not written: fill the remaining 'Final (human):' lines in annotation/disagreements.md.")
    OUT.write_text("".join(json.dumps(g, ensure_ascii=False) + "\n" for g in gold), encoding="utf-8")
    counts = pd.Series([g["gold_regulation"] for g in gold]).value_counts().to_dict()
    print(f"wrote {OUT}: {counts}")


if __name__ == "__main__":
    main()
