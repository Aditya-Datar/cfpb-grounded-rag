"""Drafter fix in the finalized pipeline (EXPERIMENT_LOG E17; pre-registered before running).

    .venv/Scripts/python.exe scripts/run_drafter_fix.py --split dev --arms B0 B1 B2
    .venv/Scripts/python.exe scripts/run_drafter_fix.py --split heldout --arms B0 <chosen>   # only if the rule fires

Frozen: the finalized pipeline's retrieval (GPT-5.6 Sol reranker + rubric hints, top1x5 context:
outputs/pipeline_runs/full-gpt_rubric_top1/ranked.parquet), the drafter model (Super, temperature 0),
the checker (mean(DeBERTa, Ultra) >= CUT, src/cfpb/verify/ensemble.py) and verification gating exactly
as the app runs it (cfpb.generate.revise.gate_draft with the ensemble checker, 2 rounds, keep policy).
Only the drafter's rule 1 changes:
  B0  prompt v1 (the app today)
  B1  quote-anchored (E13 A3) + choose the provisions that govern what the consumer asks the company to fix
  B2  B1 + each sentence opens with a short phrase naming the part of the complaint it answers
Scored by scripts/score_clusters.py (FINAL ACCURACY, frozen clusters); guard "addresses the complaint"
(Ultra, one call per draft, same prompt as E13). Paired bootstrap over complaints vs B0.
Writes outputs/pipeline_runs/fix-<arm>-<split>-{nogate,gate}/ and results/drafter_fix_<split>.json.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from run_drafter_ablation import A3_RULE1, RELEVANCE, RULE1, ArmGenerator  # noqa: E402

from cfpb.annotation import load_items  # noqa: E402
from cfpb.generate import nemotron as nm  # noqa: E402
from cfpb.generate.revise import gate_draft  # noqa: E402
from cfpb.pipeline.corpus import load_corpus  # noqa: E402
from cfpb.verify.ensemble import CUT, ULTRA, EnsembleVerifier  # noqa: E402

BASE = ROOT / "outputs" / "pipeline_runs" / "full-gpt_rubric_top1"
B1_RULE1 = A3_RULE1 + (" Choose the provisions that govern what the consumer is asking the company to fix, the most "
                       "directly relevant first.")
B2_RULE1 = B1_RULE1 + (" Begin each sentence with a short phrase naming the part of the complaint it answers (for "
                       "example: \"On the disputed late payment, ...\"), then restate the provision.")
ARMS = {"B0": None, "B1": B1_RULE1, "B2": B2_RULE1}
IDS = {"dev": "annotation/attribution_ids_dev.txt", "heldout": "annotation/attribution_ids_heldout.txt"}
REL_CACHE = ROOT / "outputs" / "drafter_ablation" / "relevance_cache"  # shared with E13


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=list(IDS), default="dev")
    ap.add_argument("--arms", nargs="+", default=list(ARMS))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--context", choices=["retrieved", "oracle"], default="retrieved",
                    help="oracle: gold-section chunks (k 5) from full-oracle-local, for the attribution comparison")
    ap.add_argument("--limit", type=int, default=None, help="smoke test on the first N complaints")
    args = ap.parse_args()
    ids = [l.strip() for l in open(ROOT / IDS[args.split], encoding="utf-8") if l.strip()][:args.limit]
    items = load_items().set_index("complaint_id")
    corpus = load_corpus([str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")])
    base = BASE if args.context == "retrieved" else ROOT / "outputs" / "pipeline_runs" / "full-oracle-local"
    tag0 = "" if args.context == "retrieved" else "oracle-"
    ranked = pd.read_parquet(base / "ranked.parquet")
    ranked = ranked[ranked.complaint_id.isin(ids)]
    ctx = {cid: [corpus.get(r.chunk_id).ranked(int(r.rank), float(r.score)) for r in g.sort_values("rank").itertuples()]
           for cid, g in ranked.groupby("complaint_id")}
    checker = EnsembleVerifier()
    _ = checker._model  # load DeBERTa once, before the worker threads (lazy import is not thread-safe)
    reviser = nm.NemotronGenerator()  # the app's drafter rewrites flagged sentences
    rel_client = nm.NemotronGenerator(model=ULTRA)

    def relevance(cid, sentences):
        msg = RELEVANCE.format(complaint=" ".join(items.loc[cid, "narrative_clean"].split()[:600]), draft=" ".join(sentences))
        f = REL_CACHE / (hashlib.sha1(json.dumps([ULTRA, msg]).encode()).hexdigest() + ".json")
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        text = re.sub(r"<think>.*?</think>", "", rel_client._call([{"role": "user", "content": msg}])["choices"][0]
                      ["message"].get("content") or "", flags=re.S)
        m = re.search(r"\{.*\}", text, re.S)
        try:
            d = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            d = {}
        out = {"addresses": str(d.get("addresses", "")).lower().startswith("y"), "score": float(d.get("score", np.nan))}
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(out), encoding="utf-8")
        return out

    summary = {"split": args.split, "cut": CUT, "context": args.context, "base_retrieval": str(base.relative_to(ROOT)), "arms": {}}
    runs = []
    for arm in args.arms:
        rule = ARMS[arm]
        gen = nm.NemotronGenerator() if rule is None else ArmGenerator(nm.SYSTEM_PROMPT.replace(RULE1, rule), nm.USER_TEMPLATE)

        def one(cid):
            clean = items.loc[cid, "narrative_clean"]
            draft = gen.generate(clean, ctx[cid])
            v0 = checker.verify(draft, ctx[cid]).checks
            parts0 = [checker.last_parts.get(c.sentence, (np.nan, np.nan)) for c in v0]
            texts, cited, checks, info = gate_draft(clean, draft, ctx[cid], reviser, checker, CUT, 2)
            parts1 = [checker.last_parts.get(c.sentence, (np.nan, np.nan)) for c in checks]
            return cid, draft, v0, parts0, texts, checks, parts1, info

        with ThreadPoolExecutor(args.workers) as ex:
            res = list(ex.map(one, ids))
        print(f"{arm}: drafted, checked and gated {len(res)} complaints", flush=True)
        rel_before = {cid: relevance(cid, d.sentences) for cid, d, *_ in res}
        rel_after = {cid: relevance(cid, t) for cid, _, _, _, t, *_ in res}
        for tag, pick in (("nogate", lambda r: (r[2], r[3])), ("gate", lambda r: (r[5], r[6]))):
            rows = []
            for r in res:
                checks, parts = pick(r)
                for c, (e, u) in zip(checks, parts):
                    rows.append({"complaint_id": r[0], "condition": args.context, "sentence_idx": c.sentence_idx,
                                 "sentence": c.sentence, "premise_chunk_ids": list(c.premise_chunk_ids),
                                 "entail_prob": c.entail_prob, "contradict_prob": c.contradict_prob,
                                 "label": "supported" if c.entail_prob >= CUT else "unsupported",
                                 "verifier": checker.model_name, "threshold": CUT, "nli": e, "ultra": u})
            name = f"fix-{tag0}{arm}-{args.split}-{tag}"
            d = ROOT / "outputs" / "pipeline_runs" / name
            d.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_parquet(d / "sentences.parquet", index=False)
            ranked.to_parquet(d / "ranked.parquet", index=False)
            shutil.copy(base / "classification.parquet", d / "classification.parquet")
            rel = rel_before if tag == "nogate" else rel_after
            (d / "run_info.json").write_text(json.dumps({"arm": arm, "rule1": rule, "prompt_version": getattr(gen, "version", nm.PROMPT_VERSION),
                                                         "gating": tag == "gate", "checker": checker.model_name, "cut": CUT,
                                                         "split": args.split, "context": args.context}, indent=1), encoding="utf-8")
            summary["arms"][f"{arm}-{tag}"] = {"run": name, "n_sentences": len(rows), "sentences_per_draft": len(rows) / len(ids),
                                               "supported": float(np.mean([x["label"] == "supported" for x in rows])),
                                               "addresses_complaint": float(np.mean([rel[c]["addresses"] for c in ids])),
                                               "rewritten": int(sum(bool(g.get("original")) for r in res for g in r[7])) if tag == "gate" else 0}
            runs.append(name)

    out = ROOT / "results" / f"drafter_fix_{tag0}{args.split}.json"
    rows_dir = "outputs/drafter_fix/rows"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "score_clusters.py"), "--runs", *runs,
                    "--out", f"results/drafter_fix_{tag0}{args.split}_clusters.json", "--rows-out", rows_dir], check=True, cwd=ROOT)
    sc = json.loads((ROOT / "results" / f"drafter_fix_{tag0}{args.split}_clusters.json").read_text(encoding="utf-8"))["runs"]
    for key, m in summary["arms"].items():
        c = sc[m["run"]]["cutoff_0.5"]
        m |= {"FINAL_ACCURACY": c["FINAL_ACCURACY"], "ci95": c["ci95"], "strict_accuracy": c["strict_accuracy"],
              "acceptable_drafts": c["acceptable_drafts"], "tier_share": sc[m["run"]]["tier_share"]}
    rng = np.random.default_rng(0)
    for tag in ("nogate", "gate"):
        ref = ROOT / rows_dir / f"fix-{tag0}B0-{args.split}-{tag}.parquet"
        if not ref.exists():
            continue
        b = pd.read_parquet(ref).groupby("complaint_id").ok_cut.agg(["sum", "size"])
        for arm in args.arms:
            if arm == "B0":
                continue
            a = pd.read_parquet(ROOT / rows_dir / f"fix-{tag0}{arm}-{args.split}-{tag}.parquet").groupby("complaint_id").ok_cut.agg(["sum", "size"])
            j = a.join(b, lsuffix="_a", rsuffix="_b", how="inner")
            na, da, nb, db = (j[c].to_numpy(float) for c in ("sum_a", "size_a", "sum_b", "size_b"))
            idx = rng.integers(0, len(j), (10000, len(j)))
            dd = na[idx].sum(1) / da[idx].sum(1) - nb[idx].sum(1) / db[idx].sum(1)
            summary["arms"][f"{arm}-{tag}"]["minus_B0"] = {"diff": float(na.sum() / da.sum() - nb.sum() / db.sum()),
                                                           "ci95": [float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))]}
    out.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for k, m in summary["arms"].items():
        extra = m.get("minus_B0")
        print(f"{k:12s} FINAL {m['FINAL_ACCURACY']:.3f} [{m['ci95'][0]:.3f}, {m['ci95'][1]:.3f}]  supported {m['supported']:.3f}"
              f"  acceptable {m['acceptable_drafts']:.3f}  addresses {m['addresses_complaint']:.3f}  sent/draft {m['sentences_per_draft']:.2f}"
              + (f"  vs B0 {extra['diff']:+.3f} [{extra['ci95'][0]:+.3f}, {extra['ci95'][1]:+.3f}]" if extra else ""), flush=True)


if __name__ == "__main__":
    main()
