"""Parse saved eCFR part XML files into structured records (schema v2).

Reads:  data/parts/part-<number>.xml
Writes: data/processed/sections.jsonl
        reports/parse_report.json

Keeps ordered blocks, paragraph paths, interpretation references,
section metadata, citations, notes, and parsing quality statistics.
Paragraph paths are inferred; ambiguous transitions are flagged.
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path

PARTS = ("1005", "1026", "1022", "1006")
REGULATION = {
    "1005": "E",
    "1026": "Z",
    "1022": "V",
    "1006": "F",
}
SCHEMA_VERSION = 2
ECFR_BASE = "https://www.ecfr.gov/current/title-12"
RECORD_TYPES = {"SECTION", "APPENDIX"}
PARAGRAPH_TAGS = {
    "P",
    "P-1",
    "P-2",
    "P-3",
    "P-DASH",
    "P1",
    "P2",
    "PSPACE",
    "FP",
    "FP-1",
    "FP-2",
    "FP-DASH",
    "FP1-2",
    "FP2",
    "FP2-2",
    "FP2-3",
    "FRP",
    "FRP0",
}
HEADING_TAGS = {"HEAD", "HD", "HD1", "HD2", "HD3", "HD4", "HD5", "HD6"}
WRAPPER_TAGS = {"EXTRACT", "EXAMPLE", "NOTE", "FTNT"}
NOTE_TAGS = {"XREF", "EDNOTE", "EFFDNOTE", "AUTH", "SOURCE"}
IMAGE_TAGS = {"img", "IMG", "GPH"}
DROP_INLINE = {"FTREF"}
SECTION_RE = re.compile(r"\d{4}\.\d+[A-Za-z]?")
HEADING_PREFIX_RE = re.compile(
    r"^\s*§+\s*\d{4}\.\d+[A-Za-z]?(?:\s*[-–]\s*\d{4}\.\d+[A-Za-z]?)?\s*"
)
INTERP_SECTION_RE = re.compile(r"^\s*Section\s+(\d{4}\.\d+[A-Za-z]?)\b", re.I)
INTERP_APPENDIX_RE = re.compile(r"^\s*Appendix\s+([A-Z0-9]+)\b")
INTERP_REF_RE = re.compile(
    r"^\s*(?:Paragraph\s+)?(\d{1,4}(?:\.\d+)?(?:\([A-Za-z0-9]+\))+)"
)
COMMENT_NO_RE = re.compile(r"^\s*(\d{1,3})\.\s")


def get_text(element):
    """Whitespace-normalised text, including formatting tags, minus footnote marks."""
    parts = []

    def rec(e):
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
    return re.sub("\\s+", " ", "".join(parts)).strip()


def get_heading(element):
    for child in element:
        if child.tag == "HEAD":
            return get_text(child)
    return ""


def count_non_whitespace(s):
    return len(re.sub("\\s+", "", s))


def get_record_text(element, root=True):
    """All text of a record's element, excluding nested records and footnote marks."""
    parts = []

    def rec(e, is_root):
        if e.text:
            parts.append(e.text)
        for c in e:
            if (
                isinstance(c.tag, str)
                and c.tag not in DROP_INLINE
                and (not (c.tag.startswith("DIV") and c.get("TYPE") in RECORD_TYPES))
            ):
                rec(c, False)
            if c.tail:
                parts.append(c.tail)

    rec(element, root)
    return "".join(parts)


LEVEL_KINDS = (
    "alpha_lower",
    "digit",
    "roman_lower",
    "alpha_upper",
    "digit",
    "roman_upper",
)
ROMAN_VALUES = {
    "i": 1,
    "v": 5,
    "x": 10,
    "l": 50,
    "c": 100,
    "d": 500,
    "m": 1000,
}
ROMAN_PAIRS = [
    (1000, "m"),
    (900, "cm"),
    (500, "d"),
    (400, "cd"),
    (100, "c"),
    (90, "xc"),
    (50, "l"),
    (40, "xl"),
    (10, "x"),
    (9, "ix"),
    (5, "v"),
    (4, "iv"),
    (1, "i"),
]
RUN_RE = re.compile(r"^\s*((?:\([A-Za-z0-9]{1,6}\)\s*)+)")
SINGLE_RE = re.compile(r"\(([A-Za-z0-9]{1,6})\)")
COMPOUND_RE = re.compile(
    r"^([^()—–.;:]{1,200}?)\s*[—–]\s*((?:\([A-Za-z0-9]{1,6}\)\s*)+)"
)


def int_to_roman(n):
    out = []
    for v, s in ROMAN_PAIRS:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


def roman_to_int(s):
    if not s or any((ch not in ROMAN_VALUES for ch in s)):
        return None
    total = 0
    for i, ch in enumerate(s):
        v = ROMAN_VALUES[ch]
        nxt = ROMAN_VALUES[s[i + 1]] if i + 1 < len(s) else 0
        total += -v if nxt > v else v
    return total if int_to_roman(total) == s else None


def alpha_to_int(s):
    if not s or len(set(s)) != 1:
        return None
    return (len(s) - 1) * 26 + (ord(s[0]) - 96)


def get_marker_candidates(marker):
    if marker.isdigit():
        return {"digit": int(marker)}
    if not marker.isalpha() or not (marker.islower() or marker.isupper()):
        return {}
    suffix = "lower" if marker.islower() else "upper"
    low, out = (marker.lower(), {})
    a = alpha_to_int(low)
    if a:
        out[f"alpha_{suffix}"] = a
    roman_value = roman_to_int(low)
    if roman_value:
        out[f"roman_{suffix}"] = roman_value
    return out


def get_leading_markers(text):
    """Return (markers, remaining_text); handles '(a)(1)' runs and '(a) Heading—(1)'."""
    m = RUN_RE.match(text)
    if not m:
        return ([], text)
    markers, rest = (SINGLE_RE.findall(m.group(1)), text[m.end() :])
    while True:
        c = COMPOUND_RE.match(rest)
        if not c:
            break
        markers += SINGLE_RE.findall(c.group(2))
        rest = rest[c.end() :]
    return (markers, rest)


# Infer the usual six legal paragraph levels in document order.
class PathTracker:
    """Feed markers in document order; read back the legal paragraph path."""

    def __init__(self):
        self.stack = []

    @property
    def path(self):
        return [e[0] for e in self.stack]

    def push_run(self, markers):
        certain = True
        for marker in markers:
            marker_certain = self._push(marker)
            certain = certain and marker_certain
        return (self.path, certain)

    def _set(self, level, marker, kind, value):
        del self.stack[level:]
        self.stack.append([marker, kind, value])

    def _push(self, marker):
        marker_candidates, depth = (get_marker_candidates(marker), len(self.stack))
        # Try the next sibling at an existing level.
        for level in range(depth - 1, -1, -1):
            kind = LEVEL_KINDS[level]
            if marker_candidates.get(kind) == self.stack[level][2] + 1:
                self._set(level, marker, kind, marker_candidates[kind])
                return True
        # Otherwise, try the first child at the next level.
        if depth < len(LEVEL_KINDS) and marker_candidates.get(LEVEL_KINDS[depth]) == 1:
            self._set(depth, marker, LEVEL_KINDS[depth], 1)
            return True
        for level in range(depth - 1, -1, -1):
            if marker_candidates.get(LEVEL_KINDS[level]) == 1:
                self._set(level, marker, LEVEL_KINDS[level], 1)
                return False
        for level in range(depth - 1, -1, -1):
            kind = LEVEL_KINDS[level]
            if marker_candidates.get(kind, 0) > self.stack[level][2]:
                self._set(level, marker, kind, marker_candidates[kind])
                return False
        if depth < len(LEVEL_KINDS) and LEVEL_KINDS[depth] in marker_candidates:
            self._set(
                depth, marker, LEVEL_KINDS[depth], marker_candidates[LEVEL_KINDS[depth]]
            )
        return False


def get_path_label(path):
    return "".join((f"({p})" for p in path))


def extract_table(node):
    rows = []
    if node.tag == "GPOTABLE":
        for hd in node.iter("BOXHD"):
            rows.append([get_text(c) for c in hd.iter("CHED")])
        for row in node.iter("ROW"):
            rows.append([get_text(c) for c in row if c.tag == "ENT"])
    else:
        for row in node.iter("TR"):
            rows.append([get_text(c) for c in row if c.tag in {"TD", "TH"}])
    rows = [record for record in rows if any(record)]
    text = "\n".join((" | ".join(record) for record in rows)) or get_text(node)
    return {
        "type": "table",
        "text": text,
        "rows": rows,
    }


# Citations and notes stay outside blocks used for chunking.
def extract_blocks(element):
    """Ordered raw blocks for one record. Returns (blocks, citation, notes)."""
    blocks = []
    citation = []
    notes = []

    def add(btype, text, in_wrapper, **extra):
        blocks.append(
            {
                "type": btype,
                "text": text,
                "in_wrapper": in_wrapper,
                **extra,
            }
        )

    def visit_children(node, in_wrapper, skip_own_head):
        if node.text and node.text.strip() and (not skip_own_head):
            add("other", normalize_text(node.text), in_wrapper, xml_tag=node.tag)
        for child in node:
            if not (skip_own_head and child.tag == "HEAD"):
                visit(child, in_wrapper)
            if child.tail and child.tail.strip():
                add("other", normalize_text(child.tail), in_wrapper, xml_tag=node.tag)

    def visit(node, in_wrapper):
        tag = node.tag
        if not isinstance(tag, str):
            return
        if (
            tag.startswith("DIV")
            and node.get("TYPE") in RECORD_TYPES
            and (node is not element)
        ):
            return
        if tag == "CITA":
            t = get_text(node)
            if t:
                citation.append(t)
        elif tag in NOTE_TAGS:
            t = get_text(node)
            if t:
                notes.append({"tag": tag, "text": t})
        elif tag in ("TABLE", "GPOTABLE"):
            tb = extract_table(node)
            if tb["text"]:
                blocks.append({**tb, "in_wrapper": in_wrapper})
        elif tag in IMAGE_TAGS:
            blocks.append(
                {
                    "type": "image",
                    "text": "",
                    "in_wrapper": in_wrapper,
                    "attributes": dict(node.attrib),
                }
            )
        elif tag in PARAGRAPH_TAGS:
            t = get_text(node)
            if t:
                add("paragraph", t, in_wrapper)
        elif tag in HEADING_TAGS:
            t = get_text(node)
            if t:
                add("heading", t, in_wrapper)
        elif tag in WRAPPER_TAGS:
            if any((c.tag in PARAGRAPH_TAGS for c in node)):
                visit_children(node, True, False)
            else:
                t = get_text(node)
                if t:
                    add("paragraph", t, True)
        elif len(node):
            visit_children(node, in_wrapper, False)
        else:
            t = get_text(node)
            if t:
                add("other", t, in_wrapper, xml_tag=tag)

    visit_children(element, False, True)
    return (blocks, " ".join(citation), notes)


def normalize_text(s):
    return re.sub("\\s+", " ", s).strip()


# Each block receives the same metadata fields, including non-text blocks.
def add_block_metadata(blocks, content_type):
    """Add i, path, label, continuation, path_certain, interp_* to every block (in place)."""
    tracker = PathTracker()
    section = ref = None
    for i, block in enumerate(blocks):
        block.update(
            {
                "i": i,
                "path": [],
                "label": "",
                "continuation": False,
                "path_certain": True,
                "interp_section": None,
                "interp_ref": None,
                "comment_no": None,
            }
        )
        if block["type"] == "image":
            continue
        if content_type == "regulation":
            block["continuation"] = True
            if block["type"] == "paragraph" and (not block["in_wrapper"]):
                markers, _ = get_leading_markers(block["text"])
                if markers:
                    _, block["path_certain"] = tracker.push_run(markers)
                    block["continuation"] = False
            block["path"] = tracker.path
            block["label"] = get_path_label(block["path"])
        elif content_type == "interpretation":
            text = block["text"]
            if block["type"] == "heading":
                m = INTERP_SECTION_RE.match(text)
                if m:
                    section, ref = (m.group(1), None)
                else:
                    m = INTERP_APPENDIX_RE.match(text)
                    if m:
                        section, ref = (f"appendix-{m.group(1)}", None)
                    else:
                        m = INTERP_REF_RE.match(text)
                        if m:
                            ref = m.group(1)
            elif block["type"] == "paragraph":
                m = COMMENT_NO_RE.match(text)
                if m:
                    block["comment_no"] = int(m.group(1))
            block["interp_section"], block["interp_ref"] = (section, ref)


# Coverage is a character-count heuristic, not proof of complete extraction.
def calculate_coverage(element, heading, blocks, citation, notes):
    src = count_non_whitespace(get_record_text(element))
    out = (
        count_non_whitespace(heading)
        + count_non_whitespace(citation)
        + sum((count_non_whitespace(n["text"]) for n in notes))
    )
    for block in blocks:
        out += count_non_whitespace(block["text"].replace("|", ""))
    if src == 0:
        return 1.0
    return out / src


def parse_part(xml_path, part_number, snapshot_date):
    root = ET.parse(xml_path).getroot()
    records = []
    node_types = Counter()

    def walk(element, hierarchy):
        node_type = (element.get("TYPE") or "").strip()
        current = hierarchy
        if node_type:
            node_types[node_type] += 1
            current = hierarchy + [
                {
                    "type": node_type,
                    "number": element.get("N", ""),
                    "heading": get_heading(element),
                }
            ]
        if node_type in RECORD_TYPES:
            records.append(
                make_record(element, node_type, part_number, current, snapshot_date)
            )
        for child in element:
            if isinstance(child.tag, str):
                walk(child, current)

    walk(root, [])
    seen = Counter()
    for record in records:
        seen[record["record_id"]] += 1
        if seen[record["record_id"]] > 1:
            record["record_id"] += f"#{seen[record['record_id']]}"
    return (records, node_types, root)


def make_record(element, node_type, part_number, hierarchy, snapshot_date):
    heading, number = (get_heading(element), (element.get("N") or "").strip())
    blocks, citation, notes = extract_blocks(element)
    is_interp = any(
        (
            "official interpretation" in item["heading"].lower()
            or "supplement i" in item["heading"].lower()
            for item in hierarchy
        )
    )
    if is_interp:
        content_type = "interpretation"
    elif node_type == "APPENDIX":
        content_type = "appendix"
    else:
        content_type = "regulation"
    add_block_metadata(blocks, content_type)
    ids = SECTION_RE.findall(number) or SECTION_RE.findall(heading)
    section = ids[0] if node_type == "SECTION" and ids else None
    ident = number or re.sub("\\W+", "-", heading).strip("-").lower() or "unknown"
    subpart_item = None
    for item in reversed(hierarchy):
        if item["type"] == "SUBPART":
            subpart_item = item
            break
    in_subpart = node_type == "SECTION" and subpart_item is not None
    section_heading = heading
    if node_type == "SECTION":
        section_heading = HEADING_PREFIX_RE.sub("", heading).strip()
    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": f"12:{part_number}:{node_type}:{ident}",
        "title": 12,
        "part": part_number,
        "regulation": REGULATION.get(part_number),
        "subpart": subpart_item["number"] if in_subpart else None,
        "subpart_heading": subpart_item["heading"] if in_subpart else None,
        "section": section,
        "section_range": ids if node_type == "SECTION" and len(ids) > 1 else None,
        "heading": heading,
        "section_heading": section_heading,
        "content_type": content_type,
        "reserved": "reserved" in heading.lower(),
        "hierarchy": hierarchy,
        "blocks": blocks,
        "citation": citation,
        "notes": notes,
        "n_chars": sum((len(block["text"]) for block in blocks)),
        "coverage": round(
            calculate_coverage(element, heading, blocks, citation, notes), 4
        ),
        "source_url": f"{ECFR_BASE}/part-{part_number}"
        + (f"/section-{section}" if section else ""),
        "snapshot_date": snapshot_date,
    }


def build_part_report(records, node_types, root):
    block_types = Counter(
        (block["type"] for record in records for block in record["blocks"])
    )
    other_tags = Counter(
        (
            block.get("xml_tag")
            for record in records
            for block in record["blocks"]
            if block["type"] == "other"
        )
    )
    uncertain = [
        (record["record_id"], block["label"], block["text"][:60])
        for record in records
        for block in record["blocks"]
        if not block["path_certain"]
    ]
    raw = Counter((el.tag for el in root.iter() if isinstance(el.tag, str)))
    interp = [
        record for record in records if record["content_type"] == "interpretation"
    ]
    return {
        "records_by_type": dict(
            Counter((record["content_type"] for record in records))
        ),
        "section_ids": [
            record["section"]
            for record in records
            if record["content_type"] == "regulation"
        ],
        "subparts": sorted(
            {record["subpart"] for record in records if record["subpart"]}
        ),
        "reserved": [record["record_id"] for record in records if record["reserved"]],
        "empty_not_reserved": [
            record["record_id"]
            for record in records
            if not record["reserved"] and record["n_chars"] == 0
        ],
        "block_types": dict(block_types),
        "other_block_tags": dict(other_tags),
        "n_uncertain_paths": len(uncertain),
        "uncertain_paths_sample": uncertain[:15],
        "interpretation_blocks_with_ref": sum(
            (
                1
                for record in interp
                for block in record["blocks"]
                if block["interp_ref"]
            )
        ),
        "node_types": dict(node_types),
        "raw_tag_counts": {
            t: raw.get(t, 0)
            for t in (
                "TABLE",
                "GPOTABLE",
                "FTNT",
                "FTREF",
                "SU",
                "EXTRACT",
                "XREF",
                "EDNOTE",
                "img",
                "GPH",
            )
        },
        "low_coverage": [
            (record["record_id"], record["coverage"])
            for record in records
            if record["coverage"] < 0.95
        ],
    }


def resolve_snapshot_date(arg, snapshot_file, fallback_file):
    if arg:
        return arg
    if snapshot_file.exists():
        d = json.loads(snapshot_file.read_text()).get("snapshot_date")
        if d:
            return d
    print(
        "WARNING: no snapshot date given or recorded; using the part file's modified date",
        file=sys.stderr,
    )
    return date.fromtimestamp(fallback_file.stat().st_mtime).isoformat()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--parts-dir", type=Path, default=Path("data/parts"))
    parser.add_argument(
        "--out", type=Path, default=Path("data/processed/sections.jsonl")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("reports/parse_report.json")
    )
    parser.add_argument(
        "--snapshot-file", type=Path, default=Path("data/raw/ecfr_snapshot.json")
    )
    parser.add_argument("--snapshot-date", default=None)
    args = parser.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    snapshot_date = resolve_snapshot_date(
        args.snapshot_date, args.snapshot_file, args.parts_dir / f"part-{PARTS[0]}.xml"
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": snapshot_date,
        "parts": {},
    }
    bad = False

    with args.out.open("w", encoding="utf-8") as output:
        for part in PARTS:
            records, node_types, root = parse_part(
                args.parts_dir / f"part-{part}.xml", part, snapshot_date
            )
            for record in records:
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
            part_summary = build_part_report(records, node_types, root)
            report["parts"][part] = part_summary
            worst = min((record["coverage"] for record in records), default=1.0)
            if worst < 0.9 or part_summary["empty_not_reserved"]:
                bad = True
            print(
                f"Part {part}: {len(records)} records "
                f"{part_summary['records_by_type']}  "
                f"uncertain paths {part_summary['n_uncertain_paths']}  "
                f"worst coverage {worst:.3f}  "
                f"low-coverage {len(part_summary['low_coverage'])}  "
                f"empty-not-reserved {len(part_summary['empty_not_reserved'])}"
            )
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print("report ->", args.report)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
