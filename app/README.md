# Complaint Review: the officer app

A web application for a compliance officer who answers CFPB consumer complaints. It runs the project's pipeline on each complaint and puts the officer in charge of the result:

- **Inbox.** Every case with its status, the governing section found, how many draft sentences were flagged, and the countdown to the CFPB's 15-day initial-response deadline. Cases can be filtered by status, regulation or owner, and searched.
- **Case page.**
  - **Triage:** product and issue from DistilBERT.
  - **Scope check:** H5, flagging complaints that may fall outside Regulations E, F, V, Z and the FCRA.
  - **Regulation passages:** the top five passages retrieved, linked to the official text, with a warning when they disagree with the product's usual regulation.
  - **Draft response:** Nemotron's draft, with each sentence marked supported or flagged by the NLI checker. Clicking a sentence opens the passage it relies on.
  - **Editing:** the officer edits the draft and chooses which passages each sentence relies on. Saving creates a new version, and every sentence is checked again.
  - **Decisions:** approve or refer. Approving a draft with flagged sentences needs an explicit override and a written justification.
  - **History:** every action is recorded with the officer's name.
- **New complaint.** Paste a complaint, and it is analysed in the background while the page shows each stage.
- **Insights & models.** Workload charts, plus what each model is and how it scored in the project's evaluation.

The tool assists a compliance officer and does not give legal advice; the page says so wherever a decision is made.

## Architecture

```
React + TypeScript (app/frontend, Vite)
        │  JSON over /api
FastAPI (app/backend/main.py) ── worker thread runs analyses one at a time (engine.py)
        │                                   │
Postgres on Neon, schema cfpb_app      src/cfpb pipeline: DistilBERT, BM25 + mpnet,
(cases, analyses, drafts, events)      H5 scope model, Nemotron (NVIDIA API), DeBERTa NLI
```

- **Database:** with `DATABASE_URL` unset, the app uses a local SQLite file at `outputs/app/app.db`.
- **Scope model:** `app/backend/artifacts/scope_model.json` is Gagan's H5 logistic regression, refit by `train_scope.py` to the same numbers: report-half AUROC 0.740, threshold 0.386.
- **Model loading:** models load in the background at startup, and the sidebar shows when they are ready.

## Run it

From the repo root, with the project venv active and the data bundle unzipped:

```bash
pip install -r requirements-classifier.txt -r app/requirements-app.txt
cd app/frontend && npm install && npm run build && cd ../..
python -m app.backend.seed                 # once: loads the 198 gold complaints
uvicorn app.backend.main:app --port 8000   # then open http://localhost:8000
```

For frontend work, run `npm run dev` in `app/frontend` (port 5173, proxies `/api` to 8000) next to uvicorn.

**Settings** go in `.env` at the repo root (git-ignored). They are listed at the top of `app/backend/config.py`:

| Variable | Default | What it does |
|---|---|---|
| `DATABASE_URL` | local SQLite | Neon Postgres URL |
| `NVIDIA_API_KEY` | none | Without it, live drafting is off; seeded drafts still work |
| `CFPB_GENERATOR_MODEL` | `nvidia/nemotron-3.5-super-vl-120b-a12b` | Drafting model. The project's original model was retired by NVIDIA on 2026-10-03 |
| `CFPB_NLI_CUTOFF` | 0.99658203125 | Atharva's cutoff T |
| `CFPB_RETRIEVER` | `hybrid` (alpha 0.8) | The H1 winner: mpnet + BM25. `bm25` or `dense` also work |

## Data in the demo

- **Seeded cases:** `seed.py` creates one case per gold complaint. Complaints a saved pipeline run already drafted come with that draft and its NLI scores, so no API call is needed.
- **Which saved run:** it imports `outputs/pipeline_runs/full-bm25` (Anirudh's full run, on Drive) if present, otherwise the midterm `pilot-bm25`. To switch, rerun `python -m app.backend.seed --reset --run outputs/pipeline_runs/full-bm25`.
- **Received dates:** these are simulated within the last 14 days so the deadlines are live. The real CFPB filing date is shown on each case.

## Timing on a laptop CPU

- **Classifying, retrieval and the scope check:** a second or two.
- **Re-checking an edited draft:** about 30 seconds for 3 to 5 sentences, because the NLI model runs on CPU.
- **Drafting:** up to several minutes per complaint, depending on the NVIDIA queue.
