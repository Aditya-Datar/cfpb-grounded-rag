# CLAUDE_PROGRESS.md: Build Log and Handoff Context

Companion to `CLAUDE.md`. `CLAUDE.md` holds the project's fixed decisions (scope, methods, related work, deliverables, rules for graded work). **This file is the living engineering log**: what code exists, what has been run, what we found in the data, and what comes next. Last updated 2026-10-06 (commit after `bbe73e5`).

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

Data files are git-ignored, so every member regenerates them locally. Check your run against Sec. 3: you should get 276,626 usable narratives. The seed is fixed, but identical output on other machines and library versions has **not** been verified; report any difference in the log.

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
| 1. Classifier: DistilBERT, macro-F1 | A | `classifier` (pushed) | **Code ready and CPU-tested; not yet run on a GPU.** Run `notebooks/train_classifier_colab.ipynb` (Sec. 6) |
| 2. Regulation corpus and retrieval | B | not created | Not started; does not depend on complaints, so it can start now |
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
| `data/processed/narratives_clean.parquet` | 276,626 | usable narratives (schema below) |
| `data/processed/train.parquet` / `val.parquet` / `test.parquet` | 111,563 / 13,945 / 13,946 | classifier splits (schema below) |
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

### Narrative dataset, v1 (pipeline run 2026-10-06, 4.5 min)

All 10 zips pass the zip integrity test and share one 16-column header.

| Step | Count |
|---|---:|
| Complaints received 2025-08-14 to 2026-08-14 (deduped on `complaint_id`) | 6,809,200 |
| With a non-empty narrative | 469,659 (6.9%) |
| Usable after cleaning (at least 20 words, redaction density 0.5 or less, exact-text dedupe) | 276,626 |
| Classifier splits (`product`, at most 20k per class before splitting, 80/10/10) | train 111,563 / val 13,945 / test 13,946 |
| Annotation sample | 120 (30 each for E, F, V, Z) |

Usable narratives by product. They are **far less skewed** than all complaints: credit reporting is 90% of complaints but only 33% of usable narratives.

| Product | All complaints | Usable narratives | In `train` | Candidate regulation |
|---|---:|---:|---:|---|
| Credit reporting or other personal consumer reports | 6,152,294 | 90,158 | 16,000 | V |
| Debt collection | 332,548 | 55,544 | 16,000 | F |
| Checking or savings account | 86,182 | 36,610 | 16,000 | E |
| Credit card | 95,747 | 34,860 | 16,000 | Z |
| Money transfer, virtual currency, or money service | 38,283 | 17,601 | 14,081 | E |
| Mortgage | 31,772 | 13,000 | 10,400 | Z |
| Vehicle loan or lease | 24,594 | 10,274 | 8,219 | Z |
| Payday loan, title loan, personal loan, or advance loan | 17,440 | 7,364 | 5,891 | Z |
| Student loan | 19,671 | 6,617 | 5,294 | Z |
| Prepaid card | 6,311 | 2,785 | 2,228 | E |
| Debt or credit management | 4,358 | 1,813 | 1,450 | none |

In this window, all complaints by candidate regulation: V 6,152,294; F 332,548; Z 189,224; E 130,776; none 4,358. Usable narratives by candidate regulation: V 90,158; Z 72,115; E 56,996; F 55,544.

- **Classifier labels:** 11 products; 89 distinct issues in `train`. Class sizes in `train` range from 16,000 down to 1,450, so report macro-F1.
- **Narrative length** (words, after cleaning): median 175, IQR 93 to 285, mean 229, max 6,089. DistilBERT's 512-token limit will truncate roughly the longest quarter (*estimate: tokens per word not measured*); consider head plus tail truncation.
- **Redaction density:** median 0.027, 75th percentile 0.05. Most narratives are lightly masked.
- **Annotation sample mix:** E has 10 each of checking/savings, money transfer, and prepaid; F has 30 debt collection; V has 30 credit reporting; Z has 6 each of credit card, payday/personal loan, student loan, mortgage, and vehicle. It excludes the classifier test set.
- **Data-quality observation (prevalence NOT yet measured):** the first sampled debt-collection narrative reads like a credit-repair template, a formal letter citing the FDCPA, FCRA, and Indiana law. Given the CFPB's note about credit-repair and automated submissions (CLAUDE.md Sec. 8), such templates may be common. Measure this before claiming it, for example by counting near-duplicate texts or statute mentions. Template letters cite statutes by name, which may make retrieval look easier than it is on organic complaints, so template vs organic is a candidate error-analysis slice.

## 4. Design decisions made in code (and why)

- **Redaction cleaning** (`clean.py`): CFPB masks PII as runs of `XXXX`, masks dates as `XX/XX/XXXX`, and wraps amounts in braces like `{$250.00}`. We map these to `[REDACTED]`, `[DATE]`, and `$250.00`, so models see one consistent token.
- **Filters:** narratives need at least 20 words and a redaction density of 0.5 or less (`--min-words`, `--max-redaction`). Defaults were not tuned. Given the profile above, the redaction filter removes very little.
- **Dedupe before splitting:** consumers often file the same narrative against several companies (for example, all three credit bureaus). We dedupe on a SHA-1 of normalized text so copies cannot sit in both train and test. Near-duplicates (for example, templates with different names) are **not** caught.
- **Class cap:** `--max-per-class 20000` before the 80/10/10 split, stratified by `product`. Classes with fewer than 10 rows go to train only (none at present).
- **Annotation sample:** `PRODUCT_TO_REGULATION` assigns a *candidate* regulation used only for stratification. Sampling is round-robin across products within each regulation, and the sample is disjoint from the classifier test set.
- **Seed:** 544 everywhere (`config.RANDOM_SEED`).

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
1. **Run it:** open `notebooks/train_classifier_colab.ipynb` in Colab (download it from GitHub, then *File → Upload notebook*). **Team decision 2026-10-10: no GitHub tokens.** The code comes in as a ZIP on a shared Drive folder `cfpb-grounded-rag/`: GitHub, branch `classifier`, *Code → Download ZIP*, uploaded unopened. The same folder holds `data/processed/{train,val,test}.parquet` and `annotation_sample.csv` (about 220 MB). The notebook uses the newest `cfpb-grounded-rag*.zip`, so **re-download the ZIP after every push**. If the data is missing it rebuilds it (about 15 minutes, about 8 GB RAM).
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
