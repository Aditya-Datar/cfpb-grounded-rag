"""Re-score finished runs with the DeBERTa + Nemotron Ultra ensemble checker (EXPERIMENT_LOG E12d).

    .venv/Scripts/python.exe scripts/rescore_ensemble.py --runs full-super_rubric_top1 heldout-super_rubric_gate-keep \
        --half 1

Ensemble score = mean(DeBERTa entail, Ultra judge support probability); supported if
>= CUT, the cutoff chosen on checker set 1 (results/checker_ultra_compare.json; set 2 BA
0.829 vs 0.679 for NLI@T). Ultra uses the judge-v1 prompt and the same premises as NLI.
Writes outputs/pipeline_runs/<run>+ens/ with entail_prob = ensemble score and
label = supported/unsupported at CUT, so scripts/score_clusters.py's "@0.5" column reads
the ensemble decision (its "@T" column is not meaningful for these runs).
"""
import argparse
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cfpb.pipeline.corpus import load_corpus  # noqa: E402
from cfpb.retrieval.metrics import half  # noqa: E402
from cfpb.verify.llm_judge import LLMJudgeVerifier  # noqa: E402

ULTRA = "nvidia/nemotron-3-ultra-550b-a55b"
CUT = json.loads((ROOT / "results" / "checker_ultra_compare.json").read_text())["nli_or_ultra_avg"]["cut_set1"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--half", type=int, default=None, help="only this half (1 = held-out)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--suffix", default="+ens", help="output run folder suffix")
    args = ap.parse_args()
    corpus = load_corpus([str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")])
    judge = LLMJudgeVerifier(ULTRA)
    for run in args.runs:
        src = ROOT / "outputs" / "pipeline_runs" / run
        s = pd.read_parquet(src / "sentences.parquet")
        if args.half is not None:
            s = s[s["complaint_id"].map(half) == args.half].reset_index(drop=True)
        print(f"{run}: {len(s)} sentences", flush=True)

        def one(r):
            return judge.score([corpus.get(c).text for c in r.premise_chunk_ids], r.sentence)

        with ThreadPoolExecutor(args.workers) as ex:
            res = list(ex.map(one, s.itertuples()))
        s["nli_entail"] = s["entail_prob"]
        s["ultra_prob"] = [p for p, _ in res]
        s["ultra_label"] = [lab for _, lab in res]
        s["entail_prob"] = (s["nli_entail"] + s["ultra_prob"]) / 2
        s["label"] = ["supported" if e >= CUT else "unsupported" for e in s["entail_prob"]]
        s["threshold"] = CUT
        s["verifier"] = f"mean(nli, {ULTRA})"
        dst = ROOT / "outputs" / "pipeline_runs" / f"{run}{args.suffix}"
        dst.mkdir(parents=True, exist_ok=True)
        s.to_parquet(dst / "sentences.parquet", index=False)
        for f in ("ranked.parquet", "classification.parquet"):
            if (src / f).exists():
                shutil.copy(src / f, dst / f)
        (dst / "run_info.json").write_text(json.dumps({"base": run, "half": args.half, "checker": s["verifier"][0],
                                                       "cut": CUT, "unreadable": int((s.ultra_label == "unreadable").sum())},
                                                      indent=1), encoding="utf-8")
        print(f"{run}: supported NLI@T {(s.nli_entail >= 0.99658203125).mean():.3f}, Ultra {(s.ultra_prob >= 0.5).mean():.3f}, "
              f"ensemble {(s.entail_prob >= CUT).mean():.3f}", flush=True)


if __name__ == "__main__":
    main()
