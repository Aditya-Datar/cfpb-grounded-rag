#!/bin/bash
# One-time setup on a CARC LOGIN node (needs internet):  bash carc/setup_env.sh
# Creates the venv, installs requirements with a CUDA build of torch, and pre-downloads
# the models so GPU jobs work even if compute nodes have no outbound internet.
set -eo pipefail   # no -u: `module` scripts reference unset variables
source carc/env.sh                         # modules, CFPB_REPO, CFPB_VENV (edit them there first)
python -m venv "$CFPB_VENV"
source "$CFPB_VENV/bin/activate"
mkdir -p logs   # Slurm needs this folder to exist before any sbatch

pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt

python - <<'EOF'
from huggingface_hub import snapshot_download
for m in ["sentence-transformers/all-mpnet-base-v2",
          "BAAI/bge-base-en-v1.5",
          "intfloat/e5-base-v2",
          "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"]:
    print("downloading", m); snapshot_download(m)
EOF
python -m pytest -q
echo "setup done: now run carc/check_data.sh"
