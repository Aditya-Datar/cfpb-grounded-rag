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
# torch 2.14.1 (CUDA 12.6 build): transformers 5.x needs torch >= 2.6 (it calls torch.accelerator),
# and the cu121 index stops at 2.5.1. Same torch version as the tested laptop setup.
pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt   # pins transformers and sentence-transformers to the tested versions

# The tests never load a real model, so check the stack imports here: fail now, not inside a GPU job.
python - <<'EOF'
import torch, transformers, sentence_transformers
from transformers.utils import is_torch_available
assert is_torch_available(), f"transformers {transformers.__version__} disabled torch {torch.__version__}"
from sentence_transformers import SentenceTransformer  # noqa: F401  (raised NameError 'nn' when broken)
print("torch", torch.__version__, "| transformers", transformers.__version__,
      "| sentence-transformers", sentence_transformers.__version__, "| CUDA build", torch.version.cuda)
EOF

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
