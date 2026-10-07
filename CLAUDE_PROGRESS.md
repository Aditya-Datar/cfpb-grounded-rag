# CLAUDE_PROGRESS.md: Build Log and Handoff Context

Companion to `CLAUDE.md`. `CLAUDE.md` holds the project's fixed decisions (scope, methods, related work, deliverables) and stays unchanged on `main`. **This file is the living engineering log**: what code exists, what has been run, what we found in the data, and what is blocked. Every Claude session (and every teammate) should read both files before writing code, and **append to the log at the bottom after each iteration**.

---

## 1. Current state (update this section; keep it short)

| Stage | Branch | Status | Owner |
|---|---|---|---|
| 0. Data processing | `data-processing` | Code written and tested; narrative source found (FOIA archive, Sec. 3); archive not yet downloaded | Aditya |
| 1. Classifier (DistilBERT) | n/a | Not started | Pair A (TBD) |
| 2. Regulation corpus + retrieval | n/a | Not started | Pair B (TBD) |
| 3. Generation + 4. NLI verification | n/a | Not started | Pair C (TBD) |

## 2. Repo layout

```
CLAUDE.md                 project decisions (do not edit on feature branches)
CLAUDE_PROGRESS.md        this file: build log and handoff
requirements.txt          deps; later-stage deps are commented out
.gitignore                ignores *.csv, *.parquet, data/, outputs/, .venv/, models/
src/cfpb/config.py        paths, column map, PRODUCT_TO_REGULATION heuristic, seed (544),
                          date window, FOIA archive file list
src/cfpb/data/load.py     chunked .csv/.zip exports -> one Parquet, filtered by Date received
src/cfpb/data/clean.py    redaction cleaning, redaction density, dedupe hash, filters
src/cfpb/data/profile.py  JSON profile (label counts, narrative coverage, lengths)
src/cfpb/data/split.py    classifier train/val/test; stratified annotation sample
scripts/fetch_narrative_archive.py   downloads the 10 FOIA archive zips (~365 MB)
scripts/run_data_pipeline.py   end-to-end stage 0 CLI
tests/test_clean.py       unit tests for cleaning and dedupe
```

### Setup (Windows, Git Bash or PowerShell)

The machine's global Python 3.12 has a broken numpy (the folder has no `__init__.py`), so always use the project venv:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest -q tests
.venv/Scripts/python scripts/fetch_narrative_archive.py
.venv/Scripts/python scripts/run_data_pipeline.py
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

## 3. Data facts (verified)

### Where narratives come from (read this first)

- **The live CFPB data has no narratives.** On 2026-08-14 the CFPB stopped publishing complaint narratives. We checked on 2026-10-06: the search API returns no narrative field for any date range, even 2023, with or without `has_narrative=true`. The bulk `complaints.csv.zip` (last modified 2026-10-06) has only 15 columns, with no `Consumer complaint narrative`. **Do not try to re-download from the API or bulk file**; it cannot fix this.
- **Narratives live in the FOIA Reading Room archive:** https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/ . It holds 21 zipped CSV exports covering complaints received 2011-12-01 to 2026-08-14. Each has 16 columns, including `Consumer complaint narrative`. Many rows still have an empty narrative, because only consumers who opted in had theirs published.
- We use exports 12 to 21 (July 2025 to Aug 2026), about 365 MB zipped; the list is in `config.ARCHIVE_FILES`. `scripts/fetch_narrative_archive.py` downloads them to `data/raw/foia_archive/`.
- **Project window: 2025-08-14 to 2026-08-14 inclusive** (`config.DATE_MIN`, `DATE_MAX`; team decision 2026-10-06). It is one full year ending on the last day narratives exist. Complaints received after 2026-08-14 have no public narrative anywhere.
- Archive exports may overlap, so the pipeline drops duplicate `complaint_id`s.
- The archive files do not include `Consumer consent provided?`.

### Structured profile of the live data (earlier snapshot, now deleted)

`filtered_data.csv` was the bulk file filtered to 2025-10-01 to 2026-09-30: 7,004,226 complaints, 15 columns, no narratives. Its derived `data/processed/complaints.parquet` may still be on Aditya's machine; the next pipeline run overwrites it. Product counts:

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

The narrative subset will be much smaller and may have a different product mix; profile it once the archive is downloaded.

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

1. Run `scripts/fetch_narrative_archive.py` and then `scripts/run_data_pipeline.py`. Paste the narrative profile (count, product mix, word-length quantiles, redaction density) into Sec. 3, and check that each regulation has enough narratives for 30 gold pairs.
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

### 2026-10-06: Narrative source found (Aditya + Claude)
- Confirmed that the live API and bulk file have no narratives for any period (checked 2023, 2025, and 2026 ranges), so a fresh download cannot fix the gap. Deleted `filtered_data.csv`. Wrote an API downloader, then deleted it uncommitted, since it could only reproduce the same data.
- API facts recorded for future reference: the CDN returns 403 without an `Accept` header, the maximum `size` is 100,000 (100,001 returns 400), and parallel requests get 429.
- Found the FOIA Reading Room narratives archive (Sec. 3). Previewed the header of export 21: 16 columns, including `Consumer complaint narrative`.
- Replaced `load.csv_to_parquet` and the `--narratives` side-join with `load.exports_to_parquet`, which takes several .csv/.zip files and filters by date. The pipeline now reads the archive by default (`--inputs` overrides it) and dedupes on `complaint_id`.
- Added `scripts/fetch_narrative_archive.py` and the archive file list in config.
- Tested on a synthetic zip: both date bounds are inclusive, out-of-window rows are dropped, and quoted narratives containing commas parse correctly. All 6 unit tests pass. The real archive is not downloaded yet.

### 2026-10-06: Window moved to 2025-08-14 to 2026-08-14
- Team decision: use one full year ending on the last narrative date, instead of Oct 2025 to Oct 2026, whose last 1.5 months have no text.
- Added export 12 (July to Aug 2025, 84.2 MB) to `ARCHIVE_FILES`; the total download is now 10 files, about 365 MB.
