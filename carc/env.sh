# Sourced by every carc/*.sbatch job (and by you on the login node).
# EDIT the three marked lines once for your CARC account; nothing else should need changing.
#
# USC CARC docs: https://www.carc.usc.edu/user-guides  (check `module avail` / `module spider python`
# on a login node: module names change between software stacks).

module purge
module load gcc/13.3.0 python/3.11.9          # EDIT if `module spider python` shows a different version
export CFPB_REPO="${CFPB_REPO:-$HOME/cfpb-grounded-rag}"   # EDIT: where you unzipped / cloned the repo
export CFPB_VENV="${CFPB_VENV:-/project/$USER/cfpb-venv}"  # EDIT: a /project or /home path with ~5 GB free

# Model downloads go to scratch, not your small home quota.
export HF_HOME="${HF_HOME:-/scratch1/$USER/hf_cache}"
export HF_HUB_DISABLE_SYMLINKS_WARNING=1
export TOKENIZERS_PARALLELISM=false
mkdir -p "$HF_HOME"

if [ -f "$CFPB_VENV/bin/activate" ]; then source "$CFPB_VENV/bin/activate"; else echo "no venv at $CFPB_VENV yet (run carc/setup_env.sh)"; fi
cd "$CFPB_REPO"
