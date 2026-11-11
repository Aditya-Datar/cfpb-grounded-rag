#!/bin/bash
# Attribution run, step 1 (Anirudh): fill the Nemotron response cache. API calls only, no GPU.
# Run on a LOGIN node inside tmux (it takes 1-3 hours at the 40 requests/minute limit and
# survives disconnects):   tmux new -s gen ;  bash carc/generate.sh bm25 ;  Ctrl-b d to detach
# Needs NVIDIA_API_KEY in .env at the repo root (get it from Aditya privately; never commit it).
# Cached calls are free, so re-running after an interruption resumes where it stopped.
set -eo pipefail   # no -u: `module` scripts reference unset variables
source carc/env.sh
R="${1:-bm25}"
IDS="${IDS:-annotation/attribution_ids.txt}"
CORPUS=chunking/data/processed/chunks.jsonl

python scripts/run_pipeline_batch.py --retriever precomputed --ranked "outputs/retrieval/$R/ranked.parquet" \
  --corpus "$CORPUS" --ids "$IDS" --generator nemotron --verifier stub --run-name "gen-$R"
python scripts/run_pipeline_batch.py --retriever oracle --corpus "$CORPUS" --ids "$IDS" \
  --generator nemotron --verifier stub --run-name gen-oracle
echo "cache filled for $R and oracle: now  sbatch --export=ALL,RETRIEVER=$R carc/verify.sbatch"
