"""Run the single-complaint pipeline over the gold-set complaints and write the
stage tables of docs/INTERFACES.md.

    python scripts/run_pipeline_batch.py --retriever oracle
    python scripts/run_pipeline_batch.py --retriever stub --limit 10
    python scripts/run_pipeline_batch.py --retriever precomputed \
        --ranked outputs/retrieval/bm25/ranked.parquet \
        --corpus chunking/data/processed/chunks.jsonl data/processed/reg_chunks.parquet::statute

--corpus takes one or more "path" or "path::kind1+kind2" specs and must
contain every chunk_id the rankings use (the corpus the retriever indexed).

Complaint text comes from data/processed/annotation_sample.csv (120 items)
and, if present, annotation_topup.csv (78 more); gold-set ids without text
are reported and skipped. Writes outputs/pipeline_runs/<run-name>/:
    classification.parquet  ranked.parquet  responses.parquet  sentences.parquet
    run_info.json           settings, stage sources, item counts, git commit
Stages not built yet run as stubs (listed in run_info "stubbed_stages").
"""
import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.annotation import load_items  # noqa: E402
from cfpb.config import OUTPUT_DIR, ROOT  # noqa: E402
from cfpb.pipeline import load_pipeline  # noqa: E402
from cfpb.pipeline.batch import to_frames  # noqa: E402
from cfpb.pipeline.corpus import DEFAULT_CORPUS, DEFAULT_GOLD, OracleRetriever, load_corpus, load_gold  # noqa: E402
from cfpb.pipeline.retrievers import PrecomputedRetriever  # noqa: E402


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
        return out + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retriever", choices=["stub", "oracle", "precomputed"], required=True)
    ap.add_argument("--corpus", nargs="+", default=[str(DEFAULT_CORPUS)],
                    help='chunk files for oracle/precomputed: "path" or "path::kind1+kind2"')
    ap.add_argument("--ranked", type=Path, help="ranked.parquet for --retriever precomputed")
    ap.add_argument("--min-top-score", type=float, default=None,
                    help="precomputed: abstain when the top score is below this")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None, help="first N items only (smoke runs)")
    ap.add_argument("--run-name", default=None)
    ap.add_argument("--require-models", action="store_true")
    args = ap.parse_args()

    gold = load_gold(DEFAULT_GOLD)
    items = load_items()
    texts = dict(zip(items["complaint_id"], items["narrative_clean"]))
    ids = [cid for cid in gold if cid in texts]
    missing = len(gold) - len(ids)
    if args.limit:
        ids = ids[:args.limit]
    print(f"gold items: {len(gold)}, with text: {len(gold) - missing}, running: {len(ids)}")
    if missing:
        print(f"  {missing} gold items have no text locally (add data/processed/annotation_topup.csv)")

    pipe = load_pipeline(require_models=args.require_models, k=args.k)
    bound = None  # complaint_id -> retriever for that complaint
    if args.retriever == "oracle":
        bound = OracleRetriever(load_corpus(args.corpus), gold).for_complaint
    elif args.retriever == "precomputed":
        if not args.ranked:
            ap.error("--retriever precomputed needs --ranked")
        pre = PrecomputedRetriever(args.ranked, load_corpus(args.corpus), args.min_top_score)
        unranked = [cid for cid in ids if cid not in set(pre.complaint_ids)]
        if unranked:
            print(f"  {len(unranked)} items have no ranking in {args.ranked}; skipped")
            ids = [cid for cid in ids if cid not in set(unranked)]
        bound = pre.for_complaint
    condition = "oracle" if args.retriever == "oracle" else "retrieved"

    t0 = time.perf_counter()
    results = {cid: pipe.analyze(texts[cid], retriever=bound(cid) if bound else None) for cid in ids}
    elapsed = time.perf_counter() - t0

    run_name = args.run_name or f"{args.retriever}-{datetime.now():%Y%m%d-%H%M%S}"
    out = OUTPUT_DIR / "pipeline_runs" / run_name
    out.mkdir(parents=True, exist_ok=True)
    frames = to_frames(results, condition)
    for name, df in frames.items():
        df.to_parquet(out / f"{name}.parquet", index=False)

    first = next(iter(results.values()), None)
    info = {
        "date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "args": {k: str(v) for k, v in vars(args).items()},
        "condition": condition,
        "classifier": first.classification.source if first else None,
        "retriever": first.retrieval.retriever if first else None,
        "corpus": first.retrieval.corpus if first else None,
        "stubbed_stages": first.stubbed_stages if first else [],
        "n_gold": len(gold), "n_gold_without_text": missing, "n_run": len(results),
        "n_abstained": int(sum(r.retrieval.abstained for r in results.values())),
        "seconds": round(elapsed, 1),
        "rows": {name: len(df) for name, df in frames.items()},
        "versions": {"python": platform.python_version()},
    }
    (out / "run_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"wrote {out} in {elapsed:.1f}s: " + ", ".join(f"{k} {v}" for k, v in info["rows"].items()))


if __name__ == "__main__":
    main()
