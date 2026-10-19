"""Regulation corpus loader and the oracle retriever.

Two chunk sets exist and the team has not picked one yet (CLAUDE_PROGRESS.md
Sec. 7, 2026-10-15 overlap entry). `Corpus.load` reads either and maps both to
one record shape, so retrievers and the demo do not care which is used:

  - data/processed/reg_chunks.parquet (branch regulation-corpus,
    scripts/build_reg_corpus.py): regulation, interpretation, appendix and
    FCRA statute chunks; paragraphs in full form, e.g. "1005.11(c)(2)".
  - chunking/data/processed/chunks.jsonl (branch chunking): regulation text
    only, no FCRA; paragraphs relative to the section, e.g. "(c)(2)".

The oracle retriever returns the gold section's chunks for a gold complaint:
the "oracle" condition of the attribution experiment (INTERFACES.md Sec. 4).
"""
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from cfpb.config import PROCESSED_DIR, ROOT
from cfpb.pipeline.schema import NONE_LABEL, Retrieval, RetrievedChunk

DEFAULT_CORPUS = PROCESSED_DIR / "reg_chunks.parquet"
DEFAULT_GOLD = ROOT / "annotation" / "gold_final.jsonl"
RULE_KINDS = ("regulation", "statute")  # binding text; interpretations are an ablation


@dataclass
class Chunk:
    chunk_id: str
    regulation: str  # E, F, V, Z, FCRA
    section: str
    paragraph: str   # full form, e.g. 1005.11(c)(2); empty for a whole-section chunk
    kind: str        # regulation, interpretation, appendix, statute
    heading: str
    text: str
    source_url: str

    def ranked(self, rank: int, score: float) -> RetrievedChunk:
        return RetrievedChunk(rank, self.chunk_id, score, self.regulation, self.section,
                              self.paragraph, self.heading, self.text, self.source_url)


PART_TO_REGULATION = {"1005": "E", "1006": "F", "1022": "V", "1026": "Z", "1681": "FCRA"}


def _regulation_of(section: str) -> str:
    return PART_TO_REGULATION.get(section[:4], "")


def _full_paragraph(section: str, paragraph: str) -> str:
    if not paragraph or paragraph.startswith(section):
        return paragraph
    return section + paragraph


class Corpus:
    def __init__(self, chunks: list[Chunk], name: str):
        self.chunks, self.name = chunks, name
        self._by_id = {c.chunk_id: c for c in chunks}
        if len(self._by_id) != len(chunks):
            raise ValueError(f"{name}: duplicate chunk_id")
        self._by_section: dict[str, list[Chunk]] = {}
        for c in chunks:  # keeps corpus (document) order within a section
            self._by_section.setdefault(c.section, []).append(c)

    @classmethod
    def load(cls, path=DEFAULT_CORPUS, kinds=None) -> "Corpus":
        """Read one chunk file; `kinds` keeps only those kinds (e.g. ("statute",)).
        Rows without `regulation` or `kind` (e.g. FCRA rows appended to
        chunks.jsonl with only the INTERFACES fields) get them from the section."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"No corpus at {path}. Build it with scripts/build_reg_corpus.py --date 2026-10-13, "
                "or pass the chunking branch's chunks.jsonl.")
        df = (pd.read_parquet(path) if path.suffix == ".parquet"
              else pd.read_json(path, lines=True, dtype=False))
        df = df.astype(object).where(df.notna(), "")
        kind_col = "kind" if "kind" in df else "content_type" if "content_type" in df else None
        chunks = []
        for r in df.to_dict("records"):
            section = str(r["section"])
            regulation = r.get("regulation") or _regulation_of(section)
            kind = (r[kind_col] if kind_col else "") or ("statute" if regulation == "FCRA" else "regulation")
            if kinds is not None and kind not in kinds:
                continue
            chunks.append(Chunk(str(r["chunk_id"]), regulation, section,
                                _full_paragraph(section, str(r["paragraph"])), kind,
                                r["heading"], r["text"], r["source_url"]))
        name = path.name if kinds is None else f"{path.name}[{'+'.join(kinds)}]"
        return cls(chunks, name=name)

    @classmethod
    def merge(cls, *corpora: "Corpus", keep_first: bool = False) -> "Corpus":
        """One corpus from several, e.g. Pair B's chunks.jsonl plus the FCRA
        statute rows of reg_chunks.parquet. Duplicate chunk_ids raise, unless
        `keep_first` (for a lookup-only corpus spanning several files)."""
        chunks, seen = [], set()
        for corpus in corpora:
            for c in corpus.chunks:
                if keep_first and c.chunk_id in seen:
                    continue
                seen.add(c.chunk_id)
                chunks.append(c)
        return cls(chunks, name="+".join(corpus.name for corpus in corpora))

    def __len__(self) -> int:
        return len(self.chunks)

    def get(self, chunk_id: str) -> Chunk:
        return self._by_id[chunk_id]

    def section(self, section: str, kinds=RULE_KINDS) -> list[Chunk]:
        return [c for c in self._by_section.get(section, []) if kinds is None or c.kind in kinds]

    @property
    def kinds(self) -> list[str]:
        return sorted({c.kind for c in self.chunks})


def load_corpus(specs, keep_first: bool = False) -> Corpus:
    """Corpus from one or more specs "path" or "path::kind1+kind2", e.g.
    ["chunking/data/processed/chunks.jsonl", "data/processed/reg_chunks.parquet::statute"]."""
    specs = [specs] if isinstance(specs, (str, Path)) else list(specs)
    corpora = []
    for spec in specs:
        path, _, kinds = str(spec).partition("::")
        corpora.append(Corpus.load(path, kinds=tuple(kinds.split("+")) if kinds else None))
    return corpora[0] if len(corpora) == 1 else Corpus.merge(*corpora, keep_first=keep_first)


def load_gold(path=DEFAULT_GOLD) -> dict[str, dict]:
    """complaint_id -> gold record (gold_regulation, gold_section, gold_paragraph, ...)."""
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return {r["complaint_id"]: r for r in rows}


def _overlaps(paragraph: str, gold_paragraph: str) -> bool:
    """True if one paragraph contains the other, e.g. a 1005.11(c) chunk and
    gold 1005.11(c)(1), or a 1005.11(c)(2) chunk and gold 1005.11(c)."""
    if not paragraph or not gold_paragraph:
        return False
    return (paragraph == gold_paragraph or paragraph.startswith(gold_paragraph + "(")
            or gold_paragraph.startswith(paragraph + "("))


class OracleRetriever:
    """Gold-section chunks for a gold-set complaint. Retrieval takes text, not
    an id, so bind a complaint first:

        oracle = OracleRetriever(Corpus.load())
        pipe.analyze(text, retriever=oracle.for_complaint("23571192"))

    Order: chunks overlapping the gold paragraph (score 1.0), then the rest of
    the section (0.5), in document order. A NONE gold label abstains.
    """
    is_stub = False

    def __init__(self, corpus: Corpus, gold: dict[str, dict] | None = None, kinds=RULE_KINDS):
        self.corpus, self.kinds = corpus, kinds
        self.gold = gold if gold is not None else load_gold()

    def for_complaint(self, complaint_id: str) -> "_BoundOracle":
        if complaint_id not in self.gold:
            raise KeyError(f"Complaint {complaint_id} is not in the gold set")
        return _BoundOracle(self, self.gold[complaint_id])

    def retrieve_for(self, gold: dict, k: int) -> Retrieval:
        name = "oracle"
        corpus = f"{self.corpus.name}:{'+'.join(self.kinds) if self.kinds else 'all'}"
        if gold["gold_regulation"] == NONE_LABEL:
            return Retrieval([], abstain_score=1.0, abstained=True, retriever=name, corpus=corpus)
        chunks = self.corpus.section(gold["gold_section"], self.kinds)
        if not chunks:
            raise LookupError(f"Gold section {gold['gold_section']} has no chunks in {corpus}")
        para = gold.get("gold_paragraph") or ""
        hits = [c for c in chunks if _overlaps(c.paragraph, para)]
        rest = [c for c in chunks if c not in hits]
        ranked = [(c, 1.0) for c in hits] + [(c, 0.5) for c in rest]
        return Retrieval([c.ranked(i + 1, s) for i, (c, s) in enumerate(ranked[:k])],
                         abstain_score=0.0, abstained=False, retriever=name, corpus=corpus)


class _BoundOracle:
    is_stub = False

    def __init__(self, oracle: OracleRetriever, gold: dict):
        self.oracle, self.gold = oracle, gold

    def retrieve(self, narrative_clean: str, k: int) -> Retrieval:
        return self.oracle.retrieve_for(self.gold, k)
