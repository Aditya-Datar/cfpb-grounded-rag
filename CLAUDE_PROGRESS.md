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
| 1. Classifier: DistilBERT, macro-F1 | A | `classifier` (pushed) | **v2 baseline done (2026-10-15).** Product: test macro-F1 **0.808**, accuracy 0.843. Issue: test macro-F1 **0.325** (labels present in test; 0.310 if all 88 train labels are counted), accuracy 0.581. Trained models load locally via `cfpb.classify.predict.ComplaintClassifier` |
| 2. Regulation corpus and retrieval | B | `regulation-corpus` | **Corpus built:** 4,319 chunks (Regs E/F/V/Z from eCFR 2026-10-13, plus the FCRA statute, U.S. Code 2024); retriever (BM25, dense, hybrid, with abstention) not started |
| 3. Generation and 4. NLI verification | C | not created | Not started |
| Backend: single-complaint pipeline for the demo | Anirudh | `backend` | **Runs end to end (2026-10-19):** `cfpb.pipeline` with the real classifier, a corpus loader for both chunk sets, an oracle retriever (gold section), a batch runner writing INTERFACES.md tables, a minimal Streamlit page (`demo/app.py`), and **adapters so the BM25 retriever plugs in as soon as it lands** (live function or `ranked.parquet`). Real retriever, generator and verifier still stubs (Sec. 7) |
| Annotation (gold pairs) | all | `regulation-corpus` | **Done (2026-10-16): `annotation/gold_final.jsonl`**, 198 items: 127 in scope (E 29, F 30, Z 27, FCRA 36, V 5) + 71 NONE. Two LLM annotators (regulation kappa 0.904, section kappa 0.845), 26 disagreements human-adjudicated, 20/20 human spot check OK |

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
src/cfpb/regs/ecfr.py               eCFR API download (needs Accept-Encoding: gzip)
src/cfpb/regs/fcra.py               FCRA statute download (GovInfo, U.S. Code 2024) and parsing into statute chunks
src/cfpb/annotation.py              annotation item set: load_items() = sample + top-up; in-scope top-up plan
scripts/make_topup_sample.py        draws the 78-item in-scope top-up (hash-ordered, reproducible)
scripts/make_chatgpt_package.py     builds annotation/chatgpt_package/generated/ (rubric copied from the skill)
scripts/compare_annotators.py       kappa and agreement between two label files, plus a disagreements.md report
scripts/build_gold.py               spot-check list (--init) and final gold assembly from agreed labels plus human decisions
src/cfpb/regs/parse.py              eCFR XML -> structure-aware chunks (regulation / interpretation / appendix)
scripts/build_reg_corpus.py         builds data/processed/reg_chunks.parquet + annotation/regulation_sections.md
scripts/reg_lookup.py               print section/paragraph text, keyword search, annotation complaints
scripts/check_llm_labels.py         validates LLM label files (section exists, quote verbatim)
.claude/skills/regulation-annotator/SKILL.md   project skill: grounded complaint -> section labelling
docs/INTERFACES.md                  PROPOSED stage interfaces (freeze after team review)
annotation/regulation_sections.md   the 146-section list (generated)
tests/test_regs_parse.py            parser tests (paragraph grouping, roman numerals, interpretations)
data_fingerprint.json               SHA-1 of sorted complaint_ids per split (team reference)
notebooks/train_classifier_colab.ipynb   step-by-step Colab runner (fresh-session safe)
requirements-classifier.txt         torch, transformers, matplotlib on top of requirements.txt
tests/test_clean.py                  unit tests for cleaning and dedupe
tests/test_classify_data.py         unit tests for truncation, batching, padding
src/cfpb/classify/predict.py        ComplaintClassifier: load a trained best/ model, predict on new text
scripts/evaluate_classifier.py      re-score a finished run from saved predictions (or --repredict)
tests/test_split.py                 hash-split stability tests
tests/test_metrics.py               macro-F1 convention tests
src/cfpb/pipeline/                  single-complaint pipeline for the Streamlit demo: schema.py (result
                                     types), stages.py (stage protocols, classifier adapter, stubs), core.py
scripts/analyze_complaint.py        run the pipeline on one complaint, print JSON
tests/test_pipeline.py              pipeline tests (stubs, abstention, stage swapping)
src/cfpb/pipeline/corpus.py         Corpus (loads reg_chunks.parquet or chunking's chunks.jsonl), OracleRetriever
src/cfpb/pipeline/batch.py          PipelineResults -> classification/ranked/responses/sentences tables
src/cfpb/pipeline/retrievers.py     FunctionRetriever (live retrieve(query, k)), PrecomputedRetriever (ranked.parquet)
tests/test_pipeline_retrievers.py   adapter, corpus merge and round-trip tests
scripts/run_pipeline_batch.py       pipeline over the gold-set complaints -> outputs/pipeline_runs/<run>/
tests/test_pipeline_corpus.py       corpus loader and oracle tests (+ real-data checks, skipped if absent)
demo/app.py                         minimal Streamlit page: streamlit run demo/app.py
requirements-demo.txt               classifier stack plus streamlit
.claude/launch.json                 runs the demo in the Claude Code desktop preview
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

- **Reg V coverage gap (important for annotation).** Most credit-reporting complaints concern bureau dispute investigations. Those duties sit in the FCRA statute (15 U.S.C. 1681i), not in Reg V (12 CFR 1022), which covers narrower ground such as furnisher accuracy and direct disputes. Credit reporting is 33% of usable narratives, so many may have **no governing section in our four-part corpus**. The rubric needs a "no in-scope section" label; the team decides whether to accept that or add FCRA text. *Verified against eCFR (2026-10-15): Reg V has 1022.40 Scope, 1022.41 Definitions, 1022.42 accuracy and integrity policies, 1022.43 Direct disputes; Reg V has no Official Interpretations supplement.*
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

**Pair B: retrieval (corpus done).** Build BM25, dense (Sentence-BERT + FAISS) and hybrid retrievers over `reg_chunks.parquet`, following `docs/INTERFACES.md` Sec. 2. Decide whether interpretation chunks are indexed (ablation).

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

### 2026-10-15: v2 classifier baseline (Colab A100, run by a teammate; analysed by Aditya + Claude)
- **Verified fresh v2 runs:** run_info rows are 111,527 / 14,022 / 13,905, and the prediction ids equal the v2 val/test ids exactly. Each history has 3 new epochs that differ from v1, so nothing resumed from stale checkpoints. The reported val score equals the best epoch. Environment: A100-SXM4-80GB, bf16, transformers 5.18.0, pandas 2.2.3, about 2.2 min per epoch, default settings. 14.4% of train narratives are truncated at 512 tokens.
- **Product (11 classes):** val macro-F1 by epoch 0.782, 0.799, **0.801** (best is epoch 3, still rising slightly). **Test: macro-F1 0.808, accuracy 0.843, weighted-F1 0.842.**
  - Per-class test F1: mortgage 0.951, student loan 0.917, vehicle 0.883, credit reporting 0.865, credit card 0.851, debt collection 0.837, money transfer 0.810, checking/savings 0.801, payday/personal 0.764, prepaid 0.696 (recall 0.621), debt or credit management 0.509 (recall 0.384, n = 190).
  - Top confusions: money transfer to checking 228 and the reverse 215; credit reporting to debt collection 131 and the reverse 127; credit card to checking 95 and the reverse 78.
  - Accuracy by confidence: 41% at 0.5 or below, 54% from 0.5 to 0.7, 71% from 0.7 to 0.9, 90% from 0.9 to 0.99, and **98.5% above 0.99** (4,128 of 13,905 test rows).
- **Issue (88 train labels):** val macro-F1 by epoch 0.255, 0.293, **0.307**. **Test: macro-F1 0.310 over all 88 labels / 0.325 over the 84 labels present in test, accuracy 0.581, weighted-F1 0.564.**
  - Four labels have no test examples and were never predicted ("Credit limit changed", "Incorrect exchange rate", "Problem with overdraft", "Property was sold"). `train.evaluate` passes all train labels to sklearn, so they count as F1 = 0. **Proposed fix (not yet applied):** average over labels present in the true or predicted labels, which is sklearn's default.
  - 29 labels have test F1 = 0; all 22 labels with 10 or fewer test examples score 0. Mean F1 by test support: 0 for 10 or fewer, 0.17 for 11 to 30, 0.30 for 31 to 100, 0.52 for 101 to 300, 0.57 for 301 to 1,000, and 0.65 above 1,000. **Macro-F1 over the 39 issues with at least 100 test examples is 0.538.**
  - Top confusions are near-synonym consumer labels: "Problem with a company's investigation" predicted as "Incorrect information on your report" 192 times; "Problem with a lender … charging your account" as "Managing an account" 134; "False statements or representation" as "Attempts to collect debt not owed" 120; "Improper use of your report" as "Incorrect information" 114. **65.9% of the 5,828 issue errors are an issue valid for the true product.**
  - Accuracy by confidence: 21% at 0.3 or below, 35% from 0.3 to 0.5, 51% from 0.5 to 0.7, 68% from 0.7 to 0.9, and **91.5% above 0.9**.
  - One val row is excluded because its label ("Lost or stolen refund") never appears in train.
- **Versus v1:** the test sets differ (v2 test overlaps v1 test only partly, and the row count changed), so the numbers are **not** a controlled comparison. Product is 0.808 vs 0.798 and issue (all labels) 0.310 vs 0.297. Treat v2 as the official baseline.
- **Open items for Pair A:**
  1. Approve the macro-F1 convention fix above.
  2. Decide on issue-label handling (merge rare issues, or report the at-least-100-examples subset alongside).
  3. Optional: a 4th epoch for product, since val was still rising.
  4. Freeze the output interface with Pairs B and C.

### 2026-10-15: Macro-F1 convention fixed, models reusable without retraining (Aditya + Claude)
- **Fix:** `train.compute_metrics` now averages macro-F1 over the labels present in the split's true or predicted labels, sklearn's default. Train labels with no examples in the split and never predicted are listed in `labels_without_examples` instead of scoring 0. A predicted-but-absent label still counts as 0. The old number is kept as `macro_f1_all_train_labels`, and three tests are in `tests/test_metrics.py`. This does not change best-epoch selection: absent labels were never predicted, so the old score is a fixed rescaling of the new one.
- **Re-scored v2 runs from the saved predictions, no retraining** (`scripts/evaluate_classifier.py`): issue val 0.3066 to **0.3137** (86 labels scored), issue test 0.3100 to **0.3248** (84 labels scored; no test examples for "Credit limit changed", "Incorrect exchange rate", "Problem with overdraft", "Property was sold"). Product is unchanged (val 0.8011, test 0.8077). `run_info.json` records the rescoring under `"rescored"`. Original files are backed up in the session scratchpad only.
- **Model loading:** `ComplaintClassifier("outputs/classifier/<label>/best")` reads the truncation settings from `run_info.json`, cleans raw CFPB text automatically, and returns label, prob, and top-k. Verified on CPU: on 150 random test complaints per model, it gives **100% label agreement** with the Colab predictions; probability differences are median 0.0003 (product) / 0.0013 (issue) and at most 0.008, from bf16 on GPU versus fp32 on CPU. Raw and pre-cleaned input give the same labels. Speed is about 3 narratives/sec on Aditya's CPU. The weights (`best/`, about 268 MB each) live on Drive `Dataset/outputs/classifier/<label>/best/` and on Aditya's laptop; they are git-ignored.
- 46 unit tests pass.
- **eCFR facts for Pair B** (API, 2026-10-15; Title 12 up to date as of 2026-10-13): section/appendix counts are Part 1005 (Reg E) 27/4, Part 1006 (Reg F) 15/4, Part 1022 (Reg V) 45/14, Part 1026 (Reg Z) 59/18, so **146 sections** in total. Table-of-contents endpoint: `https://www.ecfr.gov/api/versioner/v1/structure/<date>/title-12.json?part=<n>`. The full-text endpoint `.../full/<date>/title-12.xml?part=<n>` returned HTTP 406 to a range request; work out the right request when building the corpus.

### 2026-10-15: Regulation corpus, interfaces, LLM annotation tooling (branch `regulation-corpus`)
- **eCFR download:** Title 12 up to date as of 2026-10-13. Parts 1005, 1006, 1022, 1026 were fetched as full XML through the eCFR API; the full-text endpoint returns HTTP 406 unless the request sends `Accept-Encoding: gzip`. Transfer was about 1.1 MB compressed and 5.3 MB of XML, stored in `data/raw/ecfr/` (git-ignored).
- **Corpus:** `data/processed/reg_chunks.parquet` has **4,070 chunks**: 1,540 regulation, 2,418 interpretation (Supplement I), 112 appendix. By part: E 236/388/15, F 91/111/9, V 255/0/19, Z 958/1,919/69. There are 146 sections, 10 of them reserved.
  - Regulation chunks are top-level paragraphs, split at numbered subparagraphs when over 350 words; the median is 94 words.
  - Interpretation chunks are grouped by commentary heading and mapped to a section or paragraph; 97.8% map to a rule section, and the rest are appendix commentary.
  - 380 chunks are word-window pieces (`#k`) of 106 over-long single comments or paragraphs.
  - Coverage: 99.3% to 100% of source words land in chunks; the dropped text is heading-only blocks.
  - Spot checks: 1006.18(b)'s roman items stay inside (b), 1026.13 runs (a) to (i), and 1006.34 splits into (b)(1) to (5).
- **`docs/INTERFACES.md`** (PROPOSED) covers complaint records, classifier output, chunks, retriever output and section-level scoring, gold labels, generation (retrieved vs oracle conditions, caching), and verification. Freeze it after team review.
- **TA ruling, 2026-10-15:** LLMs may do the annotation (Claude Code, ChatGPT, ...); LLM bias is acceptable given the team's lack of legal expertise. This supersedes CLAUDE.md Sec. 5's "human labels are ground truth" for annotation; CLAUDE.md is unchanged pending a team edit. Report these as *silver* labels. The protocol is in `annotation/ANNOTATION_GUIDE.md`: Annotator A is Claude with the skill; Annotator B is a different LLM family, blind; kappa between A and B; humans adjudicate disagreements and spot-check 20.
- **Legal-skill search (TA suggestion):** reviewed Anthropic's `anthropics/claude-for-legal` (Apache-2.0; plugins for commercial, corporate, employment, privacy, product, regulatory monitoring, IP, litigation, legal clinic, law student) and community skills (contract review, GDPR-style compliance). **None targets consumer-finance complaint-to-regulation mapping**, and several bundle hooks, scripts, or MCP connectors, so none were installed. We wrote a project skill instead (`.claude/skills/regulation-annotator/SKILL.md`). It follows the useful conventions (grounded citations, flag unverified items, "draft, not legal advice"). The method is: facts, coverage gate, read the section text with interpretations, elements test, conclusion with a verbatim quote. Every section number in its decision table was checked against the corpus; two remembered Reg V numbers (1022.80, 1022.90) were not in the corpus and were left out. The prepaid claim (1005.18(e)) and the "debt collector" definition (1006.2(i)) were also checked against the text.
- **Pilot (Annotator A = claude-opus-5-5, 3 items):**
  - 16625083 (Equifax dispute letter): NONE, governed by FCRA 1681i, confidence 2.
  - 16779625 (card payment marked late): Z 1026.10(a), confidence 2, runner-up 1026.13.
  - 23571192 (Wells Fargo denied an unauthorized-EFT claim without documents): E 1005.11(d)(1), confidence 3.
  - `check_llm_labels.py` passes all 3 and rejects a copy with a one-word quote change.
- `scripts/reg_lookup.py --search` is a crude TF-IDF helper; for "unauthorized debit card" it ranks 1005.17 (overdraft) above 1005.11, so the skill relies on its decision table plus reading, not on search.

### 2026-10-15: Annotator A labels for all 120 complaints, plus the ChatGPT package
- **Labels:** `annotation/llm_labels_claude-opus-5-5.jsonl`, 120/120, made by claude-opus-5-5 with the `regulation-annotator` skill in 11 batches. Every batch passed `check_llm_labels.py` (section exists and matches the regulation, paragraph under section, quote verbatim, NONE names the governing law).
  - A batch-9 slip (two complaint_ids swapped between items) was caught before saving by an id-to-company cross-check, and every label was then re-checked against its company.
- **Distribution:** NONE 77, F 22, E 12, Z 7, V 2. Confidence 1/2/3 = 20/47/53.
  - Sections: 1005.11 ×10, 1006.18 ×10, 1006.38 ×8, 1006.14 ×3, 1005.6, 1022.43 and 1026.12 ×2 each, and 1026.10, 1026.13, 1026.18, 1026.53, 1026.19, 1006.34 ×1 each.
- **Key finding (sampling heuristic vs label):**

  | Candidate | E | F | NONE | V | Z |
  |---|---:|---:|---:|---:|---:|
  | E | 12 | 0 | 18 | 0 | 0 |
  | F | 0 | 19 | 11 | 0 | 0 |
  | **V** | 0 | 1 | **29** | 0 | 0 |
  | Z | 0 | 2 | 19 | 2 | 7 |

  - Credit-reporting complaints are almost entirely CRA disputes or identity-theft blocks under the **FCRA statute** (36 of the 77 NONE cite the FCRA).
  - Many Reg Z-candidate complaints are federal student loans, RESPA/Reg X servicing, title release, or other law.
  - **Only 43 items are in scope for retrieval evaluation, and V (2) and Z (7) are too few** for the planned ~30 per regulation. This confirms the Sec. 5 risk. **The team must decide:**
    - (a) add the FCRA statute (15 U.S.C. 1681) and/or RESPA/Reg X to the corpus;
    - (b) resample using issue-level filters to reach about 30 in-scope items per regulation; or
    - (c) keep NONE as a first-class outcome the system must detect, and report retrieval on in-scope items only.
- **Labelling conventions** that emerged, written into `annotation/chatgpt_package/01_INSTRUCTIONS.md` for the team to ratify:
  - CRA disputes and blocks: NONE.
  - Consumer-initiated scam payments: NONE (1005.2(m)).
  - Denied unauthorized-EFT claims: 1005.11 by paragraph; loss only: 1005.6.
  - Payment not credited: 1026.13 with a written dispute, else 1026.10.
  - Collector ignores a written validation request: 1006.38(d)(2). Collector reports disputed or false data: 1006.18(c)(2). No validation notice: 1006.34(a).
  - Original creditors are not Reg F debt collectors.
- **ChatGPT package (Annotator B):**
  - `annotation/chatgpt_package/` holds `README.md`, `PROMPTS.md` (step 1 blind in batches of 20, step 2 compare), and `01_INSTRUCTIONS.md` (the rubric).
  - `scripts/make_chatgpt_package.py` regenerates `generated/` (git-ignored): complaints without labels, the section list, full rule text for E/F/V/Z (about 1.3 MB), and Claude's labels for step 2 only.
  - `scripts/compare_annotators.py` reports agreement and kappa at regulation and section level and writes `annotation/disagreements.md` for human adjudication. It was tested on a doctored copy (2 changes gave section kappa 0.971 and the right confusion table), and `check_llm_labels.py` rejected that copy's mismatched quote, as intended.

### 2026-10-15: FCRA added, in-scope top-up, abstention design (all 198 items labelled)
- **Why:** Annotator A's 120 labels gave only 43 in-scope items (E 12, F 22, Z 7, V 2), and 64% were NONE, with 36 of those governed by the FCRA statute. The team chose three things together:
  1. Add the FCRA to the corpus.
  2. Top up the in-scope items for E, F, and Z.
  3. Treat NONE as a first-class abstention outcome.
- **FCRA corpus:**
  - Source: GovInfo `USCODE-2024-title15-chap41-subchapIII.htm` (513 KB, current through 2025-01-06).
  - `src/cfpb/regs/fcra.py` keeps only the statute text (between `field-start:statute` and `field-end:statute`, so editorial notes are dropped) and chunks by subsection, splitting long subsections at paragraph headings and merging heading-only pieces.
  - Result: 31 sections (1681 to 1681x), 249 `statute` chunks (`S:<section>(<sub>)(<para>)`), with 100% of statute words covered and no duplicate ids. Tested in `tests/test_regs_parse.py`.
  - The corpus is now **4,319 chunks** and 177 listed sections. FCRA sections appear in `annotation/regulation_sections.md` as "15 U.S.C. 1681i", and labels use "1681i".
  - Tools updated: `reg_lookup.py` (`--reg FCRA`, statute kind) and `check_llm_labels.py` (accepts FCRA).
- **Relabel:** 36 NONE-because-FCRA items moved to FCRA sections: 1681i(a)(1) for CRA disputes, 1681i(a)(7) for method of verification, 1681c-2(a) for identity-theft blocks, 1681b(a), 1681e(b), and 1681s-2(a)(2)/(a)(6)/(b) for furnishers. Three NONE items stay NONE with corrected governing-law text. The full list is in `annotation/label_revisions.md`. The scratchpad holds a v1 copy only; the 3 pushed pilot lines are in git history.
- **Top-up:** `scripts/make_topup_sample.py` draws 78 items, hash-ordered and round-robin over sub-issues, excluding the classifier test set and the sample:
  - E: 30 from unauthorized, debit card, and banking-error sub-issues
  - Z: 36 from card purchase disputes, unauthorized charges, cards opened without consent, payment problems, and fees or interest
  - F: 12 from validation, notice, calls, and old-debt suit sub-issues

  Ids are in `annotation/annotation_topup_ids.txt`. 64% of the top-up landed in scope.
- **All 198 labelled by Annotator A** (claude-opus-5-5, skill), in batches of 10 to 12. Each batch passed `check_llm_labels.py` and an id-to-company cross-check. 5 runner-ups equal to the gold section were cleared.
  - **Final:** in scope **129** (E 29, F 32, Z 29, FCRA 36, V 3), NONE **69**. Confidence 1/2/3 = 45/99/54.
  - Top sections: 1005.11 ×25, 1681i ×19, 1006.18 ×12, 1681c-2 ×11, 1026.13 ×10, 1006.38 ×9, 1026.12 ×7.
- **New rubric conventions from the top-up**, all verified in the text:
  - Merchant disputes over authorized debit purchases are not Reg E errors (NONE).
  - Gift cards are excluded from "prepaid account" (1005.2, quoted: "(D)(1) A gift certificate ... (2) A store gift card"), so only 1005.20 applies.
  - Paper checks, business accounts, and wires: NONE.
  - A prepaid card denied only for late reporting: 1005.18(e)(1).
  - Credit card fraud: 1026.13(a)(1) if the issuer investigated and denied, 1026.12(b) if only the use is described.
  - No statement delivered before the due date: 1026.5(b)(2)(ii)(A).
  - Collector reporting before any contact: 1006.30(a)(1).
  - Written cease-communication notice ignored: 1006.6(c)(1).

  The single source of the rubric is now the conventions section of `.claude/skills/regulation-annotator/SKILL.md`, rewritten for FCRA and NONE; all 50 section numbers it cites were checked against the corpus.
- **Abstention** (`docs/INTERFACES.md` Sec. 7): every stage may output NONE.
  - The retriever exposes `abstain_score`; generation drafts a referral when abstaining.
  - Metrics: abstention P/R/F1 on all 198, retrieval P@k/R@k on the 129, and end-to-end accuracy.
  - The attribution experiment uses in-scope items only.
- **ChatGPT package regenerated:** 198 complaints, the FCRA text (`08_FCRA_1681.md`), the rubric auto-copied from the skill (`01_INSTRUCTIONS.template.md` -> `generated/01_INSTRUCTIONS.md`), and Claude's labels in `09_claude_labels.md` for step 2. `PROMPTS.md` now covers 10 batches of 20.
- `docs/INTERFACES.md`, `annotation/ANNOTATION_GUIDE.md`, and this file are updated. 50 unit tests pass.
- **Open:**
  - Run the ChatGPT cross-check.
  - Have a human adjudicate disagreements and spot-check 20 items.
  - Ratify the rubric conventions as a team.
  - Update CLAUDE.md's scope ("four regulations", "120 pairs", "human labels are ground truth") once the team agrees.
  - Tell the TA about the FCRA scope addition.

### 2026-10-15: Annotator B (ChatGPT) cross-check and agreement
- Aditya ran the package in ChatGPT. The model recorded itself as `llm:chatgpt-gpt-6` (model name as reported by ChatGPT, not verified). Outputs: `annotation/llm_labels_chatgpt.jsonl` (198 lines) and `annotation/chatgpt_review.jsonl` (26 lines, one per disagreement).
- **Validation:** `check_llm_labels.py` passes all 198 ChatGPT labels: sections exist and all quotes are verbatim.
- **Agreement (Claude A vs ChatGPT B, `compare_annotators.py`):**
  - Regulation level: 92.4%, **Cohen's kappa 0.904**.
  - Section level: 86.9%, **kappa 0.845**.
  - Abstention (NONE vs in scope): 95.5%, kappa 0.898.
  - By subset: sample 88.3%, top-up 84.6% section agreement.
  - By A's confidence: 66.7% (conf 1), 89.9% (conf 2), 98.1% (conf 3). Confidence is informative.
- **The 26 disagreements:**
  - 11 same regulation, different section (e.g. 1681i vs 1681c-2 on mixed dispute/identity-theft complaints; vague Reg Z interest complaints, where B chose 1026.13(a)(6)).
  - 9 NONE vs in scope.
  - 6 different regulation (mostly furnisher cases on the FCRA/Reg V/Reg F boundary).
  - B's own review preferred B in 13, A in 12, and neither in 1.
  - One note for the adjudicator: on 21757875, B's reason cites the prepaid rule (1005.18(e)(1)), but the card is Direct Express, a government benefit account, so 1005.15's modified rules may be the better reference.
- **Human steps remaining (annotators A and B must not adjudicate):**
  1. Fill `- **Final (human):**` for the 26 items in `annotation/disagreements.md` with `A`, `B`, or an explicit label, plus initials, e.g. `B [AD]`.
  2. Fill `- **Check (human):**` for the 20 agreed items in `annotation/spot_check.md` (hash-selected) with `OK` or a corrected label.
  3. Run `python scripts/build_gold.py`. It writes `annotation/gold_final.jsonl` only when every item is decided. The builder was tested with simulated decisions on copies: 198 written, source counts correct; the real files were restored with decisions blank.
- **Report wording:** silver labels from two LLM annotators of different families under a shared rubric, kappa 0.904 (regulation) and 0.845 (section), with human adjudication of disagreements and a 20-item human spot check.

### 2026-10-15: Overlap found with branch `chunking` (Ishani + Ujjwal, Pair B), not yet merged
- Branch `chunking` was cut from `classifier` at `09914e7`, before `regulation-corpus` existed, so the two branches built **regulation parsing and chunking twice**.
  - Theirs: `chunking/xml_parser.py`, `parse_regulations.py`, `chunk_regulations.py`; 2,629 chunks committed as `chunking/data/processed/chunks.jsonl`; 24 tests.
  - Ours: `src/cfpb/regs/parse.py` and `scripts/build_reg_corpus.py`, giving `data/processed/reg_chunks.parquet`.
- **Compared on 2026-10-15:**
  - **Source:** both use eCFR Title 12 as of 2026-10-13. Theirs is the bulk XML (AMDDATE Oct. 1, 2026); ours is the eCFR API.
  - **Coverage:** the same **136 regulation sections**; theirs has regulation text only (`content_type` = regulation).
  - **Annotation compatibility:** **all 93 Claude and all 100 ChatGPT regulation evidence quotes appear verbatim in their chunks** for the cited section, so the gold labels are fully compatible with their corpus. The only difference is paragraph format: theirs is relative (`(b)(1)`), ours is full (`1005.11(b)(1)`).
  - **Theirs has design features *expected* to help retrieval (untested; no retrieval run on either corpus yet):**
    - paragraph paths checked against eCFR renderer ids, with 0 mismatches after Ujjwal's `(i)` fix
    - chunk size tuned to the chosen embedding model, `all-mpnet-base-v2` (384 tokens, `--max-chars 1400`)
    - parent-paragraph intros carried into each chunk, plus `embed_text`
    - paragraph anchors in `source_url`
    - a fixed, committed corpus file
  - **Ours adds what theirs lacks:** the **FCRA statute** (249 chunks; 36 gold items are FCRA), **Supplement I official interpretations** (2,418 chunks; their open question 2), appendices (112), and the annotation tooling that reads the corpus (`reg_lookup.py`, `check_llm_labels.py`, `make_chatgpt_package.py`).
  - Ours also answers some of their open questions: Reg V sections verified (1022.40-.43), and section-level scoring plus abstention specified in `docs/INTERFACES.md`.
- **Recommendation (needs Pair B and the team):**
  - Choose the retrieval corpus by **measuring**, not by design argument: run the same retriever over both chunk sets on the 129 in-scope gold items, and compare section-level precision@k and recall@k (this is the planned chunking ablation; Pair B to own it). Until then, their `chunks.jsonl` is the default, because Pair B owns it and it is tuned to the chosen model.
  - Add the FCRA statute to it in their schema (and optionally Supplement I as a separate `content_type` for an ablation).
  - Point our annotation tools at it.
  - Retire `src/cfpb/regs/parse.py` for retrieval use.
  - Merge `regulation-corpus` and `chunking` with one reconciled `CLAUDE_PROGRESS.md`.
- **Conflicts to expect when merging:** `CLAUDE_PROGRESS.md` (both appended), `.gitignore`, `requirements.txt`, `README.md`. Also, `chunking/data/raw/ECFR-title12.xml` (39 MB) is committed on their branch, against working rule 5; their own log flags this.
- **Correction (same day):** the comparison above first said "theirs is stronger for retrieval". That was a design-based expectation, not a measurement. Their token counts and their 0-mismatch paragraph check come from their log and were not re-verified here; only the section coverage and the quote compatibility were checked directly.

### 2026-10-16: Gold set finalised (`annotation/gold_final.jsonl`)
- **Human adjudication by Aditya (initials AD), who is not one of the LLM annotators:**
  - 26 disagreements: took A in 12, B in 13, and an own label in 1. That one, 20834286, became NONE: both LLMs chose a Reg Z section, but the facts show bad payment-date advice, not a crediting failure.
  - 20-item hash-selected spot check of agreed items: **20/20 OK**, 0 corrected.
- **Final gold:** 198 items. **127 in scope** (E 29, F 30, Z 27, FCRA 36, V 5) and **71 NONE**. By source: 152 agreed, 20 agreed and spot-checked, 26 adjudicated. Every section exists and matches its regulation; every paragraph sits under its section; NONE items have no section; all 198 annotation items are covered.
- **Annotator accuracy against the final gold:**
  - Claude: regulation 0.965, section 0.929.
  - ChatGPT: regulation 0.949, section 0.934.
  - On the 26 disputed items: Claude 46.2%, ChatGPT 50.0% (section).
  - *Caveat:* these are inflated as overall measures, because 172 gold labels are the annotators' agreed labels. The informative numbers are the inter-annotator kappa, the 20/20 spot check, and the near-even split on disputed items.
- **Adjudicator's call to note:** 21757875 (a Direct Express government benefit card) was settled as B, `1005.18(e)(1)`, the prepaid late-reporting rule. Claude had flagged that the benefit-card rule 1005.15 might fit better. The gold keeps the human decision.
- `docs/INTERFACES.md` Sec. 3 now names `annotation/gold_final.jsonl` as the official gold set (JSONL, since `*.csv` is git-ignored).
- **Report wording:** 198 complaints labelled by two LLM annotators from different families (Claude Opus 5.5, ChatGPT) under a shared written rubric with verbatim-quote validation. Cohen's kappa 0.904 (regulation) and 0.845 (section); disagreements adjudicated by a team member; 20/20 human spot check. Gold: 127 in-scope complaint-to-section pairs plus 71 out-of-scope (NONE).

### 2026-10-16: Classifier interface frozen; issue-reporting rule decided
- **Interface frozen** (all pairs agreed): `docs/INTERFACES.md` Sec. 1, giving per complaint `pred_product`, `pred_product_prob`, `pred_issue`, `pred_issue_prob`.
- **Reporting rule (team decision):**
  - The headline is **product macro-F1 0.808** (test).
  - The issue classifier is reported as macro-F1 over all 84 issues present in test (**0.325**), plus macro-F1 over the **39 issues with at least 100 test examples (0.538, covering 91.7% of complaints)**, plus accuracy **0.581**, plus the **product-consistent rate 0.857** (the predicted issue is valid for the complaint's product).
  - The at-least-100 cutoff is fixed now, before writing, and the all-issue number is always shown next to it.
  - Frequent-issue macro-F1 is computed on the full test set, averaging only over the frequent labels. Do **not** drop the rows of rare issues, since that hides false positives (it gave an inflated 0.555).
  - No retraining with merged rare issues.
- All numbers are saved in `results/classifier_test_metrics.json`. The `results/` folder is tracked, for small numbers the report cites.

### 2026-10-18: Backend skeleton, single-complaint pipeline (branch `backend`, Anirudh + Claude)
- **Decision (Anirudh, assigned the backend):** no separate API server. The Streamlit demo imports the pipeline directly and caches it with `@st.cache_resource`. A thin FastAPI wrapper over the same `analyze()` can be added later if the UI and models must run on different machines.
- **Branch:** `backend`, cut from `regulation-corpus` at `ead53c7`, so it has the classifier, `docs/INTERFACES.md` and the gold set. Not merged with `chunking`.
- **What:** `src/cfpb/pipeline/`. `load_pipeline().analyze(narrative)` cleans the text with `clean_narrative`, then runs classify, retrieve, draft and verify, and returns a `PipelineResult` (dataclasses; `to_dict()` gives JSON-safe output). Field names follow `docs/INTERFACES.md` Secs. 1, 2, 4, 5 and 7.
  - **Stage contract** (`stages.py`), for Pairs B and C to implement: `classify(text) -> Classification`, `retrieve(text, k) -> Retrieval` (ranked chunks with text and `source_url`, plus `abstain_score` and `abstained`), `generate(text, context) -> Draft` (sentences aligned with cited chunk ids), `verify(draft, context) -> Verification`. Pass the real object to `Pipeline(...)`; nothing else changes.
  - **Abstention:** if the retriever abstains, the pipeline returns a fixed referral draft (wording from INTERFACES.md Sec. 7) and calls neither the generator nor the verifier, so NONE costs no LLM call.
  - **Classifier:** `DistilBertClassifier` wraps `ComplaintClassifier` for product (and issue, if present). `load_pipeline()` uses `outputs/classifier/{product,issue}/best` when present, else a stub with a warning; `require_models=True` raises instead.
  - **Stubs:** retriever, generator and verifier are placeholders marked `[stub]`, and verification labels are `unchecked`, never `supported`. `PipelineResult.stubbed_stages` lists them so the demo can label placeholder output.
  - `scripts/analyze_complaint.py --text "..."` prints the result as JSON; `--abstain` exercises the NONE path.
- **Tests:** `tests/test_pipeline.py`, 11 tests. Full suite: 53 passed, 2 skipped (torch not installed), Python 3.14.7, macOS, fresh `.venv` from `requirements.txt`.
- **Not verified:** the real `DistilBertClassifier` path. This machine has no torch and no model weights, so only the stub classifier ran. Check with the `best/` folders from Drive before the demo relies on it.
- **Next:**
  1. Wire in the real classifier and time it on CPU (about 3 narratives/sec was measured on Aditya's laptop).
  2. Swap in Pair B's retriever once the corpus is chosen (`chunking` vs `regulation-corpus`, Sec. 7 2026-10-15). The `RetrievedChunk` fields map to either corpus.
  3. With Pair C: the LLM generator with response caching (`cache_key`, INTERFACES.md Sec. 4) and the NLI verifier.

### 2026-10-19: Real classifier, corpus loader, oracle retriever, batch runner, demo page (branch `backend`, Anirudh + Claude)
- **Local files** (git-ignored), from Drive: `outputs/classifier/{product,issue}/best/` (safetensors, about 268 MB each) and `run_info.json`, plus `data/processed/annotation_sample.csv`. Both `run_info.json` files report 111,527 train rows, the v2 baseline, and their label lists match the models' `config.json`. They predate the 2026-10-15 rescoring (no `"rescored"` key, issue test macro-F1 shows 0.310); this does not affect predictions.
- **Real classifier verified** through `load_pipeline(require_models=True)` on macOS (CPU, torch 2.14.1, transformers 5.20.2, Python 3.14.7). Loading both models takes about 4 s. Classification on the 120 sample complaints: median 43 ms, p90 78 ms, max 511 ms per complaint. Predicted product matches the consumer-chosen product on 110 of 120 and issue on 79 of 120. **This is a sanity check, not a metric:** the sample excludes the classifier test set but may overlap train.
- **Corpus:** rebuilt `data/processed/reg_chunks.parquet` with `scripts/build_reg_corpus.py --date 2026-10-13`. It gives 4,319 chunks, as logged on 2026-10-15, and `annotation/regulation_sections.md` came out byte-identical. `Corpus.load` also reads the `chunking` branch's `chunks.jsonl` (2,629 chunks); a copy is in `data/processed/chunks_chunking.jsonl`, extracted with `git show`. Paragraphs are normalised to full form (`(c)(2)` becomes `1005.11(c)(2)`).
- **Oracle retriever** (`OracleRetriever(...).for_complaint(id)`, passed per call via `Pipeline.analyze(..., retriever=...)`): returns the gold section's regulation and statute chunks; interpretations are left out by default (an ablation). Chunks containing or contained in the gold paragraph come first (score 1.0), then the rest of the section (0.5), in document order. NONE abstains.
  - On `reg_chunks.parquet`, all 127 in-scope gold items get a gold-paragraph chunk at rank 1, and all 71 NONE items abstain. The gold section has a median of 8 rule chunks per in-scope item (max 35).
  - On the chunking set, 91 of 127 items work, again all with a paragraph match at rank 1. The other 36 are FCRA, which it does not contain.
  - The **oracle passage size** (whole section vs the gold paragraph only) is still the open question from the 2026-10-14 chunking entry. Here it is the top k chunks (default 5).
- **Batch runner** (`scripts/run_pipeline_batch.py --retriever oracle|stub`) writes `classification`, `ranked`, `responses` and `sentences` Parquet tables (INTERFACES.md Secs. 1, 2, 4, 5) plus `run_info.json`. An oracle run on the 120 sample items took 6.6 s with the real classifier: 43 abstentions, exactly the NONE items. Each rank-1 section equals the gold section, as expected for the oracle. The 78 top-up items are skipped until `data/processed/annotation_topup.csv` is present.
- **Demo page** (`demo/app.py`): sidebar with the retriever (default or oracle), k, and a gold-set complaint picker; panels for classification, retrieved passages with citations and source links, the draft with per-sentence colouring, and the sentence-check table. Stubbed stages carry a "Placeholder" badge. Checked in the desktop browser preview on 23571192 (oracle 1005.11(d) at rank 1, gold 1005.11(d)(1)) and on a NONE mortgage complaint (referral shown).
  - Two fixes from that check: a referral no longer counts `generate`/`verify` as stubbed, since neither runs; and classification moved from `st.metric` to text, because metric boxes cut off long issue names.
- **Secrets:** `.env` and `.streamlit/secrets.toml` added to `.gitignore`, ready for the LLM key.
- **Tests:** 72 passed (macOS, `.venv` with `requirements-demo.txt`), including the two real-data checks: the oracle over all 198 gold items, and the real classifier.
- **Next:**
  1. Add `annotation_topup.csv` (ask Aditya) so the batch runner and demo cover all 198 items.
  2. Plug in the real retriever once built.
  3. Settle the oracle passage size with the retrieval and generation owners.

### 2026-10-19: Retriever adapters, latest regulation-corpus merged, test metrics in the demo (branch `backend`, Anirudh + Claude)
- **Merged `origin/regulation-corpus` (`36ac64f`) into `backend`:** brings the frozen classifier interface and `results/classifier_test_metrics.json`. The only conflict was this file, where both sides appended entries; both are kept, in date order. The batch runner's `classification.parquet` already uses the frozen names (`pred_product`, `pred_product_prob`, `pred_issue`, `pred_issue_prob`), plus three extra columns.
- **Why adapters:** BM25 is assigned to Pair B on a new branch `retrieval-bm25` (Sec. 6.5.6, on `chunking`). It will deliver the INTERFACES.md Sec. 2 forms: a function `retrieve(query, k) -> [{chunk_id, score}]` and `outputs/retrieval/<run>/ranked.parquet`. The pipeline also needs chunk text and citations, so `src/cfpb/pipeline/retrievers.py` looks the ids up in the corpus the retriever indexed:
  - `FunctionRetriever(fn, corpus, name, min_top_score=None)`: live retrieval in the demo or pipeline.
  - `PrecomputedRetriever(ranked_path, corpus, min_top_score=None).for_complaint(id)`: replays a ranked file, bound per complaint like the oracle. It honours an `abstained` column when present.
  - **Abstention:** with `min_top_score`, a complaint abstains when its top score is below the threshold (Sec. 6.5.6 uses the top BM25 score as the abstain signal). `abstain_score` is the negated top score. Abstaining results keep their ranked chunks for evaluation; the pipeline still drafts a referral.
  - An unknown `chunk_id` raises an error that names the corpus, so a corpus mismatch is caught at once.
- **Corpus:**
  - `Corpus.load(path, kinds=...)` filters by kind.
  - `Corpus.merge(...)` combines files.
  - `load_corpus(["chunks.jsonl", "reg_chunks.parquet::statute"])` builds Pair B's planned corpus (their chunks plus the FCRA statute rows): **2,878 chunks** (2,629 + 249).
  - Rows appended with only the INTERFACES fields (no `regulation` or `kind`, as in the Sec. 6.5.6 quick pass) get both inferred from the section number.
  - The real corpora load with unchanged counts (4,319 and 2,629).
- **Batch runner:** `--retriever precomputed --ranked <file> --corpus <specs...> [--min-top-score t]`. Checked by replaying `oracle-sample-smoke/ranked.parquet` (20 items), and by an oracle run on Pair B's planned corpus (`--corpus data/processed/chunks_chunking.jsonl data/processed/reg_chunks.parquet::statute`, all 120 sample items, 6.3 s).
- **Demo:**
  - New retriever mode **"Precomputed rankings"**. It lists every `outputs/retrieval/*/ranked.parquet` and `outputs/pipeline_runs/*/ranked.parquet`, offers only complaints that file ranks, and resolves chunk ids across every chunk file present locally.
  - When the classifier is real, the classification panel shows the **test metrics from `results/classifier_test_metrics.json`**. Per the team's reporting rule, the all-issue macro-F1 (0.325) always appears next to the at-least-100-examples number (0.538).
  - Checked in the browser preview on 23571192 with the Pair B corpus run: Pair B's chunk `1005.11(d)(1)` comes first, exactly the gold paragraph.
- **Tests:** 81 passed (9 new in `tests/test_pipeline_retrievers.py`, including a round trip of the batch runner's own `ranked.parquet`).
- **For Pair B:** with `outputs/retrieval/bm25/ranked.parquet` saved locally, the demo picks it up with no code change. For live use, pass `FunctionRetriever(bm25.retrieve, load_corpus([...]), "bm25", min_top_score=...)` to `Pipeline`.

