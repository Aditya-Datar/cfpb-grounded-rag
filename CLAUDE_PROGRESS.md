# CLAUDE_PROGRESS.md: Build Log and Handoff Context

Companion to `CLAUDE.md`. `CLAUDE.md` holds the project's fixed decisions (scope, methods, related work, deliverables) and stays unchanged on `main`. **This file is the living engineering log**: what code exists, what has been run, what we found in the data, and what is blocked. Every Claude session (and every teammate) should read both files before writing code, and **append to the log at the bottom after each iteration**.

---

## 1. Current state (update this section; keep it short)

| Stage | Branch | Status | Owner |
|---|---|---|---|
| 0. Data processing | `data-processing` | Code written and tested; **blocked on narratives** (see Sec. 3) | Aditya |
| 1. Classifier (DistilBERT) | n/a | Not started | Pair A (TBD) |
| 2. Regulation corpus + retrieval | n/a | Not started | Pair B (TBD) |
| 3. Generation + 4. NLI verification | n/a | Not started | Pair C (TBD) |

## 2. Repo layout

```
CLAUDE.md                 project decisions (do not edit on feature branches)
CLAUDE_PROGRESS.md        this file: build log and handoff
requirements.txt          deps; later-stage deps are commented out
.gitignore                ignores *.csv, *.parquet, data/, outputs/, .venv/, models/
src/cfpb/config.py        paths, column map, PRODUCT_TO_REGULATION heuristic, seed (544)
src/cfpb/data/load.py     chunked CSV -> Parquet; optional narrative join on Complaint ID
src/cfpb/data/clean.py    redaction cleaning, redaction density, dedupe hash, filters
src/cfpb/data/profile.py  JSON profile (label counts, narrative coverage, lengths)
src/cfpb/data/split.py    classifier train/val/test; stratified annotation sample
scripts/run_data_pipeline.py   end-to-end stage 0 CLI
tests/test_clean.py       unit tests for cleaning and dedupe
```

### Setup (Windows, Git Bash or PowerShell)

The machine's global Python 3.12 has a broken numpy (the folder has no `__init__.py`), so always use the project venv:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest -q tests
.venv/Scripts/python scripts/run_data_pipeline.py --csv filtered_data.csv
```

On macOS/Linux use `.venv/bin/python`.

### Pipeline outputs (all git-ignored and regenerable)

| File | Contents |
|---|---|
| `data/processed/complaints.parquet` | all rows, 12 kept columns, as strings |
| `outputs/profile_all.json` | profile of every complaint |
| `data/processed/narratives_clean.parquet` | cleaned, filtered, deduped narratives |
| `outputs/profile_narratives.json` | profile of usable narratives |
| `data/processed/{train,val,test}.parquet` | classifier splits, stratified by `product` |
| `data/processed/annotation_sample.csv` | about 30 per regulation, blank gold columns for annotators |

## 3. Data facts (verified by running code on our snapshot)

**Snapshot:** `filtered_data.csv` (2.0 GB, not in git; ask Aditya for a copy). 7,004,226 complaints, `Date received` from 2025-10-01 to 2026-09-30.

Product counts:

| Product | Count | Candidate regulation |
|---|---:|---|
| Credit reporting or other personal consumer reports | 6,360,781 (90.8%) | V |
| Debt collection | 319,850 | F |
| Credit card | 93,490 | Z |
| Checking or savings account | 86,556 | E |
| Money transfer, virtual currency, or money service | 38,548 | E |
| Mortgage | 32,270 | Z |
| Vehicle loan or lease | 24,705 | Z |
| Student loan | 19,590 | Z |
| Payday loan, title loan, personal loan, or advance loan | 17,994 | Z |
| Prepaid card | 6,173 | E |
| Debt or credit management | 4,269 | none |

**BLOCKER: the snapshot has no narrative column.** Its 15 columns are: Date received, Product, Sub-product, Issue, Sub-issue, Company public response, Company, State, ZIP code, Tags, Submitted via, Date sent to company, Company response to consumer, Timely response?, Complaint ID. Both `Consumer complaint narrative` and `Consumer consent provided?` are missing. Without narrative text there is nothing to classify, nothing to use as a retrieval query, and nothing to annotate. The pipeline profiles the structured fields and then stops with a clear message.

Fix options, in order of preference:
1. Re-export from the CFPB bulk CSV (`complaints.csv.zip`, see CLAUDE.md Sec. 4) keeping the narrative column. Filter by date afterwards, not before.
2. If the current bulk file no longer carries narratives (CFPB stopped publishing new ones in August 2026), get previously published ones from the FOIA Reading Room. Save them as a CSV with `Complaint ID` and `Consumer complaint narrative` columns, then run with `--narratives <file>`; `load.py` joins on Complaint ID.
3. Not yet verified: whether narratives for complaints received after August 2026 exist at all. If they do not, the usable window shrinks to roughly Oct 2025 to Aug 2026.

## 4. Design decisions made in code (and why)

- **Redaction cleaning** (`clean.py`): CFPB masks PII as `XXXX` runs and dates as `XX/XX/XXXX`, and wraps amounts in braces like `{$250.00}`. We map these to `[REDACTED]`, `[DATE]`, and `$250.00`, so models see one consistent token instead of X runs of varying length.
- **Filters:** narratives must have at least 20 words and a redaction density of 0.5 or less. Both are CLI flags (`--min-words`, `--max-redaction`) and should be tuned once real narratives are profiled.
- **Dedupe before splitting:** one consumer often files the same narrative against all three credit bureaus (visible in the snapshot as identical rows with different companies). We dedupe on a SHA-1 of the normalized text so copies cannot sit in both train and test.
- **Class cap:** `--max-per-class 20000` (default) keeps credit reporting from swamping fine-tuning. Report macro-F1 as CLAUDE.md requires. Splits are 80/10/10, stratified by `product`. Classes with fewer than 10 rows go to train only.
- **Annotation sample** (`split.annotation_sample`): `PRODUCT_TO_REGULATION` assigns each complaint a *candidate* regulation used only for stratification. It is round-robin across products within a regulation, so Reg Z is not all mortgages, and it excludes the classifier test set. Annotators fill `gold_regulation`, `gold_section`, `gold_paragraph`, `annotator`, `confidence`, and `notes`.
- **Seed:** 544 everywhere (`config.RANDOM_SEED`).

## 5. Open issues and risks for the team

- **Reg V coverage gap (important for annotation).** Most credit-reporting complaints are about bureau dispute investigations, and those duties sit in the FCRA statute (15 U.S.C. 1681i), not in Reg V (12 CFR 1022). Reg V covers narrower ground, such as furnisher accuracy and direct disputes (1022.40 to 1022.43). Many of the 91% credit-reporting complaints may therefore have **no governing section in our four-part corpus**. The rubric needs a "no in-scope section" label, and the team should decide whether to accept this or add FCRA text. *Section numbers here come from general knowledge and are not yet verified against eCFR; check them during corpus parsing.*
- The same applies, to a smaller degree, to mortgages (RESPA / Reg X) and deposit accounts (Reg DD), both outside our scope.
- `PRODUCT_TO_REGULATION` is a product-level heuristic. An issue-level mapping would be more precise (for example, a credit card "unauthorized transaction" complaint is a Reg Z billing-error case, while a debit card one is Reg E). Revisit after the rubric is drafted.
- Interfaces between stages are not frozen yet (CLAUDE.md week 2). Proposed classifier input: `narratives_clean.parquet` columns `complaint_id`, `narrative_clean`, `product`, `issue`.

## 6. Next steps

1. **Unblock narratives** (Sec. 3), then rerun `scripts/run_data_pipeline.py` and paste the narrative profile (count, word-length quantiles, redaction density) into Sec. 3.
2. Pair B: download eCFR XML for Parts 1005, 1026, 1022, 1006; chunk by section; verify the Reg V section numbers above.
3. Draft the annotation rubric, including the "no in-scope section" label.
4. Pair A: DistilBERT on `train.parquet`, label `product` first, `issue` second.

---

## 7. Iteration log (append newest at the bottom)

### 2026-10-06: Stage 0 scaffold (Aditya + Claude)
- Created branch `data-processing` from `main` (958e917).
- Added `.gitignore`, `requirements.txt`, the `src/cfpb` package, `scripts/run_data_pipeline.py`, and `tests/test_clean.py`.
- Profiled `filtered_data.csv`: 7,004,226 rows, 2025-10-01 to 2026-09-30, **no narrative column** (blocker, see Sec. 3).
- Tests: 6 unit tests pass. A synthetic smoke test (3,000 fake narratives) gave splits of 1,760 / 220 / 220 with a cap of 200 per class, and an annotation sample of exactly 30 per regulation, spread across products.
- Found that pandas 3 drops grouping columns from `groupby.apply`; the split code avoids `apply` for that reason.
- Full run on the real snapshot: ingest took about 1 minute, producing `complaints.parquet` (63 MB, down from 2.0 GB CSV). The run stopped as designed at the narrative check (0 narratives).
- Structured profile (`outputs/profile_all.json`):
  - 90 distinct issues.
  - Candidate regulation counts: V 6,360,781; F 319,850; Z 188,049; E 131,277; none 4,269.
  - Submitted via: Web 6,969,322 (99.5%); Phone 15,411; Referral 13,344; Postal mail 6,149.
  - Top issues: "Incorrect information on your report" 3,811,531; "Improper use of your report" 1,306,860; "Problem with a company's investigation into an existing problem" 1,214,505; "Attempts to collect debt not owed" 138,289.
  - The 99.5% web share fits the CFPB's own note (CLAUDE.md Sec. 8) that automated and credit-repair submissions drove the surge.
