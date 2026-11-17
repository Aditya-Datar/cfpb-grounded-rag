# H1 results: dense and hybrid retrieval vs BM25 (Ishani)

**Question.** Does dense (Sentence-BERT) or hybrid (dense plus BM25) retrieval put the gold regulation section in the top 5 more often than BM25?

**Setup.** `scripts/run_retrieval.py` via `carc/retrieval.sbatch`, three encoders: `sentence-transformers/all-mpnet-base-v2` (no prefix), `BAAI/bge-base-en-v1.5` (query prefix "Represent this sentence for searching relevant passages: "), `intfloat/e5-base-v2` (query prefix "query: "). Sections are ranked by their best chunk. The hybrid weight alpha was tuned by MRR on the dev half only. **Unless a line says otherwise, numbers are on the report half: 65 in-scope complaints**, with 95% confidence intervals (CIs) from a percentile bootstrap (10,000 resamples over complaints). The gain column is the paired difference against BM25 on the same complaints. Source files: `results/retrieval_{mpnet,bge,e5}.json`.

**Terms.**
- **BM25:** the sparse keyword-retrieval baseline.
- **hit@k:** the share of complaints whose gold section is among the top k retrieved sections.
- **MRR:** mean reciprocal rank of the gold section; 0 if it is not retrieved.
- **FCRA:** the Fair Credit Reporting Act statute chunks (15 U.S.C. 1681–1681x).

**Headline corpus.** I treat the default corpus (four regulations plus FCRA statute chunks) as the headline and the four-regulation corpus as the ablation. That choice is my assumption; the task file does not name a headline variant.

## Main results (report half, n = 65)

### With FCRA (default corpus, 2,954 chunks; headline)

| Retriever | alpha | hit@1 | hit@5 | hit@10 | MRR | hit@5 gain vs BM25 |
|---|---|---|---|---|---|---|
| BM25 | | 0.062 [0.015, 0.123] | 0.246 [0.138, 0.354] | 0.338 [0.231, 0.462] | 0.164 [0.108, 0.228] | |
| dense mpnet | | 0.200 [0.108, 0.308] | 0.615 [0.492, 0.738] | 0.831 [0.738, 0.923] | 0.393 [0.315, 0.480] | +0.369 [+0.231, +0.508] |
| **hybrid mpnet** | 0.8 | 0.200 [0.108, 0.308] | **0.662 [0.538, 0.769]** | 0.800 [0.708, 0.892] | 0.402 [0.326, 0.488] | +0.415 [+0.292, +0.538] |
| dense bge | | 0.169 [0.077, 0.262] | 0.569 [0.446, 0.692] | 0.708 [0.600, 0.815] | 0.333 [0.256, 0.416] | +0.323 [+0.185, +0.462] |
| hybrid bge | 0.9 | 0.169 [0.077, 0.262] | 0.538 [0.415, 0.662] | 0.708 [0.600, 0.815] | 0.329 [0.251, 0.412] | +0.292 [+0.154, +0.431] |
| dense e5 | | 0.123 [0.046, 0.200] | 0.431 [0.308, 0.554] | 0.646 [0.523, 0.754] | 0.272 [0.202, 0.348] | +0.185 [+0.031, +0.338] |
| hybrid e5 | 0.8 | 0.123 [0.046, 0.200] | 0.492 [0.369, 0.615] | 0.692 [0.585, 0.800] | 0.286 [0.215, 0.362] | +0.246 [+0.108, +0.385] |

### Without FCRA (four-regulation corpus, 2,629 chunks; ablation)

| Retriever | alpha | hit@1 | hit@5 | hit@10 | MRR | hit@5 gain vs BM25 |
|---|---|---|---|---|---|---|
| BM25 | | 0.062 [0.015, 0.123] | 0.185 [0.092, 0.277] | 0.277 [0.169, 0.385] | 0.130 [0.075, 0.194] | |
| dense mpnet | | 0.231 [0.138, 0.338] | 0.585 [0.462, 0.708] | 0.662 [0.554, 0.769] | 0.375 [0.284, 0.468] | +0.400 [+0.277, +0.523] |
| hybrid mpnet | 1.0 | 0.231 [0.138, 0.338] | 0.585 [0.462, 0.708] | 0.662 [0.554, 0.769] | 0.375 [0.284, 0.468] | +0.400 [+0.277, +0.523] |
| dense bge | | 0.138 [0.062, 0.231] | 0.400 [0.277, 0.523] | 0.523 [0.400, 0.646] | 0.249 [0.173, 0.331] | +0.215 [+0.092, +0.354] |
| hybrid bge | 0.7 | 0.123 [0.046, 0.200] | 0.354 [0.246, 0.477] | 0.523 [0.400, 0.646] | 0.242 [0.168, 0.322] | +0.169 [+0.062, +0.277] |
| dense e5 | | 0.092 [0.031, 0.169] | 0.292 [0.185, 0.400] | 0.462 [0.338, 0.585] | 0.202 [0.135, 0.275] | +0.108 [-0.015, +0.231] |
| hybrid e5 | 0.8 | 0.077 [0.015, 0.154] | 0.323 [0.215, 0.446] | 0.508 [0.385, 0.631] | 0.206 [0.143, 0.276] | +0.138 [+0.015, +0.262] |

Without FCRA, the dev-half alpha for mpnet is 1.0, so **hybrid mpnet is exactly the dense mpnet retriever** in that variant.

### Chosen alpha (tuned on the dev half by MRR, `alpha_tuning_dev_mrr`; the MRR values in this table are dev half, not report half)

| Model | With FCRA | Without FCRA |
|---|---|---|
| mpnet | 0.8 (dev MRR 0.403; 0.388 at alpha 1.0) | 1.0 (hybrid = dense) |
| bge | 0.9 | 0.7 |
| e5 | 0.8 | 0.8 |

## Interpretation

- **H1 is supported on the with-FCRA headline corpus.** All six dense and hybrid retrievers beat BM25 on report-half hit@5, and every paired gain CI excludes 0. They range from +0.185 [+0.031, +0.338] (dense e5) to +0.415 [+0.292, +0.538] (hybrid mpnet). **"All six beat BM25" applies to the with-FCRA headline only.** On the four-regulation ablation (without FCRA), five of six gains exclude 0, but **dense e5 does not beat BM25 clearly**: hit@5 +0.108 [-0.015, +0.231].
- **Best retriever by the task's rule (report-half hit@5, ties by MRR): hybrid mpnet, alpha 0.8, hit@5 0.662 [0.538, 0.769].** It is **not distinguishable from dense mpnet**: the paired difference is +0.046 [-0.031, +0.123] in hit@5 and +0.010 [-0.022, +0.041] in MRR (supplementary analysis below). This data shows no detectable benefit from the BM25 component: the CI allows anything from a small loss to a moderate gain. mpnet's dev-half tuning also preferred an alpha close to 1. The winner was picked on the same report-half numbers it is reported on, so its lead over the runner-up is optimistically biased.
- **Encoders (exploratory: supplementary pairs, 21 comparisons, no multiple-comparison correction; with FCRA, report half).** mpnet is ahead of e5 on hit@5, like for like, with intervals that exclude 0: dense +0.185 [+0.031, +0.338], hybrid +0.169 [+0.031, +0.308]. mpnet's differences from bge do not exclude 0, except hybrid mpnet vs hybrid bge (+0.123 [+0.015, +0.246]). e5 is behind, but it ran without its `passage: ` prefix on chunks, so this does not show that e5 is a worse encoder.
- **Per regulation (descriptive only; `by_regulation_all`, with FCRA, hit@5, all 127 in-scope items including the dev half used to tune alpha, no CIs).**
  - For mpnet, Regulation Z gains the most: BM25 0.11 vs mpnet 0.63 (n = 27).
  - Regulation E is next: 0.17 vs 0.59 to 0.62 (n = 29).
  - This pattern is encoder-specific. On Z, bge reaches 0.52, and e5 only 0.30 to 0.33.
  - For FCRA (n = 36) and Regulation F (n = 30), the gains are smaller, and BM25 is already higher there (0.50 and 0.40).
  - Regulation V has only 5 items and cannot be interpreted.
- **FCRA chunks.** The without-FCRA corpus cannot retrieve the 36 FCRA-gold items at all (hit@5 0.00 for every retriever), so the two variants are not directly comparable on overall numbers.

## Supplementary analysis (not from the shared scripts)

**These files are extras beyond the README's required files.** They are produced by my own script, not by `scripts/run_retrieval.py`:
- [`ishani_supplement/h1_supplement.py`](ishani_supplement/h1_supplement.py), the script;
- [`ishani_supplement/h1_supplement.json`](ishani_supplement/h1_supplement.json), its output.

They are the source for the paired differences between retrievers and for the hub-chunk counts below. The script reads only the shared script's saved rank files (`outputs/retrieval/ranks_*.parquet` and `*/ranked.parquet`). It uses the same bootstrap (10,000 resamples, `numpy.default_rng(0)`, same item order), so the resamples are identical to the main script's. Self-check: it reproduces every `gain_vs_bm25` mean and CI in the three JSONs exactly, and BM25 ranks are identical across the three runs. Report half, with FCRA, n = 65:

| Pair (row minus column) | hit@5 difference | MRR difference |
|---|---|---|
| hybrid mpnet − dense mpnet | +0.046 [-0.031, +0.123] | +0.010 [-0.022, +0.041] |
| hybrid mpnet − dense bge | +0.092 [-0.031, +0.215] | +0.069 [-0.011, +0.151] |
| hybrid mpnet − hybrid bge | +0.123 [+0.015, +0.246] | +0.074 [-0.001, +0.150] |
| hybrid mpnet − dense e5 | +0.231 [+0.077, +0.385] | +0.130 [+0.033, +0.232] |
| hybrid mpnet − hybrid e5 | +0.169 [+0.031, +0.308] | +0.117 [+0.024, +0.211] |
| dense mpnet − dense bge | +0.046 [-0.077, +0.169] | +0.059 [-0.028, +0.146] |
| dense mpnet − dense e5 | +0.185 [+0.031, +0.338] | +0.121 [+0.020, +0.224] |

All 21 pairwise differences among the seven retrievers were computed; the table shows the ones relevant to picking a retriever. **No multiple-comparison correction was applied**, so an interval that barely excludes 0 should be read as weak evidence.

**Hub chunk.** One chunk, `12-1006-1006.34-c-4-i` (Regulation F), appears among the top 5 chunks for many complaints. Report half, in-scope, with FCRA, it appears for: BM25 16/65, dense mpnet 4/65, hybrid mpnet 5/65, dense bge 2/65, hybrid bge 2/65, dense e5 16/65, **hybrid e5 26/65**. Without FCRA: BM25 17/65, hybrid e5 30/65. These counts are not all errors. One report-half complaint (18393830, gold Regulation F 1006.34(a)) has the hub's own section as gold; for it, the hub is a correct hit. It is 1 of hybrid mpnet's 5/65 and none of the other retrievers' counts. The hub may contribute to e5's weaker results; I have not tested that. It is worth checking in the error analysis.

## Caveats

- **Small sample:** n = 65, so CIs are wide, ±0.09 to ±0.12 on hit@5. Differences between the stronger retrievers are mostly within noise.
- **Silver labels:** the gold sections are adjudicated silver labels produced by LLM annotation (`annotation/ANNOTATION_GUIDE.md`, 2026-10-15 update), not independent human labels.
- **Headline variant:** with-FCRA as the headline is my assumption (see top).
- **e5 handicap:** the shared script never adds e5's expected `passage: ` prefix to chunks, so e5 runs below its intended setup. I did not change shared code.
- **Truncation:** complaints longer than the encoder's input limit (384 word pieces for mpnet) are truncated by the encoder.
- **Regulation V** has only 5 in-scope items; its per-regulation numbers cannot be interpreted.
- **No multiple-comparison correction** on the 21 supplementary pairwise comparisons.
- **Alpha on the hybrid** was tuned on the dev half only. No encoders were added after looking at report-half numbers; the three encoders are the ones the task file specifies. The best retriever is picked by report-half hit@5, as the task file specifies, so its lead over the runner-up is optimistically biased.

## What went wrong

- **The BM25 determinism check did not match exactly.** In `with_fcra.all_in_scope.bm25` (all 127 in-scope items, not the report half), MRR is 0.19578700706981042 in all three new runs, against 0.19578700706981036 in `results/retrieval_bm25.json`, a difference of ≈6e-17 (5.55e-17). Every other metric, in both corpus variants, matches exactly. Evidence that this is floating-point summation order only, checked by me on CARC against the baseline rankings (not in a committed file):
  - the top-10 chunk lists and all 1,980 scores are bitwise identical to the baseline rankings for 198/198 complaints;
  - the gold-section rank is identical for 127/127 in-scope complaints;
  - `math.fsum` over the new reciprocal ranks reproduces the baseline MRR exactly.

  I told Aditya, as the task file requires. His reply, as relayed by me and paraphrased here (not his exact words), was to do whatever I felt was correct. I took this as clearance to proceed, not as approval of a tolerance for the check.
- **Environment:** my first three jobs (13917005 to 13917007, 2026-11-09) crashed with `NameError: name 'nn' is not defined`. That is the transformers problem described in the README, and those jobs produced no results. After Aditya's fix (commit `e5ac79a`), I reran `carc/setup_env.sh` in the same venv. It reported torch 2.14.1+cu126, transformers 5.19.0, sentence-transformers 6.2.0 and CUDA build 12.6, with 127 tests passed and 1 skipped. All results here come from the rerun jobs below.

## Commands and job IDs

From the repo root on CARC (`~/cfpb-grounded-rag`, commit `e5ac79a`), after `bash carc/setup_env.sh`. `bash carc/check_data.sh` reports every file ok (rechecked 2026-11-16).

```bash
sbatch carc/retrieval.sbatch                                                    # job 14070980 (mpnet)
sbatch --export=ALL,MODEL=BAAI/bge-base-en-v1.5,PREFIX="Represent this sentence for searching relevant passages: ",TAG=bge carc/retrieval.sbatch   # job 14070981
sbatch --export=ALL,MODEL=intfloat/e5-base-v2,PREFIX="query: ",TAG=e5 carc/retrieval.sbatch                                                     # job 14070982
python ~/h1_supplement.py --tags mpnet bge e5 --out ~/h1_supplement_out.json   # supplementary, login node, reads saved outputs only
```

I reran the supplementary script on 2026-11-16, and its output was byte-identical to the first run. That output is committed as `ishani_supplement/h1_supplement.json`; the script is committed unchanged as `ishani_supplement/h1_supplement.py`.

All three jobs ran on a Tesla P100 and finished cleanly. Rankings are under `outputs/retrieval/{bm25,dense,hybrid}_{mpnet,bge,e5}[_no_fcra]/ranked.parquet` (not committed). The best retriever's `hybrid_mpnet/ranked.parquet` goes to the team Drive under `final-experiments/ishani/`.
