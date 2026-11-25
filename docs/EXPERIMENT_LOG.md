# Experiment log (for the final report)

One entry per experiment: question, setup, split, result, files, caveats. Newest last.
Numbers are copied from the result files named in each entry; re-check them there before
they go into the paper. Narrative history stays in `CLAUDE_PROGRESS.md`.

**Shared setup unless stated.**
- Complaints: the 127 in-scope attribution complaints (`annotation/attribution_ids.txt`), split by `cfpb.retrieval.metrics.half`: dev = 0 (62), held-out "report" = 1 (65). Retrieval tuning uses all in-scope gold items; its dev half is the same 62 complaints.
- Choices are made on dev only; held-out is run once per chosen configuration.
- Checker: DeBERTa-v3-large NLI (`MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`), cutoffs 0.5 and T = 0.99658203125 (frozen 2026-11-04).
- Drafter prompt v1-9d0f038c, `nvidia/nemotron-3.5-super-vl-120b-a12b` unless stated.
- GPT-5.6 Sol runs go through the Codex CLI on Aditya's ChatGPT Edu login: **evaluation only**, never an app dependency.

---

## E1. Why is strict accuracy low? Drafter context layout (2026-11-19)

- **Question:** the drafter cites the gold section in only about 28% of sentences. Is that the context layout?
- **Root cause:** the prompt asks the drafter to explain which obligations in the passages apply, and the context held 5 distinct sections, so it surveys all of them.
- **Setup:** same drafts pipeline, three context layouts, metric = share of sentences citing the gold section (no NLI). Script `scripts/run_generation_context_test.py`.

| Layout | Dev | Held-out |
|---|---|---|
| current (5 distinct sections) | 0.278 | 0.284 |
| **top1x5 (up to 5 chunks of the top section)** | **0.631** | **0.558** |
| top2_3_2 | 0.517 | 0.417 |

- **Decision:** top1x5, chosen on dev.
- **File:** `results/generation_context_test.json`.

## E2. Strict attribution runs, full pipeline (2026-11-19)

- **Metric:** sentence supported AND premise includes the gold section (micro, 127 complaints).

| Run | @0.5 | @T | Supported @0.5 / @T |
|---|---|---|---|
| full-llm_rerank (5 sections) | 0.251 | 0.123 | n/a |
| full-llm_top1 (top section) | 0.557 | 0.360 | 0.926 / 0.591 |
| full-oracle-local (gold given) | 0.857 | 0.529 | 0.857 / 0.529 |

- **Oracle gap for top1:** +0.277 [0.185, 0.372] at 0.5, +0.156 [0.081, 0.232] at T.
- **Files:** `results/attribution_full_llm_rerank*.json`, `results/attribution_full_llm_top1*.json`.

## E3. Cluster-based final accuracy (2026-11-19)

- **Why:** single-gold-section scoring is too strict for complaints that several sections can govern.
- **Protocol:** `docs/CLUSTER_SCORING_PROTOCOL.md`.
  - one cluster per (CFPB issue, gold section): 55 clusters
  - built by Claude (regulation-annotator skill), reviewed blind by Mistral Large 4 (reasoning effort low)
  - a member is kept only if both accept
  - 74 of 175 proposed members accepted; 55 of 55 definitions controls rejected
  - frozen with SHA-256 `4f569aee43cf…`
- **FINAL ACCURACY:** sentence supported AND cites the gold section or a cluster member.

| Run | @0.5 [95% CI] | @T | Dev / held-out @0.5 |
|---|---|---|---|
| full-llm_rerank | 0.400 [0.354, 0.444] | 0.226 | 0.416 / 0.384 |
| **full-llm_top1** | **0.623 [0.541, 0.701]** | 0.402 | 0.715 / **0.532** |
| full-oracle-local | 0.857 | 0.529 | held-out 0.865 |

- **Files:** `results/final_accuracy_clusters.json`, `results/cluster_freeze.json`, `annotation/clusters_frozen.jsonl`.
- **Caveats:**
  - the metric was designed after the strict results were seen
  - cluster labels are silver (LLM-built, LLM-reviewed, no human review)
  - the top1 layout was chosen on dev, so held-out 0.532 is the unbiased figure

## E4. Loss breakdown for full-llm_top1 (2026-11-19)

- **Sentence tier shares:**
  - 0.595 gold section
  - 0.076 cluster member
  - 0.212 same law family
  - 0.117 other law
- **Supported share @0.5:** 0.926.
- **Conclusion:** most loss is the top-ranked section being wrong.
- **Top-k section hit of the shipped reranker** (all / held-out):

| k | All | Held-out |
|---|---|---|
| 1 | 0.583 | 0.538 |
| 2 | 0.701 | 0.631 |
| 3 | 0.795 | 0.754 |
| 5 | 0.890 | 0.877 |

- **Issue-based section prior** (learned on dev): held-out top-1 rose from 0.538 to 0.554 (+1 of 65). Not pursued.

## E5. Reranker model swap (2026-11-19 to 11-20, dev only)

- **Setup:**
  - same first stage (Nemotron Embed 8B + BM25, alpha 0.8, classifier regulation prior b 0.2)
  - K = 10 candidate sections, 90-word passages
  - same RERANK_PROMPT unless "+ rubric"
  - script `scripts/run_reranker_swap.py`, results `results/reranker_swap_half0.json`
  - dev = 62 complaints
  - gold in first-stage top 10 = 0.919, which is the ceiling for hit@5

| Reranker | hit@1 | hit@3 | hit@5 | MRR | No answer |
|---|---|---|---|---|---|
| nemotron-3.5-lightning-30b-a3b (shipped) | 0.629 | 0.839 | 0.903 | 0.744 | 1 |
| minimax-m3.1-flash | 0.629 | 0.855 | 0.903 | 0.750 | 1 |
| mistral-large-4-1t-a52b (reasoning low) | 0.645 | 0.871 | 0.903 | 0.763 | 5 |
| nemotron-3-ultra-550b-a55b | 0.677 | 0.871 | 0.919 | 0.779 | 0 |
| nemotron-3.5-super-vl-120b-a12b | 0.710 | 0.855 | 0.919 | 0.801 | 0 |
| kimi-k3.1-pro | 0.726 | 0.887 | 0.919 | 0.801 | 3 |
| gpt-5.6-sol (Codex) | 0.774 | 0.871 | 0.919 | 0.835 | 0 |
| Super, K = 20 | 0.661 | 0.871 | 0.903 | 0.778 | 0 |
| Super, 200-word passages | 0.661 | 0.855 | 0.919 | 0.774 | 0 |
| **Super + rubric hints** | **0.774** | 0.919 | 0.919 | 0.848 | 0 |
| **GPT-5.6 Sol + rubric hints** | **0.839** | 0.919 | 0.919 | 0.883 | 0 |
| Kimi + rubric hints | 0.806 | 0.919 | 0.919 | 0.862 | 3 |

- **Super error analysis** (18 dev misses):
  - 5 had the gold section outside the top 10 (first-stage ranks 12–45, often a classifier law-family miss)
  - 13 were rerank errors, 10 of them with the gold section at rank 2
  - Super prefers the general dispute sections (1026.13, 1006.38, 1681i) over the rubric's specific duty sections (1026.12(b), 1006.18(c)(2), 1681c-2)
- **Rubric hints:** the team's section-choice conventions (from the annotation rubric) placed in the prompt. **Disclose:** the gold labels were made with the same conventions.
- **Kimi + rubric vs Super + rubric:** +2 of 62 at hit@1, but 3 unusable answers and about 40 s per call.
- **Recommended:**
  - deployable: Super + rubric (no failed answers; already the drafter)
  - evaluation upper reference: GPT + rubric
- **Held-out:** not yet run.

## E6. Second cluster reviewer: GPT-5.6 Sol (2026-11-20)

- **Setup:**
  - same prompt as Mistral, one item per call, blind (empty temp directory, no tools)
  - `scripts/review_clusters.py --reviewer gpt`, output `annotation/clusters_review_gpt.jsonl`
- **Results:**
  - GPT accepted 101 of 175 members and rejected 55 of 55 controls
  - Mistral vs GPT on 172 members: 78.5% agreement, **Cohen's kappa 0.58**
  - disagreements: 31 GPT-only accepts, 6 Mistral-only

| Membership rule | Members | 5-section @0.5 | top1 all @0.5 | top1 held-out @0.5 | top1 held-out @T |
|---|---|---|---|---|---|
| Mistral accepts (frozen) | 74 | 0.400 | 0.623 | 0.532 | 0.309 |
| GPT accepts | 101 | 0.451 | 0.653 | 0.543 | 0.321 |
| Both accept | 68 | 0.394 | 0.623 | 0.532 | 0.309 |
| Either accepts | 107 | 0.457 | 0.653 | 0.543 | 0.321 |

- **Conclusion:** the reviewer choice moves the held-out headline by about 1 point. The frozen file is unchanged; the choice of official rule is pending.

## E7. GPT-5.6 Sol as checker: H4 extension (2026-11-20)

- **Setup:**
  - judge prompt judge-v1-5ead5110, `LLMJudgeVerifier("codex:gpt-5.6-sol")`, `scripts/llm_judge.py --workers 4`, compared with NLI at T
  - results `results/llm_judge_codex_gpt-5.6-sol.json` (set 1, 50 pairs) and `results/llm_judge_codex_gpt-5.6-sol_v2.json` (set 2, 100 pairs)
- **Caveat:** ChatGPT was one of the two annotators of both gold sets, so the agreed pairs favour GPT.

| Set | GPT BA @0.5 | NLI BA @T | GPT AUROC | NLI AUROC | GPT unsupported recall @0.5 |
|---|---|---|---|---|---|
| 1 (50) | 0.752 | 0.798 | 0.901 | 0.843 | 0.54 |
| 2 (100) | 0.647 | 0.679 | 0.836 | 0.734 | 0.29 |

- **Cutoff tuned on set 1** (1.0, so only support_probability 100 counts), applied to set 2:
  - GPT balanced accuracy 0.756 vs NLI 0.679, with unsupported recall 0.941
  - difference +0.078 [−0.037, 0.192], not significant
  - on the 17 set-2 adjudicated pairs (all unsupported): GPT 0.882 vs NLI 0.647 accuracy

## E8. GPT-5.6 Sol as drafter, oracle context, dev (2026-11-20)

- **Setup:**
  - `run_pipeline_batch.py --retriever oracle --generator codex --verifier nli --ids annotation/attribution_ids_dev.txt --run-name dev-oracle-gpt`
  - same prompt and parsing as Nemotron (`src/cfpb/generate/codex.py`)
- **Compare with:** full-oracle-local (Super) on the same 62 dev complaints. Checker DeBERTa for both; GPT does not judge its own drafts.
- **Run:** 62 drafts, 0 referrals, 4,983 s.

| Drafter (oracle context, dev 62) | Sentences | Per draft | Supported @0.5 [95% CI] | Supported @T [95% CI] | Words per sentence | Word overlap with cited passage |
|---|---|---|---|---|---|---|
| **Nemotron Super 120B** | 252 | 4.06 | **0.849 [0.790, 0.902]** | **0.536 [0.466, 0.602]** | 33.2 | 0.851 |
| GPT-5.6 Sol (Codex) | 245 | 3.95 | 0.784 [0.726, 0.837] | 0.424 [0.350, 0.498] | 29.3 | 0.731 |

- **Paired per-complaint difference, GPT minus Super:** −0.046 [−0.130, 0.044] at 0.5 (not significant); **−0.099 [−0.185, −0.014] at T** (significant).
- **Likely reason:** GPT paraphrases more (73% vs 85% of its words appear in the cited passage), and NLI favours near-verbatim sentences. Sentences with 90% or more overlap are supported at about 0.92–0.93 for both drafters. Below 90% overlap: GPT 0.775 (n 231), Super 0.799 (n 144).
- **So:** under this checker, GPT is not a better drafter. Its loss is mostly paraphrase that NLI penalises, not clear evidence of worse drafting. Separating the two needs a checker that tolerates paraphrase, such as a judge from a third model family.
- **Decision:** keep Super as the drafter.
- **Files:** `outputs/pipeline_runs/dev-oracle-gpt/`.

## E9. Final accuracy with the strongest links, full pipeline (2026-11-21)

- **Question:** what final accuracy does the pipeline reach with the best reranker found in E5?
- **Setup:**
  - first stage as E5; rerank K = 10, 90-word passages, rubric hints; drafter gets up to 5 chunks of the reranker's top section (top1x5, E1)
  - `scripts/build_top1_rerank.py --model gpt|super`, then `run_pipeline_batch.py --retriever precomputed --generator nemotron --verifier nli --ids annotation/attribution_ids.txt`
  - drafter Super 120B, checker DeBERTa (E7/E8 kept both); scored with `scripts/score_clusters.py` and the frozen clusters (Mistral-accepts rule, E3)
  - runs `full-super_rubric_top1` (13,323 s, 532 sentences) and `full-gpt_rubric_top1` (13,404 s, 525 sentences)
- **Reranker choice was made on dev (E5); held-out is run once here.**

| Run | Top section correct (all) | FINAL @0.5 all [95% CI] | FINAL @T all [95% CI] | Dev / **held-out** @0.5 | Dev / **held-out** @T | Strict @0.5 / @T | Supported @0.5 / @T |
|---|---|---|---|---|---|---|---|
| full-llm_top1 (Lightning, no rubric; E3) | 0.583 | 0.623 [0.541, 0.701] | 0.402 [0.337, 0.466] | 0.715 / **0.532** | 0.494 / **0.309** | 0.557 / 0.360 | 0.926 / 0.591 |
| **full-super_rubric_top1 (deployable)** | 0.701 | **0.741 [0.668, 0.808]** | 0.489 [0.426, 0.551] | 0.828 / **0.657** | 0.579 / **0.402** | 0.645 / 0.432 | 0.932 / 0.622 |
| full-gpt_rubric_top1 (evaluation only) | 0.803 | **0.800 [0.737, 0.859]** | 0.526 [0.467, 0.583] | 0.848 / **0.754** | 0.588 / **0.466** | 0.747 / 0.495 | 0.933 / 0.613 |
| full-oracle-local (gold section given) | 1.000 | 0.857 [0.818, 0.893] | 0.529 [0.481, 0.574] | 0.849 / **0.865** | 0.536 / **0.523** | 0.857 / 0.529 | 0.857 / 0.529 |

- **Sentence tiers** (gold / cluster / same family / other law): Super + rubric 0.692 / 0.100 / 0.122 / 0.086; GPT + rubric 0.802 / 0.055 / 0.069 / 0.074.
- **Held-out @0.5:** Super + rubric closes 12.5 of the 33.3 points between the old top1 run and the oracle; GPT + rubric closes 22.2.
- **Caveats:**
  - rubric hints share conventions with the gold labels (E5 disclosure)
  - cluster labels are silver (E3)
  - GPT runs through Aditya's ChatGPT Edu login and cannot be an app dependency
  - the supported share at T barely moves (0.59 to 0.62): the drafter + checker loss is unchanged by better retrieval
- **Files:** `results/final_accuracy_clusters.json`, `outputs/pipeline_runs/full-{super,gpt}_rubric_top1/`, `outputs/retrieval/{super,gpt}_rubric_top1/`.

## E10. Verification gating (2026-11-21 to 11-22)

- **Question:** the oracle ceiling (0.865 held-out @0.5) means retrieval alone cannot pass about 86%. Can sending flagged sentences back to the drafter close the drafter + checker loss?
- **Setup:** `scripts/run_verification_gating.py` from full-super_rubric_top1. Sentences with NLI entail < T go back to Super with the same passages (revise prompt rev1-9cf1f95b): rewrite from the cited passage wording, or DROP. A rewrite replaces the sentence only if NLI scores it higher. 2 rounds.
  - `-keep`: sentences still below T stay (flagged for the officer). `-drop`: they are removed; coverage reported.
- **Independent check:** `scripts/judge_gating.py` re-scores every rewritten sentence before and after with the GPT-5.6 Sol judge, plus 30 unrewritten controls, because the gate and the metric use the same checker.
- **Pre-registered held-out rule (fixed 2026-11-22 11:38, before any dev result):** run held-out gating once (Super + rubric, 65; `annotation/attribution_ids_heldout.txt`) only if dev `-keep` FINAL@0.5 > base dev FINAL@0.5 (0.828) AND the GPT judge's after-minus-before supported share is >= 0. Gating on the GPT + rubric base (127) runs under the same rule as an evaluation-only reference.
- **Smoke (3 dev complaints):** 5 of 9 rewrites accepted; rewrites near-verbatim (word overlap 0.96); verbatim restatements often still score 0.977-0.996, below T.
- **Dev result (2026-11-22 12:02):** 86 sentences flagged in 44 drafts; round 1 accepted 44 rewrites, round 2 accepted 5 of 68 (46 sentences revised in total; 3 model DROPs). Rewrites are near-verbatim: mean word overlap with the premise 0.924.

| Dev (62) | Sentences | Supported @0.5 / @T | FINAL @0.5 | FINAL @T |
|---|---|---|---|---|
| base full-super_rubric_top1 (dev half) | 261 | 0.946 / 0.670 | 0.828 | 0.579 |
| **gate-keep** | 261 | 0.985 / 0.732 | **0.862** | **0.640** |
| gate-drop (73% of sentences kept, 60/62 drafts non-empty) | 191 | 1.000 / 1.000 | 0.874 | 0.874 (equal by construction) |

  - Drop @T equals @0.5 because every kept sentence passed T; it is not comparable with the others and needs the coverage figure beside it.
- **Independent GPT judge on the 46 rewritten dev sentences (12:04):**

| Sentences | n | GPT supported @0.5 | GPT supported @1.0 | NLI supported @0.5 |
|---|---|---|---|---|
| before rewrite | 46 | 0.783 | 0.174 | 0.739 |
| after rewrite | 46 | 0.957 | 0.826 | 0.957 |
| control (unrewritten, random 30) | 30 | 0.800 | 0.333 | 1.000 |

  - After minus before, GPT @0.5: **+0.174 [0.065, 0.283]**. The second-family judge agrees the rewrites are better supported, so the NLI gain is not only checker-specific writing.
  - Not measured: whether near-verbatim rewrites still address the complaint (relevance). Needs a manual sample.
  - **Rule fired: yes** (dev keep 0.862 > 0.828; GPT diff +0.174 >= 0). Held-out gating started 12:04.
- **Held-out and reference runs (queue finished 14:55):**
  - held-out Super + rubric (65): 115 flagged in 58 drafts; 60 + 11 rewrites accepted (62 sentences revised, 2 DROPs); supported @0.5 0.919 -> 0.985, @T 0.576 -> 0.649; overlap 0.941
  - GPT + rubric base (127): 203 flagged in 104 drafts; 101 + 13 accepted (104 revised, 8 DROPs); supported @0.5 0.933 -> 0.981, @T 0.613 -> 0.682

| Run | Held-out FINAL @0.5 | Held-out FINAL @T | All 127 @0.5 [95% CI] | Sentences kept |
|---|---|---|---|---|
| full-llm_top1 (old app) | 0.532 | 0.309 | 0.623 [0.541, 0.701] | 100% |
| full-super_rubric_top1 | 0.657 | 0.402 | 0.741 [0.668, 0.808] | 100% |
| **Super + rubric + gating, keep (deployable)** | **0.705** | **0.454** | n/a (held-out run only) | 100% |
| Super + rubric + gating, drop | 0.699 | 0.699* | n/a | 65% (62/65 drafts non-empty) |
| full-gpt_rubric_top1 | 0.754 | 0.466 | 0.800 [0.737, 0.859] | 100% |
| **GPT + rubric + gating, keep (eval reference)** | **0.806** | **0.519** | 0.844 [0.780, 0.902] | 100% |
| GPT + rubric + gating, drop | 0.827 | 0.827* | 0.863 [0.795, 0.923] | 68% (120/127 non-empty) |
| full-oracle-local (no gating) | 0.865 | 0.523 | 0.857 [0.818, 0.893] | 100% |

  \* equal to @0.5 by construction (every kept sentence passed T).
  - **Paired held-out gain of gating (keep vs no gating, bootstrap over complaints):** Super +0.048 [0.026, 0.072] @0.5, +0.052 [0.024, 0.084] @T; GPT base +0.052 [0.029, 0.078] @0.5, +0.052 [0.026, 0.083] @T. Significant in all four.
  - **Dev vs held-out:** the dev gain was +0.034 @0.5; held-out +0.048, so no sign of dev overfitting.
  - **GPT + rubric + gating keep (0.806 held-out) is within 6 points of the ungated oracle (0.865).**
  - The drop policy gives no held-out gain over keep for Super at @0.5 and removes 35% of sentences; keep is the recommended policy (the officer sees flagged sentences).
  - Caveats: the gate and the metric share the NLI checker (GPT judge on dev confirms the direction); rewrites are near-verbatim statute text, so relevance to the complaint is not measured; gating was not applied to the oracle run, so the oracle is no longer a strict ceiling for gated runs.
- Results: `results/final_accuracy_gating_dev.json`, `results/judge_gating_dev-super_rubric_gate-keep.json`, `results/final_accuracy_gating.json`; queue log `outputs/queue_2026-11-22.log`.

## E11. Reranker self-consistency vote (2026-11-22, dev only)

- **Question:** does showing Super + rubric the 10 candidates in 5 orders (first-stage order + 4 fixed-seed shuffles, seed 544) and voting raise top-1 section accuracy (single call: 0.774)?
- **Votes:** majority of the top-1 answers; Borda over the top-5 lists. Also records whether low agreement flags misses (a possible referral signal).
- Script `scripts/run_rerank_vote.py`, result `results/rerank_vote_super_half0.json`. Sanity check: 1 order reproduces 0.774 from the cache.
- **Result (dev 62, 310 calls, 2 empty answers):**

| Rule | hit@1 | hit@3 |
|---|---|---|
| single call (first-stage order) | 0.774 | 0.919 |
| majority of 5 top-1 answers | 0.790 | n/a |
| Borda over 5 top-5 lists | 0.774 | 0.919 |

  - Mean top-1 agreement across orders 0.933; no complaint had agreement < 0.6, so agreement is no referral signal here.
  - **Conclusion:** order sensitivity is low; voting gains +1 of 62 at 5x cost. Not adopted.
- Not applied to held-out.

## E12. A better checker (2026-11-22): in progress

- **Why:** E10 decomposition. At @0.5 the checker costs under 1 point (retrieval dominates); at @T, 26–30% of held-out sentences cite the right section but are flagged, and even the oracle scores 0.523 @T.
- **Research** (subagent, primary sources, 2026-11-22): candidate grounding checkers with LLM-AggreFact balanced accuracy: FactCG-DeBERTa-L 75.6 (0.4B, MIT; untuned, its Table 10), MiniCheck-Flan-T5-L 75.0 (0.8B), Granite Guardian 3.3 8B 76.5, Bespoke-MiniCheck-7B 77.4 (non-commercial); SummaC-ZS 67.9 for comparison (MiniCheck Table 2). None evaluated on regulations.

### E12a. Re-calibrating DeBERTa, no new model (`scripts/run_checker_calibration.py`, `results/checker_calibration.json`)

- **Setup:** set 1 (50) and set 2 (100) checker labels; rules from the stored DeBERTa score and lexical containment (share of sentence words in the premise). Chosen on set 1, tested on set 2; also 5-fold CV x20 over all 150.

| Rule | Chosen on set 1 | Set 1 BA | Set 2 BA | CV over 150 BA (sd) |
|---|---|---|---|---|
| NLI >= tau | tau = T | 0.798 | 0.679 | 0.705 (0.016) |
| containment >= c | c = 0.95 | 0.668 | 0.666 | 0.627 (0.022) |
| NLI >= tau OR containment >= c | tau = T, no auto-pass | 0.798 | 0.679 | 0.683 (0.014) |

- **Near-verbatim sentences are not all supported:** overlap >= 0.95: n 47, labels say 77% supported, NLI@T flags 38%; overlap >= 0.9: n 89, 62% supported, NLI@T flags 45%. About half of the near-verbatim flags are label-consistent (for example a copied provision misapplied or missing a condition), so the earlier reading "most T flags on verbatim text are checker errors" was too strong.
- **Conclusion:** T is already DeBERTa's best cutoff; auto-passing verbatim text hurts. Improvement needs a different checker.
- **Caveat:** set 2 labels are AI-adjudicated and accepted by Atharva (`human_validated: false` in checker_gold_v2.jsonl); treat as silver.

### E12c. FactCG-DeBERTa-L and MiniCheck-Flan-T5-L (`scripts/run_checker_bench.py`, `src/cfpb/verify/grounding.py`, `results/checker_bench.json`)

- **Setup:** both downloaded from Hugging Face (yaxili96/FactCG-DeBERTa-v3-Large 1.7 GB, lytang/MiniCheck-Flan-T5-Large 3.0 GB) with Aditya's OK. Input formats follow the authors' code; FactCG reproduces its README example (0.784). Deviation: regex sentence splitter instead of NLTK for chunking. Same premises as NLI (corpus text of premise_chunk_ids). CPU.

| Checker | AUROC set 1 / set 2 | BA @0.5 set 1 / set 2 | Cutoff chosen on set 1 | Set 2 BA at that cutoff | Set 2 unsupported recall | CV over 150 BA | Set 2 BA minus NLI@T [95% CI] |
|---|---|---|---|---|---|---|---|
| DeBERTa NLI (current) | 0.843 / 0.734 | 0.625 / 0.607 | about T | 0.699 (0.679 at exactly T) | 0.73 | 0.725 | n/a |
| FactCG-DeBERTa-L | 0.787 / 0.691 | 0.649 / 0.656 | 0.695 | 0.665 | 0.43 | 0.684 | -0.014 [-0.117, +0.091] |
| MiniCheck-Flan-T5-L | 0.816 / 0.680 | 0.649 / 0.577 | 0.930 | 0.661 | 0.59 | 0.658 | -0.017 [-0.111, +0.079] |
| mean(FactCG, MiniCheck) | 0.812 / 0.712 | 0.670 / 0.587 | 0.928 | 0.648 | 0.75 | 0.717 | n/a |

- **Conclusion:** neither grounding model beats DeBERTa NLI on our regulation pairs; both have lower AUROC on both sets. Their LLM-AggreFact advantage (about 75 vs 68 for SummaC-ZS) does not transfer to dense regulatory text. Reportable as a negative result: first test of these checkers on regulations that we found.
- The only checker that beat NLI on set 2 so far is the GPT-5.6 Sol judge at the set-1 cutoff (E7: 0.756 vs 0.679, CI crosses 0), which is evaluation-only and was one of the label annotators.

### E12b. Nemotron Ultra 550B as judge, and DeBERTa + Ultra ensemble (`results/llm_judge_nemotron-3-ultra-550b-a55b*.json`, `results/checker_ultra_compare.json`)

- **Setup:** `scripts/llm_judge.py --model nvidia/nemotron-3-ultra-550b-a55b`, judge prompt judge-v1-5ead5110, both sets; 2 unreadable replies per set (counted as 0.5). First run died on an unretried dropped connection; `NemotronGenerator._call` now retries `ConnectionError` and `http.client.HTTPException` too.
- Ultra was not one of the label annotators (unlike GPT), so it has no annotator advantage.
- Same protocol as E12c (cutoff chosen on set 1, tested on set 2; 5-fold CV x20 over 150). Ensemble = mean of DeBERTa entail and Ultra support probability (the only combination tried).

| Checker | AUROC set 1 / set 2 | Cutoff (set 1) | Set 1 BA | Set 2 BA | CV over 150 BA |
|---|---|---|---|---|---|
| DeBERTa NLI | 0.843 / 0.734 | about T | 0.817 | 0.699 (0.679 at exactly T) | 0.725 |
| Nemotron Ultra judge | 0.769 / 0.824 | 0.5 | 0.716 | 0.753 | 0.717 |
| GPT-5.6 Sol judge (eval only, annotator) | 0.901 / 0.836 | 0.997 | 0.788 | 0.756 | 0.764 |
| **mean(DeBERTa, Ultra)** | **0.847 / 0.873** | **0.974** | 0.782 | **0.829** | **0.815** |

- **Ensemble vs NLI@T on set 2 (paired bootstrap):** **+0.151 [0.068, 0.237]**, significant. Unsupported recall 0.863 vs 0.745; supported recall 0.796 vs 0.612.
- **Decision:** adopt mean(DeBERTa, Ultra) >= 0.974 as the candidate checker (deployable: free API, one Ultra call per sentence).
- **Caveat:** set 2 labels are silver (AI-adjudicated, accepted by Atharva).

### E12d. Re-scoring held-out runs with the ensemble checker (`scripts/rescore_ensemble.py --half 1`, `results/final_accuracy_ensemble_heldout.json`)

- Held-out sentences of four runs re-checked by mean(DeBERTa, Ultra) >= 0.974; same frozen clusters. Ultra unreadable replies: 0-1 per run.

| Run (held-out 65) | Supported: NLI@0.5 / NLI@T / Ultra@0.5 / **ensemble** | FINAL: NLI@0.5 | NLI@T | **ensemble** [95% CI] |
|---|---|---|---|---|
| full-oracle-local (no gating) | 0.857 / 0.523 / 0.733 / **0.519** | 0.865 | 0.523 | **0.519 [0.446, 0.587]** |
| full-super_rubric_top1 | 0.919 / 0.576 / 0.745 / **0.535** | 0.657 | 0.402 | **0.384 [0.303, 0.463]** |
| Super + rubric + gating (keep) | 0.985 / 0.649 / 0.815 / **0.661** | 0.705 | 0.454 | **0.483 [0.393, 0.573]** |
| GPT + rubric + gating (keep) | 0.981 / 0.627 / 0.832 / **0.672** | 0.806 | 0.519 | **0.556 [0.471, 0.639]** |

- **Reading:** the best-validated checker supports about as many sentences as NLI@T, so under it final accuracy sits near the @T numbers, well below the NLI@0.5 headline. NLI@0.5 had set-2 BA 0.607 (it passes many unsupported sentences), so the @0.5 figures overstate accuracy.
- **Gating still helps under the new checker:** Super 0.384 -> 0.483 (+0.099), although half of the ensemble is the NLI model that drove the gate.
- **Implication:** the honest headline should use the ensemble checker; raising it needs gating driven by the ensemble (rewrite what it flags), not a different checker alone. (`scripts/llm_judge.py --model nvidia/nemotron-3-ultra-550b-a55b`, both sets)

## E13. Why does the drafter fail with the correct section? One-factor ablation (2026-11-22): done

- **Why:** under the ensemble checker the oracle run (gold section given) is only about 52% supported (dev 0.516, held-out 0.519), so generation is the largest loss.
- **Design (Aditya's call):** causal ablation, not LLM error labelling. An LLM sorting of flagged sentences into causes was started and stopped (`scripts/diagnose_flags.py`; GPT hit the Codex rate limit; DeepSeek dropped as never validated on set 2; Ultra-only labelling would be correlational and only about 75% reliable).
- **Frozen:** dev 62, oracle context (gold-section chunks, k 5), Super drafter at temperature 0, checker mean(DeBERTa, Ultra) >= 0.974 (NLI@T also reported). One factor changes per arm:
  - A0 baseline prompt v1 (must reproduce dev oracle 0.516)
  - A1 no complaint text in the drafter input
  - A2 instruction: state only what the passages say; no consumer, company or facts
  - A3 quote-anchored: each sentence restates one provision in the passage's wording, keeping every condition
  - A4 context size: top oracle chunk only (k 1)
  - A5 drafter model: GPT-5.6 Sol (Codex, evaluation only), prompt v1; drafts cached from E8 (62/62)
- **Guard metric:** Ultra judges per draft whether it addresses the consumer's main grievance (so an arm cannot win by ignoring the complaint).
- **GPT in the checker (tested 2026-11-22, `results/checker_ensembles_with_gpt.json`):** cutoff on set 1, set 2 BA / CV150: GPT 0.756 / 0.763; DeBERTa+GPT 0.750 / 0.797; Ultra+GPT 0.802 / 0.784; DeBERTa+Ultra+GPT 0.789 / 0.833; DeBERTa+Ultra 0.829 / 0.814. Adding GPT does not improve the held-out set-2 figure (its CV edge includes set 1, which ChatGPT helped label), so the checker stays DeBERTa+Ultra. GPT stays where it is best: reranker (E5, E9) and as drafter arm A5.
- **Codex quota (checked 23:27):** 5-hour window 2% used, weekly 18%; the earlier 429 was a burst limit from 4 parallel calls, so Codex calls now use 2 workers.
- Script `scripts/run_drafter_ablation.py`; results `results/drafter_ablation.json`, rows `outputs/drafter_ablation/<arm>.parquet`, log `outputs/drafter_ablation.log`.

### E13 results, arms A0 to A4 (finished 2026-11-23)

Dev 62, oracle context. Supported share = FINAL ACCURACY here (section is gold). Paired bootstrap over complaints vs A0, 10,000 resamples.

| Arm | Change | Sent./draft | Ensemble supported | vs A0 [95% CI] | NLI@T | Ultra@0.5 | Word overlap | Addresses complaint |
|---|---|---|---|---|---|---|---|---|
| A0 | baseline v1 | 4.07 | **0.516** (reproduces E12d) | | 0.536 | 0.690 | 0.874 | 0.403 |
| A1 | no complaint text | 2.74 | 0.418 | -0.098 [-0.203, +0.005] | 0.476 | 0.594 | 0.843 | 0.081 |
| A2 | "state only what passages say" | 4.26 | 0.549 | +0.033 [-0.049, +0.118] | 0.473 | 0.686 | 0.975 | 0.145 |
| A3 | quote-anchored, keep every condition | 4.08 | **0.767** | **+0.251 [+0.178, +0.326]** | 0.340 | 0.881 | 0.985 | 0.145 |
| A4 | top chunk only (k 1) | 3.40 | 0.398 | -0.118 [-0.196, -0.036] | 0.417 | 0.682 | 0.787 | 0.355 |

Reading:
- **The one factor that moves support is how the sentence is anchored to the passage (A3, +25 points, CI clear of zero).** Telling the model only to avoid facts (A2) is not enough; the gain needs "restate one provision, keep every condition". So most of the oracle failure is the drafter paraphrasing loosely and dropping or bending conditions, not missing context.
- **Less context hurts (A4, -12 points):** the correct provision is often not in the top chunk. Removing the complaint (A1) does not help either.
- **Trade-off:** A3 (and A2) drafts mostly stop addressing the consumer's grievance (0.40 -> 0.15 by the Ultra guard). A3 alone is not a usable response; it is a faithful rule summary.
- **Checker caution:** for A3 the two checkers disagree. Ultra rises to 0.881, but DeBERTa@T falls to 0.340 despite 98.5% word overlap (same pattern as the near-verbatim finding: DeBERTa at T is unreliable on close restatements). The ensemble gain is therefore partly Ultra's judgement; a human spot-check of A3 sentences is needed before claiming it.
- **App (2026-11-23):** the app now uses this ensemble checker (src/cfpb/verify/ensemble.py), so app and evaluation agree.
- **Design implied:** a two-part draft: quote-anchored rule sentences (checked against the passage) plus explicitly labelled application sentences linking the rule to the complaint (shown to the officer as "application, not verified by the passage"). Not yet tested.

### E13 arm A5: GPT-5.6 Sol as drafter (prompt v1, k 5; finished 2026-11-23)

| Arm | Sent./draft | Ensemble supported | vs A0 [95% CI] | NLI@T | Ultra@0.5 | Word overlap | Addresses complaint |
|---|---|---|---|---|---|---|---|
| A5 GPT drafter | 3.95 | 0.478 | -0.038 [-0.121, +0.045] | 0.424 | 0.829 | 0.762 | 0.419 |

- Swapping the drafter model does not help: GPT is level with Super (difference not significant, point estimate lower). The two checkers split again: Ultra likes GPT's drafts (0.829), DeBERTa@T does not (0.424); GPT paraphrases more (overlap 0.76 vs 0.87).
- Conclusion of E13: the drafter failure is the **prompt (anchoring to the passage), not the model**. GPT remains the best reranker (E9), not a better drafter. The lever is A3-style anchoring, combined with a way to keep addressing the complaint.

## E14. Is the scoring too strict? (2026-11-23)

Question (Aditya): is the metric harsher than needed and dragging final accuracy down? Checked two parts.

**1. Support part: checker vs the checker label sets** (scratch script; per-pair scores saved to `outputs/checker_scored_v1.parquet`, `_v2.parquet`)

| Checker | Set 1 (50): labels / checker say supported | sens / spec | Set 2 (100): labels / checker | sens / spec |
|---|---|---|---|---|
| Ensemble @ CUT | 0.520 / 0.460 | 0.731 / 0.833 | 0.490 / 0.460 | 0.796 / 0.863 |
| DeBERTa @ T | 0.520 / 0.560 | 0.846 / 0.750 | 0.490 / 0.430 | 0.612 / 0.745 |
| DeBERTa @ 0.5 | 0.520 / 0.880 | 1.000 / 0.250 | 0.490 / 0.870 | 0.980 / 0.235 |

- The ensemble is not harsher than the labels: it calls 46% supported where the labels say 49%. About half of drafted sentences are unsupported by the labels' own reading.
- The old @0.5 headline was too lenient (87% vs 49%; it passes 3 of 4 unsupported sentences).

**2. Section part and a label-error correction** (held-out 65, ensemble checker; from `results/final_accuracy_ensemble_heldout.json`). "Same law" counts tier 3 (another section of the gold law), the coarse fallback CLAUDE.md allows. "Label-corrected" applies the Rogan-Gladen correction with set-2 sens 0.796 / spec 0.863 to the supported rate (sensitivity analysis, not a headline).

| Run | Final (tier 1-2) | Same law (tier 1-3) | Supported, any section | Label-corrected final |
|---|---|---|---|---|
| Oracle | 0.519 | 0.519 | 0.519 | 0.579 |
| Super + rubric | 0.384 | 0.476 | 0.535 | 0.433 |
| Super + rubric + gating | 0.483 | 0.587 | 0.661 | 0.581 |
| GPT + rubric + gating | 0.556 | 0.597 | 0.672 | 0.672 |

- Even the most generous defensible reading tops out near 0.6 to 0.67. Re-scoring cannot reach 92%; the gap is real unsupported content (E13) plus wrong sections.
- Recommendation: keep the frozen headline (it was pre-registered); report same-law and label-corrected figures beside it as secondary or sensitivity analyses, with the disclosure.

## E15. Alternatives to DeBERTa in the checker (2026-11-23)

Downloads approved by Aditya. Scorers in `src/cfpb/verify/grounding.py` (kinds `hhem`, `alignscore`, `bespoke`; input formats from the authors' code, see the module docstring); harness `scripts/run_checker_bench.py --with-ultra`; scores cached in `outputs/checker_bench/<kind>.json`; results `results/checker_bench_{hhem,alignscore,bespoke,combos}.json`. Protocol as E12: cutoff chosen on set 1 (50), tested on set 2 (100); 5-fold CV x20 over all 150; paired bootstrap on set 2.

- HHEM-2.1-open (vectara/hallucination_evaluation_model; its remote code read before running).
- AlignScore-large (yzha/AlignScore checkpoint, loaded with `weights_only=True`; inference re-implemented from the authors' inference.py/model.py, 'nli_sp' mode).
- Bespoke-MiniCheck-7B through Ollama (`bespoke-minicheck`, Q4_K_M). **Deviation:** 4-bit build, because the bf16 model needs about 15.5 GB of RAM (machine has 16 GB). Score = P(Yes)/(P(Yes)+P(No)) from first-token log-probabilities.

| Checker | Set 2 BA @ set-1 cut | CV150 | vs reference [95% CI] |
|---|---|---|---|
| DeBERTa (this harness) | 0.699 | 0.725 | |
| HHEM | 0.585 | 0.644 | vs DeBERTa -0.093 [-0.201, +0.014] |
| AlignScore | 0.634 | 0.669 | vs DeBERTa -0.045 [-0.144, +0.055] |
| Bespoke-MiniCheck-7B | **0.733** | 0.734 | vs DeBERTa +0.054 [-0.056, +0.162] |
| **DeBERTa + Ultra (current)** | **0.829** | 0.802 | reference |
| HHEM + Ultra | 0.738 | 0.735 | -0.091 [-0.177, -0.008] |
| AlignScore + Ultra | 0.749 | 0.752 | -0.080 [-0.163, +0.002] |
| Bespoke + Ultra | 0.801 | 0.792 | -0.028 [-0.102, +0.047] |
| DeBERTa + Bespoke | 0.741 | 0.733 | |
| DeBERTa + Bespoke + Ultra | 0.734 | 0.799 | -0.096 [-0.174, -0.018] |

- Bespoke is the best standalone small checker (above DeBERTa alone, not significant), but no replacement or addition beats DeBERTa + Ultra. **The app keeps DeBERTa + Ultra.** Negative result for the report: three grounding checkers built for LLM output do not beat a general NLI model when paired with an LLM judge on regulation text.
- Bespoke is also slow here (3-20 s per pair on this machine through Ollama), so it would not suit the app without a GPU.

## E16. GPT reranker in the finalized pipeline and the app (2026-11-23, Aditya's call)

- Choice made on dev, as the protocol requires: top-ranked section correct on dev 0.839 (GPT + rubric) vs 0.774 (Super + rubric) (`results/reranker_swap_half0.json`). Held-out confirms: **0.769 [0.662, 0.862] vs 0.631 [0.508, 0.754]** (`results/reranker_top1_section.json`).
- **Finalized pipeline from now on:** Nemotron Embed 8B + BM25 + prior -> GPT-5.6 Sol reranker with rubric hints (K 10) -> top1x5 context -> Super drafter (v1) -> DeBERTa + Ultra checker -> gating (2 rounds, keep). Held-out FINAL ACCURACY under the ensemble checker: **0.556 [0.471, 0.639]** (E12d run full-gpt_rubric_gate-keep+ens), vs 0.483 with the Super reranker.
- Code: `src/cfpb/retrieval/llm_rerank.py` now calls Codex for `codex:` models with the experiments' cache (`codex_post` moved there from `scripts/run_reranker_swap.py`); `LLMRerankRetriever(model, fallback)`. App: `CFPB_RERANK_MODEL` (default `codex:gpt-5.6-sol`), `CFPB_RERANK_FALLBACK` (default Super); Insights step 2 shows the held-out figures.
- Check: the module reproduces the experiment's top section on 8/8 complaints (cache hits); app end to end on throwaway SQLite (15284705): context identical to full-gpt_rubric_top1, 5 sentences, 2 rewritten, 1 flagged, verify + gating 158 s.
- Dependency note: the reranker uses the Codex login of the machine running the app (now Aditya's ChatGPT Edu login, his decision); a deployment should log in with its own account. Disclose in the report that the best configuration uses a hosted GPT model.

## E17. Drafter fix in the finalized pipeline (pre-registered 2026-11-23, before any run)

- **Question:** does the E13 anchoring gain survive in the full pipeline (retrieved section, GPT reranker) without the draft ignoring the complaint?
- **Frozen:** GPT reranker + rubric, top1x5 context (full-gpt_rubric_top1), Super drafter at temperature 0, ensemble checker (CUT 0.97378), gating exactly as the app (gate_draft, ensemble flags, 2 rounds, keep), frozen clusters for scoring. Script `scripts/run_drafter_fix.py`.
- **Arms (rule 1 only):** B0 prompt v1 (the app today); B1 quote-anchored (A3) + "choose the provisions that govern what the consumer is asking the company to fix, the most directly relevant first"; B2 = B1 + "begin each sentence with a short phrase naming the part of the complaint it answers".
- **Rule (fixed now):** on dev (62), choose B1 or B2 by FINAL ACCURACY with gating, among arms whose "addresses the complaint" share is >= B0's minus 0.05. Run held-out (65) once, with B0 and the chosen arm, only if the chosen arm's dev gain over B0 (gating) has a 95% CI lower bound > 0. Otherwise report the dev result and keep B0.
- **Dev result (2026-11-24, 62 complaints; `results/drafter_fix_dev.json`, `results/drafter_fix_dev_clusters.json`).** FINAL ACCURACY at the ensemble cutoff (score_clusters' "@0.5" column is the run's own label, i.e. ensemble >= CUT; its "@T" column does not apply to ensemble scores):

  | Arm | No gating | With gating | Gating vs B0 (paired, 95% CI) | Addresses complaint (gated) | Sentences/draft |
  |---|---|---|---|---|---|
  | B0 (v1) | 0.556 [0.484, 0.625] | 0.794 [0.716, 0.863] | - | 0.323 | 4.15 |
  | B1 | 0.722 [0.636, 0.802] | 0.789 [0.703, 0.865] | -0.005 [-0.048, +0.038] | 0.210 | 3.82 |
  | B2 | 0.278 [0.222, 0.333] | 0.787 [0.702, 0.864] | -0.007 [-0.057, +0.040] | 0.194 | 3.71 |

  Acceptable drafts with gating: B0 0.855, B1 0.839, B2 0.806.
- **Rule applied:** both B1 and B2 fail the guard (addresses 0.210 and 0.194 < 0.323 - 0.05 = 0.273), and neither gain has a CI lower bound above 0. The rule does not fire: no held-out run; B0 stays.
- **Reading:** without gating, B1's anchoring gain replicates in the full pipeline (+0.165 [+0.091, +0.241], close to E13's A3 +0.251), but gating already recovers the same ground for B0 (0.556 -> 0.794), so the two fixes are redundant; anchoring only costs relevance. B2's sentence openers ("On the disputed late payment, ...") are not in the passage and the checker rejects them before gating (0.278). Note dev numbers run well above held-out (B0 gated 0.794 here vs 0.556 held-out), so dev is not a headline.
- **Follow-up, registered 2026-11-24 before running (Aditya approved):** the held-out headline 0.556 (E16) came from run full-gpt_rubric_gate-keep+ens, where gating was driven by DeBERTa flags and only the final scoring used the ensemble. The app gates with the ensemble. Run B0 once on held-out (65) with ensemble-driven gating (`run_drafter_fix.py --split heldout --arms B0`) to measure the pipeline as the app runs it. No setting is chosen from this run; it is reported as the finalized pipeline's held-out figure alongside 0.556.
- **Held-out result (2026-11-24, 65 complaints; `results/drafter_fix_heldout.json`, `results/drafter_fix_heldout_clusters.json`).** Finalized pipeline as the app runs it (B0, ensemble-driven gating): FINAL ACCURACY **0.694 [0.599, 0.782]**; gold section only 0.653; supported 0.847; acceptable drafts 0.754. Before gating: 0.444 [0.364, 0.522], acceptable 0.508. Tier shares 0.769 / 0.045 / 0.071 / 0.116 (same retrieval as E16). Compare 0.556 [0.471, 0.639] for the DeBERTa-driven gating run (E16).
- **Caveats for the report:** (1) gating now rewrites against the same checker that scores the draft, so part of the gain may be the reviser learning to satisfy the checker rather than the regulation; a human spot-check of rewritten sentences is needed before this is the headline. (2) Rewriting lowers "addresses the complaint" (0.477 -> 0.338). (3) Dev ran higher (0.794), as usual.
- **Oracle follow-up, registered 2026-11-24 before running (Aditya approved):** same run with the oracle context (gold-section chunks, k 5, as full-oracle-local) on held-out, so the retrieved-vs-oracle gap is measured under identical ensemble-driven gating (`run_drafter_fix.py --split heldout --arms B0 --context oracle`). Smoke test (2 complaints): drafts identical to full-oracle-local.
- **Oracle held-out result (2026-11-24, 65 complaints; `results/drafter_fix_oracle-heldout.json`; summary in `results/final_results.json` -> `finalized_pipeline`).** Same drafter, checker and ensemble-driven gating, oracle context: before gating 0.519 [0.446, 0.587] (acceptable 0.600), with gating **0.808 [0.745, 0.864]** (acceptable 0.892, addresses 0.277).
- **Attribution, matched (oracle minus retrieved, paired over complaints):** before gating +0.075 [-0.033, +0.183]; with gating **+0.114 [+0.002, +0.228]**. With gating, of the 0.306 of retrieved-run sentences that fail, about 0.11 is attributable to retrieval and about 0.19 remains with the correct passage (generation). At the midterm (BM25, NLI@0.5) the retrieval gap was +0.70; retrieval no longer dominates, generation does.
