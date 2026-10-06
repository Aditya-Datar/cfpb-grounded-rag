# cfpb-grounded-rag

Regulation-grounded triage and response drafting for CFPB consumer complaints (CSCI 544, Group 36).

- Project decisions: [CLAUDE.md](CLAUDE.md)
- Build log, data findings, and handoff notes: [CLAUDE_PROGRESS.md](CLAUDE_PROGRESS.md) (read this before coding)

## Quick start

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m pytest -q tests
.venv/Scripts/python scripts/run_data_pipeline.py --csv filtered_data.csv
```

Data files are git-ignored; get the snapshot from the team.
