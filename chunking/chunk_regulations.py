"""Split parsed regulation sections into retrieval chunks.

Reads:  data/processed/sections.jsonl and the FCRA source HTML
Writes: data/processed/chunks.jsonl

A section whose chunk text fits in MAX_CHARS stays one chunk. A longer
section is split at paragraph boundaries, going one level deeper only
where a paragraph is still too long. Every chunk starts with the section
heading and the intro text of each parent paragraph, so a chunk for
(c)(2) also carries the words of (c).

`embed_text` is the text to embed for search. It equals `text`, except when
`text` is over the embedding model's token limit: then each parent intro is
shortened to its heading, so the model still sees the chunk's own words.
Needs the `tokenizers` package and downloads the model's tokenizer once.

The default corpus also contains the Fair Credit Reporting Act (FCRA), which
is in scope but is not part of eCFR Title 12. Pass --no-fcra to reproduce the
four-regulation-only corpus for an ablation.
"""

import argparse
import functools
import json
import re
import statistics
import sys
from pathlib import Path

from parse_regulations import COMPOUND_RE, PARTS, RUN_RE, RUNIN_RE, SINGLE_RE, candidates, leading_markers

CHUNKING_DIR = Path(__file__).resolve().parent
REPO_ROOT = CHUNKING_DIR.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Chunk size limit. 1400 keeps chunks within all-mpnet-base-v2's 384 tokens, except
# for chunks that cannot be split further (see CLAUDE_PROGRESS.md, 2026-10-14).
MAX_CHARS = 1400
EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"
EMBED_MAX_TOKENS = 384  # max_seq_length in the model's sentence_bert_config.json
FCRA_FILENAME = "USCODE-2024-title15-chap41-subchapIII.htm"
DEFAULT_SECTIONS_PATH = CHUNKING_DIR / "data" / "processed" / "sections.jsonl"
DEFAULT_OUT_PATH = CHUNKING_DIR / "data" / "processed" / "chunks.jsonl"
DEFAULT_FCRA_PATH = REPO_ROOT / "data" / "raw" / "fcra" / FCRA_FILENAME
# A heading ends at the first dash, or at a period followed by a space ("1026.20" does not count).
HEADING_END_RE = re.compile(r"[—–]|\.(?=\s|$)")


@functools.lru_cache(maxsize=None)
def load_token_counter(model=EMBED_MODEL):
    """Token count as the embedding model sees it: special tokens included, no padding or truncation."""
    try:
        from tokenizers import Tokenizer
    except ImportError:
        raise SystemExit(
            "chunk_regulations.py needs the 'tokenizers' package to build embed_text.\n"
            "Install it in the repo venv:\n"
            "  .venv/bin/python -m pip install tokenizers        (macOS/Linux)\n"
            "  .venv\\Scripts\\python -m pip install tokenizers    (Windows)"
        ) from None
    try:
        tokenizer = Tokenizer.from_pretrained(model)
    except Exception as e:
        raise SystemExit(f"Could not load the {model} tokenizer from Hugging Face: {e}") from None
    # The shipped tokenizer.json pads and truncates to 128 tokens, which would hide long chunks.
    tokenizer.no_truncation()
    tokenizer.no_padding()
    return lambda text: len(tokenizer.encode(text).ids)


def heading_only(text):
    """'(2) Timing and content. Except as ...' -> '(2) Timing and content.'"""
    m = HEADING_END_RE.search(text)
    return text[: m.end()].strip() if m else text


class Node:
    """One paragraph in a section's outline, e.g. (c) or (c)(2)."""

    def __init__(self, path):
        self.path = path
        self.pieces = []  # (order, text, path_certain) written directly under this paragraph
        self.children = {}  # path -> Node, in document order

    def subtree_pieces(self):
        out = list(self.pieces)
        for child in self.children.values():
            out += child.subtree_pieces()
        return sorted(out)


def split_at_markers(text):
    """Split a block's text where each leading marker starts.

    '(c) Time limits—(1) Ten-day period.' -> ['(c) Time limits—', '(1) Ten-day period.']
    '(b) Record retention. (1) Any person' -> ['(b) Record retention. ', '(1) Any person']
    A marker with no words of its own stays with the next one:
    '(a)(1) “Access device” means' -> ['', '(a)(1) “Access device” means']
    """
    m = RUN_RE.match(text)
    if not m:
        return [text]
    starts = [m.start(1) + s.start() for s in SINGLE_RE.finditer(m.group(1))]
    offset = m.end()
    # Same loop as parse_regulations.leading_markers, but keeping positions.
    while True:
        c = COMPOUND_RE.match(text[offset:])
        if not c:
            # Heading ending in '.' or ':', then a marker that can start a list: (1), (i), (A), (a).
            c = RUNIN_RE.match(text[offset:])
            if c and 1 not in candidates(SINGLE_RE.findall(c.group(2))[0]).values():
                c = None
        if not c:
            break
        starts += [offset + c.start(2) + s.start() for s in SINGLE_RE.finditer(c.group(2))]
        offset += c.end()
    starts[0] = 0
    segments = [text[a:b] for a, b in zip(starts, starts[1:] + [len(text)])]
    for j in range(len(segments) - 1):
        if not SINGLE_RE.sub("", segments[j]).strip():
            segments[j + 1] = segments[j] + segments[j + 1]
            segments[j] = ""
    return segments


def build_tree(blocks):
    root = Node(())
    nodes = {(): root}

    def node_for(path):
        if path not in nodes:
            nodes[path] = node_for(path[:-1]).children[path] = Node(path)
        return nodes[path]

    for block in blocks:
        if not block["text"]:
            continue
        path, certain = tuple(block["path"]), block["path_certain"]
        markers = [] if block["continuation"] else leading_markers(block["text"])[0]
        k = len(markers)
        segments = split_at_markers(block["text"]) if k > 1 else []
        # A fused block like '(c) Intro—(1) Text' feeds both (c) and (c)(1).
        if len(segments) == k > 1 and list(path[-k:]) == markers:
            for j, segment in enumerate(segments):
                if segment.strip():
                    node_for(path[: len(path) - k + 1 + j]).pieces.append(
                        ((block["i"], j), segment.strip(), certain)
                    )
        else:
            # Unmarked blocks stay with the paragraph before them.
            node_for(path).pieces.append(((block["i"], 0), block["text"], certain))
    return root


def chunk_record(record, max_chars=MAX_CHARS, count_tokens=None):
    """Chunks for one regulation record, as a list of dicts in document order.

    count_tokens defaults to the embedding model's tokenizer; tests may pass their own.
    """
    count_tokens = count_tokens or load_token_counter()
    heading_line = record["heading"]
    chunks = []

    def make_text(context, body):
        return "\n".join([heading_line] + [p[1] for p in context + body])

    def make_embed_text(context, body, text):
        if count_tokens(text) <= EMBED_MAX_TOKENS:
            return text
        return "\n".join([heading_line] + [heading_only(p[1]) for p in context] + [p[1] for p in body])

    def visit(node, context):
        body = node.subtree_pieces()
        text = make_text(context, body)
        if len(text) > max_chars and node.children:
            # Too long: this paragraph's own words become context for each child.
            for child in node.children.values():
                visit(child, context + sorted(node.pieces))
            return
        chunks.append((node, context, body, text))

    root = build_tree(record["blocks"])
    visit(root, [])
    check_coverage(record, root, chunks)
    return [to_output(record, *c, make_embed_text(c[1], c[2], c[3])) for c in chunks]


def to_output(record, node, context, body, text, embed_text):
    section = record["section"]
    label = "".join(f"({p})" for p in node.path)
    certain = all(p[2] for p in context + body)
    # Anchors look like #p-1005.11(c)(2); only link one when the path is trusted.
    anchor = f"#p-{section}{label}" if label and certain else ""
    return {
        "chunk_id": f"12-{record['part']}-{section}-" + ("-".join(node.path) or "all"),
        "part": record["part"],
        "section": section,
        "paragraph": label,
        "heading": record["section_heading"],
        "text": text,
        "source_url": record["source_url"] + anchor,
        "embed_text": embed_text,
        "content_type": record["content_type"],
        "regulation": record["regulation"],
        "path_certain": certain,
        "n_chars": len(text),
        "record_id": record["record_id"],
    }


def _fcra_fits(heading, body, max_chars, count_tokens):
    text = "\n".join([heading, body])
    return len(text) <= max_chars and count_tokens(text) <= EMBED_MAX_TOKENS


def _split_fcra_block(heading, block, max_chars, count_tokens):
    """Split an oversized statutory block at sentences, then word boundaries."""
    if _fcra_fits(heading, block, max_chars, count_tokens):
        return [block]
    sentences = re.split(r"(?<=[.;:])\s+(?=(?:\([A-Za-z0-9]+\)\s*)?[A-Z])", block)
    units = sentences if len(sentences) > 1 else block.split()
    joiner = " "
    pieces, current = [], []
    for unit in units:
        candidate = joiner.join(current + [unit])
        if current and not _fcra_fits(heading, candidate, max_chars, count_tokens):
            pieces.append(joiner.join(current))
            current = []
        # A single sentence can still be too large. Fall back to words without
        # dropping or truncating any statute text.
        if not current and not _fcra_fits(heading, unit, max_chars, count_tokens) and " " in unit:
            pieces.extend(_split_fcra_block(heading, unit, max_chars, count_tokens))
        else:
            current.append(unit)
    if current:
        pieces.append(joiner.join(current))
    return pieces or [block]


def _pack_fcra_text(heading, body, max_chars, count_tokens):
    """Pack FCRA HTML blocks within the character and embedding limits.

    The FCRA parser emits one line per structural HTML block. Packing those
    lines preserves subsection/paragraph boundaries. Oversized statutory-body
    blocks split at sentence boundaries, with a word-boundary fallback.
    """
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    lines = [piece for line in lines for piece in _split_fcra_block(
        heading, line, max_chars, count_tokens
    )]
    pieces, current = [], []
    for line in lines:
        candidate_body = "\n".join(current + [line])
        if current and not _fcra_fits(heading, candidate_body, max_chars, count_tokens):
            pieces.append("\n".join([heading] + current))
            current = []
        current.append(line)
    if current:
        pieces.append("\n".join([heading] + current))
    return pieces or [heading]


def fcra_to_output(chunk, max_chars=MAX_CHARS, count_tokens=None):
    """Convert one ``cfpb.regs.fcra`` chunk to the fixed JSONL schema."""
    # Keep this argument parallel with chunk_record and force tokenizer setup
    # during a real corpus build, even though FCRA chunks have no repeated
    # parent context that can be shortened for embed_text.
    count_tokens = count_tokens or load_token_counter()
    texts = _pack_fcra_text(chunk.heading, chunk.text, max_chars, count_tokens)
    relative_paragraph = chunk.paragraph.removeprefix(chunk.section)
    raw_suffix = relative_paragraph or "all"
    suffix = re.sub(r"[^A-Za-z0-9]+", "-", raw_suffix).strip("-") or "all"
    if "#" in chunk.chunk_id:
        suffix += "-window-" + chunk.chunk_id.rsplit("#", 1)[1]
    outputs = []
    for i, text in enumerate(texts, 1):
        piece_suffix = suffix if len(texts) == 1 else f"{suffix}-piece-{i}"
        outputs.append({
            "chunk_id": f"15-fcra-{chunk.section}-{piece_suffix}",
            "part": "FCRA",
            "section": chunk.section,
            "paragraph": relative_paragraph,
            "heading": re.sub(r"^§\s*\S+\.?\s*", "", chunk.heading),
            "text": text,
            "source_url": chunk.source_url,
            "embed_text": text,
            "content_type": "statute",
            "regulation": "FCRA",
            "path_certain": True,
            "n_chars": len(text),
            "record_id": f"15:FCRA:STATUTE:{chunk.section}",
        })
    return outputs


def load_fcra_chunks(path=DEFAULT_FCRA_PATH, max_chars=MAX_CHARS, count_tokens=None, fetch_missing=True):
    """Parse FCRA HTML and return chunks in the fixed JSONL corpus schema."""
    from cfpb.regs.fcra import fetch, parse_fcra

    path = Path(path)
    if not path.exists():
        if not fetch_missing:
            raise FileNotFoundError(path)
        path = fetch(path.parent)
    source_chunks, _ = parse_fcra(path)
    outputs = []
    for chunk in source_chunks:
        outputs.extend(fcra_to_output(chunk, max_chars, count_tokens))
    return outputs


def check_coverage(record, root, chunks):
    """Every piece of text is a chunk body exactly once, or context for split parents."""
    in_body, in_context = [], set()
    for _, context, body, _ in chunks:
        in_body += [p[0] for p in body]
        in_context |= {p[0] for p in context}
    all_pieces = root.subtree_pieces()
    for order, text, _ in all_pieces:
        n = in_body.count(order)
        if n > 1 or (n == 0 and order not in in_context):
            raise AssertionError(f"{record['record_id']}: piece {order} lost or duplicated: {text[:60]}")

    def squash(s):
        return re.sub(r"\s+", "", s)

    if squash("".join(p[1] for p in all_pieces)) != squash("".join(b["text"] for b in record["blocks"])):
        raise AssertionError(f"{record['record_id']}: block text changed while splitting")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sections", type=Path, default=DEFAULT_SECTIONS_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_PATH)
    parser.add_argument("--parts", nargs="+", default=list(PARTS))
    parser.add_argument(
        "--max-chars", type=int, default=MAX_CHARS, help=f"chunk size limit in characters (default {MAX_CHARS})"
    )
    parser.add_argument(
        "--fcra-html", type=Path, default=DEFAULT_FCRA_PATH,
        help="FCRA source HTML; downloaded from GovInfo if missing",
    )
    parser.add_argument(
        "--no-fcra", action="store_true",
        help="exclude the FCRA statute (four-regulation ablation)",
    )
    parser.add_argument("--show", metavar="SECTION", help="print every chunk of one section, e.g. 1005.11")
    args = parser.parse_args(argv)
    count_tokens = load_token_counter()  # fail early if the tokenizer is unavailable

    chunks = []
    with args.sections.open(encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            if (
                record["part"] in args.parts
                and record["content_type"] == "regulation"
                and not record["reserved"]
            ):
                chunks += chunk_record(record, args.max_chars, count_tokens)

    if not args.no_fcra:
        chunks += load_fcra_chunks(args.fcra_html, args.max_chars, count_tokens)

    ids = [c["chunk_id"] for c in chunks]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise AssertionError(f"duplicate chunk_ids: {duplicates[:10]}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as out:
        for chunk in chunks:
            out.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"max chars: {args.max_chars}")
    for part in args.parts:
        mine = [c for c in chunks if c["part"] == part]
        if not mine:
            continue
        sizes = [c["n_chars"] for c in mine]
        sections = {c["section"] for c in mine}
        whole = sum(1 for c in mine if not c["paragraph"])
        print(
            f"Part {part}: {len(mine)} chunks from {len(sections)} sections "
            f"({whole} kept whole)  chars min {min(sizes)} median {statistics.median(sizes):.0f} "
            f"max {max(sizes)}  over {args.max_chars}: {sum(s > args.max_chars for s in sizes)}  "
            f"uncertain paths: {sum(not c['path_certain'] for c in mine)}"
        )
    fcra = [c for c in chunks if c["regulation"] == "FCRA"]
    if fcra:
        sizes = [c["n_chars"] for c in fcra]
        print(
            f"FCRA: {len(fcra)} chunks from {len({c['section'] for c in fcra})} sections  "
            f"chars min {min(sizes)} median {statistics.median(sizes):.0f} max {max(sizes)}  "
            f"over {args.max_chars}: {sum(s > args.max_chars for s in sizes)}"
        )
    over_text = sum(count_tokens(c["text"]) > EMBED_MAX_TOKENS for c in chunks)
    over_embed = sum(count_tokens(c["embed_text"]) > EMBED_MAX_TOKENS for c in chunks)
    shortened = sum(c["embed_text"] != c["text"] for c in chunks)
    print(
        f"over {EMBED_MAX_TOKENS} tokens ({EMBED_MODEL}): text {over_text}, embed_text {over_embed}  "
        f"(embed_text shortened for {shortened} chunks)"
    )
    print("chunks ->", args.out)

    if args.show:
        for chunk in (c for c in chunks if c["section"] == args.show):
            print(f"\n=== {chunk['chunk_id']}  ({chunk['n_chars']} chars)  {chunk['source_url']}")
            print(chunk["text"])


if __name__ == "__main__":
    main()
