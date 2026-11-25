"""Figures for the midterm report, all computed from tracked results and local run outputs.

    python scripts/make_report_figures.py      # writes results/figures/fig*.png and .pdf

Needs the pilot runs (outputs/pipeline_runs/pilot-bm25, pilot-oracle), the annotation items
(data/processed/annotation_*.csv) and the classifier test report (outputs/classifier/product/).

fig1_attribution      supported vs supported-and-correct, BM25 vs oracle, 95% CI + human labels
fig2_retrieval_hitk   BM25 section-level hit@k, k = 1..10, with and without the FCRA
fig3_checker_scores   checker entailment scores by human label, with the 0.5 and tuned cutoffs
fig4_per_regulation   supported-and-correct by regulation, BM25 vs oracle
fig5_cutoff_gap       attribution gap as the checker cutoff gets stricter
fig6_product_f1       product classifier F1 per class (test set)
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.annotation import load_items  # noqa: E402
from cfpb.config import OUTPUT_DIR, ROOT  # noqa: E402
from cfpb.pipeline.corpus import load_corpus  # noqa: E402

OUT = ROOT / "results" / "figures"
RUNS = OUTPUT_DIR / "pipeline_runs"
FAILED = {"20515686"}  # empty oracle draft (finish_reason=length), excluded from both arms
CORPUS = [str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")]

# Validated two-slot categorical palette (dataviz reference palette, light mode).
BM25, ORACLE = "#eb6834", "#2a78d6"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8f8e89", "#e6e5e1"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False, "savefig.dpi": 300,
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / f"{name}.png")


def boot_ci(x, n=10000, seed=0):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    b = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(n)]
    return np.percentile(b, [2.5, 97.5])


def pilot_rates(tau=0.5):
    """Per-complaint share of sentences supported / supported-and-gold, for each arm."""
    corpus = load_corpus(CORPUS)
    gold = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str).set_index("complaint_id")
    out = {}
    for arm, run in (("bm25", "pilot-bm25"), ("oracle", "pilot-oracle")):
        s = pd.read_parquet(RUNS / run / "sentences.parquet")
        s = s[~s["complaint_id"].isin(FAILED)].copy()
        s["sup"] = s["entail_prob"] >= tau
        s["gold"] = s["sup"] & np.array([gold.loc[c, "gold_section"] in {corpus.get(i).section for i in p}
                                         for c, p in zip(s["complaint_id"], s["premise_chunk_ids"])])
        out[arm] = s.groupby("complaint_id")[["sup", "gold"]].mean()
    ids = out["bm25"].index.intersection(out["oracle"].index)
    return {k: v.loc[ids] for k, v in out.items()}, gold


def human_rates():
    s = pd.read_json(ROOT / "annotation" / "checker_set.jsonl", lines=True, dtype={"pair_id": str, "complaint_id": str})
    s = s.merge(pd.read_json(ROOT / "annotation" / "checker_gold.jsonl", lines=True, dtype=str), on="pair_id")
    corpus = load_corpus(CORPUS)
    gold = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str).set_index("complaint_id")
    s["sup"] = s["gold_label"] == "supported"
    s["gold"] = s["sup"] & np.array([gold.loc[c, "gold_section"] in {corpus.get(i).section for i in p}
                                     for c, p in zip(s["complaint_id"], s["premise_chunk_ids"])])
    return s


def fig1_attribution():
    r, _ = pilot_rates()
    h = human_rates()
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    groups = [("sup", "Supported by the\ngiven passage"), ("gold", "Supported and from\nthe correct section")]
    w = 0.34
    for gi, (col, label) in enumerate(groups):
        for ai, (arm, color, name, hk) in enumerate((("bm25", BM25, "BM25 passages", "retrieved"),
                                                    ("oracle", ORACLE, "Correct passage", "oracle"))):
            x = gi + (ai - 0.5) * (w + 0.04)
            v = r[arm][col].to_numpy()
            lo, hi = boot_ci(v)
            ax.bar(x, v.mean() * 100, w, color=color, label=name if gi == 0 else None, zorder=2)
            ax.errorbar(x, v.mean() * 100, yerr=[[v.mean() * 100 - lo * 100], [hi * 100 - v.mean() * 100]],
                        fmt="none", ecolor=INK2, elinewidth=1, capsize=3, zorder=3)
            ax.text(x, hi * 100 + 2.5, f"{v.mean() * 100:.0f}%", ha="center", va="bottom", fontsize=9, color=INK)
            hv = h.loc[h["condition"] == hk, col].mean() * 100
            ax.scatter(x, hv, marker="D", s=34, facecolor="white", edgecolor=INK, linewidth=1.2, zorder=4,
                       label="Human labels (25 sentences per arm)" if (gi == 0 and ai == 0) else None)
    ax.set_xticks([0, 1], [g[1] for g in groups])
    ax.set_ylim(0, 105)
    ax.set_ylabel("Sentences (% per complaint)")
    ax.grid(axis="x", visible=False)
    ax.set_title("Same model and prompt, only the passage changes (40 complaints)", loc="left", color=INK)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.2), ncol=3, fontsize=8)
    save(fig, "fig1_attribution")


def fig2_retrieval_hitk():
    from cfpb.retrieval.bm25 import BM25Retriever, load_chunks
    items = load_items()[["complaint_id", "narrative_clean"]]
    gold = pd.read_json(ROOT / "annotation" / "gold_final.jsonl", lines=True, dtype=str)
    df = items.merge(gold[gold["gold_regulation"] != "NONE"], on="complaint_id")
    ks = np.arange(1, 11)
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    for fcra, color, name in ((True, ORACLE, "Regulations + FCRA (2,954 chunks)"),
                              (False, MUTED, "Regulations only (2,629 chunks)")):
        bm = BM25Retriever(load_chunks(include_fcra=fcra))
        ranks = []
        for r in df.itertuples():
            secs = [s for s, _ in bm.ranked_sections(r.narrative_clean)]
            ranks.append(secs.index(r.gold_section) + 1 if r.gold_section in secs else 10 ** 6)
        ranks = np.array(ranks)
        hit = [(ranks <= k).mean() * 100 for k in ks]
        ax.plot(ks, hit, color=color, linewidth=2, marker="o", markersize=4.5, label=name)
        ax.annotate(f"{hit[-1]:.0f}%", (10, hit[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK)
    ax.plot(ks, ks / 167 * 100, color=MUTED, linewidth=1, linestyle=":", label="Random (167 sections)")
    ax.set_xticks(ks)
    ax.set_xlim(0.6, 10.9)
    ax.set_ylim(0, 60)
    ax.set_xlabel("k (top-k sections)")
    ax.set_ylabel("Correct section in top k (%)")
    ax.set_title("BM25 retrieval, 127 in-scope complaints", loc="left", color=INK)
    ax.legend(loc="upper left", fontsize=8)
    save(fig, "fig2_retrieval_hitk")


def fig3_checker_scores():
    s = pd.read_json(ROOT / "annotation" / "checker_set.jsonl", lines=True, dtype={"pair_id": str})
    s = s.merge(pd.read_json(ROOT / "annotation" / "checker_gold.jsonl", lines=True, dtype=str), on="pair_id")
    bench = json.loads((ROOT / "results" / "checker_benchmark.json").read_text(encoding="utf-8"))
    tuned = bench["best_threshold_in_sample"]["threshold"]
    # Scores pile up near 1, so plot distance from 1 on a log axis: 1 - p.
    gap = np.clip(1 - s["checker_entail"].astype(float).to_numpy(), 1e-4, 1)
    y = (s["gold_label"] == "supported").to_numpy()
    rng = np.random.default_rng(0)
    fig, ax = plt.subplots(figsize=(6.2, 2.4))
    # Shape, not the arm colours, separates the two human labels (blue/orange mean BM25/oracle elsewhere).
    for row, mask, filled in ((1, y, True), (0, ~y, False)):
        ax.scatter(gap[mask], row + rng.uniform(-0.17, 0.17, mask.sum()), s=30, zorder=3, linewidth=1.2,
                   facecolor=INK2 if filled else "white", edgecolor=INK2)
    for t, name in ((0.5, "default cutoff 0.5"), (tuned, f"strict cutoff {tuned:.4f}")):
        ax.axvline(1 - t, color=INK2, linewidth=1, linestyle="--", zorder=2)
        ax.annotate(name, (1 - t, 1.62), xytext=(5, 0), textcoords="offset points", ha="left",
                    va="center", fontsize=8, color=INK2)
    ax.set_xscale("log")
    ax.invert_xaxis()
    ticks = [0.5, 0.9, 0.99, 0.999, 0.9999]
    ax.set_xticks([1 - t for t in ticks], [str(t) for t in ticks])
    ax.set_xlabel("Checker entailment score (log scale toward 1; flagged to the left of a cutoff)")
    ax.set_yticks([0, 1], ["Human:\nunsupported", "Human:\nsupported"])
    ax.set_ylim(-0.5, 1.85)
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Checker vs human labels on 50 sentences (AUROC {bench['auroc']:.2f})", loc="left", color=INK)
    save(fig, "fig3_checker_scores")


def fig4_per_regulation():
    r, gold = pilot_rates()
    reg = gold.loc[r["bm25"].index, "gold_regulation"]
    order = ["E", "F", "FCRA", "V", "Z"]
    fig, ax = plt.subplots(figsize=(5.0, 2.8))
    for i, g in enumerate(order):
        ids = reg[reg == g].index
        a, b = r["bm25"].loc[ids, "gold"].mean() * 100, r["oracle"].loc[ids, "gold"].mean() * 100
        ax.plot([a, b], [i, i], color=GRID, linewidth=3, zorder=1, solid_capstyle="round")
        ax.scatter(a, i, s=60, color=BM25, zorder=3, edgecolor="white", linewidth=1.5,
                   label="BM25 passages" if i == 0 else None)
        ax.scatter(b, i, s=60, color=ORACLE, zorder=3, edgecolor="white", linewidth=1.5,
                   label="Correct passage" if i == 0 else None)
        ax.text(a - 3, i, f"{a:.0f}%", ha="right", va="center", fontsize=8, color=INK2)
        ax.text(b + 3, i, f"{b:.0f}%", ha="left", va="center", fontsize=8, color=INK2)
    names = {"E": "Reg E", "F": "Reg F", "FCRA": "FCRA", "V": "Reg V", "Z": "Reg Z"}
    ax.set_yticks(range(len(order)), [f"{names[g]} (n={int((reg == g).sum())})" for g in order])
    ax.invert_yaxis()
    ax.set_xlim(-12, 112)
    ax.set_xlabel("Sentences supported and from the correct section (%)")
    ax.grid(axis="y", visible=False)
    ax.set_title("By regulation (40 complaints)", loc="left", color=INK)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.22), ncol=2, fontsize=8)
    save(fig, "fig4_per_regulation")


def fig5_cutoff_gap():
    taus = [0.5, 0.7, 0.9, 0.95, 0.98, 0.99, 0.995, 0.9966]
    rows = []
    for t in taus:
        r, _ = pilot_rates(t)
        d = (r["oracle"]["gold"] - r["bm25"]["gold"]).to_numpy() * 100
        lo, hi = boot_ci(d)
        rows.append((t, d.mean(), lo, hi))
    t, m, lo, hi = map(np.array, zip(*rows))
    h = human_rates()
    hgap = (h.loc[h.condition == "oracle", "gold"].mean() - h.loc[h.condition == "retrieved", "gold"].mean()) * 100
    x = np.arange(len(taus))
    fig, ax = plt.subplots(figsize=(5.2, 2.9))
    ax.fill_between(x, lo, hi, color=ORACLE, alpha=0.15, linewidth=0)
    ax.plot(x, m, color=ORACLE, linewidth=2, marker="o", markersize=4.5, label="Checker estimate (95% CI)")
    ax.axhline(hgap, color=INK2, linewidth=1, linestyle="--")
    ax.text(len(taus) - 1, hgap + 2, f"Human labels: +{hgap:.0f} pts", ha="right", va="bottom", fontsize=8, color=INK2)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    for xi, mi in zip(x[[0, -1]], m[[0, -1]]):
        ax.annotate(f"+{mi:.0f}", (xi, mi), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8, color=INK)
    ax.set_xticks(x, [str(v) for v in taus], rotation=30)
    ax.set_xlabel("Checker cutoff (stricter to the right)")
    ax.set_ylabel("Gap: correct minus BM25 (pts)")
    ax.set_ylim(-5, 85)
    ax.set_title("The gap stays positive at every cutoff; its size shrinks", loc="left", color=INK)
    ax.legend(loc="lower left", fontsize=8)
    save(fig, "fig5_cutoff_gap")


def fig6_product_f1():
    rep = pd.read_csv(OUTPUT_DIR / "classifier" / "product" / "classification_report_test.csv", encoding="utf-8-sig")
    rep = rep.rename(columns={rep.columns[0]: "Class"})
    rep = rep[~rep["Class"].isin(["accuracy", "macro avg", "weighted avg"])].sort_values("f1-score")
    short = {"Credit reporting or other personal consumer reports": "Credit reporting",
             "Money transfer, virtual currency, or money service": "Money transfer / virtual currency",
             "Payday loan, title loan, personal loan, or advance loan": "Payday / title / personal loan"}
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    y = np.arange(len(rep))
    ax.barh(y, rep["f1-score"], height=0.62, color=ORACLE, zorder=2)
    for yi, (f, n) in enumerate(zip(rep["f1-score"], rep["support"])):
        ax.text(f + 0.01, yi, f"{f:.2f}  (n={int(n):,})", va="center", fontsize=8, color=INK2)
    macro = rep["f1-score"].mean()
    ax.set_yticks(y, [short.get(c, c) for c in rep["Class"]])
    ax.set_xlim(0, 1.18)
    ax.set_xlabel("F1 on the test set (13,905 complaints)")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Product classifier F1 by class (macro-F1 {macro:.3f}); the two smallest classes score lowest",
                 loc="left", color=INK, fontsize=9)
    save(fig, "fig6_product_f1")


if __name__ == "__main__":
    fig1_attribution()
    fig2_retrieval_hitk()
    fig3_checker_scores()
    fig4_per_regulation()
    fig5_cutoff_gap()
    fig6_product_f1()
