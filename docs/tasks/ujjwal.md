# Ujjwal: ablations (chunking strategy, with and without FCRA)

Read [README.md](README.md) first (CARC setup, data bundle, rules, hand-back).

## Goal

The proposal promised ablations over **chunking strategy** and **retriever type**. Retriever type is Ishani's H1 comparison; you own **chunking** and the **corpus scope** (with or without the FCRA statute). The question: does chunking by regulation structure (Pair B's chunker, the project's design choice) retrieve the gold section better than naive fixed windows, and how sensitive is it to chunk size? All runs are retrieval-only, scored at the section level against the same gold labels, so chunkings with different chunk ids are directly comparable.

## Chunkings to compare

| tag | how it is built | what it tests |
|---|---|---|
| `struct1400` | Pair B's `chunks.jsonl` (structure-aware, max 1,400 characters), the default | baseline |
| `struct700` | `chunking/chunk_regulations.py --max-chars 700` | smaller structure-aware chunks |
| `struct2800` | `chunking/chunk_regulations.py --max-chars 2800` | larger structure-aware chunks (some exceed mpnet's 384-token input) |
| `fixed200` | `scripts/make_fixed_chunks.py --words 200 --stride 150` | fixed word windows that ignore paragraph structure |
| `section` | `scripts/make_fixed_chunks.py --words 0` | one chunk per whole section (embedding sees only the start) |

Caveat for the write-up: `chunk_regulations.py --max-chars` also re-chunks the FCRA statute (for example 539 FCRA chunks at 700 characters vs 325 by default), while `make_fixed_chunks.py` copies the default FCRA chunks unchanged. The without-FCRA numbers isolate the regulation chunking cleanly; use those for the chunking conclusion.

## Steps

1. Setup per README. The FCRA source HTML comes with the data bundle (`data/raw/fcra/`).
2. Build the chunk files (login node, CPU, a minute each):
   ```bash
   python chunking/chunk_regulations.py --max-chars 700  --out chunking/data/processed/chunks_struct700.jsonl
   python chunking/chunk_regulations.py --max-chars 2800 --out chunking/data/processed/chunks_struct2800.jsonl
   python scripts/make_fixed_chunks.py --words 200 --stride 150
   python scripts/make_fixed_chunks.py --words 0
   ```
   Each prints chunk counts; record them. Never overwrite `chunking/data/processed/chunks.jsonl`.
3. Retrieval for each chunking (BM25, dense mpnet and hybrid, with and without FCRA, in one job each):
   ```bash
   sbatch --export=ALL,TAG=struct1400 carc/retrieval.sbatch
   sbatch --export=ALL,CHUNKS=chunking/data/processed/chunks_struct700.jsonl,TAG=struct700 carc/retrieval.sbatch
   sbatch --export=ALL,CHUNKS=chunking/data/processed/chunks_struct2800.jsonl,TAG=struct2800 carc/retrieval.sbatch
   sbatch --export=ALL,CHUNKS=chunking/data/processed/chunks_fixed200_s150.jsonl,TAG=fixed200 carc/retrieval.sbatch
   sbatch --export=ALL,CHUNKS=chunking/data/processed/chunks_section.jsonl,TAG=section carc/retrieval.sbatch
   ```
4. Sanity checks:
   - `struct1400` is the same configuration as Ishani's `mpnet` run: every metric in the two JSON files must agree (only the tag differs). Dense scores can differ in the last decimals across GPUs; if any hit@k differs, stop and tell Aditya.
   - In every file, `all_in_scope.bm25.n` = 127 and `report_half` n is the same across chunkings (same complaints, same split).
   - Every gold section exists in every chunk file (checked when the files were designed; if `run_retrieval.py` reports far lower hit@10 for one chunking, check for missing sections first).
5. Compare. The question is the **difference between chunkings for the same retriever**, so for each pair (struct1400 vs X) compute the paired difference in report-half hit@5 and MRR. `run_retrieval.py` reports paired gains only against BM25 within a run. For the cross-chunking comparison, write a small analysis script under `scripts/analysis/` (your own file) that reads `outputs/retrieval/ranks_<tag>[_no_fcra].parquet` for two tags (one row per gold complaint: `rank_bm25`, `rank_dense`, `rank_hybrid` = rank of the gold section in the full ranking, NaN for NONE items and for gold sections absent from that corpus, e.g. FCRA items without FCRA; plus `dev_half`), keeps in-scope report-half rows (`gold_regulation != "NONE"` and `dev_half == False`), and bootstraps the paired difference over complaints with `paired_gain` from `scripts/run_retrieval.py` (10,000 resamples, seed 0; convert NaN to None first). Do not write a new bootstrap.

## Deliverables

- `results/retrieval_struct1400.json`, `_struct700`, `_struct2800`, `_fixed200`, `_section`, and your comparison output `results/ablation_chunking.json`.
- `scripts/analysis/compare_chunkings.py` (your script).
- `docs/tasks/results/ujjwal.md`: a table (rows: chunkings with their chunk counts; columns: hit@1, hit@5, MRR for BM25, dense and hybrid on the report half, without FCRA) with 95% CIs, the paired difference vs `struct1400` with CIs, and a with-vs-without-FCRA table for `struct1400`. Then: does structure-aware chunking beat fixed windows, does chunk size matter, and does adding the FCRA statute help or hurt retrieval for non-FCRA complaints (`non_fcra_report_half`)?

## Do not

- Do not modify `chunking/chunk_regulations.py`, `scripts/run_retrieval.py` or `src/`: add your own analysis script instead.
- Do not run the generator on the ablation chunkings (out of scope and costs API calls).
