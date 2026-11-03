#!/bin/bash
# H1 (Ishani) and chunking ablation (Ujjwal): dense + hybrid retrieval on a GPU.
#   sbatch carc/retrieval.sbatch                                  # mpnet, with and without FCRA
#   sbatch --export=ALL,MODEL=BAAI/bge-base-en-v1.5,PREFIX="Represent this sentence for searching relevant passages: ",TAG=bge carc/retrieval.sbatch
#   sbatch --export=ALL,CHUNKS=chunking/data/processed/chunks_fixed200_s150.jsonl,TAG=fixed200 carc/retrieval.sbatch
#SBATCH --job-name=cfpb-retrieval
#SBATCH --account=CHANGE_ME            # EDIT: your CARC project account (`myaccount` on a login node)
#SBATCH --partition=gpu                 # EDIT if your account uses another GPU partition
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=logs/%x-%j.out

set -eo pipefail   # no -u: `module` scripts reference unset variables
source carc/env.sh
mkdir -p logs
nvidia-smi --query-gpu=name,memory.total --format=csv

python scripts/run_retrieval.py \
  --model "${MODEL:-sentence-transformers/all-mpnet-base-v2}" \
  --query-prefix "${PREFIX:-}" \
  --chunks "${CHUNKS:-chunking/data/processed/chunks.jsonl}" \
  --tag "${TAG:-mpnet}" \
  --device cuda
