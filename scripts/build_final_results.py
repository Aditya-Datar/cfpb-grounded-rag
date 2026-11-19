"""Collect the project's final numbers into one file: results/final_results.json.

    python scripts/build_final_results.py

Reads only the results JSONs that the experiment scripts wrote (nothing is
recomputed) and records, for every block, the file it came from. Intervals are
the 95% bootstrap CIs stored in those files. Verdicts are derived mechanically
from the stored intervals (does the CI exclude 0, or 0.5 for AUROC), so the
wording in the report can be checked against this file.
"""
import json
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
T = 0.99658203125  # Atharva's NLI cutoff, frozen on checker set 1 on 2026-11-04


def load(name: str) -> dict:
    return json.loads((R / name).read_text(encoding="utf-8"))


def est(mean, ci) -> dict:
    return {"estimate": round(float(mean), 4), "ci95": [round(float(ci[0]), 4), round(float(ci[1]), 4)]}


def excludes(ci, value=0.0) -> bool:
    return ci[0] > value or ci[1] < value


def metric_block(m: dict) -> dict:
    """hit@1/5/10 and MRR with CIs from a run_retrieval.py block."""
    return {k: est(m[k], m["ci95"][k]) for k in ("hit@1", "hit@5", "hit@10", "mrr")} | {"n": m["n"]}


def h1() -> dict:
    out = {"source": ["results/retrieval_bm25.json", "results/retrieval_mpnet.json", "results/retrieval_bge.json",
                      "results/retrieval_e5.json"],
           "split": "report half (metrics.half == 1), in-scope complaints", "alpha": "tuned on the dev half by MRR"}
    for variant in ("with_fcra", "without_fcra"):
        rows = {}
        for tag in ("mpnet", "bge", "e5"):
            d = load(f"retrieval_{tag}.json")[variant]
            rh = d["report_half"]
            rows.setdefault("bm25", metric_block(rh["bm25"]))
            for kind in ("dense", "hybrid"):
                g = rh[kind]["gain_vs_bm25"]
                rows[f"{kind}_{tag}"] = metric_block(rh[kind]) | {
                    "hit@5_gain_vs_bm25": est(g["hit@5"]["mean"], g["hit@5"]["ci95"]),
                    "mrr_gain_vs_bm25": est(g["mrr"]["mean"], g["mrr"]["ci95"]),
                    **({"alpha": d["hybrid_alpha"]} if kind == "hybrid" else {})}
        out[variant] = {"n_chunks": load("retrieval_mpnet.json")[variant]["n_chunks"], "retrievers": rows}
    w = out["with_fcra"]["retrievers"]
    gains = {k: v["hit@5_gain_vs_bm25"] for k, v in w.items() if k != "bm25"}
    best = max((k for k in w if k != "bm25"), key=lambda k: (w[k]["hit@5"]["estimate"], w[k]["mrr"]["estimate"]))
    out["best_retriever"] = {"name": best, "rule": "report-half hit@5 with FCRA, ties by MRR (docs/tasks/ishani.md)",
                             "note": "picked on the numbers it is reported on, so its lead is optimistic; "
                                     "hybrid mpnet minus dense mpnet hit@5 +0.046 [-0.031, +0.123] "
                                     "(docs/tasks/results/ishani_supplement/h1_supplement.json)"}
    out["verdict"] = {"hypothesis": "Dense or hybrid retrieval puts the gold section in the top 5 more often than BM25.",
                      "supported": all(excludes(g["ci95"]) and g["estimate"] > 0 for g in gains.values()),
                      "detail": f"with FCRA, all {len(gains)} dense/hybrid hit@5 gains over BM25 have CIs above 0; "
                                f"best {best} hit@5 {w[best]['hit@5']['estimate']} vs BM25 {w['bm25']['hit@5']['estimate']}"}
    return out


def h2_h3() -> dict:
    out = {"source": "results/attribution_full_{bm25,hybrid_mpnet}[_tau0.9966].json",
           "generator": "nvidia/nemotron-3.5-super-vl-120b-a12b (the frozen nemotron-3-super-120b-a12b was retired by "
                        "NVIDIA on 2026-10-03); temperature 0, prompt v1-9d0f038c, k = 5",
           "n_complaints": None, "conditions": {}}
    for ret in ("bm25", "hybrid_mpnet"):
        for cut, sfx in (("0.5", ""), ("T", "_tau0.9966")):
            d = load(f"attribution_full_{ret}{sfx}.json")
            out["n_complaints"] = d["n_complaints"]
            block = {"failed_generations": sum(len(v) for v in d["failed_generations"].values()),
                     "gold_section_in_retrieved_top5": round(d["gold_section_in_retrieved_topk"], 4)}
            for cond in ("retrieved", "oracle"):
                c = d[cond]
                block[cond] = {"n_sentences": c["n_sentences"],
                               **{k.replace("pct_", "share_"): round(c[k], 4) for k in
                                  ("pct_supported_micro", "pct_supported_macro",
                                   "pct_supported_and_gold_section_micro", "pct_supported_and_gold_section_macro")}}
            g1, g2 = d["gap_supported_oracle_minus_retrieved"], d["gap_supported_and_gold_oracle_minus_retrieved"]
            block["gap_supported"] = est(g1["mean"], g1["ci95"])
            block["gap_supported_and_gold_section"] = est(g2["mean"], g2["ci95"])
            block["gap_supported_by_retrieval_hit"] = {("hit" if k == "True" else "miss"): v
                                                      for k, v in d["gap_by_retrieval_hit"].items()}
            out["conditions"][f"{ret}@{cut}"] = block
    c = out["conditions"]
    out["verdicts"] = {
        "H2": {"hypothesis": "Drafts from the oracle section are more often supported and about the right section "
                             "than drafts from retrieved passages.",
               "supported": all(excludes(c[k]["gap_supported_and_gold_section"]["ci95"])
                                and c[k]["gap_supported_and_gold_section"]["estimate"] > 0 for k in c),
               "detail": "gap in supported-and-gold-section positive with CI above 0 for both retrievers at both cutoffs; "
                         "partly by construction (oracle passages are all gold-section)"},
        "H3": {"hypothesis": "Even with the oracle section, a measurable share of sentences is unsupported.",
               "supported": True,
               "unsupported_share_oracle": {"at_0.5": round(1 - c["bm25@0.5"]["oracle"]["share_supported_micro"], 4),
                                            "at_T": round(1 - c["bm25@T"]["oracle"]["share_supported_micro"], 4)},
               "detail": "share depends strongly on the cutoff; no CI on the share itself"}}
    return out


def h4() -> dict:
    s1 = load("checker_h4_set1_fixed_tau_audit.json")
    u2 = load("checker_h4_v2_final_uncertainty.json")["references"]["primary_claude"]
    agree = load("checker_annotation_agreement_v2.json")

    def four(m):
        return {k: est(m[k]["estimate"], m[k]["ci95"]) for k in
                ("balanced_accuracy", "kappa_vs_gold", "flagged_unsupported_recall", "auroc")}

    set2_nli_T = u2["comparisons"]["shared_T"]
    return {
        "source": ["results/checker_h4_set1_fixed_tau_audit.json", "results/checker_benchmark_v2.json",
                   "results/llm_judge_mistral-large-4-1t-a52b_v2.json", "results/checker_h4_v2_final_uncertainty.json",
                   "results/checker_annotation_agreement_v2.json"],
        "frozen_cutoff_T": T,
        "set1": {"n": s1["n"], "labels": "adjudicated by the team (2026-10-20)",
                 "note": "T was chosen on set 1, so NLI@T here is optimistic",
                 "nli@0.5": four(s1["nli"]["shared_0.5"]), "nli@T": four(s1["nli"]["shared_T"]),
                 "nli@T_exact_source_decoding": four(s1["nli"]["exact_T"]),
                 "judge_deepseek_v4.1_flash": four(s1["judge"])},
        "set2": {"n": 100, "held_out": "no sentence shared with set 1; 50 BM25-retrieved and 50 oracle pairs",
                 "labels": "AI-adjudicated (Claude worksheet), not human-validated; accepted by Atharva",
                 "annotator_agreement": {"agreement": agree["agreement"], "cohen_kappa": round(agree["cohen_kappa"], 4)},
                 "nli@0.5": four(u2["comparisons"]["shared_0.5"]["nli"]), "nli@T": four(set2_nli_T["nli"]),
                 "judge_mistral_large_4": four(u2["judge"]),
                 "judge_minus_nli@T_balanced_accuracy": est(set2_nli_T["judge_minus_nli_balanced_accuracy"]["estimate"],
                                                            set2_nli_T["judge_minus_nli_balanced_accuracy"]["ci95"]),
                 "note": "DeepSeek V4.1 Flash returned HTTP 410 (retired) for set 2"},
        "verdict": {"hypothesis": "The NLI checker agrees with the reference labels well enough to flag unsupported "
                                  "sentences; if not, an LLM judge does better.",
                    "supported": "partly",
                    "detail": "held-out set 2: NLI@T balanced accuracy "
                              f"{set2_nli_T['nli']['balanced_accuracy']['estimate']:.3f}, catches "
                              f"{set2_nli_T['nli']['flagged_unsupported_recall']['estimate']:.1%} of unsupported sentences; "
                              "the LLM judge is not better (difference CI includes 0). Moderate agreement, not reliable "
                              "enough to replace review: the checker is a screening aid."},
    }


def h5() -> dict:
    out = {"source": ["results/abstention_mpnet.json", "results/abstention_mpnet_no_fcra.json"],
           "positive_class": "gold_regulation == NONE", "baseline_midterm_bm25_top_auroc": 0.43}
    for tag, name in (("mpnet", "with_fcra"), ("mpnet_no_fcra", "without_fcra")):
        d = load(f"abstention_{tag}.json")
        lr = d["logistic_regression"]
        singles = {k: est(v["report_half"]["auroc"], v["report_half"]["ci95"]) for k, v in d["single_signals"].items()}
        p = lr["prf_report"]
        tp = round(p["recall"] * p["n_none"])
        fp = round(tp / p["precision"]) - tp if p["precision"] else None
        out[name] = {"n": d["n"], "n_none": d["n_none"], "n_report_half": d["n_report_half"],
                     "single_signal_auroc_report_half": singles,
                     "logistic_regression": {"auroc_report_half": est(lr["report_half"]["auroc"], lr["report_half"]["ci95"]),
                                             "cv_5fold_x20_auroc": {"mean": round(lr["cv_5fold_x20_auroc"]["mean"], 4),
                                                                    "sd": round(lr["cv_5fold_x20_auroc"]["sd"], 4)},
                                             "threshold_dev": round(lr["threshold_tuned_on_dev"], 4),
                                             "precision": round(p["precision"], 4), "recall": round(p["recall"], 4),
                                             "f1": round(p["f1"], 4), "true_flags": tp, "false_flags": fp,
                                             "false_per_true_flag": round(fp / tp, 2) if tp else None}}
    lr = out["with_fcra"]["logistic_regression"]
    out["exploratory_rechecks"] = {
        "status": "post hoc, after seeing report-half results (docs/tasks/results/gagan.md Secs. 4-7)",
        "logreg_minus_best_single_signal_auroc": est(0.074, [-0.005, 0.167]),
        "bm25_top_vs_n_words_spearman": 0.986,
        "with_minus_without_fcra_auroc": {"all_91": est(0.108, [0.018, 0.202]), "excluding_fcra_gold": est(0.085, [-0.012, 0.189])}}
    out["verdict"] = {"hypothesis": "Retrieval confidence flags complaints no regulation covers, better than the BM25 "
                                    "top score (AUROC 0.43).",
                      "supported": excludes(lr["auroc_report_half"]["ci95"], 0.5),
                      "detail": f"logistic regression AUROC {lr['auroc_report_half']['estimate']} "
                                f"{lr['auroc_report_half']['ci95']}, CI above 0.5 and 0.43; but "
                                f"{lr['false_per_true_flag']} wrong referrals per correct one, so useful as a prompt, "
                                "not for automatic abstention"}
    return out


def ablations() -> dict:
    a = load("ablation_chunking.json")
    comp = {}
    for alt, d in a["comparisons"].items():
        comp[alt] = {r: {m: est(d["paired_difference"][r][m]["mean"], d["paired_difference"][r][m]["ci95"])
                         for m in ("hit@5", "mrr")} for r in ("bm25", "dense", "hybrid")}
    f = a["fcra_scope"]["paired_difference_with_minus_without"]
    return {"source": ["results/ablation_chunking.json", "results/retrieval_{struct700,struct1400,struct2800,fixed200,section}.json"],
            "chunking": {"baseline": a["baseline"], "corpus": "regulations only (no FCRA)", "n": 65,
                         "paired_difference_alternative_minus_baseline": comp,
                         "finding": "structure-aware struct1400 beats fixed 200-word windows for dense and hybrid "
                                    "(CIs below 0); whole sections are indistinguishable for hybrid"},
            "fcra_distraction": {"population": a["fcra_scope"]["population"], "n": a["fcra_scope"]["n"],
                                 "with_minus_without_fcra": {r: {m: est(f[r][m]["mean"], f[r][m]["ci95"])
                                                                 for m in ("hit@5", "mrr")} for r in f},
                                 "finding": "adding FCRA chunks lowers dense and hybrid hit@5 on non-FCRA complaints"}}


def classifier() -> dict:
    c = load("classifier_test_metrics.json")
    return {"source": "results/classifier_test_metrics.json", "model": "DistilBERT", "test_n": c["product"]["n"],
            "product": {"macro_f1": c["product"]["macro_f1"], "accuracy": c["product"]["accuracy"]},
            "issue": {"accuracy": c["issue"]["accuracy"],
                      "macro_f1_all_issues": c["issue"]["macro_f1_by_min_support"]["min_test_support_1"]["macro_f1"],
                      "n_issues": c["issue"]["macro_f1_by_min_support"]["min_test_support_1"]["n_issues"],
                      "macro_f1_issues_with_100_plus_test_examples":
                          c["issue"]["macro_f1_by_min_support"]["min_test_support_100"]["macro_f1"]}}


def main() -> None:
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    gold = [json.loads(line) for line in (ROOT / "annotation" / "gold_final.jsonl").read_text(encoding="utf-8").splitlines()]
    regs: dict[str, int] = {}
    for g in gold:
        regs[g["gold_regulation"]] = regs.get(g["gold_regulation"], 0) + 1
    out = {
        "project": "CSCI 544 Group 36: Regulation-Grounded Triage and Response Drafting for CFPB Consumer Complaints",
        "built": str(date.today()), "git_commit": commit, "builder": "scripts/build_final_results.py",
        "data": {"gold_complaints": len(gold), "in_scope": len(gold) - regs.get("NONE", 0), "by_regulation": regs,
                 "split": "metrics.half(complaint_id): 0 = dev (tuning), 1 = report",
                 "labels": "silver gold labels from adjudicated LLM annotation (annotation/ANNOTATION_GUIDE.md)"},
        "caveats": [
            "Generator changed: the frozen Nemotron model was retired on 2026-10-03; all final drafts use "
            "nvidia/nemotron-3.5-super-vl-120b-a12b. Midterm pilot numbers are not comparable.",
            "Checker set 2 labels are AI-adjudicated and not human-validated.",
            "T was tuned on checker set 1 (drafts from the retired model); set 2 is the transfer test.",
            "Report-half samples are small (65 in-scope retrieval items, 91 for H5, 100 checker pairs); "
            "most differences between strong systems are within noise.",
        ],
        "classifier": classifier(),
        "H1_retrieval": h1(),
        "H2_H3_attribution": h2_h3(),
        "H4_checker": h4(),
        "H5_scope_detection": h5(),
        "ablations": ablations(),
    }
    out["summary"] = {k: v for k, v in {
        "H1": out["H1_retrieval"]["verdict"]["supported"],
        "H2": out["H2_H3_attribution"]["verdicts"]["H2"]["supported"],
        "H3": out["H2_H3_attribution"]["verdicts"]["H3"]["supported"],
        "H4": out["H4_checker"]["verdict"]["supported"],
        "H5": out["H5_scope_detection"]["verdict"]["supported"]}.items()}
    path = R / "final_results.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out["summary"]), "\nwrote", path)


if __name__ == "__main__":
    main()
