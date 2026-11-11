# Final experiments: task handoff (read this first)

This folder hands the compute-heavy final experiments to five teammates. Each person has one file. Point your Claude at **this README plus your own file**: they are written so Claude can do the work on USC CARC without any other context.

| Person | File | Hypothesis / deliverable | Depends on |
|---|---|---|---|
| Ishani | [ishani.md](ishani.md) | H1: dense and hybrid retrieval vs BM25 | nothing |
| Gagan | [gagan.md](gagan.md) | H5: detecting complaints no regulation covers (NONE) | nothing (runs retrieval itself) |
| Anirudh | [anirudh.md](anirudh.md) | H2/H3: full attribution run (retrieved vs oracle); demo update | nothing for BM25; Ishani's best retriever for the second run |
| Atharva | [atharva.md](atharva.md) | H4: checker cutoff, LLM judge, second checker label set | Anirudh's full runs (only for the second label set) |
| Ujjwal | [ujjwal.md](ujjwal.md) | Ablations: chunking strategy, with/without FCRA | nothing |

Aditya keeps the code, the shared evaluation scripts, error analysis and the final report. All the code is already written and tested on branch `final-experiments`; your job is to run it at full scale on CARC, check the outputs, and report them. If something in the code looks wrong, **stop and tell Aditya** rather than patching shared scripts yourself: one owner keeps results comparable.

## Hypotheses (from the midterm report)

- **H1** Dense or hybrid retrieval puts the gold section in the top 5 more often than BM25.
- **H2** Drafts written from the correct (oracle) section are more often supported *and* about the right section than drafts from retrieved passages.
- **H3** Even with the oracle section, a measurable share of sentences is unsupported (a generation-side error).
- **H4** The NLI checker agrees with the adjudicated labels well enough to flag unsupported sentences; if not, an LLM judge does better.
- **H5** Retrieval confidence signals can flag complaints that no regulation in the corpus covers, better than the BM25 top score (AUROC 0.43 at the midterm).

## One-time setup on CARC (everyone)

1. **Code.** On a CARC login node, get branch `final-experiments` into `~/cfpb-grounded-rag`: either `git clone` with your own GitHub access and `git checkout final-experiments`, or download the branch ZIP from GitHub and upload/unzip it. Never put a GitHub token in a shared or committed file.
2. **Data.** Download `cfpb_data_bundle.zip` from the team Drive (Aditya uploads it; built by `scripts/make_data_bundle.py`) and unzip it **at the repo root**. It adds the git-ignored complaint texts, the cached Nemotron responses, the midterm pilot runs and the BM25 rankings.
3. **Edit `carc/env.sh`** (three lines marked `EDIT`): the Python module, the repo path, the venv path. On a login node check `module spider python` and `myaccount`; module names and accounts are per user, so verify them, don't guess.
4. **Edit the `#SBATCH --account` and `--partition` lines** in the `carc/*.sbatch` file you use.
5. `bash carc/setup_env.sh` on the login node: creates the venv, installs CUDA torch and the requirements, pre-downloads the models (compute nodes may not have internet), and runs the test suite (all tests should pass).
6. `bash carc/check_data.sh`: every required file should say `ok`.

Run every command and submit every job **from the repo root** (`cd ~/cfpb-grounded-rag`; log paths are relative). Submit jobs with `sbatch`, watch them with `squeue -u $USER`, read `logs/<job>-<id>.out`. Do not run GPU work on login nodes. The NVIDIA API key (only Anirudh and Atharva need it) is shared privately by Aditya; put it in `.env` at the repo root as `NVIDIA_API_KEY=...`. It is git-ignored: never commit, paste or log it.

## Rules (all tasks)

- **Never edit the gold labels:** `annotation/gold_final.jsonl`, `annotation/checker_gold.jsonl`, `annotation/checker_disagreements.md`. The scripts refuse to overwrite the adjudicated checker file.
- **Never change the generator** (model `nvidia/nemotron-3-super-120b-a12b`, temperature 0, prompt `v1-9d0f038c`) or the NLI model. Changing either invalidates every collected number.
- **Report on the held-out half.** Scripts split items by `cfpb.retrieval.metrics.half(complaint_id)`: half 0 is for tuning (hybrid weight, thresholds), half 1 is for reporting. Do not tune anything on half 1.
- **Only in-scope items** (gold regulation not NONE, 127 of 198) count for retrieval and attribution metrics; NONE items are only for H5.
- Every number you report must come from a results JSON the scripts wrote. Quote confidence intervals; with 60 to 130 items most differences are within noise, and saying so is a valid finding.
- Write findings the way the report does: what was measured, on how many items, what the interval says. No claims beyond the data.

## What to hand back

1. The results JSON files listed in your task file (they are small and go in git under `results/`).
2. A short write-up `docs/tasks/results/<your-name>.md`: a table of the main numbers with 95% CIs, 3 to 6 sentences of interpretation, anything that went wrong, and the exact commands and job IDs you ran.
3. Large or git-ignored outputs (parquet files) your task file names: upload to the team Drive folder `final-experiments/<your-name>/`.

Commit only your results JSON and your write-up, on a branch named `exp/<your-name>` created from `final-experiments`, and open a pull request into `final-experiments`. Do not commit `.env`, data, parquet files or model files (they are git-ignored; check `git status` before committing). Do not edit `CLAUDE.md` or `CLAUDE_PROGRESS.md`; Aditya logs your results there after merging.
