"""Fair Credit Reporting Act (15 U.S.C. 1681-1681x) as a statute corpus.

Added 2026-10-15 (team decision): 64% of the annotated complaints fell outside
Regs E/Z/V/F, and 36 of those were governed by the FCRA statute itself (credit
bureau disputes, identity-theft blocks, permissible purpose), which Reg V does
not implement.

Source: U.S. Code 2024 edition (current through 2025-01-06), GovInfo HTML of
Title 15, Chapter 41, Subchapter III. Each section starts with a
"documentid:15_<section>" comment; the law text sits between "field-start:statute"
and "field-end:statute" (editorial and amendment notes after it are skipped).
Headings: h3.section-head, h4.subsection-head "(a) ...", h4.paragraph-head
"(1) ...", h4.subparagraph-head "(A) ...", with text in p.statutory-body*.
"""
import html
import re
import urllib.request
from pathlib import Path

from cfpb.regs.parse import MAX_WORDS, Chunk, _emit

URL = ("https://www.govinfo.gov/content/pkg/USCODE-2024-title15/html/"
       "USCODE-2024-title15-chap41-subchapIII.htm")
FILENAME = "USCODE-2024-title15-chap41-subchapIII.htm"
SECTION_URL = "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title15-section{}"

TAG_RE = re.compile(r'<(h3|h4|p)\b[^>]*class="([^"]+)"[^>]*>(.*?)</\1>', re.S)
STRIP_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
SUBSECTION_RE = re.compile(r"\(([a-z]{1,2})\)")
PARAGRAPH_RE = re.compile(r"\((\d+)\)")


def fetch(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / FILENAME
    if not path.exists():
        req = urllib.request.Request(URL, headers={"User-Agent": "csci544-group36-cfpb-research/0.1"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            path.write_bytes(resp.read())
    return path


def _clean(fragment: str) -> str:
    return WS_RE.sub(" ", html.unescape(STRIP_RE.sub("", fragment))).strip()


def _sections(text: str):
    """Yield (section_number, heading, [(css_class, text), ...]) for the law text only."""
    for block in re.split(r"<!-- documentid:15_", text)[1:]:
        sec = block.split()[0]
        if not sec.startswith("1681"):
            continue
        head = re.search(r'<h3 class="section-head">(.*?)</h3>', block, re.S)
        statute = re.search(r"field-start:statute -->(.*?)<!-- field-end:statute", block, re.S)
        heading = _clean(head.group(1)) if head else f"§{sec}"
        items = []
        if statute:
            items = [(cls, _clean(body)) for _, cls, body in TAG_RE.findall(statute.group(1))]
            items = [(c, t) for c, t in items if t]
        yield sec, heading, items


def parse_fcra(path: Path) -> tuple[list[Chunk], list[dict]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks, sections = [], []
    for sec, heading, items in _sections(text):
        title = re.sub(r"^§\s*\d+[a-z]*(?:[-–]\d+)?\.\s*", "", heading)
        repealed = not items or title.lower().startswith(("repealed", "omitted"))
        sections.append({"regulation": "FCRA", "part": "15 USC 1681", "section": sec,
                         "title": title.rstrip("."), "reserved": repealed,
                         "url": SECTION_URL.format(sec)})
        if repealed:
            continue
        base = dict(regulation="FCRA", part="15 USC 1681", kind="statute", section=sec,
                    heading=heading, source_url=SECTION_URL.format(sec))

        # Group by subsection (a), (b), ...; text before the first is the section's own chunk.
        groups, cur = [], ("", [])
        for cls, t in items:
            m = SUBSECTION_RE.match(t) if cls == "subsection-head" else None
            if m:
                groups.append(cur)
                cur = (m.group(1), [(cls, t)])
            else:
                cur[1].append((cls, t))
        groups.append(cur)

        for letter, group in groups:
            if not group:
                continue
            ref = f"{sec}({letter})" if letter else sec
            if sum(len(t.split()) for _, t in group) <= MAX_WORDS:
                _emit(chunks, f"S:{ref}", paragraph=ref, text="\n".join(t for _, t in group), **base)
                continue
            # Long subsection: split at its paragraph headings "(1) ...", "(2) ...".
            parts, pref, ptexts = [], ref, []
            for cls, t in group:
                pm = PARAGRAPH_RE.match(t) if cls == "paragraph-head" else None
                if pm and ptexts:
                    parts.append((pref, ptexts))
                    pref, ptexts = f"{ref}({pm.group(1)})", [t]
                else:
                    ptexts.append(t)
            parts.append((pref, ptexts))
            # A first piece that is only the subsection heading joins the next piece.
            if len(parts) > 1 and sum(len(t.split()) for t in parts[0][1]) < 20:
                parts[1] = (parts[1][0], parts[0][1] + parts[1][1])
                parts = parts[1:]
            for pr, pt in parts:
                _emit(chunks, f"S:{pr}", paragraph=pr, text="\n".join(pt), **base)
    return chunks, sections
