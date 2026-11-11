# cfpb-grounded-rag

Regulation-grounded triage and response drafting for CFPB consumer complaints (CSCI 544, Group 36).

- Project decisions: [CLAUDE.md](CLAUDE.md)
- Build log, data findings, and handoff notes: [CLAUDE_PROGRESS.md](CLAUDE_PROGRESS.md) (read this before coding)

## Quick start

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m pytest -q tests
.venv/Scripts/python scripts/fetch_narrative_archive.py   # CFPB FOIA narrative archive, ~365 MB
.venv/Scripts/python scripts/run_data_pipeline.py
```

**Classifier (stage 1):** run [notebooks/train_classifier_colab.ipynb](notebooks/train_classifier_colab.ipynb) on a Colab GPU, or locally `python scripts/train_classifier.py --label product` after `pip install -r requirements-classifier.txt`.

Data files are git-ignored. Narratives come from the CFPB FOIA Reading Room archive, because the live API no longer publishes them (see [CLAUDE_PROGRESS.md](CLAUDE_PROGRESS.md) Sec. 3).

**Backend pipeline and demo:** `pip install -r requirements-demo.txt`, then

```bash
python scripts/build_reg_corpus.py --date 2026-10-13          # regulation corpus (once)
python scripts/analyze_complaint.py --text "My bank denied my unauthorized-transfer claim ..."
python scripts/run_pipeline_batch.py --retriever oracle       # gold-set complaints -> outputs/pipeline_runs/
python scripts/run_pipeline_batch.py --retriever precomputed --ranked outputs/retrieval/bm25/ranked.parquet \
    --corpus chunking/data/processed/chunks.jsonl data/processed/reg_chunks.parquet::statute
streamlit run demo/app.py
```

The pipeline (`src/cfpb/pipeline/`) uses the trained classifier when `outputs/classifier/{product,issue}/best/` and `run_info.json` are present (from Drive `Dataset/outputs/classifier/`). Stages not built yet run as labelled stubs. Put any LLM API key in `.env` or `.streamlit/secrets.toml`; both are git-ignored.

