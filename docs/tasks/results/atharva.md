# Atharva: H4 checker reliability results

## Frozen NLI cutoff

The NLI cutoff is frozen at **T = 0.99658203125** as of 2026-11-04, before sampling or inspecting checker label set v2. This is the `best_threshold_in_sample` in `results/checker_benchmark.json`: it maximizes balanced accuracy on the existing 50 adjudicated set-1 pairs. At this cutoff, set 1 has balanced accuracy 0.817, Cohen's kappa 0.638, and unsupported-sentence recall 0.750, compared with 0.625, 0.257, and 0.250 at the original 0.5 cutoff.

The repeated five-fold cross-validation analysis supports fixing a much higher cutoff: its mean held-fold balanced accuracy is 0.776 (5th to 95th percentile 0.737 to 0.798), mean kappa is 0.553, and mean unsupported-sentence recall is 0.745. That cross-validation result estimates whether cutoff tuning helps, but it does not supply one global threshold. Therefore the exact in-sample optimum above is fixed as T, and its honest performance will be measured once on the untouched v2 set. T will not be changed after viewing v2 labels or scores.

## Set 1

Pending LLM-judge runs.

## Set 2

Pending Anirudh's `full-bm25` and `full-oracle-nli` runs, blind annotation, adjudication, and scoring.

## Commands and job IDs

- 2026-11-04, local setup: installed the team `cfpb_data_bundle`, ran `bash carc/check_data.sh` successfully, then ran `.venv/bin/python scripts/checker_benchmark.py score`. The regenerated `results/checker_benchmark.json` matched the committed file byte-for-byte (SHA-256 `bf1aaeeb62009520be11c7f061a4b4f3297dbd4a16f9f873269bed17df9172a6`). Job ID: n/a (local run).
- 2026-11-04, local setup: `.venv/bin/python scripts/llm_judge.py`. The first DeepSeek set-1 response completed and was cached. The next request exhausted five 180-second attempts and ended with `TimeoutError: The read operation timed out`; no results JSON was written. A keyless endpoint check returned HTTP 405 in 0.62 seconds, confirming that the endpoint itself was reachable. No shared script was changed. Job ID: n/a (local run).
