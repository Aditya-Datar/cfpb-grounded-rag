"""Parse eCFR part XML into structure-aware retrieval chunks.

Chunks follow the regulation's own structure, not fixed token windows
(CLAUDE.md Sec. 4):
  - kind="regulation": one chunk per top-level paragraph of a section
    (e.g. 1026.13(b)). A paragraph over MAX_WORDS is split at its numbered
    subparagraphs (1026.13(b)(1), (2), ...). Text before (a) is the section's
    own chunk. Only something still over 2*MAX_WORDS falls back to word windows.
  - kind="interpretation": the Official Interpretations (Supplement I),
    grouped under their headings ("13(b) ...", "Paragraph 6(a)(1)"), each
    mapped to the section/paragraph it interprets. Long groups are split
    between numbered comments.
  - kind="appendix": other appendices (model forms, procedures), grouped by
    heading.

XML layout (verified 2026-10-15 on Parts 1005, 1006, 1022, 1026):
DIV5 part > DIV6 subpart > DIV8 section (HEAD "§ 1026.13 Title.") > P/FP...;
DIV9 appendices, incl. "Supplement I to Part 10xx—Official Interpretations"
whose HD1/HD2/HD3 (or short P) headings read "Section 1026.13—Title",
"13(b) Heading", "Paragraph 13(b)(1)".
"""
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass

MAX_WORDS = 350
WS_RE = re.compile(r"\s+")
BLOCK_TAGS = {"P", "FP", "FP-1", "FP-2", "HD1", "HD2", "HD3", "NOTE", "TABLE", "GPOTABLE"}
SKIP_TAGS = {"HEAD", "CITA", "SOURCE", "AUTH", "EDNOTE", "SECAUTH", "XREF", "img"}
MARK_RE = re.compile(r"^\(([a-z]{1,2}|\d{1,3}|[ivxl]{1,6}|[A-Z])\)")
ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii",
         "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx"]
SECTION_HEAD_RE = re.compile(r"^§\s*(\d+\.\d+)\s+(.*)$")
SUPP_SECTION_RE = re.compile(r"^Section\s+(\d+\.\d+)(?![\d(])\s*[—–-]?\s*(.*)$")
SUPP_PARA_RE = re.compile(r"^(?:Paragraphs?\s+)?(\d+[a-z]?)((?:\([^()\s]{1,5}\))+)")
COMMENT_START_RE = re.compile(r"^\d+\.\s")
APPENDIX_RE = re.compile(r"^(Appendix(?:es)?\s+[A-Z]\d?(?:-[A-Z]\d?)?|Supplement\s+I)\b")


@dataclass
class Chunk:
    chunk_id: str
    regulation: str      # E, F, V, Z
    part: str            # 1026
    kind: str            # regulation | interpretation | appendix
    section: str         # 1026.13, or "1026 Appendix G" / "1026 Supplement I intro"
    paragraph: str       # most specific reference, e.g. 1026.13(b)(1)
    heading: str         # section (or appendix) heading
    text: str
    n_words: int
    source_url: str


def _text(el) -> str:
    if el.tag in ("TABLE", "GPOTABLE"):  # keep table rows readable
        rows = [" | ".join(WS_RE.sub(" ", "".join(c.itertext())).strip() for c in row)
                for row in el.iter() if row.tag in ("TR", "ROW")]
        return " ; ".join(r for r in rows if r.strip())
    return WS_RE.sub(" ", "".join(el.itertext())).strip()


def _blocks(el):
    """Text blocks of a DIV in document order, not descending into nested DIVs."""
    for child in el:
        if child.tag in SKIP_TAGS or child.tag.startswith("DIV"):
            continue
        if child.tag in BLOCK_TAGS:
            t = _text(child)
            if t:
                yield child.tag, t
        else:
            yield from _blocks(child)


def _url(el, date: str) -> str:
    meta = (el.get("hierarchy_metadata") or "").replace("&quot;", '"')
    try:
        path = json.loads(meta)["path"].replace("_SUBSTITUTE_DATE_", date)
        return "https://www.ecfr.gov" + path
    except (ValueError, KeyError):
        return ""


def _windows(text: str, size: int = MAX_WORDS) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)] or [""]


def _emit(chunks, base_id, n_words_limit=2 * MAX_WORDS, **fields):
    """Append one chunk, or word-window pieces (#1, #2 ...) if very long."""
    text = fields.pop("text")
    pieces = [text] if len(text.split()) <= n_words_limit else _windows(text)
    for k, piece in enumerate(pieces, 1):
        cid = base_id if len(pieces) == 1 else f"{base_id}#{k}"
        chunks.append(Chunk(chunk_id=cid, text=piece, n_words=len(piece.split()), **fields))


def _is_roman_here(markers: list[str], i: int) -> bool:
    """Is markers[i] (a letter like 'i', 'v', 'x') a roman numeral here?"""
    m = markers[i]
    if m not in ROMAN:
        return False
    k = ROMAN.index(m)
    prev_roman = k > 0 and i > 0 and markers[i - 1] == ROMAN[k - 1]
    next_roman = i + 1 < len(markers) and k + 1 < len(ROMAN) and markers[i + 1] == ROMAN[k + 1]
    return prev_roman or next_roman or (m == "i" and i + 1 < len(markers) and markers[i + 1] == "ii")


def parse_section(div, part: str, reg: str, date: str) -> list[Chunk]:
    head = _text(div.find("HEAD")) if div.find("HEAD") is not None else ""
    m = SECTION_HEAD_RE.match(head)
    section = m.group(1) if m else div.get("N", "")
    blocks = [t for _, t in _blocks(div)]
    if not blocks:
        return []  # [Reserved]
    base = dict(regulation=reg, part=part, kind="regulation", section=section, heading=head,
                source_url=_url(div, date))
    markers = [(MARK_RE.match(t).group(1) if MARK_RE.match(t) else None) for t in blocks]
    seq = [mk or "" for mk in markers]

    # Group blocks by top-level paragraph (a), (b), ... in sequence.
    groups, current, expected = [], ("", []), "a"
    for i, (mk, t) in enumerate(zip(markers, blocks)):
        if mk == expected and not (current[0] and _is_roman_here(seq, i)):
            groups.append(current)
            current, expected = (mk, [t]), chr(ord(expected) + 1)
        else:
            current[1].append(t)
    groups.append(current)

    chunks = []
    for letter, texts in groups:
        if not texts:
            continue
        ref = f"{section}({letter})" if letter else section
        if sum(len(t.split()) for t in texts) <= MAX_WORDS:
            _emit(chunks, f"R:{ref}", paragraph=ref, text="\n".join(texts), **base)
            continue
        # Too long: split at numbered subparagraphs (1), (2), ... in sequence.
        nxt = 2 if re.search(r"\(1\)", texts[0][:400]) else 1
        parts, cur = [], (ref, [texts[0]])
        for t in texts[1:]:
            if t.startswith(f"({nxt})"):
                parts.append(cur)
                cur, nxt = (f"{ref}({nxt})", [t]), nxt + 1
            else:
                cur[1].append(t)
        parts.append(cur)
        for pref, ptexts in parts:
            _emit(chunks, f"R:{pref}", paragraph=pref, text="\n".join(ptexts), **base)
    return chunks


def parse_supplement(div, part: str, reg: str, date: str) -> list[Chunk]:
    """Official Interpretations: group comments under their headings."""
    url = _url(div, date)
    chunks, groups = [], []
    section, ref, heading = f"{part} Supplement I intro", f"{part} Supplement I intro", "Introduction"
    cur = {"section": section, "ref": ref, "heading": heading, "texts": []}
    for tag, t in _blocks(div):
        ms, mp = SUPP_SECTION_RE.match(t), SUPP_PARA_RE.match(t)
        is_heading = tag.startswith("HD") or (len(t) < 150 and not COMMENT_START_RE.match(t))
        ma = APPENDIX_RE.match(t) if is_heading else None
        if is_heading and ms:
            section, ref, heading = ms.group(1), ms.group(1), t
        elif is_heading and mp and section.startswith(part + ".") and \
                mp.group(1) == section.split(".", 1)[1]:
            ref = f"{section}{mp.group(2)}"
        elif is_heading and ma:
            section = ref = f"{part} {ma.group(1)}"
            heading = t
        elif tag.startswith("HD"):  # subpart or other heading: keep as context
            groups.append(cur)
            cur = {"section": section, "ref": ref, "heading": heading, "texts": [t]}
            continue
        else:
            cur["texts"].append(t)
            continue
        groups.append(cur)
        cur = {"section": section, "ref": ref, "heading": heading, "texts": [t]}
    groups.append(cur)

    seen = {}
    for g in groups:
        body = [t for t in g["texts"]]
        if not any(COMMENT_START_RE.match(t) or len(t.split()) > 12 for t in body):
            continue  # heading-only group
        # Pack comments ("1. ...", "2. ...") into pieces of at most MAX_WORDS.
        pieces, cur_p, n = [], [], 0
        for t in body:
            w = len(t.split())
            if cur_p and COMMENT_START_RE.match(t) and n + w > MAX_WORDS:
                pieces.append(cur_p)
                cur_p, n = [], 0
            cur_p.append(t)
            n += w
        pieces.append(cur_p)
        for texts in pieces:
            k = seen[g["ref"]] = seen.get(g["ref"], 0) + 1
            _emit(chunks, f"I:{g['ref']}~{k}", regulation=reg, part=part, kind="interpretation",
                  section=g["section"], paragraph=g["ref"], heading=g["heading"],
                  text="\n".join(texts), source_url=url)
    return chunks


def parse_appendix(div, part: str, reg: str, date: str) -> list[Chunk]:
    head = _text(div.find("HEAD")) if div.find("HEAD") is not None else ""
    m = APPENDIX_RE.match(head)
    name = f"{part} {m.group(1)}" if m else f"{part} {div.get('N', 'appendix')}"
    blocks = [t for _, t in _blocks(div)]
    chunks, cur, n, k = [], [], 0, 0
    for t in blocks + [None]:
        if t is None or (cur and n + len(t.split()) > MAX_WORDS):
            if cur:
                k += 1
                _emit(chunks, f"A:{name}~{k}", regulation=reg, part=part, kind="appendix",
                      section=name, paragraph=name, heading=head, text="\n".join(cur),
                      source_url=_url(div, date))
            cur, n = [], 0
        if t is not None:
            cur.append(t)
            n += len(t.split())
    return chunks


def parse_part(xml_path, part: str, reg: str, date: str) -> tuple[list[Chunk], list[dict]]:
    """All chunks of a part, plus its section list (for annotators)."""
    root = ET.parse(xml_path).getroot()
    chunks, sections = [], []
    for div in root.iter():
        if div.tag == "DIV8":
            sec_chunks = parse_section(div, part, reg, date)
            chunks += sec_chunks
            head = _text(div.find("HEAD")) if div.find("HEAD") is not None else ""
            m = SECTION_HEAD_RE.match(head)
            sections.append({"regulation": reg, "part": part,
                             "section": m.group(1) if m else div.get("N", ""),
                             "title": (m.group(2) if m else head).rstrip("."),
                             "reserved": not sec_chunks, "url": _url(div, date)})
        elif div.tag == "DIV9":
            head = _text(div.find("HEAD")) if div.find("HEAD") is not None else ""
            if head.startswith("Supplement I"):
                chunks += parse_supplement(div, part, reg, date)
            else:
                chunks += parse_appendix(div, part, reg, date)
    return chunks, sections


def to_records(chunks: list[Chunk]) -> list[dict]:
    return [asdict(c) for c in chunks]
