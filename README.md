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

Data files are git-ignored. Narratives come from the CFPB FOIA Reading Room archive, because the live API no longer publishes them (see [CLAUDE_PROGRESS.md](CLAUDE_PROGRESS.md) Sec. 3).
