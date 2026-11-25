# Complaint Review: the officer app

A web application for a compliance officer who answers CFPB consumer complaints. It runs the project's pipeline on each complaint and puts the officer in charge of the result:

- **Inbox.** Every case with its status, the governing section found, how many draft sentences were flagged, and the countdown to the CFPB's 15-day initial-response deadline. Cases can be filtered by status, regulation or owner, and searched.
- **Case page.**
  - **Triage:** product and issue from DistilBERT.
  - **Scope check:** H5, flagging complaints that may fall outside Regulations E, F, V, Z and the FCRA.
  - **Regulation passages:** the top five passages retrieved, linked to the official text, with a warning when they disagree with the product's usual regulation.
  - **Draft response:** Nemotron's draft, with each sentence marked supported or flagged by the checker (mean of DeBERTa NLI and the Nemotron Ultra 550B judge; DeBERTa alone without an NVIDIA key). Clicking a sentence opens the passage it relies on.
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
(cases, analyses, drafts, events)      H5 scope model, Nemotron (NVIDIA API), DeBERTa NLI + Nemotron Ultra judge
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
| `CFPB_CHECKER` | `ensemble` with an NVIDIA key, else `nli` | `ensemble`: mean(DeBERTa NLI, Nemotron Ultra 550B judge) >= `CFPB_ENSEMBLE_CUTOFF`; set-2 balanced accuracy 0.829 vs 0.679 for DeBERTa alone (EXPERIMENT_LOG E12b) |
| `CFPB_ENSEMBLE_CUTOFF` | 0.9737792968749999 | chosen on checker set 1 |
| `CFPB_NLI_CUTOFF` | 0.99658203125 | Atharva's cutoff T, used when `CFPB_CHECKER=nli` |
| `CFPB_RETRIEVER` | `llm` with an NVIDIA key, else `hybrid` | `llm`: Nemotron Embed 8B + BM25 + the classifier's regulation prior, then the reranker (`CFPB_RERANK_MODEL`) with the rubric hints ranks the top 10 sections, and the drafter gets up to 5 passages of the top-ranked section (docs/EXPERIMENT_LOG.md E5, E9). `hybrid` is the H1 winner (mpnet + BM25, alpha 0.8); `bm25` or `dense` also work |
| `CFPB_RERANK_MODEL` | `codex:gpt-5.6-sol` | GPT through the Codex CLI, using the Codex login of the machine running the app (best reranker: top-ranked section correct for 76.9% of held-out complaints vs 63.1% for Super; E9, E16). Any NVIDIA model id, e.g. `nvidia/nemotron-3.5-super-vl-120b-a12b`, uses the NVIDIA API instead. For a deployment, log Codex in with the deployment's own account |
| `CFPB_RERANK_FALLBACK` | Nemotron Super | used if the reranker fails or gives no answer (the case page notes it); `none` to turn off |
| `CFPB_GATING_ROUNDS` | 2 | Verification gating: sentences below the cutoff go back to the drafter to be rewritten from the passage wording, and a rewrite is kept only if the checker scores it higher (E10). 0 turns it off. Rewritten sentences carry a "Rewritten" badge with the original on hover |

## Data in the demo

- **Seeded cases:** `seed.py` creates one case per gold complaint. Complaints a saved pipeline run already drafted come with that draft and its checker scores, labelled at the cutoff of the checker that produced them, so no API call is needed.
- **Which saved run:** it imports `outputs/pipeline_runs/full-bm25` (Anirudh's full run, on Drive) if present, otherwise the midterm `pilot-bm25`. To switch, rerun `python -m app.backend.seed --reset --run outputs/pipeline_runs/full-bm25`.
- **Received dates:** these are simulated within the last 14 days so the deadlines are live. The real CFPB filing date is shown on each case.

## Timing on a laptop CPU

- **Classifying, retrieval and the scope check:** a second or two.
- **Re-checking an edited draft:** about 30 seconds for 3 to 5 sentences, because the NLI model runs on CPU.
- **Drafting:** up to several minutes per complaint, depending on the NVIDIA queue.
- **Checking and rewriting flagged sentences (gating):** about 3.5 minutes per complaint on CPU (up to two rewrite rounds, each re-checked by the checker; Ultra calls run in parallel with DeBERTa).
