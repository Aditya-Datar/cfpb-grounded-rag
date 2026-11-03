# Gagan: H5, detecting complaints no regulation covers

Read [README.md](README.md) first (CARC setup, data bundle, rules, hand-back).

## Goal

Test **H5**: retrieval-confidence signals can flag complaints whose gold label is NONE (no section of Regulations E, F, V, Z or the FCRA governs them), so the pipeline can refer them to a human instead of drafting a response with a wrong citation. 71 of the 198 gold complaints are NONE. The midterm baseline, the top BM25 score, was **worse than chance** (AUROC 0.43): long complaints get high BM25 scores whatever they are about.

## What the code does (already written: `scripts/run_abstention.py`)

`scripts/run_retrieval.py` (Ishani's script; you run it yourself, it is deterministic) writes one feature row per gold complaint to `outputs/retrieval/features_<tag>[_no_fcra].parquet`:

| feature | meaning |
|---|---|
| `bm25_top`, `dense_top` | best section score |
| `bm25_margin`, `dense_margin` | best minus second-best section score |
| `bm25_top_z`, `dense_top_z` | best chunk score in standard deviations above the mean over all chunks (length-robust) |
| `bm25_top5_mean`, `dense_top5_mean` | mean of the top 5 section scores |
| `n_words` | narrative length |

`run_abstention.py` scores every feature alone (oriented so low confidence predicts NONE), plus a logistic regression on all of them: fit on the dev half, AUROC with a bootstrap CI on the report half, and 5-fold cross-validation repeated 20 times over all items as a less noisy estimate. It tunes an F1-maximising threshold on the dev half and reports precision, recall and F1 of the NONE flag on the report half.

## Steps

1. Setup per README.
2. Produce the features (mpnet, both corpus variants):
   ```bash
   sbatch carc/retrieval.sbatch
   ```
3. Run the analysis (CPU only, seconds; fine on the login node or in an interactive job):
   ```bash
   python scripts/run_abstention.py --features outputs/retrieval/features_mpnet.parquet --tag mpnet
   python scripts/run_abstention.py --features outputs/retrieval/features_mpnet_no_fcra.parquet --tag mpnet_no_fcra
   ```
4. Sanity checks:
   - `single_signals.bm25_top.all.auroc` should be close to the midterm's 0.43 (it is the same signal on the same 198 items). If it is far off, stop and tell Aditya.
   - `n` = 198, `n_none` = 71, `n_report_half` around 100.
   - Read the logistic-regression coefficients: which signals carry the weight? A model that relies only on `n_words` is detecting length, not relevance. Say so if that happens.
5. Optional, only if time allows and clearly labelled as exploratory: rerun with features from Ishani's best other encoder (`--tag bge` features), to see whether the dense signal is encoder-specific.

## Deliverables

- `results/abstention_mpnet.json`, `results/abstention_mpnet_no_fcra.json`.
- `docs/tasks/results/gagan.md`: a table of report-half AUROC with 95% CI for each single signal and for the logistic regression, the CV mean ± SD, and precision / recall / F1 of the NONE flag at the dev-tuned threshold. Then: is H5 supported (does the best signal's CI exclude 0.5, and beat 0.43?), what the flag would cost in practice (how many in-scope complaints it wrongly refers per correct referral), and which signals matter.

## Do not

- Do not add features or change the model after seeing report-half numbers without reporting that you did.
- Do not change the referral behaviour in `src/cfpb/pipeline/core.py`; Aditya wires the chosen signal into the pipeline after your results.
