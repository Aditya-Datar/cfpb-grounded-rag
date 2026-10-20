"""Attribution pilot: retrieved vs oracle passage (CLAUDE.md Sec. 3, proposal M2).

    python scripts/attribution_pilot.py select            # writes annotation/pilot_ids.txt
    python scripts/run_pipeline_batch.py --retriever precomputed --ranked outputs/retrieval/bm25/ranked.parquet \
        --corpus chunking/data/processed/chunks.jsonl --ids annotation/pilot_ids.txt \
        --generator nemotron --verifier nli --run-name pilot-bm25
    python scripts/run_pipeline_batch.py --retriever oracle --corpus chunking/data/processed/chunks.jsonl \
        --ids annotation/pilot_ids.txt --generator nemotron --verifier nli --run-name pilot-oracle
    python scripts/attribution_pilot.py report --retrieved pilot-bm25 --oracle pilot-oracle

The selection is stratified (in-scope gold items only, INTERFACES.md Sec. 7):
PER_REG items per regulation, all of Reg V (5 items), chosen by SHA-1 so it is
fixed. The report gives % supported sentences per condition, the paired gap
with a bootstrap 95% CI over complaints, and the gap split by whether the
retriever's top k contained the gold section.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.annotation import load_items  # noqa: E402
from cfpb.config import OUTPUT_DIR, ROOT  # noqa: E402
from cfpb.pipeline.corpus import load_corpus  # noqa: E402

GOLD = ROOT / "annotation" / "gold_final.jsonl"
IDS = ROOT / "annotation" / "pilot_ids.txt"
CORPUS = [str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")]
PER_REG = 9
SEED = "attribution-pilot-v1"


def select() -> None:
    gold = pd.read_json(GOLD, lines=True, dtype=str)
    have_text = set(load_items()["complaint_id"])
    ins = gold[(gold["gold_regulation"] != "NONE") & gold["complaint_id"].isin(have_text)].copy()
    ins["h"] = ins["complaint_id"].map(lambda c: hashlib.sha1(f"{SEED}:{c}".encode()).hexdigest())
    picked = ins.sort_values("h").groupby("gold_regulation").head(PER_REG)
    IDS.write_text("\n".join(picked["complaint_id"]) + "\n", encoding="utf-8")
    print(f"wrote {IDS}: {len(picked)} items", picked["gold_regulation"].value_counts().to_dict())


def _rates(sent: pd.DataFrame, col: str = "supported") -> pd.Series:
    """Per complaint: share of sentences where `col` is true."""
    return sent.groupby("complaint_id")[col].mean()


def _paired(r_o: pd.Series, r_r: pd.Series, ids: list[str], n_boot: int) -> dict:
    diff = (r_o[ids] - r_r[ids]).to_numpy()
    rng = np.random.default_rng(0)
    boot = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(n_boot)]
    return {"mean": float(diff.mean()), "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}


def report(retrieved: str, oracle: str, k: int, n_boot: int = 10000) -> None:
    runs = OUTPUT_DIR / "pipeline_runs"
    gold = pd.read_json(GOLD, lines=True, dtype=str).set_index("complaint_id")
    s_r = pd.read_parquet(runs / retrieved / "sentences.parquet")
    s_o = pd.read_parquet(runs / oracle / "sentences.parquet")
    ranked = pd.read_parquet(runs / retrieved / "ranked.parquet")
    corpus = load_corpus(CORPUS)
    for s in (s_r, s_o):
        s["supported"] = s["label"] == "supported"
        # Correct AND faithful: supported by a premise that belongs to the gold section.
        gold_sec = s["complaint_id"].map(gold["gold_section"])
        s["supported_gold"] = s["supported"] & np.array([g in {corpus.get(c).section for c in p}
                                                         for g, p in zip(gold_sec, s["premise_chunk_ids"])])
    # Complaints with no sentences in either run (e.g. an empty LLM response) are reported, not scored.
    resp = {n: pd.read_parquet(runs / n / "responses.parquet") for n in (retrieved, oracle)}
    failed = {n: sorted(r.loc[r["sentences"].map(len) == 0, "complaint_id"]) for n, r in resp.items()}
    r_r, r_o = _rates(s_r), _rates(s_o)
    g_r, g_o = _rates(s_r, "supported_gold"), _rates(s_o, "supported_gold")
    ids = sorted(set(r_r.index) & set(r_o.index))

    topk = ranked[ranked["rank"] <= k].groupby("complaint_id")["section"].apply(set)
    hit = pd.Series({c: gold.loc[c, "gold_section"] in topk.get(c, set()) for c in ids})
    diff = (r_o[ids] - r_r[ids]).to_numpy()

    def cond(s, r, g):
        s = s[s["complaint_id"].isin(ids)]
        return {"n_sentences": len(s), "pct_supported_micro": float(s["supported"].mean()),
                "pct_supported_macro": float(r[ids].mean()),
                "pct_supported_and_gold_section_micro": float(s["supported_gold"].mean()),
                "pct_supported_and_gold_section_macro": float(g[ids].mean()),
                "mean_entail": float(s["entail_prob"].mean())}

    reg = gold.loc[ids, "gold_regulation"]
    out = {
        "retrieved_run": retrieved, "oracle_run": oracle, "n_complaints": len(ids), "k": k,
        "failed_generations": failed,
        "retrieved": cond(s_r, r_r, g_r), "oracle": cond(s_o, r_o, g_o),
        "gold_section_in_retrieved_topk": float(hit.mean()),
        "gap_supported_oracle_minus_retrieved": _paired(r_o, r_r, ids, n_boot),
        "gap_supported_and_gold_oracle_minus_retrieved": _paired(g_o, g_r, ids, n_boot),
        "gap_by_retrieval_hit": {str(h): {"n": int((hit == h).sum()), "mean_gap": float(diff[(hit == h).to_numpy()].mean())}
                                 for h in (True, False) if (hit == h).any()},
        "by_regulation": {g: {"n": int((reg == g).sum()),
                              "supported": {"retrieved": float(r_r[reg[reg == g].index].mean()),
                                            "oracle": float(r_o[reg[reg == g].index].mean())},
                              "supported_and_gold": {"retrieved": float(g_r[reg[reg == g].index].mean()),
                                                     "oracle": float(g_o[reg[reg == g].index].mean())}}
                          for g in sorted(reg.unique())},
        "run_info": {n: json.loads((runs / n / "run_info.json").read_text(encoding="utf-8")) for n in (retrieved, oracle)},
    }
    path = ROOT / "results" / "attribution_pilot.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k_: out[k_] for k_ in ("n_complaints", "failed_generations", "retrieved", "oracle",
                                             "gold_section_in_retrieved_topk", "gap_supported_oracle_minus_retrieved",
                                             "gap_supported_and_gold_oracle_minus_retrieved", "gap_by_retrieval_hit")}, indent=2))
    print("wrote", path)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select")
    rp = sub.add_parser("report")
    rp.add_argument("--retrieved", required=True)
    rp.add_argument("--oracle", required=True)
    rp.add_argument("--k", type=int, default=5)
    args = ap.parse_args()
    select() if args.cmd == "select" else report(args.retrieved, args.oracle, args.k)


if __name__ == "__main__":
    main()
