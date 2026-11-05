# Anirudh: H2/H3, the full attribution run, and the demo

Read [README.md](README.md) first (CARC setup, data bundle, rules, hand-back). You need the NVIDIA API key in `.env` (ask Aditya privately).

## Goal

The project's core experiment at full scale. The midterm pilot ran 41 complaints; this run uses **all 127 in-scope gold complaints**, twice:

- **Retrieved:** Nemotron drafts a response from the retriever's top 5 chunks.
- **Oracle:** the same complaint, drafted from the hand-labelled gold section's chunks.

The NLI checker labels each drafted sentence supported or unsupported. `attribution_pilot.py report` gives, per condition, the share of sentences that are supported and the share that are **supported and about the gold section**, with the paired oracle-minus-retrieved gap and a 10,000-resample bootstrap CI over complaints.

- **H2:** the gap in "supported and gold section" is positive (CI above 0): retrieval errors cost correctness.
- **H3:** the oracle condition still has unsupported sentences: generation errors remain even with the right passage.

Run it for **BM25** first, then for the **best retriever from Ishani's H1** (she tells you its name, e.g. `hybrid_mpnet`).

## What changed since the pilot (so numbers will differ, by design)

- `split_sentences` now also splits on line breaks and drops list markers. 62 of the 83 cached pilot responses contain line breaks, so the pilot merged some sentences. Full-run sentence counts are therefore not comparable one-to-one with the pilot; report the full run as the result.
- The generation cache from the pilot is in the data bundle; the 41 pilot complaints cost no API calls.

## Steps

1. Setup per README; put `NVIDIA_API_KEY=...` in `.env`. Check: `bash carc/check_data.sh` shows the generation cache and pilot runs.
2. `annotation/attribution_ids.txt` (127 ids, committed) lists the items. Regenerate it only to check: `python scripts/attribution_pilot.py select --all` must print 127 items `{'FCRA': 36, 'F': 30, 'E': 29, 'Z': 27, 'V': 5}`.
3. **Generation (login node, tmux, API only):**
   ```bash
   tmux new -s gen
   bash carc/generate.sh bm25
   ```
   About 170 uncached calls at roughly 15 to 30 s each, sequential, so well under the 40 requests/minute limit. If it stops (network, HTTP 429/5xx after retries), just rerun: cached calls are free.
4. **Verification (GPU job):**
   ```bash
   sbatch --export=ALL,RETRIEVER=bm25 carc/verify.sbatch
   ```
   This reruns both conditions with the NLI verifier (cache hits, no API), and writes `results/attribution_full_bm25.json`.
5. **Second retriever** once Ishani names it (example `hybrid_mpnet`):
   ```bash
   sbatch carc/retrieval.sbatch                        # writes outputs/retrieval/hybrid_mpnet/ranked.parquet
   # if the winner used another model (e.g. TAG=bge), copy Ishani's exact sbatch line instead
   bash carc/generate.sh hybrid_mpnet                  # login node, tmux
   sbatch --export=ALL,RETRIEVER=hybrid_mpnet carc/verify.sbatch
   ```
   The oracle run is shared between retrievers (`full-oracle-nli`), so only the retrieved side is new.
6. **Cutoff sensitivity:** when Atharva reports the cutoff tuned on checker set 1 (call it T), relabel without rerunning anything:
   ```bash
   python scripts/attribution_pilot.py report --retrieved full-bm25 --oracle full-oracle-nli --tau T --out results/attribution_full_bm25_tauT.json
   ```
7. Sanity checks:
   - `failed_generations` should be empty or nearly so; list any ids.
   - `n_complaints` = 127 (minus failures).
   - `gold_section_in_retrieved_topk` (gold section among the sections of the top 5 *chunks* the generator saw) must be at most BM25 hit@5 in `results/retrieval_bm25.json` → `with_fcra.in_scope_all`, which counts the top 5 distinct *sections*. If it is higher, stop and tell Aditya.
8. **Hand over** `outputs/pipeline_runs/full-bm25` and `full-oracle-nli` (Drive, `final-experiments/anirudh/`), and tell Atharva: he samples his second checker set from them.

## Demo (after the runs)

`demo/app.py` is yours already. Update it so the page shows the real stages for gold complaints:

- `load_pipeline(generator=NemotronGenerator(), verifier=NLIVerifier(), retriever_kind=..., alpha=...)` (both keyword arguments now exist in `src/cfpb/pipeline/core.py`; use the retriever and alpha Ishani reports). Generation for gold complaints hits the cache, so the demo costs no API calls; for free-text input keep the stub generator unless a key is configured in `.streamlit/secrets.toml` (git-ignored).
- The per-sentence faithfulness report (supported vs flagged) and the retrieved-vs-oracle side-by-side view you built.
- A short notice on the page that the tool assists a compliance officer and does not give legal advice.
Keep the demo runnable on a laptop CPU (the NLI model is slow on CPU; precomputing sentence labels from the full runs and loading them for gold complaints is fine).

## Deliverables

- `results/attribution_full_bm25.json`, `results/attribution_full_<best>.json`, and the `--tau` variants.
- `docs/tasks/results/anirudh.md`: per retriever, a table with supported % and supported-and-gold-section % for retrieved and oracle (micro and macro), the gap with its 95% CI, the gap split by whether retrieval hit the gold section (`gap_by_retrieval_hit`), and by regulation. Then: are H2 and H3 supported, and how does the gap change from BM25 to the better retriever?
- Demo changes on your `exp/anirudh` branch (pull request into `final-experiments`).

## Do not

- Do not change the generator model, prompt, temperature, `k=5`, or the NLI model/threshold in the runs (τ is varied only through `report --tau`).
- Do not run the verifier jobs on the login node.
