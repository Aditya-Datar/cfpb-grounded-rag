"""Checker validation set and benchmark (proposal M1: NLI checker vs labelled pairs).

    python scripts/checker_benchmark.py sample --runs pilot-bm25 pilot-oracle
        writes annotation/checker_set.jsonl (50 pairs, no labels) and annotation/checker_set.md
    # two annotators of different LLM families label it blind, same protocol as the gold set:
    #   annotation/checker_labels_<name>.jsonl, one {"pair_id", "label", "rationale"} per line,
    #   label "supported" or "unsupported"
    python scripts/checker_benchmark.py compare --a claude-opus-5-5 --b chatgpt
        kappa between annotators; writes annotation/checker_disagreements.md for human adjudication
    # a human fills "- **Adjudicated label:** supported [AD]" for each item in checker_disagreements.md
    python scripts/checker_benchmark.py build-gold --a claude-opus-5-5 --b chatgpt
        writes annotation/checker_gold.jsonl: agreed labels plus the adjudicated ones
    python scripts/checker_benchmark.py score
        checker vs gold: balanced accuracy at the run threshold and at the best threshold,
        AUROC, kappa; writes results/checker_benchmark.json

Sampling: 25 sentences per condition (retrieved, oracle), by SHA-1, so the set
mixes likely-supported and likely-unsupported sentences without looking at the
checker's own scores (selecting by checker score would bias the benchmark).
A sentence is labelled "supported" only if its premise text, on its own,
entails it (a careful reader would accept it as stated by the passage).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, cohen_kappa_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.config import OUTPUT_DIR, ROOT  # noqa: E402
from cfpb.pipeline.corpus import load_corpus  # noqa: E402

ANN = ROOT / "annotation"
SET = ANN / "checker_set.jsonl"
GOLD = ANN / "checker_gold.jsonl"
CORPUS = [str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")]
PER_CONDITION = 25
SEED = "checker-set-v1"


def sample(runs: list[str]) -> None:
    corpus = load_corpus(CORPUS)
    frames = [pd.read_parquet(OUTPUT_DIR / "pipeline_runs" / r / "sentences.parquet").assign(run=r) for r in runs]
    s = pd.concat(frames, ignore_index=True)
    s["h"] = [hashlib.sha1(f"{SEED}:{r.run}:{r.complaint_id}:{r.sentence_idx}".encode()).hexdigest()
              for r in s.itertuples()]
    picked = s.sort_values("h").groupby("condition").head(PER_CONDITION).sort_values(["condition", "h"])
    rows = []
    for i, r in enumerate(picked.itertuples(), 1):
        premise = "\n\n".join(f"[{cid}]\n{corpus.get(cid).text}" for cid in r.premise_chunk_ids)
        rows.append({"pair_id": f"K{i:02d}", "complaint_id": r.complaint_id, "condition": r.condition,
                     "run": r.run, "sentence_idx": int(r.sentence_idx), "sentence": r.sentence,
                     "premise_chunk_ids": list(r.premise_chunk_ids), "premise": premise,
                     "checker_entail": float(r.entail_prob)})
    with open(SET, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    # Annotator view: no condition, run or checker score (keeps labelling blind).
    md = ["# Checker validation set: label each pair supported / unsupported\n",
          "Label **supported** only if the passage text alone entails the sentence. Background knowledge, "
          "plausible inferences and true-but-unstated facts are **unsupported**.\n"]
    for row in rows:
        md += [f"## {row['pair_id']}\n", f"**Sentence:** {row['sentence']}\n", "**Passage:**\n",
               "```text\n" + row["premise"] + "\n```\n"]
    (ANN / "checker_set.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {SET} and checker_set.md: {len(rows)} pairs", picked["condition"].value_counts().to_dict())


def _labels(name: str) -> pd.Series:
    df = pd.read_json(ANN / f"checker_labels_{name}.jsonl", lines=True, dtype=str)
    assert set(df["label"]) <= {"supported", "unsupported"}, f"bad labels in {name}"
    return df.set_index("pair_id")["label"]


def compare(a: str, b: str) -> None:
    pairs = pd.read_json(SET, lines=True, dtype=str).set_index("pair_id")
    la, lb = _labels(a), _labels(b)
    ids = sorted(set(la.index) & set(lb.index) & set(pairs.index))
    assert len(ids) == len(pairs), f"{len(pairs) - len(ids)} pairs missing a label"
    agree = (la[ids] == lb[ids]).mean()
    kappa = cohen_kappa_score(la[ids], lb[ids])
    dis = [i for i in ids if la[i] != lb[i]]
    md = [f"# Checker set disagreements ({a} vs {b})\n", f"Agreement {agree:.1%}, Cohen's kappa {kappa:.3f}, "
          f"{len(dis)} to adjudicate.\n"]
    for i in dis:
        md += [f"## {i}\n", f"**Sentence:** {pairs.loc[i, 'sentence']}\n",
               f"- {a}: {la[i]}\n- {b}: {lb[i]}\n- **Adjudicated label:** \n",
               "```text\n" + pairs.loc[i, "premise"] + "\n```\n"]
    (ANN / "checker_disagreements.md").write_text("\n".join(md), encoding="utf-8")
    print(f"agreement {agree:.3f}, kappa {kappa:.3f}, disagreements {len(dis)}; wrote checker_disagreements.md")


def build_gold(a: str, b: str) -> None:
    """Agreed labels, plus the human decision for every disagreement (refuses if any is blank)."""
    import re
    la, lb = _labels(a), _labels(b)
    text = (ANN / "checker_disagreements.md").read_text(encoding="utf-8")
    decided = {}
    for block in re.split(r"^## ", text, flags=re.M)[1:]:  # one block per disagreement
        m = re.search(r"\*\*Adjudicated label:\*\*[ \t]*(supported|unsupported)\b", block)
        if m:
            decided[block.split()[0]] = m.group(1)
    rows, missing = [], []
    for pid in sorted(la.index):
        if la[pid] == lb[pid]:
            rows.append({"pair_id": pid, "gold_label": la[pid], "source": "agreed"})
        elif pid in decided:
            rows.append({"pair_id": pid, "gold_label": decided[pid], "source": "adjudicated"})
        else:
            missing.append(pid)
    if missing:
        sys.exit(f"not written: no adjudicated label for {missing}")
    with open(GOLD, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    src = pd.DataFrame(rows)
    print(f"wrote {GOLD}: {len(rows)} pairs", src["gold_label"].value_counts().to_dict(),
          src["source"].value_counts().to_dict())


def score() -> None:
    pairs = pd.read_json(SET, lines=True, dtype={"pair_id": str})
    gold = pd.read_json(GOLD, lines=True, dtype=str)
    df = pairs.merge(gold, on="pair_id", validate="1:1")
    assert len(df) == len(pairs), "every pair needs a gold label"
    y = (df["gold_label"] == "supported").to_numpy()
    s = df["checker_entail"].to_numpy()
    info = json.loads((OUTPUT_DIR / "pipeline_runs" / df["run"].iloc[0] / "run_info.json").read_text(encoding="utf-8"))
    t_run = float(info["verifier"]["threshold"])

    def at(t):
        pred = s >= t
        return {"threshold": float(t), "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
                "accuracy": float((pred == y).mean()), "kappa_vs_gold": float(cohen_kappa_score(y, pred)),
                "flagged_unsupported_recall": float((~pred & ~y).sum() / max((~y).sum(), 1))}

    best = max((at(t) for t in np.unique(np.r_[s, t_run])), key=lambda m: m["balanced_accuracy"])
    out = {"n": len(df), "n_supported_gold": int(y.sum()), "verifier": info["verifier"],
           "auroc": float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else None,
           "at_run_threshold": at(t_run),
           "best_threshold_in_sample": {**best, "note": "tuned on the same 50 pairs; optimistic"},
           "by_condition": {}}
    for c in sorted(df["condition"].unique()):
        m = df["condition"] == c
        yy, pp = y[m], s[m] >= t_run
        out["by_condition"][c] = {"n": int(m.sum()), "gold_supported": int(yy.sum()),
                                  "accuracy": float((pp == yy).mean())}
    path = ROOT / "results" / "checker_benchmark.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("sample")
    sp.add_argument("--runs", nargs="+", required=True)
    cp = sub.add_parser("compare")
    cp.add_argument("--a", required=True)
    cp.add_argument("--b", required=True)
    gp = sub.add_parser("build-gold")
    gp.add_argument("--a", required=True)
    gp.add_argument("--b", required=True)
    sub.add_parser("score")
    args = ap.parse_args()
    if args.cmd == "sample":
        sample(args.runs)
    elif args.cmd == "compare":
        compare(args.a, args.b)
    elif args.cmd == "build-gold":
        build_gold(args.a, args.b)
    else:
        score()


if __name__ == "__main__":
    main()
