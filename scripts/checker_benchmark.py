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

Second label set (H4, docs/tasks/atharva.md): every command takes --tag, which
suffixes all files (checker_set_<tag>.jsonl, checker_labels_<name>_<tag>.jsonl,
checker_disagreements_<tag>.md, checker_gold_<tag>.jsonl,
results/checker_benchmark_<tag>.json), so the first set is never overwritten.
`sample --exclude-tag ""` skips sentences already in the first set, and
`score --tau 0.37` also reports a cutoff fixed in advance (e.g. tuned on set 1).
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, cohen_kappa_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.config import OUTPUT_DIR, ROOT  # noqa: E402
from cfpb.pipeline.corpus import load_corpus  # noqa: E402

ANN = ROOT / "annotation"
CORPUS = [str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")]
PER_CONDITION = 25
SEED = "checker-set-v1"


def _sfx(tag: str) -> str:
    return f"_{tag}" if tag else ""


def set_path(tag: str = "") -> Path:
    return ANN / f"checker_set{_sfx(tag)}.jsonl"


def gold_path(tag: str = "") -> Path:
    return ANN / f"checker_gold{_sfx(tag)}.jsonl"


def sample(runs: list[str], tag: str = "", per_condition: int = PER_CONDITION,
           exclude_tags: list[str] | None = None) -> None:
    SET = set_path(tag)
    if SET.exists():
        sys.exit(f"{SET} exists; pick another --tag (labels may already point at it)")
    corpus = load_corpus(CORPUS)
    frames = [pd.read_parquet(OUTPUT_DIR / "pipeline_runs" / r / "sentences.parquet").assign(run=r) for r in runs]
    s = pd.concat(frames, ignore_index=True)
    seen = set()
    for t in exclude_tags or []:
        old = pd.read_json(set_path(t), lines=True, dtype=str)
        seen |= set(zip(old["complaint_id"], old["sentence"]))
    s = s[[(str(c), x) not in seen for c, x in zip(s["complaint_id"], s["sentence"])]]
    s["h"] = [hashlib.sha1(f"{SEED}{_sfx(tag)}:{r.run}:{r.complaint_id}:{r.sentence_idx}".encode()).hexdigest()
              for r in s.itertuples()]
    picked = s.sort_values("h").groupby("condition").head(per_condition).sort_values(["condition", "h"])
    rows = []
    for i, r in enumerate(picked.itertuples(), 1):
        premise = "\n\n".join(f"[{cid}]\n{corpus.get(cid).text}" for cid in r.premise_chunk_ids)
        rows.append({"pair_id": f"K{tag}-{i:03d}" if tag else f"K{i:02d}", "complaint_id": r.complaint_id, "condition": r.condition,
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
    (ANN / f"checker_set{_sfx(tag)}.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {SET} and checker_set{_sfx(tag)}.md: {len(rows)} pairs", picked["condition"].value_counts().to_dict())


def _labels(name: str, tag: str = "") -> pd.Series:
    df = pd.read_json(ANN / f"checker_labels_{name}{_sfx(tag)}.jsonl", lines=True, dtype=str)
    assert set(df["label"]) <= {"supported", "unsupported"}, f"bad labels in {name}"
    return df.set_index("pair_id")["label"]


def compare(a: str, b: str, tag: str = "") -> None:
    pairs = pd.read_json(set_path(tag), lines=True, dtype=str).set_index("pair_id")
    la, lb = _labels(a, tag), _labels(b, tag)
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
    out = ANN / f"checker_disagreements{_sfx(tag)}.md"
    if out.exists() and re.search(r"Adjudicated label:\*\*[ \t]*(supported|unsupported)", out.read_text(encoding="utf-8")):
        sys.exit(f"{out} already has adjudicated labels; not overwritten")
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"agreement {agree:.3f}, kappa {kappa:.3f}, disagreements {len(dis)}; wrote {out.name}")


def build_gold(a: str, b: str, tag: str = "") -> None:
    """Agreed labels, plus the human decision for every disagreement (refuses if any is blank)."""
    la, lb = _labels(a, tag), _labels(b, tag)
    GOLD = gold_path(tag)
    text = (ANN / f"checker_disagreements{_sfx(tag)}.md").read_text(encoding="utf-8")
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


def score(tag: str = "", tau: float | None = None) -> None:
    pairs = pd.read_json(set_path(tag), lines=True, dtype={"pair_id": str})
    gold = pd.read_json(gold_path(tag), lines=True, dtype=str)
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

    # Honest estimate of a tuned cutoff: 5-fold CV (cutoff picked on 4 folds, applied to the 5th), 50 repeats.
    def pick(xs, ys):
        return max(np.unique(xs), key=lambda t: balanced_accuracy_score(ys, xs >= t))
    rng, reps = np.random.default_rng(0), []
    for _ in range(50):
        folds, pred = rng.permutation(len(y)) % 5, np.zeros(len(y), bool)
        for f in range(5):
            tr, te = folds != f, folds == f
            pred[te] = s[te] >= pick(s[tr], y[tr])
        reps.append([balanced_accuracy_score(y, pred), cohen_kappa_score(y, pred), (~pred & ~y).sum() / (~y).sum()])
    reps = np.array(reps)

    out = {"n": len(df), "n_supported_gold": int(y.sum()), "verifier": info["verifier"],
           "auroc": float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else None,
           "at_run_threshold": at(t_run),
           **({"at_fixed_tau": {**at(tau), "note": "cutoff fixed before seeing this set"}} if tau is not None else {}),
           "best_threshold_in_sample": {**best, "note": "tuned on the same 50 pairs; optimistic"},
           "tuned_threshold_5fold_cv": {"balanced_accuracy": float(reps[:, 0].mean()),
                                        "kappa_vs_gold": float(reps[:, 1].mean()),
                                        "flagged_unsupported_recall": float(reps[:, 2].mean()),
                                        "balanced_accuracy_p5_p95": [float(np.percentile(reps[:, 0], 5)),
                                                                     float(np.percentile(reps[:, 0], 95))],
                                        "note": "cutoff chosen on 4 folds, scored on the 5th; 50 repeats"},
           "score_quantiles": {"supported_p10_p50": [float(np.quantile(s[y], q)) for q in (.1, .5)],
                               "unsupported_p50_p90": [float(np.quantile(s[~y], q)) for q in (.5, .9)]},
           "by_condition": {}}
    # Human-label view of the pilot: is the premise from the complaint's gold section?
    corpus = load_corpus(CORPUS)
    gold_sec = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str).set_index(
        "complaint_id")["gold_section"]
    in_gold = np.array([gold_sec[str(c)] in {corpus.get(i).section for i in p}
                        for c, p in zip(df["complaint_id"], df["premise_chunk_ids"])])
    for c in sorted(df["condition"].unique()):
        m = (df["condition"] == c).to_numpy()
        yy, pp = y[m], s[m] >= t_run
        out["by_condition"][c] = {"n": int(m.sum()), "gold_supported": int(yy.sum()),
                                  "gold_supported_and_gold_section": int((yy & in_gold[m]).sum()),
                                  "accuracy": float((pp == yy).mean())}
    path = ROOT / "results" / f"checker_benchmark{_sfx(tag)}.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("sample")
    sp.add_argument("--runs", nargs="+", required=True)
    sp.add_argument("--per-condition", type=int, default=PER_CONDITION)
    sp.add_argument("--exclude-tag", nargs="*", default=None,
                    help='skip sentences already in these sets ("" = the first set)')
    cp = sub.add_parser("compare")
    cp.add_argument("--a", required=True)
    cp.add_argument("--b", required=True)
    gp = sub.add_parser("build-gold")
    gp.add_argument("--a", required=True)
    gp.add_argument("--b", required=True)
    scp = sub.add_parser("score")
    scp.add_argument("--tau", type=float, default=None, help="also report this fixed cutoff")
    for p_ in (sp, cp, gp, scp):
        p_.add_argument("--tag", default="", help="label-set suffix; empty = the first set")
    args = ap.parse_args()
    if args.cmd == "sample":
        sample(args.runs, args.tag, args.per_condition, args.exclude_tag)
    elif args.cmd == "compare":
        compare(args.a, args.b, args.tag)
    elif args.cmd == "build-gold":
        build_gold(args.a, args.b, args.tag)
    else:
        score(args.tag, args.tau)


if __name__ == "__main__":
    main()
