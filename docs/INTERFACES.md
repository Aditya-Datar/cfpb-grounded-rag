# Stage interfaces (PROPOSED, 2026-10-15; freeze after team review)

How the stages pass data to each other, so each pair can build against these
formats (or stubs of them) independently (CLAUDE.md Sec. 6, week 2 milestone).
Stage outputs are Parquet files under `outputs/` (git-ignored), keyed by
`complaint_id` (string). **Changing a format after freeze needs a note in
CLAUDE_PROGRESS.md and a heads-up to every pair.**

Status: (0) and (1) are implemented; (2) is implemented as a corpus (regulations + FCRA statute), with the retriever still to build; (3) has silver labels from Annotator A (198 items), with Annotator B pending; (4) to (7) are proposals.

---

## 0. Complaint records (implemented, Pair A)

`data/processed/{train,val,test}.parquet` and `narratives_clean.parquet`
(`scripts/run_data_pipeline.py`). One row per complaint.

| Column | Type | Notes |
|---|---|---|
| `complaint_id` | str | CFPB id; the join key everywhere |
| `narrative_clean` | str | **model input**; masks normalized to `[REDACTED]`, `[DATE]` |
| `product`, `sub_product`, `issue`, `sub_issue` | str | consumer-selected CFPB labels |
| `company`, `state`, `date_received`, `company_response`, ... | str | metadata |
| `n_words`, `redaction_density`, `text_hash` | int/float/str | cleaning stats |

The evaluation set for stages 2 to 4 is the **annotation items** (`cfpb.annotation.load_items()`): `annotation_sample.csv` (120, stratified) plus `annotation_topup.csv` (78, in-scope top-up), 198 items in total. Of these, 129 have an in-scope gold section and 69 are NONE (see Sec. 7).

## 1. Classifier output (implemented, Pair A; **FROZEN 2026-10-16**, agreed by all pairs)

`outputs/classifier/<label>/predictions_{val,test}.parquet`, or at run time:

```python
from cfpb.classify.predict import ComplaintClassifier
clf = ComplaintClassifier("outputs/classifier/product/best")
clf.predict(texts)  # DataFrame: label, prob, top_k [(label, prob), ...]
```

Combined per complaint (merge the product and issue runs on `complaint_id`):

| Column | Type | Notes |
|---|---|---|
| `complaint_id` | str | |
| `pred_product`, `pred_product_prob` | str, float | prob = softmax max; >0.99 was 98.5% accurate on test |
| `pred_issue`, `pred_issue_prob` | str, float | |

**Use downstream:** optional retrieval routing (e.g. restrict or boost chunks of the product's candidate regulation, `config.PRODUCT_TO_REGULATION`), and confidence display in the demo.

## 2. Regulation chunks (implemented corpus, Pair B)

`data/processed/reg_chunks.parquet` (`scripts/build_reg_corpus.py`; eCFR as of 2026-10-13 plus the FCRA statute, U.S. Code 2024 edition; 4,319 chunks).

| Column | Type | Example |
|---|---|---|
| `chunk_id` | str, unique | `R:1026.13(b)`, `I:1026.13(b)(1)~1`, `A:1026 Appendix G~3`, `S:1681i(a)(1)`; `#k` suffix = word-window piece |
| `regulation` | str | `E`, `F`, `V`, `Z`, `FCRA` |
| `part` | str | `1026` |
| `kind` | str | `regulation` (rule text), `interpretation` (Supplement I official commentary), `appendix`, `statute` (FCRA) |
| `section` | str | `1026.13` (appendices: `1026 Appendix G`) |
| `paragraph` | str | most specific reference, `1026.13(b)(1)` |
| `heading` | str | `§ 1026.13 Billing error resolution.` |
| `text`, `n_words` | str, int | |
| `source_url` | str | eCFR point-in-time link (the citation shown in the demo) |

### Retriever output (proposal)

`outputs/retrieval/<run_name>/ranked.parquet`, top 10 per complaint:

| Column | Type | Notes |
|---|---|---|
| `complaint_id` | str | |
| `retriever` | str | `bm25`, `dense:<model>`, `hybrid:<weights>` |
| `corpus` | str | which `kind`s were indexed, e.g. `regulation+interpretation` |
| `rank` | int | 1 = best |
| `chunk_id` | str | |
| `score` | float | retriever-specific |

Python: `retrieve(query: str, k: int = 10) -> list[dict(chunk_id, score)]`.

**Scoring against gold (proposal; owner of the shared eval script decides):**
- A retrieved chunk is a **hit** if `chunk.section == gold_section`. Paragraph-level hits are reported as a secondary metric.
- Interpretation chunks count for the section they interpret. Report runs with and without interpretations as an ablation.
- Complaints whose gold label is `NONE` (no in-scope section) are excluded from precision@k and recall@k, and are scored as abstention instead (Sec. 7).

## 3. Gold labels (annotation output, proposal)

`annotation/gold_labels.csv` (small, so commit it). One row per complaint and annotator.

| Column | Type | Notes |
|---|---|---|
| `complaint_id` | str | from `annotation_sample.csv` |
| `annotator` | str | initials, or `llm:<model-id>` |
| `gold_regulation` | str | `E`/`F`/`V`/`Z`/`FCRA`/`NONE` |
| `gold_section` | str | `1026.13` or `1681i`, or empty for NONE; must exist in `annotation/regulation_sections.md` |
| `gold_paragraph` | str | optional, e.g. `1026.13(a)(1)` |
| `confidence` | int | 1 guess, 2 probable, 3 sure |
| `evidence_quote` | str | verbatim sentence of the section that applies (required for LLM labels) |
| `notes` | str | |

**`annotation/gold_final.jsonl` (built 2026-10-16) is the official gold set**: one line per complaint (198), with `complaint_id`, `gold_regulation`, `gold_section`, `gold_paragraph`, `source` (`agreed`, `agreed_spot_checked`, `adjudicated`, `spot_corrected`), `adjudicator`, `label_a`, and `label_b`. It is built by `scripts/build_gold.py` from the two LLM annotators plus the human decisions in `annotation/disagreements.md` and `annotation/spot_check.md`. Evaluation code should read only this file. It is JSONL rather than CSV because `*.csv` is git-ignored.

## 4. Generation (proposal, Pair C)

`outputs/generation/<run_name>/responses.parquet`. Each complaint is generated twice, under `condition` = `retrieved` and `oracle` (the attribution experiment).

| Column | Type | Notes |
|---|---|---|
| `complaint_id` | str | |
| `condition` | str | `retrieved` (top-k from stage 2) or `oracle` (gold section's chunks) |
| `context_chunk_ids` | list[str] | exactly what the model saw, in order |
| `model`, `prompt_version` | str | the single target LLM (CLAUDE.md Sec. 3); prompt file hash |
| `response` | str | draft reply citing sections |
| `sentences` | list[str] | the response split into sentences (stage 4 input) |
| `cited_chunk_ids` | list[list[str]] | per sentence, the chunks it cites (empty if none) |
| `cache_key` | str | hash of (model, prompt_version, context, complaint), so reruns cost nothing |

## 5. Verification (proposal, Pair C)

`outputs/verification/<run_name>/sentences.parquet`, one row per generated sentence.

| Column | Type | Notes |
|---|---|---|
| `complaint_id`, `condition`, `sentence_idx` | str, str, int | joins to stage 4 |
| `sentence` | str | |
| `premise_chunk_ids` | list[str] | text checked against (cited chunks, or all context) |
| `entail_prob`, `contradict_prob` | float | NLI checker (DeBERTa-v3 MNLI) or LLM judge |
| `label` | str | `supported` / `unsupported` at `threshold` |
| `verifier`, `threshold` | str, float | |

The checker validation set (50 human or LLM labelled pairs) uses the same `sentence` and `premise` text plus `gold_label`.

## 6. Shared conventions

- `complaint_id` and `chunk_id` are strings everywhere. Never use row positions.
- Every run folder has a `run_info.json`: settings, model ids, data fingerprint (`data_fingerprint.json`), library versions, date.
- Evaluate on val while developing and touch test once. Splits are fixed by `data_fingerprint.json`.

## 7. Abstention: NONE as a first-class outcome (team decision 2026-10-15)

About a third of real complaints are governed by law outside the corpus: federal student loans, RESPA/Reg X, state title law, scams the consumer authorized, and so on. In the annotation, 69 of 198 items are NONE. A compliance assistant must say "no governing section in our corpus; route to a human" rather than cite a wrong section. So:

- **Every stage may output `NONE`.**
  - The retriever returns `abstain_score` (float) with its ranking, for example 1 minus the top similarity, or a calibrated classifier.
  - The pipeline abstains when that score passes a threshold tuned on a held-out split.
  - Generation, when abstaining, drafts a referral ("this complaint appears to fall outside Regulations E/F/V/Z and the FCRA; escalate to compliance") and cites nothing.
- **Metrics:**
  - abstention precision, recall, and F1 on all 198 items (positive class = NONE)
  - retrieval precision@k and recall@k on the 129 in-scope items only
  - end-to-end accuracy: correct section, or correct abstention
- **The attribution experiment** (retrieved vs oracle passage) uses in-scope items only, since NONE items have no oracle passage.
