# Atharva: H4 checker reliability results

## Frozen NLI cutoff

The NLI cutoff is frozen at **T = 0.99658203125** as of 2026-11-04, before sampling or inspecting checker label set v2. This is the `best_threshold_in_sample` in `results/checker_benchmark.json`: it maximizes balanced accuracy on the existing 50 adjudicated set-1 pairs. At this cutoff, set 1 has balanced accuracy 0.817, Cohen's kappa 0.638, and unsupported-sentence recall 0.750, compared with 0.625, 0.257, and 0.250 at the original 0.5 cutoff.

The repeated five-fold cross-validation analysis supports fixing a much higher cutoff: its mean held-fold balanced accuracy is 0.776 (5th to 95th percentile 0.737 to 0.798), mean kappa is 0.553, and mean unsupported-sentence recall is 0.745. That cross-validation result estimates whether cutoff tuning helps, but it does not supply one global threshold. Therefore the exact in-sample optimum above is fixed as T, and its honest performance will be measured once on the untouched v2 set. T will not be changed after viewing v2 labels or scores.

## Set 1

The DeepSeek judge completed all 50 set-1 pairs with zero unreadable replies. Results are shown against both the original NLI cutoff and the cutoff frozen above. The optional Mistral judge did not complete: its NVIDIA API run stopped after 23 cached responses with `RemoteDisconnected: Remote end closed connection without response`; one restart reused those responses but stopped again after only three more. Following the task instruction to report one judge if Mistral keeps failing, no Mistral metric is reported.

| Checker | Balanced accuracy | Kappa vs gold | Unsupported recall | AUROC |
|---|---:|---:|---:|---:|
| NLI@0.5 | 0.625 | 0.257 | 0.250 | 0.843 |
| NLI@T (T = 0.99658203125) | 0.817 | 0.638 | 0.750 | 0.843 |
| DeepSeek V4.1 Flash judge | 0.713 | 0.432 | 0.542 | 0.838 |
| Mistral Large 4 judge | not completed | not completed | not completed | not completed |

Relative to NLI@0.5, the DeepSeek judge improved balanced accuracy by 0.088; the paired-bootstrap 95% confidence interval was -0.067 to 0.234. Because this interval includes zero, set 1 does not establish that the DeepSeek judge is more reliable than NLI@0.5. The frozen high-cutoff NLI result is also better than the DeepSeek result on all three thresholded metrics, although that NLI cutoff was selected on set 1 and therefore requires the untouched set-2 evaluation before drawing a final conclusion about H4.

## Set 2

### Input handoff and preparation (2026-11-17)

Anirudh's `full-bm25` and `full-oracle-nli` folders have been received and copied into `outputs/pipeline_runs/`. All ten copied files match the supplied originals by SHA-256. Both runs cover the expected 127 complaint IDs with 127 nonempty responses; the retrieved run has 326 sentence rows and the oracle run has 511. Row counts match the run metadata, sentence keys are unique within each run, every NLI probability is finite and in [0, 1], and every premise chunk resolves in the local corpus. The source did not include the producer's `SHA256SUMS` manifest, so these checks establish local copy integrity, not independent verification against his original upload. The local audit is saved in the git-ignored `outputs/h4_v2/input_manifest.json`.

Both runs identify source commit `e5ac79a-dirty`, generator `nvidia/nemotron-3.5-super-vl-120b-a12b`, prompt `v1-9d0f038c`, temperature 0, and the unchanged DeBERTa NLI model at threshold 0.5. The tracked local passage corpus matches commit `e5ac79a`. The generator differs from set 1, so set 2 will also test transfer of the prespecified cutoff across generators. **T remains 0.99658203125.**

| Source sentence file | SHA-256 |
|---|---|
| `full-bm25/sentences.parquet` | `baee055612cd169222d6f2bdbd42ac4b785f4eb4d055aea02220f9a69322fa74` |
| `full-oracle-nli/sentences.parquet` | `c6e1824d719e893068b910a9cedaa9e181c4aee151742374e95c0c064ec7de74` |

### Frozen sample and approved exclusion correction

Atharva approved an H4-only preparation step on 2026-11-17: exclude every exact set-1 sentence string before sampling, regardless of complaint ID, while leaving shared scripts unchanged. The existing sampler only excludes `(complaint_id, sentence)` tuples; its original 100-pair selection would repeat one set-1 sentence under a different complaint ID. The preparation expands the exclusions to matching tuples in the new runs and passes them as an additional exclusion set to the original `sample()` function. It changes neither the `checker-set-v1_v2` hash ordering nor the source run data. Four matching source rows are excluded before selection, without filtering by checker score or label.

The frozen sample contains **100 pairs, 50 oracle and 50 retrieved**, with zero exact sentence overlap with set 1 and zero duplicate sentence strings within v2. It represents 72 unique complaints, 16 of which also appear in set 1: this is a held-out sentence evaluation, not a disjoint-complaint evaluation. Sample/source hashes, the exact sampler invocation, and the preparation script are recorded in `results/checker_sample_v2_manifest.json`. The unchanged annotation conventions, with only the count and IDs adapted, are in `annotation/checker_prompt_v2.md`. Each independent annotator receives only that prompt and `annotation/checker_set_v2.md` in a fresh isolated session.

Blind annotation, human adjudication, and scoring remain pending. No shared script or set-1 artifact has been changed.

## Commands and job IDs

- 2026-11-05 to 2026-11-06, USC CARC login node in `tmux` session `setup`: ran `python scripts/llm_judge.py --model mistralai/mistral-large-4-1t-a52b` with the same thread limits as the DeepSeek run. The run stopped after 23/50 Mistral responses with `RemoteDisconnected: Remote end closed connection without response`. One restart reused the cache and reached 26/50, then stopped again; the process was confirmed absent with `pgrep` and the cache remained at 76 total files (50 DeepSeek plus 26 Mistral). In accordance with the task's slow/timeout fallback, the incomplete Mistral run is documented but not scored. Job ID: n/a (API-only login-node run in `tmux`).
- 2026-11-05, USC CARC login node in `tmux` session `setup`: ran `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python scripts/llm_judge.py`. The first pass produced 48 cached responses and two unreadable replies; rerunning the identical command retried only those uncached pairs and completed 50/50 with zero unreadable replies. Final output: `results/llm_judge_deepseek-v4.1-flash.json`. Job ID: n/a (API-only login-node run in `tmux`).
- 2026-11-05, local validation after merging `final-experiments` commits `9241f01` and `7e73a60`: confirmed `LLMJudgeVerifier` now uses a 600-second timeout, then reran `.venv/bin/python scripts/llm_judge.py` against the real set-1 cache. K02 completed successfully, as did K03 through K05, advancing the cache from 1/50 to 5/50 without a timeout. The local run was stopped while K06 was in flight so the remaining long run can execute in the required CARC `tmux` environment. The frozen T, judge model, prompt, temperature, token budget, and cache keys are unchanged. Job ID: n/a (local validation).
- 2026-11-04, local setup: installed the team `cfpb_data_bundle`, ran `bash carc/check_data.sh` successfully, then ran `.venv/bin/python scripts/checker_benchmark.py score`. The regenerated `results/checker_benchmark.json` matched the committed file byte-for-byte (SHA-256 `bf1aaeeb62009520be11c7f061a4b4f3297dbd4a16f9f873269bed17df9172a6`). Job ID: n/a (local run).
- 2026-11-04, local setup: `.venv/bin/python scripts/llm_judge.py`. The first DeepSeek set-1 response completed and was cached. The next request exhausted five 180-second attempts and ended with `TimeoutError: The read operation timed out`; no results JSON was written. A keyless endpoint check returned HTTP 405 in 0.62 seconds, confirming that the endpoint itself was reachable. No shared script was changed. Job ID: n/a (local run).
