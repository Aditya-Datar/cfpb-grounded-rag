"""Drafter input for the best rerankers: top-ranked section only (EXPERIMENT_LOG E1, E5).

    .venv/Scripts/python.exe scripts/build_top1_rerank.py --model gpt   # evaluation-only upper reference
    .venv/Scripts/python.exe scripts/build_top1_rerank.py --model super # deployable

For every attribution complaint (annotation/attribution_ids.txt, dev and held-out):
first stage exactly as scripts/run_reranker_swap.py (Nemotron Embed 8B + BM25, alpha 0.8,
classifier regulation prior b 0.2), K = 10 candidate sections, 90-word passages, the
rerank prompt with the rubric hints, then the reranker's first section. The drafter gets
up to 5 chunks of that section, ordered by first-stage score (the top1x5 layout chosen on
dev in E1). Dev reranker answers are reused from the cache; held-out calls are new.

Writes outputs/retrieval/<model>_rubric_top1/ranked.parquet (for run_pipeline_batch.py
--retriever precomputed) and reranked_sections.json (the full reranked order, for
retrieval metrics).
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
sys.path.insert(0, str(ROOT / "scripts"))

from run_reranker_swap import MODELS, rerank  # noqa: E402

from cfpb.annotation import load_items  # noqa: E402
from cfpb.config import PRODUCT_TO_REGULATION  # noqa: E402
from cfpb.pipeline.core import load_classifier  # noqa: E402
from cfpb.pipeline.corpus import load_corpus  # noqa: E402
from cfpb.retrieval.bm25 import DEFAULT_CHUNKS_PATH, BM25Retriever, load_chunks  # noqa: E402
from cfpb.retrieval.llm_rerank import RERANK_K, LLMRerankRetriever, section_order  # noqa: E402
from cfpb.retrieval.metrics import half  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["gpt", "super", "kimi"], required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    model, extra = MODELS[args.model]

    ids = [l.strip() for l in open(ROOT / "annotation" / "attribution_ids.txt", encoding="utf-8") if l.strip()]
    items = load_items().set_index("complaint_id")
    gold = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str).set_index("complaint_id")
    chunks = load_chunks(DEFAULT_CHUNKS_PATH, include_fcra=True)
    corpus = load_corpus([str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")])
    pos = {c["chunk_id"]: i for i, c in enumerate(chunks)}
    clf = load_classifier(require=True)
    r = LLMRerankRetriever(chunks, BM25Retriever(chunks))

    scores, cands = {}, {}
    for cid in ids:
        t = items.loc[cid, "narrative_clean"]
        s = r.first_stage(t, PRODUCT_TO_REGULATION.get(clf.classify(t).product.label))
        scores[cid] = s
        cands[cid] = section_order(np.argsort(-s, kind="stable"), chunks)

    def one(cid):
        return rerank(model, extra, items.loc[cid, "narrative_clean"], cands[cid][:RERANK_K], chunks, 90, True)

    with ThreadPoolExecutor(args.workers) as ex:
        tops = dict(zip(ids, ex.map(one, ids)))

    rows, order, fallback = [], {}, 0
    for cid in ids:
        first = [s for s, _ in cands[cid]]
        o = tops[cid] + [s for s in first if s not in tops[cid]]
        fallback += not tops[cid]  # empty answer: first-stage order
        order[cid] = o[:10]
        s = scores[cid]
        cs = sorted(corpus.section(o[0]), key=lambda c: -s[pos[c.chunk_id]] if c.chunk_id in pos else np.inf)[:5]
        rows += [{"complaint_id": cid, "retriever": f"{args.model}-rubric-rerank-top1-section", "corpus": "regulation+statute",
                  "rank": k + 1, "section": c.section, "chunk_id": c.chunk_id, "score": float(5 - k)} for k, c in enumerate(cs)]
    out = ROOT / "outputs" / "retrieval" / f"{args.model}_rubric_top1"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out / "ranked.parquet", index=False)
    (out / "reranked_sections.json").write_text(json.dumps({"model": model, "settings": extra, "K": RERANK_K,
                                                            "words_per_passage": 90, "rubric": True, "order": order},
                                                           indent=1), encoding="utf-8")
    for h, name in ((0, "dev"), (1, "held-out")):
        c = [x for x in ids if half(x) == h]
        hit1 = np.mean([order[x][0] == gold.loc[x, "gold_section"] for x in c])
        hit3 = np.mean([gold.loc[x, "gold_section"] in order[x][:3] for x in c])
        print(f"{args.model}+rubric {name:8s} n {len(c)}  top-1 section hit {hit1:.3f}  top-3 {hit3:.3f}")
    print(f"wrote {out}: {len(rows)} chunk rows; empty reranker answers (first-stage order used): {fallback}")


if __name__ == "__main__":
    main()
