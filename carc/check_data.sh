#!/bin/bash
# Checks that the git-ignored data from the team Drive bundle is in place:  bash carc/check_data.sh
cd "${CFPB_REPO:-$(dirname "$0")/..}"
ok=1
for f in data/processed/annotation_sample.csv \
         data/processed/annotation_topup.csv \
         chunking/data/processed/chunks.jsonl \
         annotation/gold_final.jsonl \
         annotation/checker_set.jsonl \
         annotation/checker_gold.jsonl; do
  if [ -s "$f" ]; then echo "ok       $f"; else echo "MISSING  $f"; ok=0; fi
done
for d in outputs/generation/cache outputs/pipeline_runs/pilot-bm25 outputs/pipeline_runs/pilot-oracle; do
  if [ -d "$d" ]; then echo "ok       $d ($(ls "$d" | wc -l) files)"; else echo "optional $d (only needed for attribution/checker tasks)"; fi
done
[ $ok = 1 ] && echo "data OK" || { echo "unzip cfpb_data_bundle.zip at the repo root (see docs/tasks/README.md)"; exit 1; }
