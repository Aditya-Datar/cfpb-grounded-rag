"""Midterm report figures, self-contained (needs only numpy + matplotlib).

    pip install numpy matplotlib
    python plot_report_figures_standalone.py        # writes ./figures/fig1..fig6 .png (300 dpi) and .pdf

All numbers below were computed from the project's result files on 2026-10-25 by
scripts/make_report_figures.py (repo branch generation-verification). Do not edit them by hand.
Colours: orange = BM25 passages, blue = correct (oracle) passage, in every figure.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# [mean, ci_low, ci_high] in % per complaint (40 complaints, checker cutoff 0.5, paired bootstrap 10k).
FIG1 = {"bm25_sup": [77.7, 66.0, 88.3], "bm25_gold": [19.0, 9.7, 29.5],
        "oracle_sup": [83.8, 74.0, 92.4], "oracle_gold": [83.8, 74.0, 92.4],
        # Human-adjudicated labels on 25 sampled sentences per arm.
        "human_bm25_sup": 36.0, "human_bm25_gold": 16.0, "human_oracle_sup": 68.0, "human_oracle_gold": 68.0}
# BM25 section-level hit@k (%) for k = 1..10, 127 in-scope gold complaints, 167 sections.
FIG2 = {"with_fcra": [7.9, 14.2, 21.3, 25.2, 31.5, 33.9, 40.9, 41.7, 44.1, 45.7],
        "without_fcra": [5.5, 11.8, 15.0, 19.7, 22.0, 24.4, 26.0, 27.6, 30.7, 33.9]}
# 50 checker-validation pairs: [checker entailment score, human label (1 = supported)].
FIG3 = {"auroc": 0.843, "tuned": 0.9965820312499999, "pairs": [
    [0.999512, 1], [0.66748, 0], [0.999023, 1], [0.993164, 1], [0.002295, 0], [0.983398, 0], [0.999023, 1],
    [0.99707, 0], [0.998535, 1], [0.99707, 1], [0.998047, 1], [0.999023, 1], [0.012589, 0], [0.997559, 1],
    [0.996582, 1], [0.736328, 0], [0.998535, 1], [0.998047, 1], [0.903809, 0], [0.999512, 0], [0.998535, 1],
    [0.99707, 1], [0.998535, 1], [0.997559, 1], [0.998047, 1], [0.999023, 1], [0.004978, 0], [0.051056, 0],
    [0.999023, 1], [0.997559, 1], [0.993164, 0], [0.998047, 0], [0.997559, 1], [0.998535, 0], [0.998535, 1],
    [0.003716, 0], [0.919922, 0], [0.670898, 1], [0.995117, 0], [0.271484, 0], [0.661133, 0], [0.99707, 0],
    [0.916504, 0], [0.997559, 0], [0.998047, 1], [0.555664, 1], [0.994141, 0], [0.981934, 0], [0.998535, 1],
    [0.994141, 0]]}
# Sentences supported AND from the gold section (%), per regulation of the gold section.
FIG4 = {"E": {"n": 9, "bm25": 8.3, "oracle": 97.8}, "F": {"n": 9, "bm25": 31.1, "oracle": 97.8},
        "FCRA": {"n": 9, "bm25": 33.7, "oracle": 90.0}, "V": {"n": 5, "bm25": 20.0, "oracle": 90.0},
        "Z": {"n": 8, "bm25": 0.0, "oracle": 41.7}}
# Attribution gap (oracle minus BM25, supported-and-correct, pts) by checker cutoff: [cutoff, mean, lo, hi].
FIG5 = {"rows": [[0.5, 64.9, 52.3, 76.8], [0.7, 63.4, 49.8, 76.5], [0.9, 60.1, 44.4, 74.5],
                 [0.95, 54.8, 40.1, 68.7], [0.98, 51.7, 37.7, 65.1], [0.99, 37.0, 23.7, 50.1],
                 [0.995, 25.5, 10.3, 40.0], [0.9966, 14.5, 1.5, 27.1]], "human_gap": 52.0}
# Product classifier, test set (13,905 complaints): [class, F1, test count].
FIG6 = [["Checking or savings account", 0.801, 1959], ["Credit card", 0.851, 2014],
        ["Credit reporting", 0.865, 2026], ["Debt collection", 0.837, 2000],
        ["Debt or credit management", 0.509, 190], ["Money transfer / virtual currency", 0.81, 1690],
        ["Mortgage", 0.951, 1306], ["Payday / title / personal loan", 0.764, 752], ["Prepaid card", 0.696, 277],
        ["Student loan", 0.917, 673], ["Vehicle loan or lease", 0.883, 1018]]

OUT = Path("figures")
BM25, ORACLE = "#eb6834", "#2a78d6"  # validated colour-blind-safe pair
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8f8e89", "#e6e5e1"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False, "savefig.dpi": 300,
    "figure.facecolor": "white", "axes.facecolor": "white"})


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / f"{name}.png")


def fig1():
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    w = 0.34
    for gi, (col, label) in enumerate((("sup", "Supported by the\ngiven passage"),
                                       ("gold", "Supported and from\nthe correct section"))):
        for ai, (arm, color, name) in enumerate((("bm25", BM25, "BM25 passages"), ("oracle", ORACLE, "Correct passage"))):
            x = gi + (ai - 0.5) * (w + 0.04)
            m, lo, hi = FIG1[f"{arm}_{col}"]
            ax.bar(x, m, w, color=color, label=name if gi == 0 else None, zorder=2)
            ax.errorbar(x, m, yerr=[[m - lo], [hi - m]], fmt="none", ecolor=INK2, elinewidth=1, capsize=3, zorder=3)
            ax.text(x, hi + 2.5, f"{m:.0f}%", ha="center", va="bottom", fontsize=9, color=INK)
            ax.scatter(x, FIG1[f"human_{arm}_{col}"], marker="D", s=34, facecolor="white", edgecolor=INK,
                       linewidth=1.2, zorder=4, label="Human labels (25 sentences per arm)" if gi + ai == 0 else None)
    ax.set_xticks([0, 1], ["Supported by the\ngiven passage", "Supported and from\nthe correct section"])
    ax.set_ylim(0, 105)
    ax.set_ylabel("Sentences (% per complaint)")
    ax.grid(axis="x", visible=False)
    ax.set_title("Same model and prompt, only the passage changes (40 complaints)", loc="left", color=INK)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.2), ncol=3, fontsize=8)
    save(fig, "fig1_attribution")


def fig2():
    ks = np.arange(1, 11)
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    for key, color, name in (("with_fcra", ORACLE, "Regulations + FCRA (2,954 chunks)"),
                             ("without_fcra", MUTED, "Regulations only (2,629 chunks)")):
        ax.plot(ks, FIG2[key], color=color, linewidth=2, marker="o", markersize=4.5, label=name)
        ax.annotate(f"{FIG2[key][-1]:.0f}%", (10, FIG2[key][-1]), xytext=(6, 0), textcoords="offset points",
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


def fig3():
    p = np.array([a for a, _ in FIG3["pairs"]])
    y = np.array([b for _, b in FIG3["pairs"]]).astype(bool)
    gap = np.clip(1 - p, 1e-4, 1)  # scores pile up near 1: plot distance from 1 on a log axis
    rng = np.random.default_rng(0)
    fig, ax = plt.subplots(figsize=(6.2, 2.4))
    for row, mask, filled in ((1, y, True), (0, ~y, False)):  # shape, not arm colours, separates the labels
        ax.scatter(gap[mask], row + rng.uniform(-0.17, 0.17, mask.sum()), s=30, zorder=3, linewidth=1.2,
                   facecolor=INK2 if filled else "white", edgecolor=INK2)
    for t, name in ((0.5, "default cutoff 0.5"), (FIG3["tuned"], f"strict cutoff {FIG3['tuned']:.4f}")):
        ax.axvline(1 - t, color=INK2, linewidth=1, linestyle="--", zorder=2)
        ax.annotate(name, (1 - t, 1.62), xytext=(5, 0), textcoords="offset points", ha="left", va="center",
                    fontsize=8, color=INK2)
    ax.set_xscale("log")
    ax.invert_xaxis()
    ticks = [0.5, 0.9, 0.99, 0.999, 0.9999]
    ax.set_xticks([1 - t for t in ticks], [str(t) for t in ticks])
    ax.set_xlabel("Checker entailment score (log scale toward 1; flagged to the left of a cutoff)")
    ax.set_yticks([0, 1], ["Human:\nunsupported", "Human:\nsupported"])
    ax.set_ylim(-0.5, 1.85)
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Checker vs human labels on 50 sentences (AUROC {FIG3['auroc']:.2f})", loc="left", color=INK)
    save(fig, "fig3_checker_scores")


def fig4():
    order = ["E", "F", "FCRA", "V", "Z"]
    names = {"E": "Reg E", "F": "Reg F", "FCRA": "FCRA", "V": "Reg V", "Z": "Reg Z"}
    fig, ax = plt.subplots(figsize=(5.0, 2.8))
    for i, g in enumerate(order):
        a, b = FIG4[g]["bm25"], FIG4[g]["oracle"]
        ax.plot([a, b], [i, i], color=GRID, linewidth=3, zorder=1, solid_capstyle="round")
        ax.scatter(a, i, s=60, color=BM25, zorder=3, edgecolor="white", linewidth=1.5, label="BM25 passages" if i == 0 else None)
        ax.scatter(b, i, s=60, color=ORACLE, zorder=3, edgecolor="white", linewidth=1.5, label="Correct passage" if i == 0 else None)
        ax.text(a - 3, i, f"{a:.0f}%", ha="right", va="center", fontsize=8, color=INK2)
        ax.text(b + 3, i, f"{b:.0f}%", ha="left", va="center", fontsize=8, color=INK2)
    ax.set_yticks(range(len(order)), [f"{names[g]} (n={FIG4[g]['n']})" for g in order])
    ax.invert_yaxis()
    ax.set_xlim(-12, 112)
    ax.set_xlabel("Sentences supported and from the correct section (%)")
    ax.grid(axis="y", visible=False)
    ax.set_title("By regulation (40 complaints)", loc="left", color=INK)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.22), ncol=2, fontsize=8)
    save(fig, "fig4_per_regulation")


def fig5():
    t, m, lo, hi = map(np.array, zip(*FIG5["rows"]))
    x = np.arange(len(t))
    fig, ax = plt.subplots(figsize=(5.2, 2.9))
    ax.fill_between(x, lo, hi, color=ORACLE, alpha=0.15, linewidth=0)
    ax.plot(x, m, color=ORACLE, linewidth=2, marker="o", markersize=4.5, label="Checker estimate (95% CI)")
    ax.axhline(FIG5["human_gap"], color=INK2, linewidth=1, linestyle="--")
    ax.text(len(t) - 1, FIG5["human_gap"] + 2, f"Human labels: +{FIG5['human_gap']:.0f} pts", ha="right",
            va="bottom", fontsize=8, color=INK2)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    for xi, mi in zip(x[[0, -1]], m[[0, -1]]):
        ax.annotate(f"+{mi:.0f}", (xi, mi), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8, color=INK)
    ax.set_xticks(x, [str(v) for v in t], rotation=30)
    ax.set_xlabel("Checker cutoff (stricter to the right)")
    ax.set_ylabel("Gap: correct minus BM25 (pts)")
    ax.set_ylim(-5, 85)
    ax.set_title("The gap stays positive at every cutoff; its size shrinks", loc="left", color=INK)
    ax.legend(loc="lower left", fontsize=8)
    save(fig, "fig5_cutoff_gap")


def fig6():
    rows = sorted(FIG6, key=lambda r: r[1])
    macro = np.mean([r[1] for r in rows])
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    y = np.arange(len(rows))
    ax.barh(y, [r[1] for r in rows], height=0.62, color=ORACLE, zorder=2)
    for yi, (_, f, n) in enumerate(rows):
        ax.text(f + 0.01, yi, f"{f:.2f}  (n={n:,})", va="center", fontsize=8, color=INK2)
    ax.set_yticks(y, [r[0] for r in rows])
    ax.set_xlim(0, 1.18)
    ax.set_xlabel("F1 on the test set (13,905 complaints)")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Product classifier F1 by class (macro-F1 {macro:.3f}); the two smallest classes score lowest",
                 loc="left", color=INK, fontsize=9)
    save(fig, "fig6_product_f1")


if __name__ == "__main__":
    for f in (fig1, fig2, fig3, fig4, fig5, fig6):
        f()
