> **Superseded by the completed AI-adjudicated analysis in [atharva.md](atharva.md).** This file preserves the earlier provisional/incomplete-run report; its pending statements describe that historical stage. Do not regenerate it with the old helper.

# Atharva H4 v2 — provisional AI-reference analysis

**Status: not human-validated and not the final H4 submission.** Atharva delegated review of the 17 disagreements to the assistant. The assistant recorded a rationale for every decision, but no human approval is claimed. All 17 decisions match GPT-6-Astra, making this provisional 100-label reference identical to that annotator's labels. Same-family adjudication bias is possible. This file reports that GPT-family adjudication, called **AI reference A** in [atharva.md](atharva.md). A second, separate AI adjudication by Claude Opus 5.5 (**AI reference B**, also not human-validated) was recorded on 2026-11-18. It is now entered in the worksheet with explicit AI tags, and its results are in [atharva.md](atharva.md) and `results/checker_benchmark_v2_claude_adjudicated.json`. The canonical human gold `annotation/checker_gold_v2.jsonl` has not been created.

_This file was edited by hand on 2026-11-18; do not regenerate it with `outputs/h4_v2/refresh_provisional_report.py`, which predates these updates._

## Data and fixed decisions

- 100 frozen pairs: 50 retrieved and 50 oracle; no set-1 sentence overlap.
- 72 complaints, including 16 also represented in set 1; this is not a disjoint-complaint test.
- T = **0.99658203125**, fixed before v2 and unchanged.
- Annotators: Claude Opus 5.5 and GPT-6-Astra; 83% agreement, Cohen's kappa 0.656.
- Both source runs use the replacement Nemotron generator, so transfer from set 1 is an additional limitation.

## NLI against the provisional AI reference

All cells show estimate [95% pair-bootstrap CI]. The intervals condition on these AI reference labels and do not account for annotation uncertainty or correlation among sentences from the same complaint.

| Checker | Balanced accuracy | Kappa | Unsupported recall | AUROC |
|---|---|---|---|---|
| NLI@0.5 | 0.615 [0.553, 0.682] | 0.237 [0.110, 0.378] | 0.250 [0.133, 0.378] | 0.745 [0.643, 0.838] |
| NLI@T | 0.673 [0.580, 0.761] | 0.344 [0.156, 0.520] | 0.750 [0.622, 0.868] | 0.745 [0.643, 0.838] |

The paired balanced-accuracy difference, T minus 0.5, is **0.058 [-0.039, 0.153]**. The interval includes zero; this provisional set does not establish improved balanced accuracy. Unsupported-sentence recall is substantially higher at T, at the cost of more unsupported flags on reference-supported sentences.

## Sensitivity to the reference annotator

Against Claude's independent labels, balanced accuracy is 0.633 at 0.5 and 0.670 at T. The paired difference is 0.037 [-0.065, 0.139]; this interval also includes zero. These are alternative references for the same 100 pairs, not another dataset.

## Judge comparison

Mistral execution has ended incomplete: **87/100 readable responses (87% coverage), 13 token-limit failures** after an identical-setting retry recovered five additional pairs. The full-cache guard prevented scoring. No partial-run performance metric or complete v2 judge comparison is reported. Excluding failed pairs could bias a comparison, and another model has not been substituted. The cache hashes, missing IDs, and diagnostic evidence are preserved in `results/checker_judge_v2_completion_audit.json`.

DeepSeek v4.1 Flash is unavailable: NVIDIA returned HTTP 410 and a retirement date of November 16. The original non-streaming Mistral attempts disconnected after 0 and 3 completed pairs. A transport-only SSE probe completed the previously failing fourth pair; the subsequent calls retained the same model, prompt, temperature 0, 4096-token budget, and cache key, with four workers and one shared 1.6-second minimum request interval. [NVIDIA streaming documentation](https://docs.api.nvidia.com/nim/reference/mistralai-mistral-large-4-1t-a52b-infer).

## Numerical boundary audit

The unchanged shared scorer uses default `pandas.read_json`. It decodes four exact-boundary probabilities slightly below T; standard-library JSON and `precise_float=True` preserve the original Parquet values. T itself has not changed. The table above reproduces the shared scorer. With exact source-value decoding, balanced accuracy at T is 0.692 against the provisional AI reference and 0.680 against Claude, compared with 0.673 and 0.670 from the shared reader. This is a numerical sensitivity check, not retuning; Aditya should resolve the loader behavior for the final shared evaluation. See `results/checker_v2_threshold_decoding_audit.json`.

## Second AI reference (B, Claude adjudicator; not human-validated)

Against reference B (49 supported / 51 unsupported), the unchanged shared scorer gives NLI balanced accuracy 0.607 [0.548, 0.673] at 0.5 and 0.679 [0.586, 0.768] at T. The gain is 0.071 [-0.025, 0.166], and unsupported recall goes from 0.235 to 0.745. With exact decoding, NLI@T is 0.699 and the gain is 0.092 [-0.002, 0.187]. The qualitative finding is consistent across these two AI references. Sources: `results/checker_benchmark_v2_claude_adjudicated.json` and `results/checker_v2_claude_adjudicated_uncertainty.json`.

## Interpretation and remaining validation

The frozen high cutoff flags more of the reference-unsupported sentences under either AI reference. The uncertainty in balanced-accuracy gain, unresolved human labels, generator transfer, and numerical boundary issue prevent a final reliability claim. No final pipeline checker recommendation is made from this provisional analysis; [atharva.md](atharva.md) gives only a recall-oriented reading, pending human validation. Human review of the 17 documented AI decisions, an owner-reviewed scoring-precision decision, and team disposition of the incomplete judge comparison are still needed for the original task's final result.

## Reproducibility

- Decisions: `annotation/checker_adjudication_ai_v2.jsonl`; provenance: `results/checker_ai_adjudication_v2_manifest.json`.
- Provisional reference: `annotation/checker_gold_v2_ai_provisional.jsonl`; no `checker_gold_v2.jsonl` has been created.
- NLI: `results/checker_benchmark_v2_ai_provisional.json` and `results/checker_benchmark_v2_claude_reference.json`.
- Uncertainty: `results/checker_provisional_v2_uncertainty.json`, seed 0, 10,000 pair resamples.
- Original benchmark functions ran in scratch directories; shared scripts and set-1 artifacts remain unchanged.
- Helper source snapshots, SHA-256 hashes, and package versions: `results/checker_h4_v2_reproduction.json`. Logs remain under ignored `outputs/h4_v2/`; current streaming status: `outputs/h4_v2/streaming/full_status.json`.
