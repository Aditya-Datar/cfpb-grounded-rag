"""Why does the drafter fail with the correct section? One-factor ablation (EXPERIMENT_LOG E13).

    .venv/Scripts/python.exe scripts/run_drafter_ablation.py --arms A0 A1 A2 A3 A4

Frozen in every arm: the 62 dev complaints (annotation/attribution_ids_dev.txt), the oracle
context (gold-section chunks, k = 5, as full-oracle-local), the drafter
(nvidia/nemotron-3.5-super-vl-120b-a12b, temperature 0, max_tokens 16384), the checker
(mean(DeBERTa NLI, Nemotron Ultra judge) >= the set-1 cutoff, E12b; NLI@T also reported) and
the scoring. Each arm changes ONE factor from A0:

  A0  baseline: prompt v1 (cache hit; reproduces full-oracle-local)
  A1  no complaint text: the user message gives only the passages
  A2  instruction: state only what the passages say; do not describe the consumer, company or facts
  A3  quote-anchored: each sentence restates one provision, following the passage wording
  A4  context size: only the top oracle chunk (k = 1)
  A5  drafter model: GPT-5.6 Sol via Codex (evaluation only), prompt v1 (cache hit; dev-oracle-gpt, E8)

Because the context is the gold section, FINAL ACCURACY = supported share. Secondary:
"addresses the complaint" (Ultra, one call per draft, 0-100) so that an arm cannot win by
writing drafts that ignore the complaint. Writes results/drafter_ablation.json after each arm.
"""
import argparse
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cfpb.annotation import load_items  # noqa: E402
from cfpb.generate import nemotron as nm  # noqa: E402
from cfpb.pipeline.corpus import OracleRetriever, load_corpus, load_gold  # noqa: E402
from cfpb.verify.llm_judge import LLMJudgeVerifier  # noqa: E402
from cfpb.verify.nli import NLIVerifier  # noqa: E402

T = 0.99658203125
ULTRA = "nvidia/nemotron-3-ultra-550b-a55b"
CUT = json.loads((ROOT / "results" / "checker_ultra_compare.json").read_text())["nli_or_ultra_avg"]["cut_set1"]
OUT = ROOT / "results" / "drafter_ablation.json"

RULE1 = "1. Write 3 to 6 sentences explaining which obligations in the passages apply to this complaint and what the company must do under them."
A2_RULE1 = ("1. Write 3 to 6 sentences stating which obligations in the passages apply to this complaint and what the company "
            "must do under them. Each sentence must state only what a passage says; do not describe the consumer, the company "
            "or the facts of the complaint.")
A3_RULE1 = ("1. Write 3 to 6 sentences stating which obligations in the passages apply to this complaint and what the company "
            "must do under them. Each sentence must restate a single provision from one passage, following that passage's own "
            "wording closely (you may shorten it, but keep every condition and exception).")
assert RULE1 in nm.SYSTEM_PROMPT
ARMS = {
    "A0": {"system": nm.SYSTEM_PROMPT, "user": nm.USER_TEMPLATE, "k": 5},
    "A1": {"system": nm.SYSTEM_PROMPT, "user": "Regulation passages:\n{passages}", "k": 5},
    "A2": {"system": nm.SYSTEM_PROMPT.replace(RULE1, A2_RULE1), "user": nm.USER_TEMPLATE, "k": 5},
    "A3": {"system": nm.SYSTEM_PROMPT.replace(RULE1, A3_RULE1), "user": nm.USER_TEMPLATE, "k": 5},
    "A4": {"system": nm.SYSTEM_PROMPT, "user": nm.USER_TEMPLATE, "k": 1},
    "A5": {"system": nm.SYSTEM_PROMPT, "user": nm.USER_TEMPLATE, "k": 5, "drafter": "codex"},
}
RELEVANCE = """A consumer filed the complaint below. A draft response written for a compliance officer follows. Does the draft address the consumer's main grievance (the obligations that govern what the consumer is asking the company to fix)? Ignore whether the legal statements are correct; judge only whether the draft is about the right problem.

Complaint:
{complaint}

Draft:
{draft}

Answer with JSON only: {{"addresses": "yes" or "no", "score": <0-100>}}"""


class ArmGenerator(nm.NemotronGenerator):
    def __init__(self, system: str, user: str):
        super().__init__()
        self.system, self.user = system, user
        self.version = "v1-" + hashlib.sha1((system + user).encode()).hexdigest()[:8]

    def messages(self, narrative_clean, context):
        complaint = " ".join(narrative_clean.split()[:nm.MAX_COMPLAINT_WORDS])
        fields = {"passages": nm.format_passages(context)}
        if "{complaint}" in self.user:
            fields["complaint"] = complaint
        return [{"role": "system", "content": self.system}, {"role": "user", "content": self.user.format(**fields)}]

    def cache_key(self, narrative_clean, context):
        payload = [self.model, self.version, self.temperature, self.max_tokens, narrative_clean,
                   [(c.chunk_id, c.text) for c in context]]
        return hashlib.sha1(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def overlap(sentence: str, premise: str) -> float:
    w = re.findall(r"[a-z0-9]+", sentence.lower())
    p = set(re.findall(r"[a-z0-9]+", premise.lower()))
    return sum(x in p for x in w) / max(1, len(w))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", default=list(ARMS))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    ids = [l.strip() for l in open(ROOT / "annotation" / "attribution_ids_dev.txt", encoding="utf-8") if l.strip()]
    items = load_items().set_index("complaint_id")
    corpus = load_corpus([str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")])
    oracle = OracleRetriever(corpus, load_gold())
    nli, judge = NLIVerifier(), LLMJudgeVerifier(ULTRA)
    rel_client = nm.NemotronGenerator(model=ULTRA)
    results = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"cut": CUT, "arms": {}}
    rows_dir = ROOT / "outputs" / "drafter_ablation"
    rows_dir.mkdir(parents=True, exist_ok=True)

    for arm in args.arms:
        cfg = ARMS[arm]
        if cfg.get("drafter") == "codex":
            from cfpb.generate.codex import CodexGenerator
            gen = CodexGenerator()
        else:
            gen = nm.NemotronGenerator() if arm == "A0" else ArmGenerator(cfg["system"], cfg["user"])
        ctx = {cid: oracle.for_complaint(cid).retrieve(items.loc[cid, "narrative_clean"], cfg["k"]).chunks for cid in ids}
        with ThreadPoolExecutor(2 if cfg.get("drafter") == "codex" else args.workers) as ex:
            drafts = dict(zip(ids, ex.map(lambda c: gen.generate(items.loc[c, "narrative_clean"], ctx[c]), ids)))
        print(f"{arm}: drafts done", flush=True)
        rows = []
        for cid in ids:
            by_id = {c.chunk_id: c for c in ctx[cid]}
            for chk in nli.verify(drafts[cid], ctx[cid]).checks:
                rows.append({"complaint_id": cid, "sentence_idx": chk.sentence_idx, "sentence": chk.sentence,
                             "premise_chunk_ids": chk.premise_chunk_ids, "nli": chk.entail_prob,
                             "premise": " ".join(by_id[p].text for p in chk.premise_chunk_ids)})
        print(f"{arm}: NLI done ({len(rows)} sentences)", flush=True)
        with ThreadPoolExecutor(args.workers) as ex:
            ult = list(ex.map(lambda r: judge.score([corpus.get(p).text for p in r["premise_chunk_ids"]], r["sentence"]), rows))

        def relevance(cid):
            msg = RELEVANCE.format(complaint=" ".join(items.loc[cid, "narrative_clean"].split()[:600]),
                                   draft=" ".join(drafts[cid].sentences))
            key = hashlib.sha1(json.dumps([ULTRA, msg]).encode()).hexdigest()
            f = rows_dir / "relevance_cache" / f"{key}.json"
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

        with ThreadPoolExecutor(args.workers) as ex:
            rel = dict(zip(ids, ex.map(relevance, ids)))
        df = pd.DataFrame(rows)
        df["ultra"] = [p for p, _ in ult]
        df["ens"] = (df["nli"] + df["ultra"]) / 2
        df["overlap"] = [overlap(a, b) for a, b in zip(df["sentence"], df["premise"])]
        df.drop(columns=["premise"]).to_parquet(rows_dir / f"{arm}.parquet", index=False)
        per = df.groupby("complaint_id").agg(n=("ens", "size"), ens=("ens", lambda x: (x >= CUT).sum()))
        res = {"n_drafts": len(ids), "n_sentences": len(df), "sentences_per_draft": len(df) / len(ids),
               "empty_drafts": int(sum(len(drafts[c].sentences) == 0 for c in ids)),
               "supported_ensemble": float((df.ens >= CUT).mean()), "supported_nli_T": float((df.nli >= T).mean()),
               "supported_nli_0.5": float((df.nli >= 0.5).mean()), "supported_ultra_0.5": float((df.ultra >= 0.5).mean()),
               "overlap_mean": float(df.overlap.mean()),
               "addresses_complaint": float(np.mean([rel[c]["addresses"] for c in ids])),
               "addresses_score_mean": float(np.nanmean([rel[c]["score"] for c in ids])),
               "prompt_version": getattr(gen, "version", nm.PROMPT_VERSION), "k": cfg["k"]}
        if arm != "A0" and (rows_dir / "A0.parquet").exists():
            base = pd.read_parquet(rows_dir / "A0.parquet")
            b = base.groupby("complaint_id").agg(n=("ens", "size"), ens=("ens", lambda x: (x >= CUT).sum()))
            j = per.join(b, lsuffix="_a", rsuffix="_b", how="inner")
            rng = np.random.default_rng(0)
            idx = rng.integers(0, len(j), (10000, len(j)))
            na, da, nb, db = (j[c].to_numpy(float) for c in ("ens_a", "n_a", "ens_b", "n_b"))
            d = na[idx].sum(1) / da[idx].sum(1) - nb[idx].sum(1) / db[idx].sum(1)
            res["minus_A0_supported_ensemble"] = {"diff": float(na.sum() / da.sum() - nb.sum() / db.sum()),
                                                  "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}
        results["arms"][arm] = res
        OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"{arm}: " + json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in res.items()}), flush=True)


if __name__ == "__main__":
    main()
