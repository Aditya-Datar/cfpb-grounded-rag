"""BM25 baseline (docs: CLAUDE_PROGRESS.md Sec. 6.5.6).

    python scripts/run_bm25.py [--stopwords]

Needs data/processed/annotation_sample.csv and annotation_topup.csv (see Sec. 0 / make_topup_sample.py).
Runs BM25 over chunking/data/processed/chunks.jsonl with and without the FCRA chunks.
Writes outputs/retrieval/bm25[_no_fcra]/ranked.parquet (git-ignored) and results/retrieval_bm25.json
(results/retrieval_bm25_stopwords.json with --stopwords; ranked.parquet is then overwritten too).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.annotation import load_items  # noqa: E402
from cfpb.config import OUTPUT_DIR, ROOT  # noqa: E402
from cfpb.retrieval.bm25 import BM25Retriever, load_chunks  # noqa: E402
from cfpb.retrieval.metrics import half, prf, rank_of, retrieval_metrics, tune_threshold  # noqa: E402

GOLD_PATH = ROOT / "annotation" / "gold_final.jsonl"
REGS = ["E", "F", "Z", "FCRA", "V"]


def run(items: pd.DataFrame, gold: pd.DataFrame, include_fcra: bool, stopwords: frozenset, name: str) -> dict:
    chunks = load_chunks(include_fcra=include_fcra)
    bm25 = BM25Retriever(chunks, stopwords)
    df = items.merge(gold, on="complaint_id", how="inner", validate="1:1")
    assert len(df) == len(gold), "every gold item needs a query narrative"

    rows, top_score, ranks = [], [], []
    for r in df.itertuples():
        top = bm25.retrieve(r.narrative_clean, k=10)
        rows += [{"complaint_id": r.complaint_id, "retriever": "bm25",
                  "corpus": "regulation+statute" if include_fcra else "regulation",
                  "rank": i + 1, "chunk_id": t["chunk_id"], "score": t["score"]} for i, t in enumerate(top)]
        secs = bm25.ranked_sections(r.narrative_clean)
        top_score.append(secs[0][1])
        ranks.append(rank_of(r.gold_section, [s for s, _ in secs]) if r.gold_section else None)
    df = df.assign(top_score=top_score, rank=ranks)

    out_dir = OUTPUT_DIR / "retrieval" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out_dir / "ranked.parquet", index=False)

    ins = df[df["gold_regulation"] != "NONE"]
    rk = lambda d: [None if pd.isna(x) else int(x) for x in d["rank"]]  # noqa: E731
    res = {"n_chunks": len(chunks), "in_scope_all": retrieval_metrics(rk(ins)),
           "by_regulation": {g: retrieval_metrics(rk(ins[ins["gold_regulation"] == g])) for g in REGS
                             if (ins["gold_regulation"] == g).any()}}
    if not include_fcra:  # FCRA items have no correct chunk; also report the items that can be hit
        res["in_scope_non_fcra"] = retrieval_metrics(rk(ins[ins["gold_regulation"] != "FCRA"]))

    is_none = (df["gold_regulation"] == "NONE").to_numpy()
    s = df["top_score"].to_numpy()
    dev = df["complaint_id"].map(half).to_numpy() == 0
    t = tune_threshold(s[dev], is_none[dev])
    res["abstention"] = {
        "signal": "abstain when top BM25 score <= threshold",
        "auroc_all": float(roc_auc_score(is_none, -s)),
        "auroc_report_half": float(roc_auc_score(is_none[~dev], -s[~dev])),
        "threshold_tuned_on_dev_half": t,
        "dev_half": prf(is_none[dev], s[dev] <= t),
        "report_half": prf(is_none[~dev], s[~dev] <= t),
    }
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stopwords", action="store_true", help="remove sklearn English stopwords")
    args = ap.parse_args()
    stop = frozenset(ENGLISH_STOP_WORDS) if args.stopwords else frozenset()

    items = load_items()[["complaint_id", "narrative_clean"]]
    gold = pd.read_json(GOLD_PATH, lines=True, dtype=str)[["complaint_id", "gold_regulation", "gold_section"]]
    gold["gold_section"] = gold["gold_section"].where(gold["gold_regulation"] != "NONE")

    results = {"retriever": "BM25Okapi (rank_bm25, k1=1.5, b=0.75)", "index_field": "embed_text",
               "tokenization": "lowercase [a-z0-9]+" + ("; sklearn English stopwords removed" if args.stopwords else "; no stopword removal"),
               "gold": "annotation/gold_final.jsonl, section-level, sections deduplicated keeping first occurrence",
               "with_fcra": run(items, gold, True, stop, "bm25"),
               "without_fcra": run(items, gold, False, stop, "bm25_no_fcra")}
    out = ROOT / "results" / ("retrieval_bm25_stopwords.json" if args.stopwords else "retrieval_bm25.json")
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    for k in ("with_fcra", "without_fcra"):
        m = results[k]["in_scope_all"]
        print(k, {x: round(m[x], 3) for x in m if x != "n"}, "n =", m["n"])
        print("  abstention", {x: round(v, 3) if isinstance(v, float) else v for x, v in results[k]["abstention"].items() if x.startswith(("auroc", "thr"))})
    print("wrote", out)


if __name__ == "__main__":
    main()
