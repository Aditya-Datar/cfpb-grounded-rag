"""Quick test: which generation context makes drafts cite the gold section? (post-hoc, 2026-11-19)

    .venv/Scripts/python.exe scripts/run_generation_context_test.py [--workers 6]

Root-cause check on full-llm_rerank: the generator surveys all five passages it is
given (five distinct sections), so most sentences cite a sibling section and the
supported-and-gold metric falls. This script re-drafts the 127 attribution
complaints with contexts built from the SAME retrieval v2 ranking
(outputs/retrieval/llm/ranked.parquet), same generator, prompt and decoding:

  current   the five distinct top sections, one best chunk each (as in full-llm_rerank)
  top1x5    up to five chunks of the first-ranked section only (oracle-shaped context)
  top2_3_2  up to three chunks of section 1, then up to two of section 2

Chunks within a section are ordered by the first-stage score (Nemotron embed + BM25).
No NLI here: the measure is the share of sentences whose premises (cited passages,
or all passages when a sentence cites none) include the gold section, an upper bound
on supported-and-gold. Selection should use the dev half (metrics.half == 0); both
halves are printed. Writes results/generation_context_test.json.
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cfpb.annotation import load_items  # noqa: E402
from cfpb.data.clean import clean_narrative  # noqa: E402
from cfpb.generate.nemotron import NemotronGenerator  # noqa: E402
from cfpb.pipeline.corpus import load_corpus  # noqa: E402
from cfpb.retrieval.bm25 import DEFAULT_CHUNKS_PATH, BM25Retriever, load_chunks  # noqa: E402
from cfpb.retrieval.llm_rerank import LLMRerankRetriever  # noqa: E402
from cfpb.retrieval.metrics import half  # noqa: E402

VARIANTS = {"current": None, "top1x5": [5], "top2_3_2": [3, 2]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    ids = [l.strip() for l in open(ROOT / "annotation" / "attribution_ids.txt", encoding="utf-8") if l.strip()]
    gold = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str).set_index("complaint_id")
    items = load_items().set_index("complaint_id")
    corpus = load_corpus([str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")])
    ranked = pd.read_parquet(ROOT / "outputs" / "retrieval" / "llm" / "ranked.parquet")
    secs_of = ranked.sort_values("rank").groupby("complaint_id")["section"].apply(list)

    chunks = load_chunks(DEFAULT_CHUNKS_PATH, include_fcra=True)
    llm = LLMRerankRetriever(chunks, BM25Retriever(chunks))
    pos = {c["chunk_id"]: i for i, c in enumerate(chunks)}

    def context(cid: str, quota):
        if quota is None:  # the full-llm_rerank context
            r = ranked[(ranked.complaint_id == cid) & (ranked["rank"] <= 5)].sort_values("rank")
            return [corpus.get(c).ranked(n, s) for n, (c, s) in enumerate(zip(r.chunk_id, r.score), 1)]
        s = llm.first_stage(items.loc[cid, "narrative_clean"], None)  # the prior is constant within a section
        out = []
        for sec, q in zip(secs_of[cid], quota):
            cs = sorted(corpus.section(sec), key=lambda c: -s[pos[c.chunk_id]] if c.chunk_id in pos else np.inf)
            out += cs[:q]
        return [c.ranked(n, 1.0) for n, c in enumerate(out, 1)]

    gen = NemotronGenerator()
    jobs = [(v, cid) for v in VARIANTS for cid in ids]

    def one(job):
        v, cid = job
        ctx = context(cid, VARIANTS[v])
        d = gen.generate(clean_narrative(items.loc[cid, "narrative_clean"]), ctx)  # same text as run_pipeline_batch
        g = gold.loc[cid, "gold_section"]
        by_id = {c.chunk_id: c.section for c in ctx}
        cites = [g in {by_id[x] for x in (cited or by_id)} for cited in d.cited_chunk_ids]
        return {"variant": v, "complaint_id": cid, "half": half(cid), "n_sentences": len(cites),
                "n_cite_gold": int(sum(cites)), "gold_in_context": g in set(by_id.values()),
                "context_sections": [c.section for c in ctx]}

    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(one, jobs))
    df = pd.DataFrame(rows)

    res = {"note": __doc__.split("\n\n")[1], "variants": {}}
    for v, t in df.groupby("variant", sort=False):
        block = {}
        for name, m in (("all", t), ("dev", t[t.half == 0]), ("report", t[t.half == 1])):
            nz = m[m.n_sentences > 0]
            block[name] = {"n": len(m), "gold_in_context": float(m.gold_in_context.mean()),
                           "sentences": int(m.n_sentences.sum()),
                           "cite_gold_micro": float(m.n_cite_gold.sum() / max(1, m.n_sentences.sum())),
                           "cite_gold_macro": float((nz.n_cite_gold / nz.n_sentences).mean()),
                           "drafts_citing_gold_at_least_once": float((m.n_cite_gold > 0).mean()),
                           "empty_drafts": int((m.n_sentences == 0).sum())}
        res["variants"][v] = block
        print(v, {k: {kk: round(vv, 3) if isinstance(vv, float) else vv for kk, vv in b.items()} for k, b in block.items()},
              flush=True)
    (ROOT / "results" / "generation_context_test.json").write_text(json.dumps(res, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
