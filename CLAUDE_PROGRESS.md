# CLAUDE_PROGRESS.md: Build Log and Handoff Context

Companion to `CLAUDE.md`. `CLAUDE.md` holds the project's fixed decisions (scope, methods, related work, deliverables, rules for graded work). **This file is the living engineering log**: what code exists, what has been run, what we found in the data, and what comes next. Last updated 2026-10-14 (branch `chunking`, commit after `a96a752`).

---

## 0. Start here (new teammate or new Claude session)

**If you are Claude:** read `CLAUDE.md` fully, then this whole file, before writing code. Claude Code auto-loads only `CLAUDE.md`, so a teammate must say "read CLAUDE_PROGRESS.md" at the start of each session (or add `@CLAUDE_PROGRESS.md` to `CLAUDE.md` once the team agrees to edit it).

**Get the code and data (about 15 minutes, no GPU):**

```bash
git clone https://github.com/Aditya-Datar/cfpb-grounded-rag.git
cd cfpb-grounded-rag
git checkout data-processing          # not merged to main yet; this file only exists here
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m pytest -q tests                   # expect: 6 passed
.venv/Scripts/python scripts/fetch_narrative_archive.py   # ~365 MB from files.consumerfinance.gov
.venv/Scripts/python scripts/run_data_pipeline.py         # ~5 min; writes data/processed/ and outputs/
```

Data files are git-ignored, so every member regenerates them locally. Check your run against Sec. 3: you should get 276,378 usable narratives, and `scripts/check_splits.py` must print "All splits match". Splits are hash-based, so they are identical across machines; rebuilding under pandas 2.2.3 and 3.0.6 gives the same rows and text (verified 2026-10-10).

**Working rules for this repo:**
1. **One branch per stage**, cut from `data-processing` until it is merged to `main`, then from `main`. Suggested names: `classifier`, `retrieval`, `generation-verification`.
2. **Do not edit `CLAUDE.md`** on feature branches; it records team decisions. Put engineering facts here.
3. **After every work session, update this file:** refresh Sec. 1 (status) and append a dated entry to Sec. 7 (what changed, what was run, the exact numbers, what broke).
4. **Numbers in this file must come from a run or a primary source.** Mark anything unverified as *unverified*. Never paste in numbers estimated by an LLM.
5. Never commit data, model weights, or API keys (`.gitignore` already covers data and models).
6. Paper Review Reports are individual graded work (CLAUDE.md Sec. 7): coach and check, do not ghostwrite.

## 1. Current state

| Stage | Pair | Branch | Status |
|---|---|---|---|
| 0. Data: download, profile, clean, split | A | `data-processing` (pushed, PR not opened) | **Done (v1).** See Sec. 3 |
| 1. Classifier: DistilBERT, macro-F1 | A | `classifier` (pushed) | **v1 results are STALE (trained on buggy cleaning and old splits). Retrain on v2 data.** v1 for reference: product test macro-F1 0.798, issue test macro-F1 0.297 (Sec. 7) |
| 2. Regulation corpus and retrieval | B | `chunking` (pushed) | **Parsing and chunking done for regulation text in all four parts** (2,104 chunks). After Ujjwal's parser fix (`232a564`), 5 of 5,006 paragraph paths still disagree with eCFR (all in 1026.19). Supplement I and appendices not chunked. Embedding model not chosen. Retrieval (FAISS, BM25) not started. See Sec. 7, 2026-10-14 (parser fix entry) |
| 3. Generation and 4. NLI verification | C | not created | Not started |
| Annotation rubric and 120 gold pairs | all | n/a | Sample ready; procedure and LLM cross-check prompts drafted in `annotation/ANNOTATION_GUIDE.md`; **rubric decisions TBD, 0 items labeled** |

**Pair A overall:** the data side is complete and the classifier code is ready. Remaining: the GPU training runs, test-set numbers, and freezing the output interface with the team.

**Open team decisions** (from CLAUDE.md Sec. 6, still undecided): who is in each pair, the single target LLM, the owner of the repo and shared evaluation script, and who drafts the rubric.

## 2. Repo layout

```
CLAUDE.md                            project decisions (do not edit on feature branches)
CLAUDE_PROGRESS.md                   this file
README.md                            short quick start
requirements.txt                     deps; later-stage deps are listed but commented out
.gitignore                           ignores *.csv, *.parquet, /data/, /outputs/, .venv/, models/, .idea/
src/cfpb/config.py                   paths, column map, PRODUCT_TO_REGULATION, seed 544,
                                     date window, FOIA archive file list
src/cfpb/data/load.py                .csv/.zip exports -> one Parquet, filtered by Date received
src/cfpb/data/clean.py               redaction cleaning, redaction density, text hash, filters
src/cfpb/data/profile.py             JSON profile (label counts, narrative coverage, lengths)
src/cfpb/data/split.py               classifier train/val/test; stratified annotation sample
scripts/fetch_narrative_archive.py   downloads the 10 FOIA archive zips
scripts/run_data_pipeline.py         end-to-end stage 0 CLI (flags: --inputs, --date-min,
                                     --date-max, --min-words, --max-redaction,
                                     --max-per-class, --per-regulation, --skip-ingest)
src/cfpb/classify/data.py           tokenization (head+tail truncation), length-bucketed batches
src/cfpb/classify/train.py          plain-PyTorch fine-tuning loop, evaluation, reports, resume
scripts/train_classifier.py         stage 1 CLI (--label product|issue, --resume, --max-train ...)
scripts/check_splits.py             verifies local splits match data_fingerprint.json
data_fingerprint.json               SHA-1 of sorted complaint_ids per split (team reference)
notebooks/train_classifier_colab.ipynb   step-by-step Colab runner (fresh-session safe)
requirements-classifier.txt         torch, transformers, matplotlib on top of requirements.txt
tests/test_clean.py                  unit tests for cleaning and dedupe
tests/test_classify_data.py         unit tests for truncation, batching, padding
```

New stages should follow the same pattern: library code in `src/cfpb/<stage>/`, a runnable script in `scripts/`, and tests in `tests/`. Scripts add `src/` to `sys.path`, so no package install is needed.

**Environment used for v1:** Windows 11, Python 3.12.2, pandas 3.0.6, pyarrow 25.0.1, scikit-learn 1.9.1, numpy 2.5.3. pandas 3 removes grouping columns from `groupby.apply`, so avoid that pattern. On Aditya's machine the global Python's numpy is broken, which is why we always use `.venv`.

### Output files (git-ignored, regenerable)

| File | Rows | Contents |
|---|---:|---|
| `data/raw/foia_archive/*.zip` + `download_log.json` | | raw archive exports and download date |
| `data/processed/complaints.parquet` | 6,809,200 | every complaint in the window, 12 columns, all strings |
| `data/processed/narratives_clean.parquet` | 276,378 | usable narratives (schema below) |
| `data/processed/train.parquet` / `val.parquet` / `test.parquet` | 111,527 / 14,022 / 13,905 | classifier splits (schema below) |
| `data/processed/annotation_sample.csv` | 120 | gold-annotation sheet |
| `outputs/profile_all.json`, `outputs/profile_narratives.json` | | profiles |
| `outputs/pipeline_run.log` | | last pipeline run log |

**Schema of `narratives_clean` and the splits** (all strings except where noted): `complaint_id`, `date_received`, `product`, `sub_product`, `issue`, `sub_issue`, `company`, `state`, `submitted_via`, `company_response`, `timely_response`, `narrative` (raw), `narrative_clean` (**use this as model input**), `n_words` (int), `redaction_density` (float), `text_hash`.

**Schema of `annotation_sample.csv`:** `complaint_id`, `regulation_candidate` (E/F/V/Z heuristic, not gold), `product`, `sub_product`, `issue`, `sub_issue`, `company`, `narrative_clean`, plus blank columns for annotators: `gold_regulation`, `gold_section`, `gold_paragraph`, `annotator`, `confidence`, `notes`.

## 3. Data facts (verified)

### Where narratives come from (read this first)

- **The live CFPB data has no narratives.** On 2026-08-14 the CFPB stopped publishing complaint narratives. We checked on 2026-10-06: the search API returns no narrative field for any date range, even 2023, with or without `has_narrative=true`. The bulk `complaints.csv.zip` has only 15 columns, with no `Consumer complaint narrative`. **Do not re-download from the API or bulk file; it cannot fix this.**
- **Narratives live in the FOIA Reading Room archive:** https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/ . It holds 21 zipped CSV exports covering complaints received 2011-12-01 to 2026-08-14, each with 16 columns including `Consumer complaint narrative`. Most rows have an empty narrative, because publication required the consumer's opt-in.
- We use exports 12 to 21 (`config.ARCHIVE_FILES`). Exports 1 to 11 give earlier history if it is ever needed.
- **Project window: 2025-08-14 to 2026-08-14 inclusive** (`config.DATE_MIN`, `DATE_MAX`; team decision 2026-10-06): one full year ending on the last day narratives exist.
- Archive exports may overlap, so the pipeline drops duplicate `complaint_id`s. The archive has no `Consumer consent provided?` column.
- When citing the data in the report: "CFPB Consumer Complaint Database narratives archive (FOIA Reading Room), exports 12 to 21, downloaded 2026-10-07 UTC."

### Narrative dataset, v2 (cleaner fix + hash splits, pipeline run 2026-10-10; v1 numbers are in the Sec. 7 log)

All 10 zips pass the zip integrity test and share one 16-column header.

| Step | Count |
|---|---:|
| Complaints received 2025-08-14 to 2026-08-14 (deduped on `complaint_id`) | 6,809,200 |
| With a non-empty narrative | 469,659 (6.9%) |
| Usable after cleaning (at least 20 words, redaction density 0.5 or less, exact-text dedupe) | 276,378 |
| Classifier splits (`product`, at most 20k per class before splitting, hash-based ~80/10/10) | train 111,527 / val 14,022 / test 13,905 |
| Annotation sample | 120 (30 each for E, F, V, Z) |

Usable narratives by product. They are **far less skewed** than all complaints: credit reporting is 90% of complaints but only 33% of usable narratives.

| Product | All complaints | Usable narratives | In `train` | Candidate regulation |
|---|---:|---:|---:|---|
| Credit reporting or other personal consumer reports | 6,152,294 | 89,993 | 15,971 | V |
| Debt collection | 332,548 | 55,465 | 15,966 | F |
| Checking or savings account | 86,182 | 36,606 | 16,024 | E |
| Credit card | 95,747 | 34,860 | 15,972 | Z |
| Money transfer, virtual currency, or money service | 38,283 | 17,602 | 14,153 | E |
| Mortgage | 31,772 | 13,000 | 10,358 | Z |
| Vehicle loan or lease | 24,594 | 10,275 | 8,241 | Z |
| Payday loan, title loan, personal loan, or advance loan | 17,440 | 7,362 | 5,878 | Z |
| Student loan | 19,671 | 6,617 | 5,279 | Z |
| Prepaid card | 6,311 | 2,785 | 2,235 | E |
| Debt or credit management | 4,358 | 1,813 | 1,450 | none |

In this window, all complaints by candidate regulation: V 6,152,294; F 332,548; Z 189,224; E 130,776; none 4,358. Usable narratives by candidate regulation: V 89,993; Z 72,114; E 56,993; F 55,465.

- **Classifier labels:** 11 products; 88 distinct issues in `train` (89 in v1). Class sizes in `train` range from 16,024 down to 1,450, so report macro-F1.
- **Narrative length** (words, after cleaning): median 175, IQR 93 to 285, mean 229, max 6,089. DistilBERT's 512-token limit will truncate roughly the longest quarter (*estimate: tokens per word not measured*); consider head plus tail truncation.
- **Redaction density:** median 0.028, 75th percentile 0.051. Most narratives are lightly masked.
- **Annotation sample mix:** E has 10 each of checking/savings, money transfer, and prepaid; F has 30 debt collection; V has 30 credit reporting; Z has 6 each of credit card, payday/personal loan, student loan, mortgage, and vehicle. It excludes the classifier test set. The v2 sample shares 119 of 120 complaints with what the hash method gives on v1 data, but **0 of 120 with the original v1 file**, which used the old shuffle. Nobody had annotated yet.
- **Data-quality observation (prevalence NOT yet measured):** the first sampled debt-collection narrative reads like a credit-repair template, a formal letter citing the FDCPA, FCRA, and Indiana law. Given the CFPB's note about credit-repair and automated submissions (CLAUDE.md Sec. 8), such templates may be common. Measure this before claiming it, for example by counting near-duplicate texts or statute mentions. Template letters cite statutes by name, which may make retrieval look easier than it is on organic complaints, so template vs organic is a candidate error-analysis slice.

## 4. Design decisions made in code (and why)

- **Redaction cleaning** (`clean.py`): CFPB masks PII as runs of `XXXX`, masks dates in several forms (`XX/XX/XXXX`, `XX/XX/2025`, `XX/XX/year>`, `XX/XX/scrub>/25`, `XX/2024`), and braces amounts (`{$250.00}`, `{>= $9,999,999}`, sometimes unclosed). We map these to `[DATE]`, `[REDACTED]`, and `$250.00`, padding with a space when a mask is glued to a word. The full list of formats is in the `clean.py` docstring and covered by tests. Residue on all 469,659 narratives: 0 with `year>`, `scrub>`, braced `$`, or lowercase `xxxx`; 10 with real words containing XX (DOXXING, EXXON, XXXVI); about 250 with `[REDACTED]/2023`, where the mask may be a month name and is left alone.
- **Filters:** narratives need at least 20 words and a redaction density of 0.5 or less (`--min-words`, `--max-redaction`). Defaults were not tuned. Given the profile above, the redaction filter removes very little.
- **Dedupe before splitting:** consumers often file the same narrative against several companies (for example, all three credit bureaus). We dedupe on a SHA-1 of normalized text so copies cannot sit in both train and test. Near-duplicates (for example, templates with different names) are **not** caught.
- **Splits are hash-based (since 2026-10-10):** each complaint's split, cap rank, and annotation rank come from SHA-1 of (seed, purpose, complaint_id), not from shuffling the table. Adding or removing rows never moves other complaints. Proportions per class are about 80/10/10, not exact. `--max-per-class 20000` keeps the lowest-hash rows per product. Classes with fewer than 10 rows go to train only (none at present). *Why:* with the old table-wide shuffle, the cleaner fix (248 fewer rows) moved 93% of the test set; with hashing it moves about 0.1%.
- **Annotation sample:** `PRODUCT_TO_REGULATION` assigns a *candidate* regulation used only for stratification. Sampling is round-robin across products within each regulation, and the sample is disjoint from the classifier test set.
- **Seed:** 544 everywhere (`config.RANDOM_SEED`); it salts the split hashes.
- **`check_splits.py` hashes ids and text:** `data_fingerprint.json` stores per split a hash of the sorted ids **and** a hash of `narrative_clean`, so files made by an older cleaner, with the same rows but different text, fail the check. Verified: the v1 files are rejected against the v2 reference.

## 5. Open issues and risks

- **Reg V coverage gap (important for annotation).** Most credit-reporting complaints concern bureau dispute investigations. Those duties sit in the FCRA statute (15 U.S.C. 1681i), not in Reg V (12 CFR 1022), which covers narrower ground such as furnisher accuracy and direct disputes. Credit reporting is 33% of usable narratives, so many may have **no governing section in our four-part corpus**. The rubric needs a "no in-scope section" label; the team decides whether to accept that or add FCRA text. *Section numbers here are unverified; check them against eCFR during corpus parsing.*
- The same applies, to a smaller degree, to mortgages (RESPA / Reg X) and deposit accounts (Reg DD), both out of scope.
- `PRODUCT_TO_REGULATION` works at product level. An issue-level mapping would be more precise: an unauthorized credit card charge falls under Reg Z billing errors, while the same problem on a debit card falls under Reg E. Revisit with the rubric.
- **Stage interfaces are not frozen** (CLAUDE.md week 2 milestone). Proposals are in Sec. 6. Agree them before Pairs B and C build against stubs.
- **Proposal vs implementation (explain in the final report).** The submitted proposal (`GROUP 36_PROJECT PROPOSAL.pdf`, not in repo) differs from what we built in three ways:
  - It says the ~120 gold pairs "reflect the real distribution across the four regulations". We follow CLAUDE.md Sec. 4 instead: stratified, 30 per regulation, because natural frequency would leave E, Z, and F with too few cases.
  - It says "two independent annotators". CLAUDE.md has all six annotate with overlap. Either way, agreement gets reported.
  - It assumes a snapshot of the live CFPB database. We had to use the FOIA narratives archive, because narratives were withdrawn on 2026-08-14 (Sec. 3).
- **Jev (TypeSafe AI) research, 2026-10-07; CLAUDE.md Sec. 9 still governs: optional extra verifier only, never a dependency.**
  - *What it is:* a "decision model" with no text generation. It returns typed answers (choice, rubric score, or yes/no) with calibrated probabilities. Released in early access 2026-09-15.
  - *Access:* an OpenRouter blog post says it can be called via `https://openrouter.ai/api/alpha/decisions` with model `typesafe/jev-1.13`. Price is $0.042 per million input tokens, output is free, and the context is about 32k tokens. **Unverified:** the OpenRouter model pages returned 404 on 2026-10-07, so test a real call before relying on it.
  - *Limits it states:* no explanations, no arithmetic or date math, text only, closed weights.
  - *Evidence:* Rafe and Das 2026 (arXiv 2609.24052) applied it to police crash narratives: F1 0.908 against human labels, and one frontier LLM was 0.059 F1 better. They note that "calibration varies by model … so each model must be audited."
  - *Fits:*
    1. **Week 3 checker benchmark:** a yes/no "is this sentence supported by the passage?" question, scored against the 50 human pairs alongside DeBERTa NLI and an LLM judge. This is already allowed by CLAUDE.md, and is the best fit.
    2. **Annotation flagging:** a choice question over E/Z/V/F/NONE. Low probability, or disagreement with the humans, flags an item for re-check (`annotation/ANNOTATION_GUIDE.md` Sec. 7).
    3. *Possible, needs a team decision because CLAUDE.md does not allow it yet:* a zero-shot product-classification baseline next to DistilBERT. Cost is negligible: about 14k test narratives at roughly 300 tokens each is about $0.2.
  - Sources: TypeSafe (typesafe.ai), the OpenRouter blog "What is Jev?", and arXiv 2609.24052.
- Branch `data-processing` is not merged to `main` yet. Open a PR once a teammate has reproduced the pipeline.

## 6. Next steps

**Pair A: classifier (code ready; GPU runs next).**
1. **Run it:** open `notebooks/train_classifier_colab.ipynb` in Colab (download it from GitHub, then *File → Upload notebook*). **Team decision 2026-10-10: no GitHub tokens.** The code comes in as a ZIP on a shared Drive folder **`Dataset/`** (owned by a teammate; each runner needs Editor access and a My Drive shortcut, so it mounts at `/content/drive/MyDrive/Dataset`): GitHub, branch `classifier`, *Code → Download ZIP*, uploaded unopened. The same folder holds `data/processed/{train,val,test}.parquet` and `annotation_sample.csv` (about 220 MB). The notebook uses the newest `cfpb-grounded-rag*.zip`, so **re-download the ZIP after every push**. If the data is missing it rebuilds it (about 15 minutes, about 8 GB RAM).
2. **Defaults:** `distilbert-base-uncased`, 3 epochs, batch 32, lr 5e-5, 6% warmup, weight decay 0.01, max 512 tokens with head 128 + tail 382 truncation, AMP (fp16 on T4, bf16 on A100). The best epoch is chosen by validation macro-F1, and the test set is evaluated once. Outputs go to Drive `outputs/classifier/<label>/`, listed in the script docstring.
3. **Log the results** in Sec. 7: GPU, minutes per epoch, val and test macro-F1, and the weakest classes. Compare settings (for example `--class-weights` or `--head-tokens 510`) on **validation only**.
4. **Interface** (proposed, to be frozen with the team): `predictions_<split>.parquet` with `complaint_id`, `true_<label>`, `pred_<label>`, `pred_<label>_prob`. Merging the product and issue runs on `complaint_id` gives the downstream table.

**Pair B: regulation corpus.** Download eCFR Title 12 Parts 1005, 1026, 1022, 1006 (XML), chunk by section structure, and verify the Reg V section numbers in Sec. 5. Proposed chunk interface: `chunk_id`, `part`, `section` (e.g. `1026.13`), `paragraph`, `heading`, `text`, `source_url`.

**Everyone.** Draft the annotation rubric (two people), including the "no in-scope section" label, then annotate `annotation_sample.csv` with overlap for inter-annotator agreement.

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

### 2026-10-06: Archive downloaded, full pipeline run (Aditya + Claude)
- Downloaded 10 archive zips (365 MB zipped, about 3.1 GB of CSV). The first pipeline attempt died when the session ended, so it was rerun cleanly; the log is in `outputs/pipeline_run.log`.
- Results are in Sec. 3: 6,809,200 complaints, 469,659 with narratives, 276,626 usable, splits of 111,563 / 13,945 / 13,946, and an annotation sample of 120.
- Output sizes: `complaints.parquet` 297 MB, `narratives_clean.parquet` 390 MB, `train.parquet` 173 MB. All are git-ignored.

### 2026-10-06: Handoff rewrite of this file, branch pushed (Aditya + Claude)
- Pushed `data-processing` to origin. Not merged; `main` still has only `CLAUDE.md`.
- Rewrote Secs. 0 to 6 for a cold start: start-here steps, working rules, per-pair status, output schemas, library versions, per-product counts (all / usable / train), proposed stage interfaces, and concrete next steps. The iteration log below is unchanged.
- Corrected stale text: "91% credit reporting" is now "33% of usable narratives", and the deleted-snapshot section was replaced by in-window counts from `outputs/profile_all.json`.


### 2026-10-07: Proposal cross-check
- Read the submitted proposal PDF. It matches the build except for annotation sampling, annotator count, and data source; these are recorded in Sec. 5 so the final report can explain them.

### 2026-10-07: Annotation guide and Jev research
- Added `annotation/ANNOTATION_GUIDE.md`. It covers what to label (Set A: 120 complaint-to-section pairs; Set B: 50 sentence-support pairs), the rubric decisions left to the drafters, the procedure (10-item pilot, two blind annotators per item, kappa, adjudication), and three LLM prompts: a blind third annotator, an adjudication helper given the full section text, and a support check. LLMs only flag items; human labels stay ground truth.
- Researched Jev (Sec. 5). Best fit: an extra verifier in the week 3 checker benchmark. API access is unverified.

### 2026-10-10: Classifier code (stage 1) on branch `classifier`
- Added `src/cfpb/classify/`, `scripts/train_classifier.py`, `scripts/check_splits.py`, `data_fingerprint.json`, `notebooks/train_classifier_colab.ipynb`, `requirements-classifier.txt`, and `tests/test_classify_data.py`. There are 11 unit tests, all passing.
- **Design:** a plain PyTorch loop instead of the HF Trainer, because Trainer arguments change across transformers versions. Transformers 5 removed `build_inputs_with_special_tokens`, so `[CLS]`/`[SEP]` are added by hand. Batches are length-bucketed to cut padding. Every epoch checkpoints to `last/` for `--resume` after Colab disconnects.
- **CPU smoke tests** (torch 2.14.1+cpu, transformers 5.19.0, 400 train / 150 eval, max_len 128): ran end to end and wrote every report. Resume from epoch 1 to 4 worked. Val macro-F1 went 0.024, 0.287, 0.326, 0.320 and train loss 2.28 to 1.47, so the model learns; the best epoch (3) was used for the final scores. The issue label (52 classes in that subsample) with `--class-weights` ran, excluding 12 val and 15 test rows with labels unseen in train. **No GPU run yet; no real scores yet.**
- **Data checks:** the pipeline peaks at 7.7 GB RAM (`--skip-ingest`, measured on Windows), so it fits free Colab (about 12.7 GB) but only just. Split files written by pandas 3.0.6 read correctly in pandas 2.2.3 (Colab's version), and the fingerprint matches. Not verified: whether rebuilding the splits under Colab's library versions reproduces identical rows. `check_splits.py` flags it if not.
- GitHub repo `Aditya-Datar/cfpb-grounded-rag` is **private** (anonymous API returns 404). A `git clone` inside Colab would need a token even for collaborators, so the team chose the ZIP-on-Drive route (next entry).

### 2026-10-10: Colab notebook switched to ZIP-on-Drive (no tokens)
- Notebook cell 3 now unpacks the newest `cfpb-grounded-rag*.zip` from the shared Drive folder instead of `git clone`. It also checks that the key classifier files exist, which catches a ZIP from the wrong branch.
- Simulated locally: built a ZIP with `git archive --prefix=cfpb-grounded-rag-classifier/`, the layout GitHub's Download ZIP uses, ran the notebook's unzip and data cells against a fake Drive folder, and passed `check_splits.py` (all 4 match). A tiny training run from the unzipped copy completed.
- Caveat: a ZIP carries no git history, so a run does not record which commit it used. Note the ZIP's upload date (printed by cell 3) in the results entry.

### 2026-10-10: Shared Drive folder is `Dataset`
- The team reuses an existing shared Drive folder named `Dataset`, with `Dataset/data/processed/` holding the 3 parquets and `annotation_sample.csv`. The notebook default changed to `/content/drive/MyDrive/Dataset`. Cell 2 now stops with instructions if the folder is missing, instead of silently creating an empty folder and rebuilding the data.
- The code ZIP goes at the top level of `Dataset/`. Results are written to `Dataset/outputs/classifier/<label>/`.

### 2026-10-10: First GPU runs (Colab, run by a teammate; analysed by Aditya + Claude)
- **Environment** (from `run_info.json`): NVIDIA A100-SXM4-80GB, bf16, Python 3.13.15, torch 2.11.0+cu130, transformers 5.18.0, sklearn 1.6.1, pandas 2.2.3. Default settings: 3 epochs, batch 32, lr 5e-5, max_len 512, head 128 + tail. **About 2.2 min per epoch** on the A100; T4 timing is still unmeasured. 14.6% of train narratives exceed 512 tokens, so they are truncated.
- **Product (11 classes):** per-epoch val macro-F1 0.790, **0.800**, 0.798 (val accuracy 0.827, 0.836, 0.835), so epoch 2 is best. Read from `product/last/training_state.pt`, because only that file was downloaded. **Test metrics are not yet copied from Drive** (`Dataset/outputs/classifier/product/`).
- **Issue (89 classes):** per-epoch val macro-F1 0.257, 0.290, **0.306**. **Test: macro-F1 0.297, accuracy 0.568, weighted-F1 0.553**, n = 13,946, with no rows excluded for unseen labels.
- **Why issue macro-F1 is low (from `classification_report_test.csv` and `predictions_test.parquet`):**
  - *Long tail.* Splits are stratified by product, not issue. 30 of 89 issues have fewer than 20 test examples, and 31 issues score F1 = 0. All 20 issues with 10 or fewer test examples score 0. Mean F1 by test support: 0 for 1 to 10 examples, 0.14 for 11 to 30, 0.26 for 31 to 100, 0.52 for 101 to 300, 0.59 for 301 to 1,000, and 0.64 above 1,000. **Macro-F1 over the 38 issues with at least 100 test examples is 0.546.**
  - *Overlapping consumer-chosen labels.* The top confusions are near-synonyms within one product. "Problem with a company's investigation" was predicted as "Incorrect information on your report" 169 times, and the reverse 126 times. "Written notification about debt" was predicted as "Attempts to collect debt not owed" 124 times; "False statements or representation" was predicted as the same 111 times. "Problem with a lender … charging your account" was predicted as "Managing an account" 129 times. **66.5% of the 6,030 issue errors pick an issue valid for the true product.** Note that 12 issue names are shared across products.
  - *Confidence is informative.* Accuracy by predicted probability: 20% at 0.3 or below, 34% from 0.3 to 0.5, 49% from 0.5 to 0.7, 69% from 0.7 to 0.9, and **91% above 0.9** (2,874 test rows). This supports showing confidence in the demo or routing low-confidence cases to a human.
- **Implications to discuss:**
  1. The proposal reports "per-category F1". Report product-level macro-F1 as the headline, and treat issue-level results with the long-tail caveat.
  2. Options for issue: merge issues with very few training examples into "other", group issues by regulation-relevant meaning, or predict issue conditioned on product.
  3. Compare any changes on **val only**.
- Model weights (`best/`, `last/`) are about 270 MB each, plus a 536 MB `training_state.pt`, and are git-ignored. The ZIP date used for these runs was not recorded.

### 2026-10-10: Results packaging cell
- Downloading output folders from Drive split them into multi-part ZIPs, because of the 1 GB+ model weights, and files went missing (product arrived with only `last/training_state.pt`). Added notebook cell 11, which writes `Dataset/outputs/results_<label>.zip` with only the result files (about 1 MB). Tested on the real issue outputs: 10 files, 1.0 MB.

### 2026-10-10: v1 product test results (from the downloaded files; v1 data)
- Product test: **macro-F1 0.798, accuracy 0.834, weighted-F1 0.833** (n = 13,946). Val macro-F1 0.800 at epoch 2, the best. Validation and test agree, so there is no sign of overfitting to validation.
- Per-class test F1: mortgage 0.943, student loan 0.915, vehicle 0.882, credit reporting 0.850, debt collection 0.834, credit card 0.833, money transfer 0.816, checking/savings 0.792, payday/personal 0.753, prepaid 0.643, debt or credit management 0.519 (recall 0.370, n = 181).
- Top confusions: money transfer to checking 228 and the reverse 207; credit reporting to debt collection 145 and the reverse 131; checking to credit card 99 and the reverse 98. Several high-confidence "errors" read as consumer mislabels; one narrative literally starts "Product : Credit Card" but is filed as money transfer. Accuracy by confidence: 35% at 0.5 or below, 58% from 0.5 to 0.7, 74% from 0.7 to 0.9, 92% from 0.9 to 0.99, and **99.0% above 0.99** (2,622 rows).
- **These v1 numbers are superseded:** retrain on v2 (next entry).

### 2026-10-10: Cleaning bug fixed, splits made hash-based (v2 data)
- **Bug:** about 24% of usable narratives (67,735) contained the date mask `XX/XX/year>`, which the cleaner turned into `[REDACTED]/year>` instead of `[DATE]`. It was found while reading classifier errors. A survey of all mask shapes in the 469,659 raw narratives found more unhandled forms: `XX/XX/scrub>` (about 1k per 200k sample), `XX/XX/scrub>/25`, `XX/2024`, `XX/XX/` with no year, masks glued to words (`informationXXXXReason`), lowercase `xxxx`, short masks (`XXX-XX-XXXX`), `{>= $...}`, `{$.99}`, unclosed and nested braces, `{ XXXX }`, and `{ REMOVED }`. All are now handled, with 33 new parametrized tests in `tests/test_clean.py`.
- **Splits:** rerunning the pipeline after the fix removed 248 rows (new duplicates once mask variants normalize), and the old shuffle-based split then moved 93% of val/test and all 120 annotation items. Replaced it with hash-based assignment (`split.stable_uniform`); see Sec. 4. Applying the hash method to v1 versus v2 data, 99.9% of rows keep their split and 119 of 120 annotation items stay. Tests in `tests/test_split.py` show that dropping 250 rows moves 0 others.
- **v2 data:** 276,378 usable; train/val/test 111,527 / 14,022 / 13,905; 88 issues in train. New `data_fingerprint.json` includes text hashes. Rebuilding under pandas 2.2.3 (Colab) gives identical ids, annotation sample, and test text.
- 43 unit tests pass.
- **Action for the team:** upload the new `data/processed/{train,val,test}.parquet` and `annotation_sample.csv` to Drive `Dataset/data/processed/`, replacing the old files. Download a fresh code ZIP, then retrain product and issue. The old Drive files and old results now fail `check_splits.py` by design.

### 2026-10-10: v2 fix pushed (`22da3d9`, branch `classifier`)
- Simulated the Colab flow from a ZIP of `origin/classifier` with the v2 data files: `check_splits.py` printed all 4 OK, 43 tests passed, and the smoke training run exited 0.
- Still on the branch: notebook cell 11 (`a4707ea`, results packaging); the revert was not requested.
- Next: re-upload the v2 data and a fresh ZIP to Drive, clear the old `Dataset/outputs/classifier/`, and retrain product and issue.

### 2026-10-14: Regulation chunker v1, verified on Part 1005 (Ishani + Claude)
- **Context:** branch `chunking` already had the eCFR parser (`2ff6104`, `a96a752`): `chunking/xml_parser.py` cuts the four parts out of `ECFR-title12.xml`, and `chunking/parse_regulations.py` writes `chunking/data/processed/sections.jsonl` (one record per section/appendix, with ordered paragraph blocks and inferred paths such as `(a)(1)(ii)`). Both scripts use paths relative to `chunking/`, so run them from there.
- **Added `chunking/chunk_regulations.py`.** Reads `sections.jsonl`, writes `chunking/data/processed/chunks.jsonl` (not committed; regenerate with `cd chunking && python chunk_regulations.py --parts 1005`). Regulation text only for now (`content_type == "regulation"`, reserved sections skipped).
  - A section stays one chunk if its chunk text fits in `MAX_CHARS = 2000` (a constant at the top of the file; provisional until the embedding model is chosen). Longer sections split at paragraph boundaries, one level deeper only where a paragraph is still too long. A paragraph with no sub-paragraphs is never cut, so it can exceed the limit.
  - Every chunk's text starts with the section heading plus the intro text of each parent paragraph. Fused XML blocks such as `(c) Time limits…—(1) Ten-day period…` are split so `(c)(2)` also carries the `(c)` intro.
  - Fields: the Sec. 6 proposed interface first (`chunk_id`, `part`, `section`, `paragraph`, `heading`, `text`, `source_url`), then `content_type`, `regulation`, `path_certain`, `n_chars`, `record_id`. `chunk_id` looks like `12-1005-1005.11-c-2`, or `12-1005-1005.11-all` for a whole section.
  - `source_url` adds a paragraph anchor such as `#p-1005.11(c)(2)`. **Verified 2026-10-14:** the eCFR renderer API (`/api/renderer/v1/content/enhanced/current/title-12?part=1005`) serves 1,082 paragraph ids for Part 1005, all in this form. (The public ecfr.gov page returned a bot-check page to curl.) Chunks with `path_certain: false` get the plain section URL.
  - Each run checks that every piece of text is a chunk body exactly once (or parent-intro context), that splitting changes no characters, and that `chunk_id`s are unique.
- **Part 1005 result:** 313 chunks from 27 sections (7 kept whole); chunk text 116 to 3,164 chars, median 825; 20 over 2,000; 67 flagged `path_certain: false`. 1005.11 gives 8 chunks ((a), (b), (c)(1) to (c)(4), (d), (e)), all checked by hand.
- **Dry run on all four parts** (output not kept; numbers are not trustworthy until the parser fix below): 1026: 1,255 chunks / 58 sections / 712 flagged / 376 over 2,000; 1022: 338 / 36 / 115 / 58; 1006: 97 / 15 / 40 / 8. All coverage checks passed. About 2,000 chunks in total, consistent with CLAUDE.md Sec. 4 "a few thousand".
- **Tests:** `tests/test_chunk_regulations.py`, 8 tests on small synthetic records, all passing. pytest is not installed on this machine, so they were run with a plain Python loop; **not yet run under pytest**.
- **Parser bug (in `parse_regulations.py`, not fixed here; owner to discuss).** Every numbered paragraph path in Part 1005 was compared against eCFR's paragraph ids: **171 of 738 (23%) do not exist on eCFR, in 9 of 27 sections** (including 1005.3, .12, .18, .19, .32, .36). The parser flags only 87 of them as uncertain; **84 are wrong but marked `path_certain: true`**.
  - Cause: the `(i)` letter-vs-roman ambiguity. `PathTracker._push` tries "next sibling at an existing level" before "first child at the next level", so after `(h)(1)` the marker `(i)` becomes the letter `(i)` instead of `(h)(1)(i)` (example: 1005.20). One misread shifts every later path in the section.
  - Effect on chunks: text is complete, but boundaries and `paragraph` labels can be wrong, and paragraphs that receive the same wrong path are merged into one chunk. This also explains most chunks over 2,000 chars.
  - Chunk-level flagging catches almost all of it, because a chunk is flagged if any of its text (including parent intros) is uncertain. Of 240 unflagged Part 1005 chunks, only one has an anchor missing on eCFR: `12-1005-1005.20-i` (really `(h)(1)(i)`).
  - A fix can be checked the same way: compare parser paths against the eCFR renderer ids.
- **Open questions:**
  1. **Embedding model** is not chosen (CLAUDE.md Sec. 3 says only "Sentence-BERT"). Its max input length decides `MAX_CHARS`.
  2. **Supplement I (official interpretations) and appendices** have no owner. Supplement I is large (about 2.7M chars for Part 1026 alone in `sections.jsonl`, versus about 1.3M chars of regulation text across all four parts) and often answers complaints directly. `annotation/ANNOTATION_GUIDE.md` Sec. 2 item 5 suggests labels point to the regulation section, not the commentary. Also, `parse_regulations.py` labels "Appendix C" of Parts 1005 and 1026 as `interpretation`, though it is an ordinary appendix.
  3. **Reg V section numbers** in Sec. 5 are still unverified against eCFR (Pair B task in Sec. 6).
  4. **Retrieval scoring:** gold labels are section-level, but one section can give several chunks, so precision@k should count one hit per section. The size of the "oracle" passage (whole section or one chunk) is undefined; a mismatch would mix chunk length into the retrieved-vs-oracle gap.
  5. **Repo hygiene:** `.gitignore` ignores only top-level `/data/`, so `chunking/data/` (including the 39 MB `ECFR-title12.xml`) is committed, against working rule 5. `chunking/` also departs from the Sec. 2 layout (`src/cfpb/<stage>/` + `scripts/`).

### 2026-10-14: Chunk size is now a command-line option (Ishani + Claude)
- `chunking/chunk_regulations.py` takes `--max-chars` (default `MAX_CHARS = 2000`, so default output is unchanged). The value is passed through `chunk_record(record, max_chars)` rather than read from a global, and the run summary prints `max chars: <value>`.
- Example: `cd chunking && python chunk_regulations.py --parts 1005 --max-chars 800 --out data/processed/chunks_800.jsonl`.
- Re-ran Part 1005 with the default: still 313 chunks from 27 sections, same size stats as the previous entry.
- Section 1005.11 gives 28 / 24 / 8 / 5 chunks at 500 / 800 / 2,000 / 4,000 chars.
- 3 new tests on the real 1005.11 record (default gives the same 8 chunks; 800 gives more than 2,000; coverage holds at 500, 800, 2,000, 4,000). All 11 tests pass, run with a plain Python loop; still not run under pytest.

### 2026-10-14: Chunker updated for Ujjwal's parser fix; all four parts chunked (Ishani + Claude)
- **Parser fix (`232a564`, Ujjwal):** `PathTracker` now resolves the `(i)` letter-vs-roman case from context (a preceding `:` or dash, else the next marker), allows skipped levels, and recognises a second fused form, `(b) Record retention. (1) …` (`RUNIN_RE`). The committed `sections.jsonl` is byte-identical to a fresh run of the new parser (`--snapshot-date 2026-10-13`).
- **Paths vs eCFR** (renderer API ids, fetched 2026-10-14), numbered regulation paragraphs whose path is not an eCFR id, before → after the fix: 1005: 171 / 738 → 0; 1026: 1,749 / 3,227 → 5; 1022: 210 / 739 → 0; 1006: 88 / 302 → 0. The 5 left are 1026.19(f)(4)(i) to (iv) and their parent: after (f)(3)(ii)(D)(3), "(4) Transactions involving a seller" is placed at (D)(4) and marked certain. Not yet reported to Ujjwal.
- **Chunker changes** (`chunking/chunk_regulations.py`): the parser renamed `get_leading_markers` to `leading_markers`, which broke the chunker's import; fixed. `split_at_markers` now also splits the period form, mirroring `leading_markers` (only a marker that can start a list, value 1, counts). Before this, 205 of 2,102 chunks lacked a parent intro (e.g. `1005.12-a-2` lacked "(a) Relation to Truth in Lending.").
- **Result, all four parts, default `--max-chars 2000`:** 1005: 309 chunks, 0 flagged, 2 over 2,000; 1026: 1,362, 1 flagged, 31 over; 1022: 341, 0, 3 over (max 3,450); 1006: 92, 0, 0 over. Total 2,104. Chunks missing a parent intro: **0**. Paragraph anchors not on eCFR: 5 of 2,072 (the 1026.19 case above). `chunking/data/processed/chunks.jsonl` regenerated locally, not committed.
- **Tests:** 16, all passing (plain Python loop; pytest still not run). New: period-form split, a cross-reference that must not split, the real 1005.12(a)(2) case, and a corpus-wide check that every chunk contains the words of all its parent paragraphs at 500 and 2,000 chars. That check finds parent intros independently of the chunker (parser markers plus a plain text search for the next marker); run on the old chunker's output it reports the same 205 chunks.
- **Still open:** the 1026.19 path; `parse_report.json` stores `§` as a broken character (`write_text` without `encoding="utf-8"`); the parser exits 1 because 1022 Appendix L is empty but not marked reserved; embedding model; Supplement I owner; Reg V section check.
