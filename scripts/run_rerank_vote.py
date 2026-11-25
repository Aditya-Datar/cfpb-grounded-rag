"""Reranker self-consistency: vote over shuffled candidate orders (EXPERIMENT_LOG E11, dev only).

    .venv/Scripts/python.exe scripts/run_rerank_vote.py --model super --perms 5

Same first stage and rubric prompt as scripts/build_top1_rerank.py (K = 10, 90 words).
The candidate list is shown to the reranker in --perms orders: the first-stage order,
then fixed-seed shuffles. Votes: top-1 majority (ties -> first-stage order of the run
that came first) and Borda over the returned top-5 lists. Reports dev hit@1 / hit@3
for the single unshuffled call and for both votes. Writes results/rerank_vote_dev.json.
"""
import argparse
import json
import sys
from collections import Counter
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
from cfpb.retrieval.bm25 import DEFAULT_CHUNKS_PATH, BM25Retriever, load_chunks  # noqa: E402
from cfpb.retrieval.llm_rerank import RERANK_K, LLMRerankRetriever, section_order  # noqa: E402
from cfpb.retrieval.metrics import half  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="super", choices=list(MODELS))
    ap.add_argument("--perms", type=int, default=5)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--half", type=int, default=0)
    args = ap.parse_args()
    model, extra = MODELS[args.model]

    ids = [l.strip() for l in open(ROOT / "annotation" / "attribution_ids.txt", encoding="utf-8") if l.strip()]
    ids = [x for x in ids if half(x) == args.half]
    items = load_items().set_index("complaint_id")
    gold = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str).set_index("complaint_id")
    chunks = load_chunks(DEFAULT_CHUNKS_PATH, include_fcra=True)
    clf = load_classifier(require=True)
    r = LLMRerankRetriever(chunks, BM25Retriever(chunks))
    cands = {}
    for cid in ids:
        t = items.loc[cid, "narrative_clean"]
        s = r.first_stage(t, PRODUCT_TO_REGULATION.get(clf.classify(t).product.label))
        cands[cid] = section_order(np.argsort(-s, kind="stable"), chunks)[:RERANK_K]

    rng = np.random.default_rng(544)
    orders = [list(range(RERANK_K))] + [list(rng.permutation(RERANK_K)) for _ in range(args.perms - 1)]
    jobs = [(cid, p) for cid in ids for p in range(args.perms)]

    def one(job):
        cid, p = job
        c = [cands[cid][k] for k in orders[p] if k < len(cands[cid])]
        return rerank(model, extra, items.loc[cid, "narrative_clean"], c, chunks, 90, True)

    with ThreadPoolExecutor(args.workers) as ex:
        res = dict(zip(jobs, ex.map(one, jobs)))

    first = {cid: [s for s, _ in cands[cid]] for cid in ids}
    out_rows, empty = {}, 0
    for cid in ids:
        runs = [res[(cid, p)] for p in range(args.perms)]
        empty += sum(not x for x in runs)
        single = (runs[0] + [s for s in first[cid] if s not in runs[0]])
        tops = [x[0] for x in runs if x]
        cnt = Counter(tops)
        maj = max(cnt, key=lambda s: (cnt[s], -tops.index(s))) if tops else first[cid][0]
        borda = Counter()
        for x in runs:
            for k, s in enumerate(x):
                borda[s] += 5 - k
        bord = sorted(borda, key=lambda s: (-borda[s], first[cid].index(s))) or first[cid]
        out_rows[cid] = {"single": single[:5], "majority_top1": maj, "borda": bord[:5], "runs": runs,
                         "agreement_top1": cnt.most_common(1)[0][1] / len(tops) if tops else 0.0}

    g = {cid: gold.loc[cid, "gold_section"] for cid in ids}
    m = {"single_hit@1": np.mean([out_rows[c]["single"][0] == g[c] for c in ids]),
         "single_hit@3": np.mean([g[c] in out_rows[c]["single"][:3] for c in ids]),
         "majority_hit@1": np.mean([out_rows[c]["majority_top1"] == g[c] for c in ids]),
         "borda_hit@1": np.mean([out_rows[c]["borda"][0] == g[c] for c in ids]),
         "borda_hit@3": np.mean([g[c] in out_rows[c]["borda"][:3] for c in ids]),
         "mean_top1_agreement": np.mean([out_rows[c]["agreement_top1"] for c in ids])}
    # does low agreement predict a miss? (useful for referral)
    lo = [c for c in ids if out_rows[c]["agreement_top1"] < 0.6]
    m["low_agreement_n"] = len(lo)
    m["low_agreement_borda_hit@1"] = float(np.mean([out_rows[c]["borda"][0] == g[c] for c in lo])) if lo else None
    m = {k: (float(v) if v is not None else None) for k, v in m.items()}
    out = {"model": model, "half": args.half, "n": len(ids), "perms": args.perms, "K": RERANK_K, "rubric": True,
           "empty_answers": empty, "metrics": m, "per_complaint": out_rows}
    (ROOT / "results" / f"rerank_vote_{args.model}_half{args.half}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"n": len(ids), "empty": empty, **m}, indent=1))


if __name__ == "__main__":
    main()
