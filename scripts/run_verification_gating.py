"""Verification gating: send checker-flagged sentences back to the drafter (EXPERIMENT_LOG E10).

    .venv/Scripts/python.exe scripts/run_verification_gating.py --base full-super_rubric_top1 \
        --ids annotation/attribution_ids_dev.txt --name dev-super_rubric_gate

Starts from a finished pipeline run (its drafts and NLI scores are reused). Every sentence
whose NLI entailment is below the gate (default T) goes back to the same drafter with the
same passages, flagged, and is rewritten so that each statement is stated in the cited
passages (or answered DROP). Rewrites are re-checked by the same NLI checker; a rewrite
replaces the sentence only if it scores higher. Up to --rounds rounds.

Writes two runs that scripts/score_clusters.py can score:
  <name>-keep : sentences still below the gate stay in the draft (flagged for the officer)
  <name>-drop : sentences still below the gate are removed (coverage reported)
plus <name>-keep/gating_log.jsonl with every original/rewrite pair and score.

Caveat: the gate and the evaluation use the same checker, so gains partly reflect writing
for that checker; an independent judge should re-score a sample.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cfpb.annotation import load_items  # noqa: E402
from cfpb.config import OUTPUT_DIR  # noqa: E402
from cfpb.generate.nemotron import MAX_COMPLAINT_WORDS, NemotronGenerator, format_passages  # noqa: E402
from cfpb.pipeline.corpus import load_corpus  # noqa: E402
from cfpb.verify.nli import NLIVerifier  # noqa: E402

T = 0.99658203125
from cfpb.generate.revise import CACHE  # noqa: E402

from cfpb.generate.revise import _LINE, _THINK, REVISE_SYSTEM, REVISE_USER, REVISE_VERSION  # noqa: E402,F401  (shared with the app)


def overlap(sentence: str, premise: str) -> float:
    w = re.findall(r"[a-z0-9]+", sentence.lower())
    p = set(re.findall(r"[a-z0-9]+", premise.lower()))
    return sum(x in p for x in w) / max(1, len(w))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="full-super_rubric_top1")
    ap.add_argument("--ids", default="annotation/attribution_ids_dev.txt")
    ap.add_argument("--name", default="dev-super_rubric_gate")
    ap.add_argument("--gate", type=float, default=T)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    base = ROOT / "outputs" / "pipeline_runs" / args.base
    ids = [l.strip() for l in open(ROOT / args.ids, encoding="utf-8") if l.strip()]
    sents = pd.read_parquet(base / "sentences.parquet")
    sents = sents[sents["complaint_id"].isin(ids)].sort_values(["complaint_id", "sentence_idx"]).reset_index(drop=True)
    ranked = pd.read_parquet(base / "ranked.parquet")
    ranked = ranked[ranked["complaint_id"].isin(ids)]
    corpus = load_corpus([str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")])
    items = load_items().set_index("complaint_id")
    gen, nli = NemotronGenerator(), NLIVerifier()

    ctx = {cid: [corpus.get(r.chunk_id).ranked(int(r.rank), float(r.score))
                 for r in g.sort_values("rank").itertuples()] for cid, g in ranked.groupby("complaint_id")}

    # current state per sentence
    rows = [dict(r) for r in sents.to_dict("records")]
    for r in rows:
        r.update(original=r["sentence"], original_entail=r["entail_prob"], revised_round=0, dropped_by_model=False)

    def call(messages):
        key = hashlib.sha1(json.dumps([gen.model, REVISE_VERSION, messages], ensure_ascii=False).encode()).hexdigest()
        path = CACHE / f"{key}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = gen._call(messages)
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return _THINK.sub("", data["choices"][0]["message"].get("content") or "")

    log = []
    for rnd in range(1, args.rounds + 1):
        todo = {}
        for i, r in enumerate(rows):
            if r["entail_prob"] < args.gate and not r["dropped_by_model"]:
                todo.setdefault(r["complaint_id"], []).append(i)
        print(f"round {rnd}: {sum(map(len, todo.values()))} flagged sentences in {len(todo)} drafts", flush=True)
        if not todo:
            break

        def ask(cid):
            mine = [i for i, r in enumerate(rows) if r["complaint_id"] == cid]
            draft = "\n".join(f"S{k + 1}{' (FLAGGED)' if i in todo[cid] else ''}: {rows[i]['sentence']}"
                              for k, i in enumerate(mine))
            complaint = " ".join(items.loc[cid, "narrative_clean"].split()[:MAX_COMPLAINT_WORDS])
            msg = [{"role": "system", "content": REVISE_SYSTEM},
                   {"role": "user", "content": REVISE_USER.format(complaint=complaint, passages=format_passages(ctx[cid]),
                                                                  draft=draft)}]
            out = {}
            for line in call(msg).splitlines():
                m = _LINE.match(line)
                if m and 0 < int(m.group(1)) <= len(mine) and mine[int(m.group(1)) - 1] in todo[cid]:
                    out[mine[int(m.group(1)) - 1]] = m.group(2)
            return out

        with ThreadPoolExecutor(args.workers) as ex:
            answers = dict(zip(todo, ex.map(ask, todo)))

        n_better = 0
        for cid, ans in answers.items():
            c = ctx[cid]
            by_id = {x.chunk_id: x for x in c}
            for i in todo[cid]:
                text = ans.get(i)
                r = rows[i]
                entry = {"complaint_id": cid, "sentence_idx": int(r["sentence_idx"]), "round": rnd,
                         "before": r["sentence"], "before_entail": r["entail_prob"], "answer": text}
                if text is None:
                    entry["outcome"] = "no answer"
                elif text.strip().upper().startswith("DROP"):
                    r["dropped_by_model"] = True
                    entry["outcome"] = "model DROP"
                else:
                    tags = re.findall(r"\[P(\d+)\]", text)
                    pids = [c[int(t) - 1].chunk_id for t in dict.fromkeys(tags) if 0 < int(t) <= len(c)] or list(by_id)
                    clean = re.sub(r"\s+([.!?,;:])", r"\1", re.sub(r"\s*\[(?:P\d+|NONE)\]", "", text)).strip()
                    e, k = nli.score([by_id[p].text for p in pids], clean)
                    entry.update(after=clean, after_entail=e, after_premise=pids)
                    if e > r["entail_prob"]:
                        r.update(sentence=clean, premise_chunk_ids=pids, entail_prob=e, contradict_prob=k,
                                 revised_round=rnd)
                        entry["outcome"] = "accepted"
                        n_better += 1
                    else:
                        entry["outcome"] = "rejected (not higher)"
                log.append(entry)
        print(f"round {rnd}: {n_better} rewrites accepted", flush=True)

    for r in rows:
        r["label"] = "supported" if r["entail_prob"] >= 0.5 else "unsupported"
        r["threshold"] = 0.5
        premise = " ".join(corpus.get(p).text for p in r["premise_chunk_ids"])
        r["overlap"] = overlap(r["sentence"], premise)
        r["premise_chunk_ids"] = list(r["premise_chunk_ids"])

    cols = list(sents.columns) + ["original", "original_entail", "revised_round", "dropped_by_model", "overlap"]
    keep = pd.DataFrame(rows)[cols]
    drop = keep[(keep["entail_prob"] >= args.gate) & ~keep["dropped_by_model"]]
    info = {"base": args.base, "ids": args.ids, "gate": args.gate, "rounds": args.rounds, "revise_prompt": REVISE_VERSION,
            "drafter": gen.model, "n_complaints": len(ids), "n_sentences": len(keep),
            "revised": int((keep["revised_round"] > 0).sum()), "model_drops": int(keep["dropped_by_model"].sum())}
    for suffix, df in (("keep", keep), ("drop", drop)):
        d = ROOT / "outputs" / "pipeline_runs" / f"{args.name}-{suffix}"
        d.mkdir(parents=True, exist_ok=True)
        df.to_parquet(d / "sentences.parquet", index=False)
        ranked.to_parquet(d / "ranked.parquet", index=False)
        shutil.copy(base / "classification.parquet", d / "classification.parquet")
        cov = {"sentences_kept": len(df), "share_kept": len(df) / max(1, len(keep)),
               "drafts_with_any_sentence": int(df["complaint_id"].nunique()), "drafts": len(ids)}
        (d / "run_info.json").write_text(json.dumps({**info, "policy": suffix, **cov}, indent=1), encoding="utf-8")
    with open(ROOT / "outputs" / "pipeline_runs" / f"{args.name}-keep" / "gating_log.jsonl", "w", encoding="utf-8") as f:
        for e in log:
            f.write(json.dumps(e, ensure_ascii=False, default=float) + "\n")

    before = sents["entail_prob"]
    print(json.dumps(info, indent=1))
    print(f"supported @0.5: {(before >= 0.5).mean():.3f} -> {(keep['entail_prob'] >= 0.5).mean():.3f}; "
          f"@T: {(before >= T).mean():.3f} -> {(keep['entail_prob'] >= T).mean():.3f}; "
          f"overlap {keep['overlap'].mean():.3f}; drop policy keeps {len(drop)}/{len(keep)} sentences, "
          f"{drop['complaint_id'].nunique()}/{len(ids)} drafts non-empty")


if __name__ == "__main__":
    main()
