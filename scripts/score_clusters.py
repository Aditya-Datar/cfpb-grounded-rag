"""Final accuracy under cluster-based scoring (docs/CLUSTER_SCORING_PROTOCOL.md, Sec. 7).

    .venv/Scripts/python.exe scripts/score_clusters.py [--runs full-llm_rerank full-llm_top1 full-oracle-local]

Each drafted sentence takes the best tier among the sections of its premise chunks
(its cited passages, or all passages when it cites none, as the checker does):
  1 gold section | 2 frozen cluster member | 3 other section of the gold law
  (FCRA and Reg V one family) | 4 other law or nothing.
Headline FINAL ACCURACY = share of sentences that are checker-supported AND tier 1-2,
micro over all sentences, at cutoff 0.5 and T, with a bootstrap CI over complaints.

Refuses to run unless annotation/clusters_frozen.jsonl matches the hash in
results/cluster_freeze.json. Writes results/final_accuracy_clusters.json.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_cluster_keys import key_id  # noqa: E402
from cfpb.annotation import load_items  # noqa: E402
from cfpb.pipeline.corpus import _regulation_of, load_corpus  # noqa: E402
from cfpb.retrieval.metrics import half  # noqa: E402

T = 0.99658203125
FAMILY = {"V": "V+FCRA", "FCRA": "V+FCRA"}


def boot(per: pd.DataFrame, n_boot: int = 10000) -> list[float]:
    """CI of a micro ratio (num/den summed over complaints), resampling complaints."""
    rng = np.random.default_rng(0)
    num, den = per["num"].to_numpy(float), per["den"].to_numpy(float)
    idx = rng.integers(0, len(per), (n_boot, len(per)))
    r = num[idx].sum(1) / np.maximum(1, den[idx].sum(1))
    return [float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", default=["full-llm_rerank", "full-llm_top1", "full-oracle-local"])
    ap.add_argument("--out", default="results/final_accuracy_clusters.json")
    ap.add_argument("--rows-out", default=None, help="folder for per-sentence tier and ok flags (one parquet per run)")
    args = ap.parse_args()

    frozen = ROOT / "annotation" / "clusters_frozen.jsonl"
    freeze = json.loads((ROOT / "results" / "cluster_freeze.json").read_text(encoding="utf-8"))
    if hashlib.sha256(frozen.read_bytes()).hexdigest() != freeze["sha256"]:
        sys.exit("clusters_frozen.jsonl does not match the frozen hash; refusing to score")
    clusters = {c["key"]: c for c in map(json.loads, open(frozen, encoding="utf-8"))}

    gold = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str).set_index("complaint_id")
    meta = load_items().set_index("complaint_id")
    corpus = load_corpus([str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")])

    def members(cid: str) -> dict[str, str]:
        c = clusters[key_id(meta.loc[cid, "issue"], gold.loc[cid, "gold_section"])]
        return {m["section"]: m["tier"] for m in c["members"]}

    def tier(cid: str, secs: set[str]) -> int:
        g = gold.loc[cid, "gold_section"]
        fam = FAMILY.get(gold.loc[cid, "gold_regulation"], gold.loc[cid, "gold_regulation"])
        if g in secs:
            return 1
        if secs & set(members(cid)):
            return 2
        if any(FAMILY.get(_regulation_of(s), _regulation_of(s)) == fam for s in secs):
            return 3
        return 4

    out = {"protocol": "docs/CLUSTER_SCORING_PROTOCOL.md", "clusters_sha256": freeze["sha256"],
           "label_status": freeze["label_status"],
           "disclosure": "metric designed after the strict results were seen; strict score reported beside it",
           "runs": {}}
    for run in args.runs:
        d = ROOT / "outputs" / "pipeline_runs" / run
        if not (d / "sentences.parquet").exists():
            print(f"{run}: no sentences.parquet, skipped")
            continue
        s = pd.read_parquet(d / "sentences.parquet")
        ranked = pd.read_parquet(d / "ranked.parquet")
        s["secs"] = s["premise_chunk_ids"].map(lambda p: {corpus.get(c).section for c in p})
        s["tier"] = [tier(c, x) for c, x in zip(s["complaint_id"], s["secs"])]
        s["core"] = [any(members(c).get(x) == "core" for x in secs) for c, secs in zip(s["complaint_id"], s["secs"])]
        res = {"n_complaints": int(s["complaint_id"].nunique()), "n_sentences": len(s),
               "tier_share": {str(t): float((s["tier"] == t).mean()) for t in (1, 2, 3, 4)}}
        top5 = ranked[ranked["rank"] <= 5].groupby("complaint_id")["section"].apply(set)
        cids = sorted(s["complaint_id"].unique())
        res["retrieval_top5"] = {
            "strict_hit": float(np.mean([gold.loc[c, "gold_section"] in top5.get(c, set()) for c in cids])),
            "cluster_hit": float(np.mean([bool(top5.get(c, set()) & set(members(c))) for c in cids]))}
        for name, sup in (("0.5", s["label"] == "supported"), ("T", s["entail_prob"] >= T)):
            s["ok"] = sup & (s["tier"] <= 2)
            s["ok_strict"] = sup & (s["tier"] == 1)
            per = s.groupby("complaint_id").agg(num=("ok", "sum"), den=("ok", "size"), strict=("ok_strict", "sum"),
                                                sup=("ok", lambda x: 0))
            g = s.groupby("complaint_id")
            main_issue = g.apply(lambda t: bool(((t["tier"] == 1) | ((t["tier"] == 2) & t["core"])) [sup.loc[t.index]].any()))
            half_ok = g["ok"].mean() >= 0.5
            block = {"FINAL_ACCURACY": float(s["ok"].mean()), "ci95": boot(per),
                     "strict_accuracy": float(s["ok_strict"].mean()),
                     "supported": float(sup.mean()),
                     "acceptable_drafts": float((main_issue & half_ok).mean()),
                     "supported_share_by_tier": {str(t): float(sup[s["tier"] == t].mean()) if (s["tier"] == t).any() else None
                                                 for t in (1, 2, 3, 4)}}
            for hname, h in (("dev", 0), ("report", 1)):
                m = s["complaint_id"].map(half) == h
                block[f"FINAL_ACCURACY_{hname}_half"] = float(s.loc[m, "ok"].mean())
            res[f"cutoff_{name}"] = block
        out["runs"][run] = res
        if args.rows_out:
            rd = ROOT / args.rows_out
            rd.mkdir(parents=True, exist_ok=True)
            s.assign(ok_cut=(s["label"] == "supported") & (s["tier"] <= 2))[
                ["complaint_id", "sentence_idx", "tier", "ok_cut"]].to_parquet(rd / f"{run}.parquet", index=False)
        a, b = res["cutoff_0.5"], res["cutoff_T"]
        print(f"{run:20s} FINAL ACCURACY  @0.5 {a['FINAL_ACCURACY']:.3f} [{a['ci95'][0]:.3f}, {a['ci95'][1]:.3f}]"
              f"  @T {b['FINAL_ACCURACY']:.3f} [{b['ci95'][0]:.3f}, {b['ci95'][1]:.3f}]"
              f"  | strict @0.5 {a['strict_accuracy']:.3f} | acceptable drafts @0.5 {a['acceptable_drafts']:.3f}"
              f" | tiers {[round(v, 3) for v in res['tier_share'].values()]}")
    (ROOT / args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
