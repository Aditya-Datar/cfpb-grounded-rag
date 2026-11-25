"""Why does the drafter fail with the correct section? Classify flagged oracle sentences (EXPERIMENT_LOG E13).

    .venv/Scripts/python.exe scripts/diagnose_flags.py --run full-oracle-local+ens_dev

Takes the sentences of an oracle run (correct section given) that the ensemble checker
flags, plus a control sample of sentences it supports, and asks two classifiers from
different families (GPT-5.6 Sol via Codex, evaluation only; Nemotron Ultra 550B) to put
each into one category, independently and blind to each other and to the checker score:

  APPLICATION   states the rule correctly but applies it to this complaint's facts or
                parties (the consumer, this company, this account), which the passage
                alone cannot confirm
  ADDED_DETAIL  adds or changes a legal detail not in the passage: a deadline, amount,
                condition, exception, party or right (a real error)
  DROPPED_CONDITION  states a conditional or limited duty as unconditional or broader
  OTHER_SOURCE  relies on a different provision or general knowledge, not this passage
  SUPPORTED     the passage fully supports the sentence as written
Writes results/diagnose_flags.json (per sentence, both labels, agreement, shares).
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cfpb.annotation import load_items  # noqa: E402
from cfpb.generate.nemotron import NemotronGenerator  # noqa: E402
from cfpb.pipeline.corpus import load_corpus  # noqa: E402

CATS = ["APPLICATION", "ADDED_DETAIL", "DROPPED_CONDITION", "OTHER_SOURCE", "SUPPORTED"]
PROMPT = """You are auditing a draft response to a consumer complaint, written for a compliance officer at a US financial company. The draft sentence below cites the regulation passage below. Decide which ONE category describes the sentence.

Categories:
APPLICATION: the sentence states what the passage requires correctly, but it applies the rule to this complaint's specific facts or parties (this consumer, this company, this account, this dispute), which the passage alone cannot confirm.
ADDED_DETAIL: the sentence adds or changes a legal detail that is not in the passage: a deadline, amount, condition, exception, party, procedure or right.
DROPPED_CONDITION: the sentence states a duty that the passage makes conditional or limited as if it were unconditional or broader (a qualifying condition, exception or scope limit is missing).
OTHER_SOURCE: the sentence relies on a different provision or general knowledge rather than this passage.
SUPPORTED: the passage fully supports the sentence as written.

Complaint (for context only):
{complaint}

Regulation passage:
{passage}

Draft sentence:
{sentence}

Answer with JSON only: {{"category": "<one of APPLICATION, ADDED_DETAIL, DROPPED_CONDITION, OTHER_SOURCE, SUPPORTED>", "reason": "<one short sentence>"}}"""
VERSION = "diag1-" + hashlib.sha1(PROMPT.encode()).hexdigest()[:8]
CACHE = ROOT / "outputs" / "diagnose_cache"
ULTRA = "nvidia/nemotron-3-ultra-550b-a55b"
MODELS = {"ultra": ULTRA, "deepseek": "deepseek-ai/deepseek-v4.1-flash", "gpt": "codex:gpt-5.6-sol"}


def ask(model: str, prompt: str) -> str:
    key = hashlib.sha1(json.dumps([model, VERSION, prompt]).encode()).hexdigest()
    f = CACHE / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))["text"]
    msgs = [{"role": "user", "content": prompt}]
    if model.startswith("codex:"):
        from cfpb.verify.codex_client import CodexClient
        data = CodexClient(model.split(":", 1)[1])._call(msgs)
    else:
        data = NemotronGenerator(model=model, max_tokens=16384)._call(msgs)
    text = re.sub(r"<think>.*?</think>", "", data["choices"][0]["message"].get("content") or "", flags=re.S)
    if text.strip():
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"text": text}), encoding="utf-8")
    return text


def parse(text: str) -> tuple[str, str]:
    m = re.search(r"\{.*\}", text, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    cat = str(d.get("category", "")).strip().upper()
    if cat not in CATS:
        cat = next((c for c in CATS if c in text.upper()), "UNREADABLE")
    return cat, str(d.get("reason", ""))[:300]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="full-oracle-local+ens_dev")
    ap.add_argument("--controls", type=int, default=25)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--classifiers", nargs="+", default=["ultra"], choices=list(MODELS))
    args = ap.parse_args()
    s = pd.read_parquet(ROOT / "outputs" / "pipeline_runs" / args.run / "sentences.parquet")
    corpus = load_corpus([str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")])
    items = load_items().set_index("complaint_id")
    flagged = s[s["label"] == "unsupported"].assign(kind="flagged")
    ctrl = s[s["label"] == "supported"].sample(min(args.controls, (s["label"] == "supported").sum()), random_state=0)
    rows = pd.concat([flagged, ctrl.assign(kind="control")], ignore_index=True)
    prompts = [PROMPT.format(complaint=" ".join(items.loc[r.complaint_id, "narrative_clean"].split()[:600]),
                             passage="\n\n".join(corpus.get(c).text for c in r.premise_chunk_ids), sentence=r.sentence)
               for r in rows.itertuples()]
    out = {}
    names = args.classifiers[:2]
    a, b = names[0], names[-1]
    for name in names:
        model = MODELS[name]
        with ThreadPoolExecutor(args.workers) as ex:
            res = [parse(t) for t in ex.map(lambda p: ask(model, p), prompts)]
        rows[f"{name}_cat"] = [c for c, _ in res]
        rows[f"{name}_reason"] = [r for _, r in res]
        print(f"{name} done", flush=True)
    rows["agree"] = rows[f"{a}_cat"] == rows[f"{b}_cat"]
    summ = {}
    for kind in ("flagged", "control"):
        x = rows[rows.kind == kind]
        two = a != b
        summ[kind] = {"n": len(x), "agreement": float(x.agree.mean()) if two else None,
                      "kappa": float(cohen_kappa_score(x[f"{a}_cat"], x[f"{b}_cat"])) if two and len(x) > 1 else None,
                      a: dict(Counter(x[f"{a}_cat"])), b: dict(Counter(x[f"{b}_cat"])),
                      "both_agree": dict(Counter(x[x.agree][f"{a}_cat"]))}
    out = {"run": args.run, "prompt": VERSION, "classifiers": [MODELS[n] for n in names], "summary": summ,
           "rows": rows.drop(columns=[c for c in rows.columns if c in ("premise_chunk_ids",)]).astype(str).to_dict("records")}
    (ROOT / "results" / f"diagnose_flags_{'_'.join(names)}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
