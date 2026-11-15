# Anirudh: H2/H3 full attribution run (BM25)

## Read this first: the generator differs from the frozen one

These runs did **not** use the frozen generator. On 2026-11-13 the frozen model `nvidia/nemotron-3-super-120b-a12b` returned HTTP 404 ("Function ... Not found for account") for a newly created build.nvidia.com key; the model page lists its free endpoint as "Deprecated". The runs below therefore used:

| Setting | Frozen (pilot) | This run |
|---|---|---|
| Model | `nvidia/nemotron-3-super-120b-a12b` | `nvidia/nemotron-3.5-super-vl-120b-a12b` (the API reports `private/nvidia/nemotron-3.5-super-120b-a12b`) |
| `max_tokens` | 4096 | 16384 |
| Request timeout | 180 s | 600 s |
| Temperature, prompt, k | 0, `v1-9d0f038c`, 5 | unchanged |
| NLI model | `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli` | unchanged |

`max_tokens` was raised because the new model reasons longer: in a 3-complaint smoke run at 4096, 1 of 6 calls spent the whole budget on reasoning and returned an empty draft (`finish_reason: length`). At 16384 all 6 smoke calls and all 254 full-run calls finished with `stop`, and no draft is empty.

The edits were made only in the CARC working copy (`src/cfpb/generate/nemotron.py`, uncommitted; `run_info.git_commit` is `e5ac79a-dirty`). Consequences:

- These numbers are not comparable with the midterm pilot, which used the frozen model.
- Atharva's T was tuned on checker set 1, drawn from the frozen model's drafts; applying it here assumes the checker's behaviour transfers across generators.
- If the team prefers to keep the frozen model (for example, if an existing key still reaches it), the whole run must be regenerated; the job scripts below make that a resubmission.

## Setup

All 127 in-scope gold complaints (`annotation/attribution_ids.txt`: FCRA 36, F 30, E 29, Z 27, V 5), each drafted twice: from BM25's top 5 chunks (retrieved) and from the gold section's chunks (oracle). No failed generations in either condition. The gold section was among the sections of the top 5 chunks the generator saw for 26.0% of complaints (`gold_section_in_retrieved_topk` 0.260), below BM25 hit@5 of 0.315 in `results/retrieval_bm25.json` (`with_fcra.in_scope_all`), as required. Nothing was tuned in this task, so all 127 complaints are reported.

Results are given at the run threshold (0.5) and at Atharva's frozen cutoff T = 0.99658203125 (`docs/tasks/results/atharva.md` on `exp/atharva`). Gaps are oracle minus retrieved, paired by complaint, with a 10,000-resample bootstrap 95% CI over complaints.

## Main results

Sources: `results/attribution_full_bm25.json` (threshold 0.5) and `results/attribution_full_bm25_tau0.9966.json` (T).

| Metric | Retrieved @0.5 | Oracle @0.5 | Retrieved @T | Oracle @T |
|---|---:|---:|---:|---:|
| Sentences | 326 | 511 | 326 | 511 |
| Supported, micro | 89.9% | 87.1% | 48.8% | 54.2% |
| Supported, macro | 81.4% | 84.9% | 34.8% | 51.6% |
| Supported and gold section, micro | 18.4% | 87.1% | 9.5% | 54.2% |
| Supported and gold section, macro | 14.5% | 84.9% | 7.3% | 51.6% |

| Gap (oracle minus retrieved) | @0.5 | @T |
|---|---|---|
| Supported | +0.035 [−0.039, 0.111] | +0.168 [0.079, 0.253] |
| Supported and gold section | +0.704 [0.639, 0.766] | +0.442 [0.380, 0.503] |

### Gap in "supported", split by whether retrieval hit the gold section (`gap_by_retrieval_hit`)

| Retrieval | n | Mean gap @0.5 | Mean gap @T |
|---|---:|---:|---:|
| Hit (gold section in top 5) | 33 | −0.044 | −0.032 |
| Miss | 94 | +0.063 | +0.238 |

### By regulation (macro, per-complaint shares)

| Regulation | n | Supported R / O @0.5 | Supported & gold R / O @0.5 | Supported R / O @T | Supported & gold R / O @T |
|---|---:|---|---|---|---|
| FCRA | 36 | 0.950 / 0.862 | 0.232 / 0.862 | 0.522 / 0.397 | 0.090 / 0.397 |
| F | 30 | 0.947 / 0.903 | 0.122 / 0.903 | 0.413 / 0.684 | 0.075 / 0.684 |
| E | 29 | 0.578 / 0.902 | 0.118 / 0.902 | 0.149 / 0.647 | 0.072 / 0.647 |
| Z | 27 | 0.741 / 0.704 | 0.074 / 0.704 | 0.265 / 0.321 | 0.028 / 0.321 |
| V | 5 | 0.800 / 0.910 | 0.200 / 0.910 | 0.300 / 0.650 | 0.200 / 0.650 |

R = retrieved, O = oracle. Per-regulation cells have no CIs; with 27 to 36 complaints (5 for V) they are descriptive only.

## Interpretation

**H2 is supported at both cutoffs.** The gap in "supported and gold section" is +0.70 [0.64, 0.77] at 0.5 and +0.44 [0.38, 0.50] at T. Part of this is by construction: in the oracle condition every passage is from the gold section, so its two oracle columns are identical, while retrieved sentences count only when they cite a gold-section chunk, which BM25 supplied for 26% of complaints.

**Whether retrieval also costs plain support depends on the cutoff.** At 0.5 the "supported" gap is +0.035 with a CI that includes zero; at T it is +0.168 [0.079, 0.253]. At T the gap comes from the 94 complaints where BM25 missed the gold section (mean +0.238), not the 33 hits (−0.032).

**H3 is supported.** With the gold passage, 12.9% of sentences are unsupported at 0.5 and 45.8% at T. The size of this generation-side share depends heavily on the cutoff; T is the better-validated one (balanced accuracy 0.817 on set 1), pending Atharva's set-2 check.

Retrieved drafts are shorter (326 vs 511 sentences). Several smoke-run retrieved drafts were a single sentence saying the passages do not address the complaint; how the checker scores such sentences, and whether they inflate retrieved-side support, has not been checked yet.

## What went wrong

- Frozen generator unreachable with a new key (HTTP 404); switched model as described above.
- `max_tokens` 4096 truncated 1 of 6 smoke drafts to empty with the new model; raised to 16384.
- First setup job failed (exit 127, `module: command not found`) because batch scripts were not login shells; job scripts use `#!/bin/bash -l`.
- No DistilBERT checkpoint is in the data bundle, so the pipeline's classifier ran as the stub (`run_info.classifier: stub`). The attribution report does not use the classifier.
- Generation ran as a CPU batch job instead of tmux on a login node (CARC policy on login-node workloads); compute nodes reached the NVIDIA API (HTTP 200).

## Commands and job IDs

USC CARC Discovery, account `xiangren_1987`. Repo `/project2/xiangren_1987/anirudhj/cfpb-grounded-rag` from a git bundle of `final-experiments` at `e5ac79a` plus `cfpb_data_bundle.zip` (both SHA-256 checked after transfer); venv `/project2/xiangren_1987/anirudhj/cfpb-venv`; python/3.11.9, torch 2.14.1+cu126, transformers 5.19.0, sentence-transformers 6.2.0. Job scripts in `/scratch1/anirudhj/cfpb-grounded-rag/jobs/`.

| Job | Partition, resources | What | Result |
|---|---|---|---|
| 14235921 | main, 8 CPU, 16G | `bash carc/setup_env.sh` | FAILED 127 (`module` not found) |
| 14235930 | main, 8 CPU, 16G | `bash carc/setup_env.sh; bash carc/check_data.sh` | COMPLETED 0:0; 127 passed, 1 skipped; data OK |
| 14236036 | main, 2 CPU, 8G | smoke: 3 ids, both conditions, `max_tokens` 4096 | COMPLETED; 1/6 drafts empty |
| 14236096 | main, 2 CPU, 8G | smoke: same, `max_tokens` 16384 | COMPLETED; 6/6 `stop` |
| 14236106 | main, 2 CPU, 8G, 12 h | `bash carc/generate.sh bm25` | COMPLETED 0:0, 1 h 08 min |
| 14236107 | gpu, 1 GPU, 4 CPU, 24G, 2 h; `afterok:14236106` | `sbatch --export=ALL,RETRIEVER=bm25 carc/verify.sbatch` | COMPLETED 0:0; wrote `results/attribution_full_bm25.json` |
| 14236571 | debug, 2 CPU, 8G (srun) | `python scripts/attribution_pilot.py report --retrieved full-bm25 --oracle full-oracle-nli --tau 0.99658203125 --out results/attribution_full_bm25_tau0.9966.json` | OK |

No `NameError` or traceback appears in any job log. `outputs/pipeline_runs/full-bm25` and `full-oracle-nli` go to Drive `final-experiments/anirudh/` with a `SHA256SUMS` file.

## Pending

- Second retriever (Ishani's H1 winner): rerun the retrieved side only; `full-oracle-nli` is shared.
- Team decision on the generator switch.
- Demo update.
