"""Parse saved eCFR part XML files into section-level records (schema v2).

Reads  data/parts/part-<n>.xml   (made by xml_parser.py)
Writes data/processed/sections.jsonl   one record per SECTION / APPENDIX / Supplement I
       reports/parse_report.json       QA numbers: coverage, reserved, uncertain paths, tag counts

Schema v2 changes versus v1 (built for chunking):
  * `blocks` is the single source of truth; the redundant `paragraphs` list is gone.
  * Every text block carries a reconstructed legal `path` (e.g. ["b","1","i"]) and `label`.
    Compound markers such as "(a) Definition of error—(1) Types ..." are split correctly.
  * Interpretation (Supplement I) blocks carry `interp_section`, `interp_ref`, `comment_no`
    so comments can be grouped under the regulation paragraph they explain.
  * Clean `section` ids ("1022.33"), a `section_range` for reserved ranges, a `reserved` flag,
    `section_heading` without the "§ N" prefix, and a `regulation` letter (E/Z/V/F).
  * Appendices and the Supplement have subpart = None (the XML nests them in the last subpart).
  * Unique, non-empty `record_id`s.
  * `citation` (the CITA amendment history) and `notes` (editorial notes, cross-reference links)
    are separate fields, not blocks, so they never end up in chunk text.
  * Nothing is silently dropped: nested non-record DIVs are descended into, stray text
    and tails are kept, and a per-record coverage ratio is reported.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path

PARTS = ("1005", "1026", "1022", "1006")
REGULATION = {"1005": "E", "1026": "Z", "1022": "V", "1006": "F"}
SCHEMA_VERSION = 2
ECFR_BASE = "https://www.ecfr.gov/current/title-12"   # URL pattern not verified against the live site
RECORD_TYPES = {"SECTION", "APPENDIX"}

PARAGRAPH_TAGS = {
    "P", "P-1", "P-2", "P-3", "P-DASH", "P1", "P2", "PSPACE", "FP", "FP-1", "FP-2",
    "FP-DASH", "FP1-2", "FP2", "FP2-2", "FP2-3", "FRP", "FRP0",
}
HEADING_TAGS = {"HEAD", "HD", "HD1", "HD2", "HD3", "HD4", "HD5", "HD6"}
WRAPPER_TAGS = {"EXTRACT", "EXAMPLE", "NOTE", "FTNT"}    # text inside does not change paragraph paths
NOTE_TAGS = {"XREF", "EDNOTE", "EFFDNOTE", "AUTH", "SOURCE"}
IMAGE_TAGS = {"img", "IMG", "GPH"}
DROP_INLINE = {"FTREF"}                                 # footnote marks glue digits onto words

SECTION_RE = re.compile(r"\d{4}\.\d+[A-Za-z]?")
HEADING_PREFIX_RE = re.compile(
    r"^\s*§+\s*\d{4}\.\d+[A-Za-z]?(?:\s*[-–]\s*\d{4}\.\d+[A-Za-z]?)?\s*")
INTERP_SECTION_RE = re.compile(r"^\s*Section\s+(\d{4}\.\d+[A-Za-z]?)\b", re.I)
INTERP_APPENDIX_RE = re.compile(r"^\s*Appendix\s+([A-Z0-9]+)\b")
INTERP_REF_RE = re.compile(r"^\s*(?:Paragraph\s+)?(\d{1,4}(?:\.\d+)?(?:\([A-Za-z0-9]+\))+)")
COMMENT_NO_RE = re.compile(r"^\s*(\d{1,3})\.\s")


# ------------------------------------------------------------------ text utils
def get_text(element: ET.Element) -> str:
    """Whitespace-normalised text, including formatting tags, minus footnote marks."""
    parts: list[str] = []

    def rec(e: ET.Element) -> None:
        if e.text:
            parts.append(e.text)
        for c in e:
            if not isinstance(c.tag, str):
                pass
            elif c.tag == "BR":
                parts.append(" ")
            elif c.tag not in DROP_INLINE:
                rec(c)
            if c.tail:
                parts.append(c.tail)

    rec(element)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def get_heading(element: ET.Element) -> str:
    for child in element:
        if child.tag == "HEAD":
            return get_text(child)
    return ""


def _nonws(s: str) -> int:
    return len(re.sub(r"\s+", "", s))


def own_text(element: ET.Element, root: bool = True) -> str:
    """All text of a record's element, excluding nested records and footnote marks."""
    parts: list[str] = []

    def rec(e: ET.Element, is_root: bool) -> None:
        if e.text:
            parts.append(e.text)
        for c in e:
            if isinstance(c.tag, str) and c.tag not in DROP_INLINE and not (
                    c.tag.startswith("DIV") and c.get("TYPE") in RECORD_TYPES):
                rec(c, False)
            if c.tail:
                parts.append(c.tail)

    rec(element, root)
    return "".join(parts)


# --------------------------------------------------------------- marker logic
# CFR hierarchy: (a) (1) (i) (A) then the italic series (1) (i) (A)
LEVEL_KINDS = ("alpha_lower", "digit", "roman_lower", "alpha_upper", "digit", "roman_lower", "alpha_upper")
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
_ROMAN_PAIRS = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
                (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
RUN_RE = re.compile(r"^\s*((?:\([A-Za-z0-9]{1,6}\)\s*)+)")
SINGLE_RE = re.compile(r"\(([A-Za-z0-9]{1,6})\)")
# "(a) Definition of error—(1) Types ..."  -> the "(1)" is a nested marker after a short heading
_HEAD_CH = r"(?:[^().:]|\((?![A-Za-z0-9]{1,6}\))[^()]*\))"   # plain text or a non-marker parenthetical
COMPOUND_RE = re.compile(r"^(" + _HEAD_CH + r"{1,250}?)\s*[—–]\s*((?:\([A-Za-z0-9]{1,6}\)\s*)+)")
# "(2) Institutions covered. (i) Except as ..."  -> run-in child marker after a short italic heading.
# The heading is a single short sentence (no inner periods); the run-in marker must be able to start
# a list (value 1: "1", "i", "A", "a"), which keeps cross-references from matching.
RUNIN_RE = re.compile(r"^(" + _HEAD_CH + r"{1,160}[.:])\s*((?:\([A-Za-z0-9]{1,6}\)\s*)+)")


def _int_to_roman(n: int) -> str:
    out = []
    for v, s in _ROMAN_PAIRS:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


def _roman_to_int(s: str):
    if not s or any(ch not in _ROMAN for ch in s):
        return None
    total = 0
    for i, ch in enumerate(s):
        v = _ROMAN[ch]
        nxt = _ROMAN[s[i + 1]] if i + 1 < len(s) else 0
        total += -v if nxt > v else v
    return total if _int_to_roman(total) == s else None


def _alpha_to_int(s: str):
    return None if not s or len(set(s)) != 1 else (len(s) - 1) * 26 + (ord(s[0]) - 96)


def candidates(marker: str) -> dict:
    if marker.isdigit():
        return {"digit": int(marker)}
    if not marker.isalpha() or not (marker.islower() or marker.isupper()):
        return {}
    suffix = "lower" if marker.islower() else "upper"
    low, out = marker.lower(), {}
    if (a := _alpha_to_int(low)):
        out[f"alpha_{suffix}"] = a
    if (r := _roman_to_int(low)):
        out[f"roman_{suffix}"] = r
    return out


def leading_markers(text: str):
    """Return (markers, remaining_text); handles '(a)(1)' runs and '(a) Heading—(1)'."""
    m = RUN_RE.match(text)
    if not m:
        return [], text
    markers, rest = SINGLE_RE.findall(m.group(1)), text[m.end():]
    while True:
        c = COMPOUND_RE.match(rest)
        if not c:
            c = RUNIN_RE.match(rest)
            if c and not _starts_list(SINGLE_RE.findall(c.group(2))[0]):
                c = None
        if not c:
            break
        markers += SINGLE_RE.findall(c.group(2))
        rest = rest[c.end():]
    return markers, rest


def _starts_list(marker: str) -> bool:
    """True if the marker can be the first item of a list: (1), (i), (A), (a)."""
    return 1 in candidates(marker).values()


class PathTracker:
    """Feed markers in document order; read back the legal paragraph path.

    Each stack entry stores its own level (0 = letter, 1 = number, 2 = roman, 3 = capital letter,
    4-6 = the italic series: number, roman, capital letter), so a paragraph may skip a level, as the
    CFR sometimes does ("(c)" followed directly by "(i)"). A marker is placed by trying, in order:
      * sibling: successor of an open paragraph, deepest first: (a)->(b), (1)->(2), (iv)->(v);
      * child: first item of a list under the current paragraph;
      * skip: first item of a list one or two levels deeper (a skipped level);
      * otherwise the smallest plausible jump, reported as uncertain.
    When a marker could be either a sibling or a child ("(i)" after "(h)(4)": letter or Roman
    numeral?), `child_hint` (previous paragraph ended in ':' or a dash) picks the child, else the
    next marker decides: the reading after which the next marker fits wins ((i) then (ii) can only
    be Roman numerals; (h) then (i) then (j) is letters). Ties go to the sibling.
    """

    def __init__(self) -> None:
        self.stack: list[list] = []          # [level, marker, kind, value]

    @property
    def path(self) -> list[str]:
        return [e[1] for e in self.stack]

    def push_run(self, markers, child_hint: bool = False, lookahead: str | None = None):
        certain = True
        for i, mk in enumerate(markers):
            nxt_mk = markers[i + 1] if i + 1 < len(markers) else lookahead
            certain &= self._push(mk, child_hint or i > 0, nxt_mk)    # later markers in a run are children
        return self.path, certain

    # -- planning (no mutation) ------------------------------------------------------------
    def _next_level(self) -> int:
        return self.stack[-1][0] + 1 if self.stack else 0

    def _sibling_plan(self, cands):
        for e in reversed(self.stack):
            kind = LEVEL_KINDS[e[0]]
            if cands.get(kind) == e[3] + 1:
                return (e[0], kind, cands[kind])
        return None

    def _child_plan(self, cands):
        lvl = self._next_level()
        if lvl < len(LEVEL_KINDS) and cands.get(LEVEL_KINDS[lvl]) == 1:
            return (lvl, LEVEL_KINDS[lvl], 1)
        return None

    def _skip_plan(self, cands):
        lvl0 = self._next_level()
        for lvl in range(lvl0 + 1, min(lvl0 + 3, len(LEVEL_KINDS))):
            if cands.get(LEVEL_KINDS[lvl]) == 1:
                return (lvl, LEVEL_KINDS[lvl], 1)
        return None

    def _plan(self, cands, child_hint: bool, marker: str, lookahead):
        child, sib = self._child_plan(cands), self._sibling_plan(cands)
        if child and sib and child != sib:
            if child_hint:
                return child
            if lookahead is not None and self._fits_after(child, marker, lookahead) \
                    and not self._fits_after(sib, marker, lookahead):
                return child
            return sib
        return child or sib or self._skip_plan(cands)

    def _fits_after(self, plan, marker: str, next_marker: str) -> bool:
        t = PathTracker()
        t.stack = [e[:] for e in self.stack]
        t._place(plan[0], marker, plan[1], plan[2])
        return t._plan(candidates(next_marker), False, next_marker, None) is not None

    # -- mutation ----------------------------------------------------------------------------
    def _place(self, level: int, marker: str, kind: str, value: int) -> None:
        while self.stack and self.stack[-1][0] >= level:
            self.stack.pop()
        self.stack.append([level, marker, kind, value])

    def _push(self, marker: str, child_hint: bool = False, lookahead: str | None = None) -> bool:
        cands = candidates(marker)
        plan = self._plan(cands, child_hint, marker, lookahead)
        if plan:
            self._place(plan[0], marker, plan[1], plan[2])
            return True
        return self._fallback(marker, cands, self._next_level())

    def _fallback(self, marker: str, cands: dict, nxt: int) -> bool:
        """Nothing fits the expected sequence: pick the smallest plausible jump and flag it uncertain.

        Candidates are (a) a later value at an open level (a skipped sibling), (b) a restart at 1
        on an open level, (c) a new, deeper level starting at a later value (its predecessor was
        never seen). The smallest gap wins, which keeps "(ii)" a Roman numeral rather than the
        35th letter, and keeps the ancestors on the stack so later siblings still resolve.
        """
        best = None                                           # (gap, -level, level, kind, value)

        def offer(gap, level, kind, value):
            nonlocal best
            cand = (gap, -level, level, kind, value)
            if best is None or cand < best:
                best = cand

        for e in self.stack:
            kind = LEVEL_KINDS[e[0]]
            v = cands.get(kind)
            if v and v > e[3]:
                offer(v - e[3] - 1, e[0], kind, v)
            if v == 1 and e[3] >= 1:
                offer(0.8, e[0], kind, 1)
        for level in range(nxt, len(LEVEL_KINDS)):
            v = cands.get(LEVEL_KINDS[level])
            if v:
                offer(v - 1 + 0.5 * (level - nxt), level, LEVEL_KINDS[level], v)
        if best:
            _, _, level, kind, value = best
            self._place(level, marker, kind, value)
        return False


def label_for(path) -> str:
    return "".join(f"({p})" for p in path)


# ------------------------------------------------------------ block extraction
def _table_block(node: ET.Element) -> dict:
    rows = []
    if node.tag == "GPOTABLE":
        for hd in node.iter("BOXHD"):
            rows.append([get_text(c) for c in hd.iter("CHED")])
        for row in node.iter("ROW"):
            rows.append([get_text(c) for c in row if c.tag == "ENT"])
    else:
        for row in node.iter("TR"):
            rows.append([get_text(c) for c in row if c.tag in {"TD", "TH"}])
    rows = [r for r in rows if any(r)]
    text = "\n".join(" | ".join(r) for r in rows) or get_text(node)
    return {"type": "table", "text": text, "rows": rows}


def extract_blocks(element: ET.Element):
    """Ordered raw blocks for one record. Returns (blocks, citation, notes)."""
    blocks: list[dict] = []
    citation: list[str] = []
    notes: list[dict] = []

    def add(btype: str, text: str, in_wrapper: bool, **extra) -> None:
        blocks.append({"type": btype, "text": text, "in_wrapper": in_wrapper, **extra})

    def visit_children(node: ET.Element, in_wrapper: bool, skip_own_head: bool) -> None:
        if node.text and node.text.strip() and not skip_own_head:
            add("other", get_text_of_str(node.text), in_wrapper, xml_tag=node.tag)
        for child in node:
            if not (skip_own_head and child.tag == "HEAD"):
                visit(child, in_wrapper)
            if child.tail and child.tail.strip():
                add("other", get_text_of_str(child.tail), in_wrapper, xml_tag=node.tag)

    def visit(node: ET.Element, in_wrapper: bool) -> None:
        tag = node.tag
        if not isinstance(tag, str):
            return
        if tag.startswith("DIV") and node.get("TYPE") in RECORD_TYPES and node is not element:
            return                                      # gets its own record
        if tag == "CITA":
            if (t := get_text(node)):
                citation.append(t)
        elif tag in NOTE_TAGS:
            if (t := get_text(node)):
                notes.append({"tag": tag, "text": t})
        elif tag in ("TABLE", "GPOTABLE"):
            tb = _table_block(node)
            if tb["text"]:
                blocks.append({**tb, "in_wrapper": in_wrapper})
        elif tag in IMAGE_TAGS:
            blocks.append({"type": "image", "text": "", "in_wrapper": in_wrapper, "attributes": dict(node.attrib)})
        elif tag in PARAGRAPH_TAGS:
            if (t := get_text(node)):
                add("paragraph", t, in_wrapper)
        elif tag in HEADING_TAGS:
            if (t := get_text(node)):
                add("heading", t, in_wrapper)
        elif tag in WRAPPER_TAGS:
            if any(c.tag in PARAGRAPH_TAGS for c in node):
                visit_children(node, True, False)
            elif (t := get_text(node)):                  # e.g. <FTNT><SU>1</SU>text</FTNT>
                add("paragraph", t, True)
        elif len(node):
            visit_children(node, in_wrapper, False)     # nested DIVs, unknown containers
        elif (t := get_text(node)):
            add("other", t, in_wrapper, xml_tag=tag)

    visit_children(element, False, True)
    return blocks, " ".join(citation), notes


def get_text_of_str(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------- path / interp labels
def _finish_blocks(blocks: list[dict], content_type: str) -> None:
    """Add i, path, label, continuation, path_certain, interp_* to every block (in place)."""
    tracker = PathTracker()
    section = ref = None
    prev_text = ""                       # last in-text paragraph; a trailing ':' predicts a child list
    upcoming: list = [None] * len(blocks)    # first marker of the next numbered paragraph, per block
    if content_type == "regulation":
        later = None
        for j in range(len(blocks) - 1, -1, -1):
            upcoming[j] = later
            bj = blocks[j]
            if bj["type"] == "paragraph" and not bj["in_wrapper"]:
                mk, _ = leading_markers(bj["text"])
                if mk:
                    later = mk[0]
    for i, b in enumerate(blocks):
        b.update(i=i, path=[], label="", continuation=False, path_certain=True,
                 interp_section=None, interp_ref=None, comment_no=None)
        if b["type"] == "image":
            continue
        if content_type == "regulation":
            b["continuation"] = True
            if b["type"] == "paragraph" and not b["in_wrapper"]:
                markers, _ = leading_markers(b["text"])
                if markers:
                    hint = prev_text.rstrip().endswith((":", "—", "–"))
                    _, b["path_certain"] = tracker.push_run(markers, hint, upcoming[i])
                    b["continuation"] = False
                prev_text = b["text"]
            b["path"] = tracker.path
            b["label"] = label_for(b["path"])
        elif content_type == "interpretation":
            text = b["text"]
            if b["type"] == "heading":
                if (m := INTERP_SECTION_RE.match(text)):
                    section, ref = m.group(1), None
                elif (m := INTERP_APPENDIX_RE.match(text)):
                    section, ref = f"appendix-{m.group(1)}", None
                elif (m := INTERP_REF_RE.match(text)):
                    ref = m.group(1)
            elif b["type"] == "paragraph" and (m := COMMENT_NO_RE.match(text)):
                b["comment_no"] = int(m.group(1))
            b["interp_section"], b["interp_ref"] = section, ref


def _coverage(element: ET.Element, heading: str, blocks, citation: str, notes) -> float:
    src = _nonws(own_text(element))
    out = _nonws(heading) + _nonws(citation) + sum(_nonws(n["text"]) for n in notes)
    for b in blocks:
        out += _nonws(b["text"].replace("|", ""))
    return 1.0 if src == 0 else out / src


# ------------------------------------------------------------------ parsing
def parse_part(xml_path: Path, part_number: str, snapshot_date: str):
    root = ET.parse(xml_path).getroot()
    records: list[dict] = []
    node_types: Counter = Counter()

    def walk(element: ET.Element, hierarchy: list[dict]) -> None:
        node_type = (element.get("TYPE") or "").strip()
        current = hierarchy
        if node_type:
            node_types[node_type] += 1
            current = hierarchy + [{"type": node_type, "number": element.get("N", ""),
                                    "heading": get_heading(element)}]
        if node_type in RECORD_TYPES:
            records.append(_make_record(element, node_type, part_number, current, snapshot_date))
        for child in element:
            if isinstance(child.tag, str):
                walk(child, current)

    walk(root, [])
    seen: Counter = Counter()
    for r in records:                                      # ensure unique ids
        seen[r["record_id"]] += 1
        if seen[r["record_id"]] > 1:
            r["record_id"] += f"#{seen[r['record_id']]}"
    return records, node_types, root


def _make_record(element, node_type, part_number, hierarchy, snapshot_date) -> dict:
    heading, number = get_heading(element), (element.get("N") or "").strip()
    blocks, citation, notes = extract_blocks(element)

    is_interp = any("official interpretation" in h["heading"].lower() or
                    "supplement i" in h["heading"].lower() for h in hierarchy)
    content_type = "interpretation" if is_interp else "appendix" if node_type == "APPENDIX" else "regulation"
    _finish_blocks(blocks, content_type)

    ids = SECTION_RE.findall(number) or SECTION_RE.findall(heading)
    section = ids[0] if (node_type == "SECTION" and ids) else None
    ident = number or re.sub(r"\W+", "-", heading).strip("-").lower() or "unknown"
    subpart_item = next((h for h in reversed(hierarchy) if h["type"] == "SUBPART"), None)
    in_subpart = node_type == "SECTION" and subpart_item is not None
    section_heading = HEADING_PREFIX_RE.sub("", heading).strip() if node_type == "SECTION" else heading

    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": f"12:{part_number}:{node_type}:{ident}",
        "title": 12, "part": part_number, "regulation": REGULATION.get(part_number),
        "subpart": subpart_item["number"] if in_subpart else None,
        "subpart_heading": subpart_item["heading"] if in_subpart else None,
        "section": section,
        "section_range": ids if (node_type == "SECTION" and len(ids) > 1) else None,
        "heading": heading, "section_heading": section_heading,
        "content_type": content_type,
        "reserved": "reserved" in heading.lower(),
        "hierarchy": hierarchy,
        "blocks": blocks,
        "citation": citation, "notes": notes,
        "n_chars": sum(len(b["text"]) for b in blocks),
        "coverage": round(_coverage(element, heading, blocks, citation, notes), 4),
        "source_url": f"{ECFR_BASE}/part-{part_number}" + (f"/section-{section}" if section else ""),
        "snapshot_date": snapshot_date,
    }


# ---------------------------------------------------------------------- QA
def part_report(records, node_types, root) -> dict:
    block_types = Counter(b["type"] for r in records for b in r["blocks"])
    other_tags = Counter(b.get("xml_tag") for r in records for b in r["blocks"] if b["type"] == "other")
    uncertain = [(r["record_id"], b["label"], b["text"][:60]) for r in records for b in r["blocks"]
                 if not b["path_certain"]]
    raw = Counter(el.tag for el in root.iter() if isinstance(el.tag, str))
    interp = [r for r in records if r["content_type"] == "interpretation"]
    return {
        "records_by_type": dict(Counter(r["content_type"] for r in records)),
        "section_ids": [r["section"] for r in records if r["content_type"] == "regulation"],
        "subparts": sorted({r["subpart"] for r in records if r["subpart"]}),
        "reserved": [r["record_id"] for r in records if r["reserved"]],
        "empty_not_reserved": [r["record_id"] for r in records if not r["reserved"] and r["n_chars"] == 0],
        "block_types": dict(block_types),
        "other_block_tags": dict(other_tags),
        "n_uncertain_paths": len(uncertain), "uncertain_paths_sample": uncertain[:15],
        "interpretation_blocks_with_ref": sum(1 for r in interp for b in r["blocks"] if b["interp_ref"]),
        "node_types": dict(node_types),
        "raw_tag_counts": {t: raw.get(t, 0) for t in
                           ("TABLE", "GPOTABLE", "FTNT", "FTREF", "SU", "EXTRACT", "XREF", "EDNOTE", "img", "GPH")},
        "low_coverage": [(r["record_id"], r["coverage"]) for r in records if r["coverage"] < 0.95],
    }


def resolve_snapshot_date(arg, snapshot_file: Path, fallback_file: Path) -> str:
    if arg:
        return arg
    if snapshot_file.exists():
        d = json.loads(snapshot_file.read_text()).get("snapshot_date")
        if d:
            return d
    print("WARNING: no snapshot date given or recorded; using the part file's modified date", file=sys.stderr)
    return date.fromtimestamp(fallback_file.stat().st_mtime).isoformat()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--parts-dir", type=Path, default=Path("data/parts"))
    ap.add_argument("--out", type=Path, default=Path("data/processed/sections.jsonl"))
    ap.add_argument("--report", type=Path, default=Path("reports/parse_report.json"))
    ap.add_argument("--snapshot-file", type=Path, default=Path("data/raw/ecfr_snapshot.json"))
    ap.add_argument("--snapshot-date", default=None)
    args = ap.parse_args(argv)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    snapshot_date = resolve_snapshot_date(args.snapshot_date, args.snapshot_file, args.parts_dir / f"part-{PARTS[0]}.xml")

    report, bad = {"schema_version": SCHEMA_VERSION, "snapshot_date": snapshot_date, "parts": {}}, False
    with args.out.open("w", encoding="utf-8") as fh:
        for part in PARTS:
            records, node_types, root = parse_part(args.parts_dir / f"part-{part}.xml", part, snapshot_date)
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            rep = report["parts"][part] = part_report(records, node_types, root)
            worst = min((r["coverage"] for r in records), default=1.0)
            bad |= worst < 0.9 or bool(rep["empty_not_reserved"])
            print(f"Part {part}: {len(records)} records {rep['records_by_type']}  "
                  f"uncertain paths {rep['n_uncertain_paths']}  worst coverage {worst:.3f}  "
                  f"low-coverage {len(rep['low_coverage'])}  empty-not-reserved {len(rep['empty_not_reserved'])}")
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print("report ->", args.report)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())