# CLAUDE_PROGRESS.md: Build Log and Handoff Context

Companion to `CLAUDE.md`. `CLAUDE.md` holds the project's fixed decisions (scope, methods, related work, deliverables, rules for graded work). **This file is the living engineering log**: what code exists, what has been run, what we found in the data, and what comes next. Last updated 2026-10-19 (branch `chunking`).

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
| 2. Regulation corpus and retrieval | B | `chunking` | **Chunking complete. Retrieval default:** 2,954 chunks in tracked `chunking/data/processed/chunks.jsonl`: 2,629 regulation-text chunks plus 325 model-tuned FCRA chunks (`--max-chars 1400`, `all-mpnet-base-v2`, 384 tokens, `embed_text`). The alternative `data/processed/reg_chunks.parquet` corpus has 4,319 chunks including interpretations and appendices for ablations. **Retriever not started; BM25 baseline is next (Sec. 6.5.6, new branch `retrieval-bm25`).** |
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

**Pair B: retrieval.** **Next: BM25 baseline on a new branch `retrieval-bm25`, as specified in Sec. 6.5.6.** Then dense (`all-mpnet-base-v2` + FAISS) and hybrid, following `docs/INTERFACES.md` Sec. 2 and Sec. 7 (abstention). Use the fixed 2,954-chunk corpus by default and evaluate the alternative corpus as an ablation.

**Everyone.** Draft the annotation rubric (two people), including the "no in-scope section" label, then annotate `annotation_sample.csv` with overlap for inter-annotator agreement.

---

## 6.5 Regulation corpora: our implementation, FCRA, design decisions, and the BM25 task (added 2026-10-19 when `regulation-corpus` was merged into `chunking`)

Branch `chunking` (Pair B, Ishani + Ujjwal) now also contains all of branch `regulation-corpus` (Aditya + Claude). That includes a **second, independently built regulation corpus**, the **FCRA statute**, the annotation work, and the **gold set**. This section records everything about the `regulation-corpus` side so Pair B can decide what to keep. Pair B owns chunking and retrieval from here.

### 6.5.1 Two corpora now in this branch

| | Pair B corpus (retrieval default) | `regulation-corpus` corpus |
|---|---|---|
| Code | `chunking/xml_parser.py`, `parse_regulations.py`, `chunk_regulations.py` | `src/cfpb/regs/ecfr.py`, `parse.py`, `fcra.py`; `scripts/build_reg_corpus.py` |
| Output | `chunking/data/processed/chunks.jsonl` (tracked) | `data/processed/reg_chunks.parquet` (git-ignored; regenerate with `python scripts/build_reg_corpus.py`) |
| Source | bulk eCFR Title 12 XML (AMDDATE Oct. 1, 2026; snapshot 2026-10-13) + FCRA from U.S. Code 2024 edition | eCFR API point-in-time **2026-10-13**; FCRA from U.S. Code 2024 edition |
| Content | regulation text of Parts 1005, 1006, 1022, 1026 **+ FCRA statute** | regulation text **+ FCRA statute + Supplement I official interpretations + appendices** |
| Chunks | **2,954** (regulation 2,629; statute 325) | **4,319** (regulation 1,540; interpretation 2,418; appendix 112; statute 249) |
| Sections | 136 regulation sections + 31 FCRA sections (167 total) | the same 167 sections |
| Sized for | `all-mpnet-base-v2` (384 tokens), `--max-chars 1400`, parent intros, `embed_text` | **not tuned to any embedding model**: word-based limit of 350 words (see 6.5.3) |
| chunk_id | `12-1005-1005.11-c-2`, `15-fcra-1681i-a-piece-1` | `R:1005.11(c)(2)`, `I:1026.13(b)(1)~1`, `A:1026 Appendix G~3`, `S:1681i(a)(1)`, with `#k` for word-window pieces |
| Tests | `tests/test_chunk_regulations.py` (27) | `tests/test_regs_parse.py` (4, including FCRA) |

**Gold compatibility (checked 2026-10-19):** the gold set is labelled by **section** (`gold_section`, e.g. `1005.11` or `1681i`), so it can be scored against either corpus. All FCRA gold sections are present in Pair B's corpus, and all 70 FCRA evidence quotes from the two LLM label files occur verbatim in the cited section's chunks.

### 6.5.2 Sources and download facts (all verified when run)
- **eCFR API** (`src/cfpb/regs/ecfr.py`):
  - Full text: `https://www.ecfr.gov/api/versioner/v1/full/2026-10-13/title-12.xml?part=<n>`. **It returns HTTP 406 unless the request sends `Accept-Encoding: gzip`.**
  - Table of contents: `.../structure/<date>/title-12.json?part=<n>`.
  - Title 12 was up to date as of 2026-10-13. XML sizes: 1005 0.86 MB, 1006 0.23 MB, 1022 0.27 MB, 1026 3.95 MB. Saved to `data/raw/ecfr/`.
- **FCRA** (`src/cfpb/regs/fcra.py`):
  - GovInfo `https://www.govinfo.gov/content/pkg/USCODE-2024-title15/html/USCODE-2024-title15-chap41-subchapIII.htm` (513 KB, U.S. Code 2024 edition, current through 2025-01-06), covering 15 U.S.C. 1681-1681x.
  - Saved to `data/raw/fcra/`. Per-section citation links use `https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title15-section<n>`.

### 6.5.3 Our chunking design (`src/cfpb/regs/parse.py`, `fcra.py`)

**Principle:** chunk by legal structure, not fixed token windows (CLAUDE.md Sec. 4). Each chunk is labelled with its `section` and its most specific `paragraph`.
- **`regulation` (rule text):**
  - One chunk per **top-level paragraph** `(a)`, `(b)`, ...
  - Text before `(a)` becomes the section's own chunk.
  - A top-level paragraph over **350 words** is split at its numbered subparagraphs `(1)`, `(2)`, ... (ids such as `R:1006.34(b)(1)`).
  - Only a piece still over **700 words** falls back to 350-word windows (`#1`, `#2`, ...).
  - **Roman vs letter `(i)`:** a marker is roman if the previous marker is the preceding numeral, or the next is the following numeral (`(i)` followed by `(ii)`). This keeps `1006.18(b)(i)`-`(vii)` inside `(b)` while still recognising a real top-level `(i)` (e.g. `1026.13(i)`). Unit-tested.
- **`interpretation` (Supplement I, official commentary):**
  - Grouped under commentary headings (`Section 1026.13—...`, `13(b) ...`, `Paragraph 6(a)(1)`) and mapped to the section or paragraph they interpret (97.8% map to a rule section; the rest is appendix commentary).
  - Groups over 350 words are split between numbered comments (`1.`, `2.`, ...).
- **`appendix`:** consecutive blocks packed up to 350 words.
- **`statute` (FCRA):**
  - Only the law text, between `field-start:statute` and `field-end:statute`; editorial and amendment notes are dropped.
  - One chunk per subsection `(a)`, `(b)`, ...; long subsections split at paragraph headings `(1)`, `(2)`, ...; a heading-only first piece is merged into the next.
- **Fields** (dataclass `Chunk`): `chunk_id`, `regulation` (E/F/V/Z/FCRA), `part`, `kind`, `section`, `paragraph`, `heading`, `text`, `n_words`, `source_url`.
- **Size statistics (words per chunk):**

  | kind | count | median | 90th percentile | max |
  |---|---:|---:|---:|---:|
  | regulation | 1,540 | 94 | 334 | 670 |
  | interpretation | 2,418 | 212 | 377 | 694 |
  | appendix | 112 | 322 | 348 | 475 |
  | statute | 249 | 113 | 350 | 573 |

  401 chunks are word-window pieces (interpretation 281, regulation 99, statute 21).
- **Coverage:** 99.3% to 100% of source words land in chunks (the dropped text is heading-only blocks); FCRA is 100%.
- **"Chunking model" (what the sizes are tuned to):** **none.** Our limit is in words (350), chosen before an embedding model was picked. Token lengths under `all-mpnet-base-v2` were **not measured**, so a share of our chunks probably exceeds its 384-token limit and would be truncated. Measure with Pair B's tokenizer before indexing our corpus with that model. Pair B's corpus *is* tuned to it.

### 6.5.4 Design decisions behind this corpus (and status)
1. **FCRA statute added (team decision 2026-10-15).** The first 120 annotations gave 64% NONE, 36 of them governed by the FCRA itself: CRA reinvestigation (1681i), identity-theft blocks (1681c-2), permissible purpose (1681b), and furnisher duties (1681s-2). Reg V does not implement these. **Scope is now Regs E/F/V/Z + FCRA**; CLAUDE.md still says four regulations (update pending a team decision; tell the TA).
2. **Interpretations and appendices are kept as separate `kind`s**, so retrieval can include or exclude them as an ablation. Pair B's open question "Supplement I has no owner" is covered here.
3. **Gold and scoring are section-level.** A retrieved chunk is a hit if `chunk.section == gold_section`; paragraph hits are secondary (`docs/INTERFACES.md` Sec. 2).
4. **NONE is a first-class abstention outcome** (`docs/INTERFACES.md` Sec. 7). 71 of 198 gold items are NONE. Retrieval is scored on the 127 in-scope items; abstention P/R/F1 is scored on all 198.
5. **Pinned to one date** (eCFR 2026-10-13) for reproducibility; gold quotes were validated against this text.
6. **Reg V sections verified:** 1022.40 Scope, 1022.41 Definitions, 1022.42 accuracy and integrity policies, 1022.43 Direct disputes. Reg V has no Supplement I.
7. **The annotation tools read this corpus:** `scripts/reg_lookup.py`, `scripts/check_llm_labels.py` (verbatim-quote check), and `scripts/make_chatgpt_package.py`. If it is retired, repoint them at the chosen corpus first.

### 6.5.5 What is decided vs open
- **Decided:** gold set (`annotation/gold_final.jsonl`); section-level scoring; abstention; FCRA in scope.
- **Open, for Pair B:**
  - **Which corpus to index.** Default: Pair B's, because they own it and it is model-tuned. The claim that it "retrieves better" is **untested**, so decide by measurement (6.5.6).
  - Whether to index interpretations.
  - Remove the 39 MB `chunking/data/raw/ECFR-title12.xml` from git before merging to `main` (working rule 5).

### 6.5.6 TODO for Pair B: BM25 baseline (do this on a NEW branch)

```bash
git fetch origin
git checkout -b retrieval-bm25 origin/chunking     # chunking now includes the gold set and FCRA code
```

1. **Corpus:** Pair B's `chunking/data/processed/chunks.jsonl`; index `embed_text` and return `text` for generation/citation. It contains the FCRA. Report results **with and without FCRA** using the chunker's `--no-fcra` option; without it, 36 FCRA gold items have no correct chunk.
2. **Queries and gold:**
   - Query text = `narrative_clean` of the annotation items (`from cfpb.annotation import load_items`; 198 items: 120 sample + 78 top-up).
   - Gold = `annotation/gold_final.jsonl` (`gold_regulation`, `gold_section`).
3. **Retriever:** `rank_bm25.BM25Okapi` (add `rank-bm25` to requirements). Lowercase, alphanumeric tokens; stopword removal optional (log the choice).
4. **Metrics on the 127 in-scope items (section level):**
   - Deduplicate ranked chunks by section, keeping the first occurrence.
   - Report hit@k and recall@k for k = 1, 5, 10 (one gold section per item), and MRR.
   - Break down by regulation (E 29, F 30, Z 27, FCRA 36, V 5).
5. **Abstention on all 198:** use the top BM25 score as the abstain signal. Report AUROC (in scope vs NONE) and P/R/F1 at a threshold. If you tune the threshold, tune it on a fixed half of the items and report on the other half; 198 items is small.
6. **Outputs:**
   - Ranked lists: `outputs/retrieval/bm25/ranked.parquet`, in the format of `docs/INTERFACES.md` Sec. 2 (`complaint_id`, `retriever`, `corpus`, `rank`, `chunk_id`, `score`).
   - Numbers: `results/retrieval_bm25.json` (tracked).
   - Add a dated entry to Sec. 7.
7. **Chunking ablation (optional, cheap with BM25):** run the same BM25 on `reg_chunks.parquet` (regulation + statute, then also + interpretation) and compare section-level hit@k. This replaces the untested "which corpus is better" argument with a measurement.
8. **Rules:**
   - Do not edit `annotation/gold_final.jsonl`.
   - Keep the gold items out of any training.
   - Commits and pushes on `retrieval-bm25`; open a PR into `chunking` (or `main`, once merged) when done.

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

### 2026-10-14: Embedding model chosen; chunk size set to 1,400 chars (Ishani + Claude)
- **Decision (Ishani with Ujjwal):** retrieval uses `sentence-transformers/all-mpnet-base-v2`. Its `max_seq_length` is 384 tokens (from the model's `sentence_bert_config.json`); longer input is cut from the end, and the 2 special tokens count toward the 384.
- **Measurement:** every chunk tokenized with the model's own tokenizer (`tokenizers` 0.23.3 in the repo `.venv`, tokenizer files only, no model weights). The shipped `tokenizer.json` pads and truncates to 128 tokens, so both must be turned off before counting. Regulation text averages about 4.5 chars per token, so 384 tokens is roughly 1,700 chars.

  | `--max-chars` | Chunks | Avg tokens | Over 384 | Could be split further | Cannot be split |
  |---:|---:|---:|---:|---:|---:|
  | 2000 | 2,104 | 198 | 160 | 124 | 36 |
  | 1500 | 2,519 | 181 | 69 | 3 | 66 |
  | 1450 | 2,566 | 179 | 67 | | |
  | **1400** | **2,629** | **177** | **66** | **0** | **66** |
  | 1200 | 2,920 | 168 | 66 | 0 | 66 |
  | 1000 | 3,262 | 159 | 66 | 0 | 66 |
  | 800 | 3,599 | 151 | 66 | 0 | 66 |

  "Cannot be split" means a paragraph with no sub-paragraphs that is over the character limit. Smaller limits only add chunks once the over-384 count reaches 66.
- **Change:** `MAX_CHARS` (default of `--max-chars`) is now 1400, the largest value that reaches 66. `chunks.jsonl` regenerated locally (not committed): 1005: 395 chunks; 1026: 1,706; 1022: 409; 1006: 119; total 2,629, 66 over 384 tokens. Tests: 1005.11 now gives 14 chunks at the default (the old 8-chunk test is pinned to 2,000), and the parent-intro check also runs at 1,400. 17 tests pass (plain Python loop).
- **The 66 that no limit fixes:** only 8 are over 384 tokens because the paragraph itself is (e.g. 1022.30(e)(6), 651 tokens). The other 58 are over because of the parent intros the team rule requires (e.g. every 1026.20(c)(2) chunk repeats the (c) and (c)(2) intros, about 400 tokens together). Because the model cuts from the end and a chunk's own text comes last, **15 chunks lose their own text entirely and 30 lose more than half** (e.g. `1026.20-c-2-v-A`: 9 tokens of its own after about 420 of intros; first logged as 11, which wrongly included the 2 special tokens). Next: measure shortening parent intros to their headings for these chunks (team decision needed, since it changes the parent-intro rule).

### 2026-10-15: `embed_text` field for the search index (Ishani + Claude)
- **What:** every chunk now has `embed_text`, placed right after the seven agreed fields. It equals `text`, except when `text` is over 384 tokens for `all-mpnet-base-v2` (counted with its tokenizer, special tokens included, padding and truncation off). Then each parent intro is cut to its heading: up to the first dash, or the first period followed by a space (so "1026.20" is not a cut point). The chunk's own paragraphs are never cut. **`text` is unchanged** and remains the full legal text for generation and the NLI verifier; **embed `embed_text`** (and use it for BM25 too, or decide otherwise as a team).
- **Why:** the model cuts input from the end, and a chunk's own text comes after its parent intros, so before this 15 chunks were embedded without any of their own words (Sec. 7, chunk-size entry above).
- **Result (all four parts, `--max-chars 1400`):** `embed_text` differs from `text` for 63 chunks. Over 384 tokens: 66 by `text`, **9 by `embed_text`**. Of the 9, 8 are single paragraphs that are long on their own (e.g. 1022.30(e)(6), 649 tokens without special tokens); 1 (`1026.36-f-3-ii-A-2-iii`) has parent intros that are lead-in sentences with no heading to cut to. No chunk's `embed_text` loses all of its own text any more.
- **Cost:** the shortened intros drop legal content that `text` keeps, e.g. in `1026.34-a-4-iii-B-1` "(iii) Presumption of compliance." loses "a creditor is presumed to have complied with this paragraph (a)(4) … if the creditor:".
- **Dependency:** `chunk_regulations.py` now needs the `tokenizers` package (0.23.3 tested; listed in `requirements.txt`) and downloads the model's tokenizer from Hugging Face on first use (about 0.5 MB, then cached). Without the package it stops with install instructions. Run it with the repo venv: `cd chunking && ../.venv/bin/python chunk_regulations.py`.
- **Tests:** 24, all passing (plain loop in `.venv`). New: field order, `heading_only` cases, shortening on a synthetic record, the missing-package message, `embed_text` never more tokens than `text` (and equal when `text` fits), and `text` unchanged. That check compares a SHA-1 over every chunk's id and text to fingerprints taken before this change (`8f7b9f2`): 2,629 chunks at 1,400 and 2,104 at 2,000.
- **Correction:** the chunk-size entry above first said `1026.20-c-2-v-A` has 11 tokens of its own; it has 9 (the 11 included the 2 special tokens). Fixed in place.

### 2026-10-15: `chunks.jsonl` is now tracked in git, on purpose (Ishani + Claude)
- **What:** `chunking/data/processed/chunks.jsonl` is committed as the **fixed regulation corpus** for retrieval and evaluation: 2,629 chunks (regulation text of Parts 1005, 1026, 1022, 1006), `--max-chars 1400`, with `embed_text` (9 chunks over 384 tokens by `embed_text`, 66 by `text`). 5.0 MB, SHA-1 `0817b6f8ea4a08358a1e6fd28e547d153051308c`. Verified byte-identical to a fresh run of `chunk_regulations.py` at `81706b5`.
- **Why:** everyone, including Colab runs from a code ZIP, must index and score against the same chunks. Gold labels, retrieval results (precision@k, recall@k) and the oracle passages refer to `chunk_id`s, so silently different local chunks would make numbers incomparable. Regenerating also needs the `tokenizers` package and a Hugging Face download, which a fixed file avoids.
- **Exception to working rule 5** ("Never commit data", Sec. 0): this is a deliberate exception for a small derived file that defines an experiment input, like `data_fingerprint.json`. Its inputs (`sections.jsonl`, the part XML) are already tracked under `chunking/data/`.
- **When to regenerate:** only on purpose, if the parser, the chunker or `--max-chars` changes. Then commit the new file in the same commit as the code change, log the new SHA-1 and chunk count here, and tell Pair C and the eval owner, since `chunk_id`s may change.

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


### 2026-10-19: `regulation-corpus` merged into `chunking` (Aditya + Claude)
- At Aditya's request, branch `regulation-corpus` was merged into Pair B's `chunking` branch, so Pair B (owner of chunking and retrieval) has everything in one place: the FCRA corpus code, our second regulation corpus, the annotation tooling, both LLM label files, and the final gold set.
- The only merge conflict was this file. Both sides were kept: the status table now has one classifier row (v2 results) and one corpus row describing both corpora, and the log keeps Pair B's 10-14/10-15 entries followed by ours.
- Added **Sec. 6.5**: both corpora compared; sources; our chunking design and statistics; the explicit note that our chunks are **not tuned to any embedding model**; design decisions (FCRA, interpretations, section-level scoring, abstention); open items; and the **BM25 baseline task for Pair B on a new branch `retrieval-bm25`** (Sec. 6.5.6).
- No Pair B files were modified.

### 2026-10-19: Chunking completed with FCRA
- Ported the FCRA into `chunking/chunk_regulations.py` and Pair B's fixed JSONL schema. The default build now downloads/parses the GovInfo U.S. Code 2024 HTML when needed; `--no-fcra` reproduces the four-regulation ablation.
- FCRA chunks keep legal subsection/paragraph structure, repeat the section heading, and pack to both `--max-chars 1400` and the `all-mpnet-base-v2` 384-token limit. Oversized statutory blocks split first at sentence boundaries and then, only when necessary, at word boundaries. All 249 source statute chunks are covered without text loss; the fixed representation has 325 chunks across 31 sections, max 1,400 chars and 354 tokens.
- Regenerated `chunking/data/processed/chunks.jsonl`: **2,954 unique chunks** (E 395, Z 1,706, V 409, F 119, FCRA 325), SHA-1 `9928d5f3e676de365761b474e30a43d4691c25a6`. Overall, 66 full `text` values exceed 384 tokens because of existing regulation parent context, while only the same 9 existing regulation `embed_text` values exceed it; **0 FCRA `embed_text` values exceed 384**.
- Gold compatibility: all 5 distinct FCRA gold sections are present, and all 70 FCRA evidence quotes across the two LLM label files occur verbatim in their cited section's fixed chunks.
- Gold data remains deliberately separate from corpus construction: `chunk_regulations.py` does **not** read or tune against `annotation/gold_final.jsonl`. Retrieval evaluation will join a ranked chunk to the official 198-item gold set by `chunk.section == gold_section`; the 71 `NONE` items intentionally have no matching chunk. Of the 127 in-scope pairs, 36 are FCRA cases.
- Paths are script-relative: `DEFAULT_SECTIONS_PATH` and `DEFAULT_OUT_PATH` resolve under `chunking/data/processed/`, while `DEFAULT_FCRA_PATH` resolves under repository-level `data/raw/fcra/`. The chunker can therefore be run from either the repository root or `chunking/` without explicit path arguments.
- Tests: `tests/test_chunk_regulations.py` now has 28 tests, including FCRA schema, boundary packing, fixed-corpus integrity, token limits, evidence-quote coverage, and script-relative path defaults. Together with the 4 parser tests, **32/32 pass under pytest** (`Python 3.13.0`, `tokenizers 0.23.3`, `pytest 9.1.1`). The real-corpus source-coverage check above also passed.
- Updated `docs/INTERFACES.md` to make the 2,954-chunk tracked JSONL the retrieval default and retain `reg_chunks.parquet` for interpretation/appendix and chunking ablations. Chunking is complete; BM25 is next and remains a separate retrieval task.

### 2026-10-19: BM25 baseline on branch `retrieval-bm25`
- **Code:** `src/cfpb/retrieval/bm25.py` (`BM25Retriever`: `retrieve(query, k)` per INTERFACES Sec. 2, plus section-deduplicated ranking), `src/cfpb/retrieval/metrics.py`, `scripts/run_bm25.py`, `tests/test_bm25.py` (5 tests, pass). `rank-bm25` is now enabled in `requirements.txt`.
- **Setup:** `rank_bm25.BM25Okapi` (k1 1.5, b 0.75) over `embed_text`; queries are `narrative_clean`; tokens are lowercase `[a-z0-9]+`. Two variants: no stopword removal (main, `results/retrieval_bm25.json`) and sklearn English stopwords removed (`results/retrieval_bm25_stopwords.json`). Section-level hits, sections deduplicated keeping first occurrence, on the 127 in-scope items. Ranked lists (top 10 chunks per complaint) go to `outputs/retrieval/bm25/` and `bm25_no_fcra/` (git-ignored).
- **Results, main variant (127 in-scope items):**

  | Corpus | hit@1 | hit@5 | hit@10 | MRR |
  |---|---:|---:|---:|---:|
  | with FCRA (2,954 chunks) | 0.079 | 0.315 | 0.457 | 0.196 |
  | without FCRA (2,629 chunks) | 0.055 | 0.220 | 0.339 | 0.144 |

  recall@k equals hit@k (one gold section per item); precision@k = hit@k / k. With stopwords removed, with FCRA: 0.071 / 0.362 / 0.496, MRR 0.219. Per-regulation numbers are in the JSON files (with FCRA, hit@10: E 0.28, F 0.53, Z 0.33, FCRA 0.61, V 0.60; V has only 5 items).
- **Observations:** (1) On the 91 non-FCRA items, hit@10 is 0.473 without the FCRA chunks, against 0.396 with them in the index (E drops from 0.45 to 0.28). The FCRA chunks therefore displace correct regulation sections under BM25. (2) Stopword removal helps hit@5/10 modestly; it is a single run on 127 items, so differences of a few points are not established.
- **Abstention (top BM25 score as signal, all 198):** AUROC is **0.43** (0.49 with stopwords), at or below chance. Long narratives score high whether or not a section governs them, so the raw top score is not a usable abstain signal. The threshold was tuned on a fixed SHA-1 half and reported on the other (91 items, 26 NONE): P/R/F1 0.28 / 0.96 / 0.43, which is close to abstaining on nearly everything. A normalised score (for example top score divided by query length) is a cheap thing to try for the dense and hybrid retrievers.
- **Not done:** the optional chunking ablation on `reg_chunks.parquet` (Sec. 6.5.6 item 7).

### 2026-10-19: Generator, NLI verifier and attribution pilot (branch `generation-verification`, Aditya + Claude)
- **Branch:** `generation-verification`, cut from `origin/backend` (Anirudh's pipeline skeleton) with `origin/retrieval-bm25` merged in, so it has the classifier, Pair B's 2,954-chunk corpus (with FCRA), BM25, the gold set and the backend. The only conflict was this file; both logs kept.
- **Target LLM (decision 2026-10-19, Aditya):** NVIDIA Nemotron through the NVIDIA API catalog, default model id `nvidia/nemotron-3-super-120b-a12b` (picked from the public `/v1/models` list on 2026-10-19). Temperature 0. Keep it fixed for every reported number. The key goes in `NVIDIA_API_KEY` (environment or git-ignored `.env`); never commit it.
- **Stage 3, `src/cfpb/generate/nemotron.py`:** `NemotronGenerator` implements the backend's `Generator` protocol. The prompt (`PROMPT_VERSION` = hash of the prompt text) asks for 3 to 6 sentences using only the given passages, each ending with `[P#]` tags; `[NONE]` if the passages do not apply. Tags are mapped to `cited_chunk_ids`; `<think>` blocks are stripped. Every call is cached in `outputs/generation/cache/<sha1>.json` keyed on model, prompt version, decoding settings, complaint and context.
- **Stage 4, `src/cfpb/verify/nli.py`:** `NLIVerifier` implements `Verifier`, following SummaC: each sentence is checked against its cited chunks (all context if none), split into 400-token windows (stride 300); `entail_prob` = max over windows, `contradict_prob` from that window; supported if `entail_prob >= 0.5` (to be tuned on the checker set). Model `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`.
  - Sanity check on Reg E 1005.11(c): correct paraphrase 0.992 entail; invented "refund within 24 hours" 0.001; wrong "60 business days" 0.997 contradiction; courtesy sentence 0.009. About 6 s per pair on CPU (torch is the CPU build).
- **Wiring:** `load_pipeline(generator=..., verifier=...)`; `scripts/run_pipeline_batch.py` gains `--generator {stub,nemotron}`, `--verifier {stub,nli}`, `--ids FILE`, and records the generator and verifier settings in `run_info.json`. Stubs stay the default, so the demo is unchanged.
- **Attribution pilot, `scripts/attribution_pilot.py`:** `select` wrote `annotation/pilot_ids.txt`: 41 in-scope gold items (9 each E, F, Z, FCRA; all 5 V; SHA-1 order). Run the batch twice (BM25 top-5 as `retrieved`, gold-section chunks as `oracle`), then `report` writes `results/attribution_pilot.json`: % supported per condition, the paired gap with a bootstrap 95% CI, the gap split by whether BM25's top 5 contained the gold section, and per-regulation rates.
- **Checker validation (M1), `scripts/checker_benchmark.py`:** `sample` takes 50 pilot sentences (25 per condition, SHA-1, not by checker score) into `annotation/checker_set.jsonl` and a blind `checker_set.md`; two LLM annotators of different families label them; `compare` gives kappa and `checker_disagreements.md`; after human adjudication into `checker_gold.jsonl`, `score` gives balanced accuracy, AUROC and kappa vs gold in `results/checker_benchmark.json`.
- **Tests:** `tests/test_generate_verify.py` (4: sentence/tag splitting, cache hit, premise choice). Full suite 118 passed.
- **Status (superseded by the next entry):** code ready; pilot not yet run.

### 2026-10-19: Attribution pilot results (branch `generation-verification`, Aditya + Claude)
- **Runs:** `outputs/pipeline_runs/pilot-oracle` (76 min) and `pilot-bm25` (78 min), 41 complaints each, Nemotron `nvidia/nemotron-3-super-120b-a12b`, temperature 0, `max_tokens` 4096, verifier threshold 0.5 (not yet tuned). 83 API calls in total (about 0.6 per minute, far under the team's 40 rpm limit). Numbers in `results/attribution_pilot.json` (`python scripts/attribution_pilot.py report --retrieved pilot-bm25 --oracle pilot-oracle`).
- **1 failed generation** (oracle, complaint 20515686, gold 1026.13): `finish_reason=length`, the whole 4,096-token budget went to reasoning (about 18.8k characters) and no answer was written. Reported as a failure, not rerun with different settings; 40 complaints are compared.
- **New measure, added to the report script:** `supported_and_gold` = the sentence is supported **and** its premise chunk belongs to the gold section. Plain `supported` only measures faithfulness to whatever passage was given (the RAGAS definition).

  | Per-complaint mean (40) | BM25 top 5 | Oracle | Gap | 95% CI (paired bootstrap) |
  |---|---:|---:|---:|---|
  | Gold section in context | 35% | 100% | | |
  | Supported | 77.7% | 83.8% | +6.1 pts | −6.6 to +19.7 |
  | Supported and gold section | 19.0% | 83.8% | **+64.9 pts** | +52.3 to +76.8 |

  Micro (per sentence): supported 83.8% vs 81.5%; supported-and-gold 24.2% vs 81.5%.
- **Findings:** retrieval dominates the error; faithfulness alone hides retrieval errors (the model faithfully restates the wrong section); generation error with the correct passage is about 16%. **Reg Z oracle drafts score only 42% supported:** many sentences apply the rule to the complaint's facts ("these charges constitute a billing error under 1026.13(a)(1)"), which the passage cannot confirm. Decide in the checker-set rubric whether such application sentences count as supported.
- **Gap split by BM25 hit (supported measure):** hit in top 5 (14 complaints) +15.6 pts; miss (26) +1.0 pts, consistent with the faithfulness-vs-correctness finding.
- **Caveats:** a pilot (40 complaints, BM25 only, checker not yet validated).
- **Project documentation for the team:** pushed to a new branch `documents` (from `main`, one file `PROJECT_DOCUMENTATION.md`): goal, proposed vs current flow (two Mermaid diagrams, render-checked), data, gold set, results, 14 project decisions with reasons, changes from the proposal, milestone status. Project-level only; the team owns documentation and slides from here.
- **Next:**
  1. Checker validation set: `python scripts/checker_benchmark.py sample --runs pilot-bm25 pilot-oracle`, then label (Claude + ChatGPT with `annotation/chatgpt_package/CHECKER_PROMPT.md`), compare, adjudicate, score.
  2. **After the midterm, move the checker to the GPU** (team decision 2026-10-19). The `.venv` has the CPU-only PyTorch build (`2.14.1+cpu`), so the GTX 1650 is unused and the checker takes about 1.5 min per complaint. Install the CUDA build, then rerun only the verifier on the cached drafts (no new API calls) and confirm the numbers match before scaling to 300 to 500 complaints.

### 2026-10-19: Checker validation set sampled; annotator A labels done
- `python scripts/checker_benchmark.py sample --runs pilot-bm25 pilot-oracle` wrote `annotation/checker_set.jsonl` (50 pairs, 25 per condition, SHA-1 order, with the checker's score kept out of the annotator view) and the blind `annotation/checker_set.md`.
- **Annotator A (Claude Opus 5.5)** labelled from `checker_set.md` only, without seeing checker scores or conditions: `annotation/checker_labels_claude-opus-5-5.jsonl`, **34 supported, 16 unsupported**, one rationale each.
- **Conventions used** (now also in `annotation/chatgpt_package/CHECKER_PROMPT.md`, so annotator B labels under the same rubric):
  - omitted cross-reference exceptions are tolerated, but a dropped substantive condition is unsupported (e.g. K34 drops "within the validation period", K31 drops the identity-theft-report requirement);
  - naming some necessary conditions is still supported;
  - "the company" may stand for the regulated party;
  - claims about the complaint's own facts are unsupported (K05, K13, K16, K27, K36, K47);
  - "the passages do not address the complaint" is unsupported (K40, K41).
- **Known issue found while labelling:** when Nemotron puts sentences on separate lines without final punctuation, `split_sentences` keeps them as one "sentence" (K06, K08, K16, K37 have 4 to 5 claims each). It affects a few responses. **Not fixed before the midterm** because a fix changes the sentence counts and needs the verifier rerun (CPU hours). Fix it (split on newlines too) together with the GPU switch, then rerun the verifier on the cached drafts.
- **Next (Aditya):** label with ChatGPT (`annotation/chatgpt_package/CHECKER_PROMPT.md` + upload `annotation/checker_set.md`), save as `annotation/checker_labels_chatgpt.jsonl`, then `python scripts/checker_benchmark.py compare --a claude-opus-5-5 --b chatgpt`, adjudicate `annotation/checker_disagreements.md` into `annotation/checker_gold.jsonl` (`{"pair_id", "gold_label"}` per line), then `python scripts/checker_benchmark.py score`.

### 2026-10-20: Checker validated against 50 human-adjudicated pairs (M1 complete)
- **Annotators:** Claude A (34 supported) vs ChatGPT B (22 supported): agreement 76.0%, **kappa 0.540**. All 12 disagreements were A = supported, B = unsupported, about how strict to be when a sentence omits a qualifier. **Aditya adjudicated** (`annotation/checker_disagreements.md`, initials AD): 4 to A (K03, K04, K21, K25), 8 to B. `build-gold` wrote `annotation/checker_gold.jsonl`: 26 supported, 24 unsupported (38 agreed, 12 adjudicated).
- **Checker vs gold** (`results/checker_benchmark.json`, `python scripts/checker_benchmark.py score`):

  | Measure | Value |
  |---|---:|
  | AUROC | 0.843 |
  | Cutoff 0.5: balanced accuracy / kappa / unsupported caught | 0.625 / 0.257 / 25% |
  | 5-fold CV tuned cutoff (50 repeats): balanced accuracy / kappa / unsupported caught | 0.776 / 0.553 / 74.5% |
  | Best in-sample cutoff 0.9966 (optimistic) | 0.817 / 0.638 |

  Scores are squeezed near 1: supported median 0.998, unsupported median 0.951 (90th percentile 0.998).
- **Reading:** good ranking; the default 0.5 cutoff is far too lenient. With a tuned cutoff, the checker agrees with the gold about as well as the two annotators agree with each other.
- **Effect on the pilot:** `supported` depends heavily on the cutoff. The supported-and-gold gap is +64.9 pts at 0.5, +60.1 at 0.9, +37.0 at 0.99 and +14.5 at 0.9966, so the direction is stable and the size is not.
  - Independent human-label estimate from the 50 pairs (`by_condition` in the JSON), 25 sentences per condition: supported 36% retrieved vs 68% oracle; supported-and-gold 16% (4/25) vs 68% (17/25).
  - **Correction to the 2026-10-19 finding:** "faithfulness alone hides retrieval errors" was partly an artefact of the lenient cutoff. The accurate claim is that faithfulness **understates** retrieval error: human gap 32 pts (supported) vs 52 pts (supported-and-gold).
- **Next (after the midterm):**
  - Benchmark an LLM judge on the same 50 pairs (proposal risk plan) against a DeBERTa cutoff tuned on a larger labelled set.
  - Do not use Nemotron as the judge (it is the generator).
  - Do this together with the GPU switch and the newline sentence-split fix.
- **`documents` branch updated** with Sec. 4.3 (human cross-check, revised findings), Sec. 4.4 (checker results), the M1 row and the current-flow diagram.

### 2026-10-19: Backend default corpus is now Pair B's `chunks.jsonl` (branch `backend`, Anirudh + Claude)
- **Why:** Ujjwal's `5b90404` on `chunking` added 325 FCRA chunks to Pair B's corpus (2,954 in total), and `docs/INTERFACES.md` Sec. 2 on that branch now makes `chunking/data/processed/chunks.jsonl` the retrieval default.
- **Change:** `cfpb.pipeline.corpus.default_corpus_path()` returns the first file that exists in `CORPUS_PREFERENCE`:
  1. `chunking/data/processed/chunks.jsonl` (Pair B, the default)
  2. `data/processed/reg_chunks.parquet` (the fallback)

  `Corpus.load()` with no path, the oracle in the demo, and the batch runner (when `--corpus` is not given) all use it, resolved at run time rather than at import. The constant `DEFAULT_CORPUS` is gone.
- **Not merged:** `chunking` is still not merged into `backend`, because it would bring the 39 MB `ECFR-title12.xml` into this branch's history (Sec. 6.5.5 says to remove it first). So on `backend` today the fallback runs. Once `chunking` is merged here or into `main`, the default switches with no code change.
- **Checked with Pair B's file from `origin/chunking` (`5b90404`)**, placed temporarily at its tracked path and then removed:
  - The backend loads all 2,954 chunks (E 395, F 119, V 409, Z 1,706, FCRA 325) with no format changes.
  - The oracle puts a gold-paragraph chunk at rank 1 for **all 127 in-scope items, including the 36 FCRA ones**, and the 71 NONE items abstain. The real-data test passed against it.
  - A batch oracle run on the 120 sample items gave 43 abstentions, the same as on the fallback.
  - In the demo, an FCRA identity-theft complaint shows `15 U.S.C. 1681c-2(a)` (Pair B chunk `15-fcra-1681c-2-a`) at rank 1.
  - Without the file, the same commands fall back to `reg_chunks.parquet`.
- **For Ujjwal:** the committed `chunks.jsonl` at `5b90404` hashes to SHA-1 `13a8266064f95900313be4fa582e83386b1771b4` (from `git show`, LF endings, 2,954 lines). The log entry above gives `9928d5f3e676de365761b474e30a43d4691c25a6`. Counts and content checks match the entry, so the logged hash was probably taken from a different build or computed another way. Worth re-logging.
- **Tests:** 82 passed, including a new test of the preference order (default, fallback, error naming the default).

### 2026-10-19: BM25 as the default retriever when present; BM25-vs-oracle view in the demo (branch `backend`, Anirudh + Claude)
- **New on other branches:**
  - `retrieval-bm25` (`759989b`, Ujjwal): `cfpb.retrieval.bm25.BM25Retriever` over Pair B's 2,954-chunk `chunks.jsonl`, with results in `results/retrieval_bm25*.json`.
  - `documents` (`d630786`, Aditya): `PROJECT_DOCUMENTATION.md` for the midterm. It reports **NVIDIA Nemotron** as the target LLM and a **40-complaint attribution pilot** with real drafts and the DeBERTa checker. That generation and checker code is **not on any pushed branch** (searched every remote branch on 2026-10-19), so the backend cannot use it yet.
- **`load_retriever()` / `load_pipeline()`:**
  - The default retriever is Pair B's BM25, wrapped in `FunctionRetriever` over `chunking/data/processed/chunks.jsonl`, whenever `cfpb.retrieval.bm25` and that file are both importable or present. Otherwise it falls back to the stub with a warning.
  - **No abstention threshold.** The top BM25 score does not separate NONE complaints (AUROC 0.43, BM25 entry above), so the default retriever never abstains.
  - New flag `require_retriever` (separate from `require_models`, which is still classifier-only) raises instead of falling back.
  - Nothing from `retrieval-bm25` is copied into `backend`; BM25 switches on when that branch is merged.
- **Batch runner:**
  - New `--retriever default`: BM25 if present, else the stub.
  - `--retriever stub` now always forces the stub.
- **Demo:**
  - "Default" mode uses BM25 when present.
  - With a gold-set complaint selected and any non-oracle retriever, a **"Compare with oracle (gold section)"** toggle runs the complaint twice and shows passages, drafts and checks side by side. Each side says where the gold section ranked, or that it was missed, and gold-section chunks are marked.
  - Rendering was split into `render_retrieval`, `render_draft` and `render_checks`, so the single view and the comparison share code.
- **Checked with the `retrieval-bm25` files placed temporarily at their merged paths, then removed:**
  - `analyze_complaint.py` used BM25: a validation-notice complaint returned 12 CFR 1006.34 chunks.
  - `run_pipeline_batch.py --retriever default` ran all 120 sample items with no abstentions (outputs/pipeline_runs/bm25-live-sample, 9.5 s).
  - In the browser, complaint 23571192 with Compare on: BM25 put `15 U.S.C. 1681c-1(i)(5)` at rank 1 and the gold section 1005.11 at rank 3; the oracle put 1005.11(d)(1) at rank 1. This is the FCRA-displacement effect in the BM25 entry, visible for a single complaint.
  - Without the files, the same commands fall back to the stub with a warning.
- **Tests:** 84 passed, including 2 new tests of BM25 detection against a stand-in module with the same API.
- **Next for the backend:** wrap the Nemotron generator and the DeBERTa checker as pipeline stages once that code is pushed. The `generate()` and `verify()` contracts in `stages.py` are what they need to match.


### 2026-11-02: Final-experiment code and CARC handoff (branch `final-experiments`, Aditya + Claude)
- **Branch:** `final-experiments`, created from `generation-verification`, with `origin/backend` (`87f7cc3`, Anirudh) merged in. Conflicts in `src/cfpb/pipeline/core.py`, `scripts/run_pipeline_batch.py` and this file were resolved by keeping both sides (BM25 default retriever plus pluggable generator/verifier). `git fetch` on 2026-11-02: no teammate branch had dense retrieval or any of the work below.
- **Plan:** the code is written and tested here; five teammates run it at full scale on USC CARC and hand back results JSONs plus a short write-up. One file per person in `docs/tasks/` (README + `ishani.md` H1, `gagan.md` H5, `anirudh.md` H2/H3 + demo, `atharva.md` H4, `ujjwal.md` chunking/FCRA ablations), written for each person's Claude to follow. Aditya keeps the shared scripts, error analysis and the final report.
- **New code:**
  - `src/cfpb/retrieval/dense.py`: `DenseRetriever` (Sentence-Transformers, normalised embeddings, exact FAISS `IndexFlatIP`, numpy fallback, embeddings cached under `outputs/retrieval/embeddings`) and `HybridRetriever` (alpha * minmax(dense) + (1 - alpha) * minmax(BM25), per query).
  - `scripts/run_retrieval.py`: BM25 vs dense vs hybrid, with and without FCRA; alpha chosen by dev-half MRR (`metrics.half == 0`); metrics on the report half with bootstrap CIs and the paired gain over BM25; writes `ranked.parquet` per retriever, per-complaint features (for H5) and gold-section ranks.
  - `scripts/run_abstention.py` (H5): single confidence signals and a logistic regression, dev-half fit, report-half AUROC with CI, repeated 5-fold CV, P/R/F1 at a dev-tuned threshold.
  - `src/cfpb/verify/llm_judge.py` + `scripts/llm_judge.py` (H4): LLM entailment judge with the NLI verifier's interface, cached and spaced for the 40 requests/minute limit; benchmarked against `checker_gold` side by side with NLI. Default judge `deepseek-ai/deepseek-v4.1-flash` (end-to-end test: 2 calls, 32 and 115 s, both parsed); `mistralai/mistral-large-4-1t-a52b` is the second judge. Of the other NVIDIA-catalog models tried, `mistral-large-2-instruct`, `mistral-large` and `kimi-k2.6` returned 404 and `gemma-4-31b-it` and `gpt-oss-20b` timed out. Mistral Large 4 is a reasoning model: at 1,024 max tokens it spent the whole budget reasoning and returned no answer, so the budget is 4,096 and empty replies are not cached; a retest at 4,096 had not answered after about 15 minutes and was stopped.
  - `scripts/make_fixed_chunks.py`: fixed word-window and whole-section chunkings for the chunking ablation (FCRA chunks copied unchanged). Every gold section is present in both.
  - `scripts/make_data_bundle.py`: zips the git-ignored inputs teammates need (complaint texts, FCRA HTML, generation cache, pilot runs, BM25 rankings) to `outputs/cfpb_data_bundle.zip`, 98 files, 0.5 MB, with no `.env`.
  - `carc/`: `env.sh`, `setup_env.sh`, `check_data.sh`, `retrieval.sbatch`, `generate.sh` (API calls on a login node in tmux), `verify.sbatch` (GPU NLI from the cache). The account, partition and module names are placeholders that each person verifies.
- **Changed code:**
  - `split_sentences` now also splits on line breaks and drops list markers. 62 of the 83 cached Nemotron responses contain line breaks, so full-run sentence counts will differ from the pilot's.
  - `checker_benchmark.py`: `--tag` (second label set without overwriting set 1), `sample --per-condition/--exclude-tag`, `score --tau`. `compare` refuses to overwrite an adjudicated disagreements file.
  - `attribution_pilot.py`: `select --all` (writes `annotation/attribution_ids.txt`: 127 items, FCRA 36, F 30, E 29, Z 27, V 5) and `report --tau/--out`.
  - `run_pipeline_batch.py`: `--verifier judge`, `--threshold`, `--judge-model`.
  - `load_retriever`/`load_pipeline`: `kind`/`retriever_kind` = bm25, dense or hybrid, with alpha.
  - `requirements.txt`: `sentence-transformers` and `faiss-cpu` enabled.
- **Checks (2026-11-02, laptop CPU):**
  - The new BM25 path reproduces `results/retrieval_bm25.json` → `in_scope_all` exactly, with and without FCRA.
  - `checker_benchmark.py score` reproduces `results/checker_benchmark.json` exactly.
  - `attribution_pilot.py report` reproduces `results/attribution_pilot.json` exactly; `--tau 0.5` gives the same output.
  - End-to-end smoke runs of `run_retrieval.py` and `run_abstention.py` used the small MiniLM model. Their numbers are not results (deleted; the teammates' mpnet runs are the results).
  - Tests: 128 passed, including new tests for dense, hybrid, judge parsing and newline splitting.

### 2026-11-05: LLM judge timeout raised to 600 s (branch `final-experiments`, Aditya + Claude)
- **Problem (Atharva):** the DeepSeek judge cached K01, then K02 got no response after all five retries at the 180 s timeout.
- **Probe (2026-11-04, Aditya's laptop, one streaming call each, not cached):** K01 187.7 s, K02 153.7 s, K03 78.2 s, all valid JSON. Waits before the response headers were 184.6, 104.7 and 74.8 s, so most of the time is before the first response. Three calls only; queueing on NVIDIA's side is the likely cause, not proven.
- **Fix:** `LLMJudgeVerifier` passes `timeout=600` to its client. The timeout is not in the judge cache key, and model, prompt, temperature and max tokens are unchanged. Nemotron generation keeps 180 s. `docs/tasks/atharva.md` now gives the new timings and 1 to 3 hours per 50 calls.
- **Checks:** 128 tests pass. The patched non-streaming path was not confirmed before pushing, at Aditya's request; to be tested on 2026-11-06.
- **Check after the push (2026-11-05, laptop):** one K02 call through the patched non-streaming judge code, temporary cache, returned a parsed reply in 595.4 s, about 5 s under the new timeout. The "1 to 3 hours per 50 calls" estimate in `docs/tasks/atharva.md` may be too low if this speed persists; one call does not show whether it does.

### 2026-11-05: Review of Gagan's H5 branch `exp/gagan` (`bcf92a7`), not merged (Aditya + Claude)
- **Checked:** the write-up's tables match his JSONs. Sanity checks pass: `bm25_top` on all items 0.433, n 198, NONE 71, report half 91, and BM25 in `retrieval_mpnet.json` matches `retrieval_bm25.json` (MRR differs only at the 16th digit). Rebuilding the mpnet features on laptop CPU reproduced his logistic regression: report AUROC 0.740 and 0.632, thresholds 0.386 and 0.272, TP/FP 22/28 and 21/43. H5 holds: CI [0.625, 0.851] excludes 0.5 and sits above 0.43.
- **Exploratory rechecks on the report half (post hoc, from a scratch script, not committed):**
  - Length: Spearman with `n_words` is 0.986 for `bm25_top` and `bm25_top5_mean`, so the small `n_words` coefficient does not show the model ignores length. AUROC: dense features only 0.661, dense plus `n_words` 0.727, all features 0.740, all without `n_words` 0.739.
  - FCRA: the no-FCRA run counts the 18 FCRA-gold complaints as covered although their text was removed; 11 of its 43 false positives are these. Paired AUROC drop 0.108 [0.018, 0.202] on all 91, 0.085 [-0.012, 0.189] without FCRA-gold items. On the 47 other in-scope items, false positives are 25 with FCRA and 32 without, at different thresholds.
  - Flag rate with FCRA by gold regulation: Z 13/15, E 7/13, F 4/15, V 1/4, FCRA 3/18. AUROC without FCRA-gold items is 0.688.
  - Logistic regression minus best single signal (`dense_top5_mean`): 0.074 [-0.005, 0.167].
- **Requested from Gagan before merge:** correct the length and FCRA claims, add CIs to the single-signal table, state the cost (28 wrong referrals per 22 correct, 1.27), add job IDs, drop `results/retrieval_mpnet.json` (Ishani's deliverable).
