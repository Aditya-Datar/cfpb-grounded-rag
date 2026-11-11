"""Benchmark the LLM entailment judge against the human-adjudicated checker labels (H4).

    python scripts/llm_judge.py                                    # first set, default judge
    python scripts/llm_judge.py --tag v2 --model google/gemma-4-31b-it

Reads annotation/checker_set[_<tag>].jsonl and checker_gold[_<tag>].jsonl and scores
the judge and the NLI checker on the same pairs: balanced accuracy and kappa at the
judge's own label, AUROC on its confidence, and the paired bootstrap difference in
balanced accuracy (judge minus NLI at its run threshold, or --nli-tau).
Writes results/llm_judge_<model>[_<tag>].json. Needs NVIDIA_API_KEY (env or .env).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, cohen_kappa_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.config import ROOT  # noqa: E402
from cfpb.pipeline.corpus import load_corpus  # noqa: E402
from cfpb.verify.llm_judge import DEFAULT_JUDGE, JUDGE_PROMPT_VERSION, LLMJudgeVerifier  # noqa: E402

ANN = ROOT / "annotation"
CORPUS = [str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_JUDGE)
    ap.add_argument("--tag", default="")
    ap.add_argument("--nli-tau", type=float, default=0.5, help="NLI cutoff to compare against")
    ap.add_argument("--n-boot", type=int, default=10000)
    args = ap.parse_args()
    sfx = f"_{args.tag}" if args.tag else ""

    pairs = pd.read_json(ANN / f"checker_set{sfx}.jsonl", lines=True, dtype={"pair_id": str})
    gold = pd.read_json(ANN / f"checker_gold{sfx}.jsonl", lines=True, dtype=str)
    df = pairs.merge(gold, on="pair_id", validate="1:1")
    assert len(df) == len(pairs), "every pair needs a gold label"
    corpus = load_corpus(CORPUS)
    judge = LLMJudgeVerifier(args.model)

    probs, labels = [], []
    for r in df.itertuples():  # same premise text the pipeline verifier would see
        p, lab = judge.score([corpus.get(c).text for c in r.premise_chunk_ids], r.sentence)
        probs.append(p)
        labels.append(lab)
    y = (df["gold_label"] == "supported").to_numpy()
    pj = np.array(probs) >= 0.5
    pn = df["checker_entail"].to_numpy() >= args.nli_tau

    def stats(pred):
        return {"balanced_accuracy": float(balanced_accuracy_score(y, pred)), "kappa_vs_gold": float(cohen_kappa_score(y, pred)),
                "accuracy": float((pred == y).mean()),
                "flagged_unsupported_recall": float((~pred & ~y).sum() / max((~y).sum(), 1))}

    rng = np.random.default_rng(0)
    diffs = []
    for _ in range(args.n_boot):
        i = rng.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            diffs.append(balanced_accuracy_score(y[i], pj[i]) - balanced_accuracy_score(y[i], pn[i]))

    out = {"judge_model": args.model, "prompt_version": JUDGE_PROMPT_VERSION, "label_set": f"checker_set{sfx}",
           "n": int(len(y)), "n_supported_gold": int(y.sum()),
           "unreadable_replies": int(sum(lab == "unreadable" for lab in labels)),
           "judge": {**stats(pj), "auroc_confidence": float(roc_auc_score(y, probs)) if 0 < y.sum() < len(y) else None},
           "nli": {**stats(pn), "tau": args.nli_tau, "auroc": float(roc_auc_score(y, df["checker_entail"]))},
           "judge_minus_nli_balanced_accuracy": {"mean": float(balanced_accuracy_score(y, pj) - balanced_accuracy_score(y, pn)),
                                                 "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]},
           "per_pair": [{"pair_id": p, "gold": g, "judge_prob": float(q), "judge_label": lab}
                        for p, g, q, lab in zip(df["pair_id"], df["gold_label"], probs, labels)]}
    path = ROOT / "results" / f"llm_judge_{args.model.split('/')[-1]}{sfx}.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "per_pair"}, indent=2))
    print("wrote", path)


if __name__ == "__main__":
    main()
