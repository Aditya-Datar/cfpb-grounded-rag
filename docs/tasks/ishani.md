# Ishani: H1, dense and hybrid retrieval

Read [README.md](README.md) first (CARC setup, data bundle, rules, hand-back).

## Goal

Test **H1**: dense (Sentence-BERT) or hybrid (dense plus BM25) retrieval puts the gold regulation section in the top 5 more often than BM25. BM25 is the midterm baseline: on the 127 in-scope gold complaints it found the gold section in the top 5 for well under half of them (see `results/retrieval_bm25.json`).

## What the code does (already written: `src/cfpb/retrieval/dense.py`, `scripts/run_retrieval.py`)

- Embeds the 2,954 chunks of `chunking/data/processed/chunks.jsonl` (field `embed_text`) and each complaint's cleaned narrative with a Sentence-Transformers model, normalised, and ranks chunks by cosine similarity with an exact FAISS index.
- Hybrid: per complaint, min-max normalises the BM25 and dense scores over all chunks and combines them as `alpha * dense + (1 - alpha) * bm25`. `alpha` is chosen from 0.0 to 1.0 in steps of 0.1 by MRR on the **dev half** only.
- Ranks *sections* (each section scored by its best chunk) and reports hit@1/5/10, precision@k and MRR, with 95% bootstrap CIs over complaints, on the **report half** (the headline) and on all in-scope items (reference only), plus the paired gain over BM25 (hit@5 and MRR) with a paired bootstrap CI.
- Runs everything twice: with the FCRA statute chunks and without them (the four-regulation corpus).
- Note: complaints longer than the model's input (384 word pieces for mpnet) are truncated by the encoder. Mention this in the write-up; it is a known limitation, not something to fix now.

## Steps

1. Setup per README. Confirm `python -m pytest -q tests/test_dense_hybrid.py` passes on CARC.
2. Main run (mpnet, the model the chunker was sized for):
   ```bash
   sbatch carc/retrieval.sbatch
   ```
   Takes a few minutes on one GPU. Output: `results/retrieval_mpnet.json`, plus `outputs/retrieval/{bm25,dense,hybrid}_mpnet[_no_fcra]/ranked.parquet` and `outputs/retrieval/features_mpnet[_no_fcra].parquet`.
3. Two more embedding models, so the H1 answer does not hinge on one encoder. These models need a query instruction prefix (from their model cards; check the cards before running):
   ```bash
   sbatch --export=ALL,MODEL=BAAI/bge-base-en-v1.5,PREFIX="Represent this sentence for searching relevant passages: ",TAG=bge carc/retrieval.sbatch
   sbatch --export=ALL,MODEL=intfloat/e5-base-v2,PREFIX="query: ",TAG=e5 carc/retrieval.sbatch
   ```
   e5 also expects `passage: ` before each document. The script embeds chunks without a prefix; note this in the write-up as a small handicap for e5 rather than changing shared code (or ask Aditya to add a `--passage-prefix` option if e5 turns out to matter).
4. Sanity checks before reporting:
   - BM25 is deterministic: in each JSON, the hit@k, precision@k, recall@k and MRR values in `with_fcra.all_in_scope.bm25` must equal `results/retrieval_bm25.json` → `with_fcra.in_scope_all` exactly (same for `without_fcra`; checked on Aditya's machine 2026-11-02). If not, stop and tell Aditya.
   - `n` in `report_half` should be about 60 to 65 (half of 127).
   - Look at `alpha_tuning_dev_mrr`: if the best alpha is 1.0, the hybrid is just the dense retriever on this data. Say so.
5. Pick the **best retriever** by report-half hit@5 (ties: MRR) and tell Anirudh its output folder name (for example `hybrid_mpnet`) so he can run the second attribution condition. He regenerates the same ranking himself with the same command; nothing needs to be copied.

## Deliverables

- `results/retrieval_mpnet.json`, `results/retrieval_bge.json`, `results/retrieval_e5.json`.
- `docs/tasks/results/ishani.md`: one table per corpus variant (with / without FCRA): rows BM25, dense, hybrid for each model; columns hit@1, hit@5, hit@10, MRR on the report half with 95% CIs, and the hit@5 gain over BM25 with its CI. Then: is H1 supported (does the gain's CI exclude 0?), which regulation benefits most (`by_regulation_all`), and the chosen alpha.
- Drive: the `ranked.parquet` of the best retriever (Anirudh can also regenerate it).

## Do not

- Do not tune alpha or pick models on the report half, and do not add models after looking at report-half numbers without saying so in the write-up.
- Do not edit `chunks.jsonl` (that is Ujjwal's ablation, done through separate files).
