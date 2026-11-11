#!/bin/bash
# Attribution run, step 2 (Anirudh): NLI verification on a GPU of responses already in the
# generation cache. Step 1 (carc/generate.sh) must have finished for the same RANKED/run names,
# otherwise this job would call the NVIDIA API from the compute node.
#   sbatch --export=ALL,RETRIEVER=bm25 carc/verify.sbatch
#   sbatch --export=ALL,RETRIEVER=hybrid_mpnet carc/verify.sbatch   # any outputs/retrieval/<name>/ranked.parquet
#SBATCH --job-name=cfpb-verify
#SBATCH --account=CHANGE_ME            # EDIT
#SBATCH --partition=gpu                 # EDIT if needed
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x-%j.out

set -eo pipefail   # no -u: `module` scripts reference unset variables
source carc/env.sh
mkdir -p logs
R="${RETRIEVER:-bm25}"
IDS="${IDS:-annotation/attribution_ids.txt}"
CORPUS=chunking/data/processed/chunks.jsonl

python scripts/run_pipeline_batch.py --retriever precomputed --ranked "outputs/retrieval/$R/ranked.parquet" \
  --corpus "$CORPUS" --ids "$IDS" --generator nemotron --verifier nli --run-name "full-$R"
if [ ! -d outputs/pipeline_runs/full-oracle-nli ]; then
  python scripts/run_pipeline_batch.py --retriever oracle --corpus "$CORPUS" --ids "$IDS" \
    --generator nemotron --verifier nli --run-name full-oracle-nli
fi
python scripts/attribution_pilot.py report --retrieved "full-$R" --oracle full-oracle-nli \
  --out "results/attribution_full_$R.json"
