"""Split parsed regulation sections into retrieval chunks.

Reads:  data/processed/sections.jsonl
Writes: data/processed/chunks.jsonl

A section whose chunk text fits in MAX_CHARS stays one chunk. A longer
section is split at paragraph boundaries, going one level deeper only
where a paragraph is still too long. Every chunk starts with the section
heading and the intro text of each parent paragraph, so a chunk for
(c)(2) also carries the words of (c).
"""

import argparse
import json
import re
import statistics
from pathlib import Path

from parse_regulations import COMPOUND_RE, PARTS, RUN_RE, SINGLE_RE, get_leading_markers

MAX_CHARS = 2000  # Chunk size limit; revisit once the embedding model is chosen.


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
    A marker with no words of its own stays with the next one:
    '(a)(1) “Access device” means' -> ['', '(a)(1) “Access device” means']
    """
    m = RUN_RE.match(text)
    if not m:
        return [text]
    starts = [m.start(1) + s.start() for s in SINGLE_RE.finditer(m.group(1))]
    offset = m.end()
    # Same loop as get_leading_markers, but keeping positions.
    while True:
        c = COMPOUND_RE.match(text[offset:])
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
        markers = [] if block["continuation"] else get_leading_markers(block["text"])[0]
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


def chunk_record(record, max_chars=MAX_CHARS):
    """Chunks for one regulation record, as a list of dicts in document order."""
    heading_line = record["heading"]
    chunks = []

    def make_text(context, body):
        return "\n".join([heading_line] + [p[1] for p in context + body])

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
    return [to_output(record, *c) for c in chunks]


def to_output(record, node, context, body, text):
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
        "content_type": record["content_type"],
        "regulation": record["regulation"],
        "path_certain": certain,
        "n_chars": len(text),
        "record_id": record["record_id"],
    }


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
    parser.add_argument("--sections", type=Path, default=Path("data/processed/sections.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("data/processed/chunks.jsonl"))
    parser.add_argument("--parts", nargs="+", default=list(PARTS))
    parser.add_argument("--show", metavar="SECTION", help="print every chunk of one section, e.g. 1005.11")
    args = parser.parse_args(argv)

    chunks = []
    with args.sections.open(encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            if (
                record["part"] in args.parts
                and record["content_type"] == "regulation"
                and not record["reserved"]
            ):
                chunks += chunk_record(record)

    ids = [c["chunk_id"] for c in chunks]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise AssertionError(f"duplicate chunk_ids: {duplicates[:10]}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as out:
        for chunk in chunks:
            out.write(json.dumps(chunk, ensure_ascii=False) + "\n")

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
            f"max {max(sizes)}  over {MAX_CHARS}: {sum(s > MAX_CHARS for s in sizes)}  "
            f"uncertain paths: {sum(not c['path_certain'] for c in mine)}"
        )
    print("chunks ->", args.out)

    if args.show:
        for chunk in (c for c in chunks if c["section"] == args.show):
            print(f"\n=== {chunk['chunk_id']}  ({chunk['n_chars']} chars)  {chunk['source_url']}")
            print(chunk["text"])


if __name__ == "__main__":
    main()
