"""Alternative chunkings for the chunking ablation (docs/tasks/ujjwal.md).

    python scripts/make_fixed_chunks.py --words 200 --stride 150    # fixed word windows
    python scripts/make_fixed_chunks.py --words 0                   # one chunk per whole section

Rebuilds the regulation chunks of Parts 1005, 1006, 1022 and 1026 from Pair B's
sections.jsonl, ignoring paragraph structure: each section's text (heading plus
its blocks, in order) is cut into windows of --words words every --stride words
(--words 0 = the whole section). FCRA chunks are copied unchanged from
chunks.jsonl so that only the regulation chunking differs. Section labels are
kept, so the section-level gold still applies.

Writes chunking/data/processed/chunks_fixed<words>[_s<stride>].jsonl (or
chunks_section.jsonl), with the same fields run_retrieval.py needs. Then:
    python scripts/run_retrieval.py --chunks chunking/data/processed/chunks_fixed200_s150.jsonl --tag fixed200
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.config import ROOT  # noqa: E402

PROCESSED = ROOT / "chunking" / "data" / "processed"


def windows(words: list[str], size: int, stride: int) -> list[list[str]]:
    if size <= 0 or len(words) <= size:
        return [words]
    out = []
    for start in range(0, len(words), stride):
        out.append(words[start:start + size])
        if start + size >= len(words):
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", type=int, required=True, help="window size in words; 0 = whole section")
    ap.add_argument("--stride", type=int, default=None, help="default: --words (no overlap)")
    args = ap.parse_args()
    stride = args.stride or args.words

    chunks = []
    with open(PROCESSED / "sections.jsonl", encoding="utf-8") as f:
        sections = [json.loads(line) for line in f]
    for s in sections:
        if s["content_type"] != "regulation" or s["reserved"]:
            continue
        text = "\n".join([s["heading"]] + [b["text"] for b in s["blocks"]])
        for i, w in enumerate(windows(text.split(), args.words, stride)):
            body = " ".join(w)
            chunks.append({"chunk_id": f"12-{s['part']}-{s['section']}-w{i:03d}", "part": s["part"],
                           "section": s["section"], "paragraph": "", "heading": s["section_heading"],
                           "text": body, "embed_text": body, "source_url": s["source_url"],
                           "content_type": "regulation", "regulation": s["regulation"], "n_chars": len(body)})
    n_reg = len(chunks)
    with open(PROCESSED / "chunks.jsonl", encoding="utf-8") as f:
        chunks += [c for c in map(json.loads, f) if c["regulation"] == "FCRA"]

    name = "chunks_section.jsonl" if args.words <= 0 else \
        f"chunks_fixed{args.words}" + (f"_s{stride}" if stride != args.words else "") + ".jsonl"
    out = PROCESSED / name
    with open(out, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"wrote {out}: {n_reg} regulation chunks + {len(chunks) - n_reg} FCRA chunks")


if __name__ == "__main__":
    main()
