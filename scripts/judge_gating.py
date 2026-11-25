"""Independent check of verification gating with a second-family judge (EXPERIMENT_LOG E10).

    .venv/Scripts/python.exe scripts/judge_gating.py --run dev-super_rubric_gate-keep

The gate and the headline metric use the same NLI checker, so NLI gains could be writing
for that checker. This re-scores every sentence that gating rewrote, before and after,
with the GPT-5.6 Sol judge (Codex, evaluation only; judge-v1 prompt, same premises), plus a
control sample of unrewritten sentences. Writes results/judge_gating_<run>.json.
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

from cfpb.pipeline.corpus import load_corpus  # noqa: E402
from cfpb.verify.llm_judge import LLMJudgeVerifier  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="dev-super_rubric_gate-keep")
    ap.add_argument("--control", type=int, default=30)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    s = pd.read_parquet(ROOT / "outputs" / "pipeline_runs" / args.run / "sentences.parquet")
    base = pd.read_parquet(ROOT / "outputs" / "pipeline_runs" / "full-super_rubric_top1" / "sentences.parquet")
    base = base.set_index(["complaint_id", "sentence_idx"])
    corpus = load_corpus([str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")])
    judge = LLMJudgeVerifier("codex:gpt-5.6-sol")

    rev = s[s["revised_round"] > 0]
    ctrl = s[s["revised_round"] == 0].sample(min(args.control, (s["revised_round"] == 0).sum()), random_state=0)
    jobs = []
    for r in rev.itertuples():
        b = base.loc[(r.complaint_id, r.sentence_idx)]
        jobs.append(("before", r.complaint_id, r.sentence_idx, r.original, list(b["premise_chunk_ids"]), r.original_entail))
        jobs.append(("after", r.complaint_id, r.sentence_idx, r.sentence, list(r.premise_chunk_ids), r.entail_prob))
    for r in ctrl.itertuples():
        jobs.append(("control", r.complaint_id, r.sentence_idx, r.sentence, list(r.premise_chunk_ids), r.entail_prob))

    def one(j):
        return judge.score([corpus.get(p).text for p in j[4]], j[3])

    with ThreadPoolExecutor(args.workers) as ex:
        scores = list(ex.map(one, jobs))
    rows = [{"kind": j[0], "complaint_id": j[1], "sentence_idx": int(j[2]), "sentence": j[3], "nli": float(j[5]),
             "gpt_prob": float(c), "gpt_label": lab} for j, (c, lab) in zip(jobs, scores)]
    df = pd.DataFrame(rows)
    summ = {}
    for k in ("before", "after", "control"):
        x = df[df["kind"] == k]
        summ[k] = {"n": len(x), "gpt_supported@0.5": float((x["gpt_prob"] >= 0.5).mean()) if len(x) else None,
                   "gpt_supported@1.0": float((x["gpt_prob"] >= 1.0).mean()) if len(x) else None,
                   "nli_supported@0.5": float((x["nli"] >= 0.5).mean()) if len(x) else None}
    if len(rev):
        b = df[df["kind"] == "before"]["gpt_prob"].to_numpy()
        a = df[df["kind"] == "after"]["gpt_prob"].to_numpy()
        rng = np.random.default_rng(0)
        d = (a >= 0.5).astype(float) - (b >= 0.5).astype(float)
        bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(10000)]
        summ["after_minus_before_gpt@0.5"] = {"diff": float(d.mean()), "ci95": [float(np.percentile(bs, 2.5)),
                                                                                float(np.percentile(bs, 97.5))]}
    out = {"run": args.run, "judge": "codex:gpt-5.6-sol", "summary": summ, "rows": rows}
    (ROOT / "results" / f"judge_gating_{args.run}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
