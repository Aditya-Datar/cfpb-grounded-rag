# Atharva: H4 checker reliability results

**Analysis complete under Atharva’s explicitly accepted AI-adjudication protocol (November 18, 2026). Set 2 is not human-validated.** The original task requested human adjudication; Atharva accepted AI adjudication instead. All 100 v2 pairs are now scored by NLI and the Mistral judge, with zero unreadable final judge responses. The original 4096-token-only Mistral run remains documented as incomplete (87/100); its completion used the separately declared adaptive output-budget policy below.

## Fixed cutoff and reference protocol

**T = 0.99658203125**, fixed on November 4 before v2 sampling/labels, remains unchanged. It was selected from the set-1 best-threshold analysis, supported by the existing repeated five-fold CV analysis. Set-1 tuned performance is optimistic; set 2 is the transfer test. No v2 optimum or v2 CV threshold was used to change T.

The frozen v2 sample contains 100 pairs, 50 oracle and 50 retrieved, from Anirudh’s `full-oracle-nli` and `full-bm25` runs. It has zero exact sentence overlap with set 1 and covers 72 complaints; 16 complaints are also represented in set 1. It is therefore sentence-held-out, not a wholly disjoint complaint cohort. The approved H4-only exclusion preparation retains the original deterministic sample order while removing all set-1 sentence text; shared sampling code is unchanged.

Claude Opus 5.5 and GPT-6-Astra independently annotated identical blind inputs: 83/100 agreement, Cohen’s kappa 0.656, and 17 disagreements. The main reference uses Claude’s completed AI-adjudication worksheet: 49 supported, 51 unsupported. The earlier GPT-family AI-adjudicated reference has 52 supported, 48 unsupported and differs only on Kv2-016, Kv2-061 and Kv2-076. Both references are preserved; neither is human-validated. Reference selection is recorded before the recovery predictions and uses the user’s latest completed worksheet, not better benchmark performance.

All table cells below show estimate [95% paired percentile-bootstrap CI], 10,000 pair resamples, seed 0. These intervals condition on the reference labels and do not account for annotation uncertainty or correlation among sentences from the same complaint.

## Set 1 — 50 original adjudicated pairs

| Checker | Balanced accuracy | Kappa | Unsupported recall | AUROC |
|---|---|---|---|---|
| NLI@0.5 | 0.625 [0.542, 0.714] | 0.257 [0.086, 0.454] | 0.250 [0.083, 0.429] | 0.843 [0.715, 0.948] |
| NLI@T (shared reader) | 0.798 [0.680, 0.901] | 0.598 [0.359, 0.800] | 0.750 [0.565, 0.913] | 0.843 [0.715, 0.948] |
| DeepSeek V4.1 Flash | 0.713 [0.589, 0.828] | 0.432 [0.179, 0.666] | 0.542 [0.333, 0.739] | 0.838 [0.723, 0.928] |
| Mistral (optional second judge) | not completed | not completed | not completed | not completed |

DeepSeek completed 50/50 with zero unreadable replies. DeepSeek minus NLI@0.5 balanced accuracy is **0.088 [-0.067, 0.234]**; versus NLI@T it is **-0.085 [-0.220, 0.050]**. The original task permits reporting one judge when optional Mistral keeps failing. Its historical CARC run reached 26/50 before repeated disconnections; no partial Mistral performance is reported. The original DeepSeek and NLI benchmark files both reproduce byte-for-byte in scratch space and remain unchanged.

The original set-1 best-threshold artifact stores 0.9965820312499999, while the frozen stated T is 0.99658203125. At the exact frozen T, the shared JSON reader yields balanced accuracy 0.798; exact source-value decoding yields 0.817, matching the original tuned best-threshold result. The table above uses the exact frozen T with the unchanged shared reader. This corrects earlier prose that conflated the original tuned result with that exact-T evaluation; it is not retuning. See `results/checker_h4_set1_fixed_tau_audit.json`.

## Set 2 — 100 pairs, accepted Claude AI adjudication

| Checker | Balanced accuracy | Kappa | Unsupported recall | AUROC |
|---|---|---|---|---|
| NLI@0.5 | 0.607 [0.548, 0.673] | 0.212 [0.092, 0.343] | 0.235 [0.125, 0.357] | 0.734 [0.632, 0.829] |
| NLI@T (shared reader) | 0.679 [0.586, 0.768] | 0.358 [0.170, 0.533] | 0.745 [0.619, 0.860] | 0.734 [0.632, 0.829] |
| Mistral adaptive output budget | 0.674 [0.589, 0.757] | 0.345 [0.173, 0.511] | 0.490 [0.354, 0.625] | 0.695 [0.605, 0.782] |
| DeepSeek V4.1 Flash | unavailable (HTTP 410) | unavailable | unavailable | unavailable |

Mistral minus NLI@T balanced accuracy: **-0.005 [-0.114, 0.110]**. Versus NLI@0.5: **0.066 [-0.043, 0.173]**. The paired 95% interval includes zero, so this set does not establish a balanced-accuracy advantage for Mistral over NLI@T.

NLI’s frozen-T minus 0.5 balanced-accuracy gain is 0.071 [-0.025, 0.166], so this reference does not establish a gain in balanced accuracy from raising the cutoff, although unsupported recall rises from 0.235 to 0.745. Condition-specific accuracy at **NLI@0.5** is 0.68 for oracle pairs and 0.52 for retrieved pairs; these are not NLI@T values or generator factuality rates.

## Sensitivity to AI adjudication and score decoding

The earlier GPT-family reference is a sensitivity analysis on the same pairs, not another dataset:

| Checker | Balanced accuracy | Kappa | Unsupported recall | AUROC |
|---|---|---|---|---|
| NLI@0.5 | 0.615 [0.553, 0.682] | 0.237 [0.110, 0.378] | 0.250 [0.133, 0.378] | 0.745 [0.643, 0.838] |
| NLI@T (shared reader) | 0.673 [0.580, 0.761] | 0.344 [0.156, 0.520] | 0.750 [0.622, 0.868] | 0.745 [0.643, 0.838] |
| Mistral adaptive output budget | 0.673 [0.586, 0.757] | 0.351 [0.171, 0.518] | 0.500 [0.360, 0.640] | 0.695 [0.603, 0.784] |

Mistral minus NLI@T under this reference: **0.000 [-0.115, 0.118]**. Interpret both references together; agreement between them is not human validation.

Four v2 probabilities lie exactly on T in the source Parquet/standard JSON representation. The unchanged shared pandas reader moves them slightly below T. Both decoding paths are reported, with T fixed:

| AI reference | NLI@T BA, exact source decoding | Judge minus NLI@T BA, exact source decoding |
|---|---|---|
| Claude (main) | 0.699 [0.605, 0.789] | -0.026 [-0.136, 0.089] |
| GPT-family (sensitivity) | 0.692 [0.598, 0.781] | -0.018 [-0.132, 0.099] |

Primary results reproduce the shared scorer. Exact decoding is a numerical sensitivity analysis, not a different cutoff or a silent shared-script fix. Aditya can choose a common loader policy for the integrated report; the observed behavior and both results are available now.

The qualitative interval conclusion for judge versus NLI@T is consistent across both AI references and both decoding methods; this consistency is not human validation.

## Judge recovery and provenance

DeepSeek’s v2 endpoint returned HTTP 410, with retirement dated November 16, before any v2 judgment. Mistral non-streaming calls disconnected; SSE recovered usable replies while preserving the model, prompt and temperature. The 4096-token-only run and retry ended with 87 readable replies and 13 failures. Diagnostic streams for the failures ended with `finish_reason=length` and empty final answers. No label was inferred from reasoning text, and no failure was silently removed.

Before larger-budget inference, `results/checker_h4_completion_protocol.json` declared the failure-only budget ladder: 4096 initially, then 16384 and at most 32768 for missing readable answers. Original completed replies are retained; recovery outputs live in a separate cache. Model `mistralai/mistral-large-4-1t-a52b`, prompt `judge-v1-5ead5110`, temperature 0, sample and T remain unchanged. This is an **adaptive-budget judge configuration**, not a claim that all requests used 4096 tokens. The amendment occurred after preliminary v2 NLI analyses; only the recovery policy was declared before recovery predictions. It is not a preregistration claim for the entire study.

Final readable responses by maximum token budget: `{"16384": 13, "4096": 87}`. All 100 responses are validated and cached, with zero unreadable final replies. Recovery sees only passages and sentences; no reference labels, NLI probabilities, or performance metrics enter the requests. The unchanged team judge script scores a separate complete combined cache with API calls explicitly disabled.

## Interpretation and pipeline recommendation

The paired 95% interval includes zero, so this set does not establish a balanced-accuracy advantage for Mistral over NLI@T. The qualitative interval conclusion for judge versus NLI@T is consistent across both AI references and both decoding methods; this consistency is not human validation. This addresses H4 against AI references; it does not establish reliability against independently human-adjudicated v2 truth. The NLI cutoff improves unsupported recall substantially under both AI references, but its balanced-accuracy-gain intervals include zero.

For the current pipeline, retain NLI at the frozen T as a fast screening checker when detecting unsupported sentences is the priority, accepting its higher false-positive rate. Use the LLM judge for offline audits where its measured agreement and long API latency are acceptable. This is an operational recommendation; the tables determine which model has higher measured agreement. Neither checker should be treated as a guarantee that a sentence is correct.

Both source runs used Anirudh’s replacement Nemotron 3.5 generator, rather than the older set-1 generator. Generator transfer, repeated complaints, AI-family adjudication bias and pair-bootstrap dependence limits constrain comparisons. The original run metadata includes a dirty working-tree suffix and no producer checksum manifest; local copies and corpus identity were verified. No drafts, samples, labels or thresholds were changed to improve judge performance.

## Reproduction and handoff

- Set-1 results: `results/checker_benchmark.json`, `results/llm_judge_deepseek-v4.1-flash.json`; exact-T audit and intervals: `results/checker_h4_set1_fixed_tau_audit.json`.
- Set-2 main reference: `annotation/checker_gold_v2.jsonl`, explicitly `human_validated: false`; source rationales and both alternative references are retained.
- Set-2 main results: `results/checker_benchmark_v2.json`, `results/llm_judge_mistral-large-4-1t-a52b_v2.json`.
- Sensitivity and intervals: `results/llm_judge_mistral-large-4-1t-a52b_v2_gpt_sensitivity.json`, `results/checker_h4_v2_final_uncertainty.json`.
- Original 87/100 run audit: `results/checker_judge_v2_completion_audit.json`; completed adaptive-run manifest: `results/checker_judge_v2_adaptive_manifest.json`.
- Sampling/annotation provenance and original helper snapshots: existing `results/checker_*manifest.json` and `results/checker_h4_v2_reproduction.json`. Completion helper source/hashes: `results/checker_h4_completion_reproduction.json`.

Commands (run locally, no scheduler job ID; API-only, Cisco VPN left off at user request):

```sh
python scripts/checker_benchmark.py build-gold --a claude --b chatgpt --tag v2
python scripts/checker_benchmark.py score --tag v2 --tau 0.99658203125
python outputs/h4_v2/adaptive/recover.py --probe --workers 1
python outputs/h4_v2/adaptive/recover.py --workers 4
python outputs/h4_v2/adaptive/score_final.py
python outputs/h4_v2/adaptive/audit_set1.py
```

The helpers invoke unchanged team scoring functions and preserve original set-1 artifacts. Thread limits were `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`; logs and caches remain ignored under `outputs/h4_v2/` and `outputs/judge/`. For Anirudh’s report rerun, use **`--tau 0.99658203125`**.

The user-requested AI-adjudicated analysis is complete. Human review remains valuable for stronger validation, but is not claimed or required by Atharva’s amended request. Team review of the AI-reference choice, adaptive-budget policy and score-loader sensitivity is documented for the PR; no approval or merge is implied.
