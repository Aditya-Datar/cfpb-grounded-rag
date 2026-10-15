# Stage interfaces (PROPOSED, 2026-10-15; freeze after team review)

How the stages pass data to each other, so each pair can build against these
formats (or stubs of them) independently (CLAUDE.md Sec. 6, week 2 milestone).
Stage outputs are Parquet files under `outputs/` (git-ignored), keyed by
`complaint_id` (string). **Changing a format after freeze needs a note in
CLAUDE_PROGRESS.md and a heads-up to every pair.**

Status: (0) and (1) are implemented; (2) is implemented as a corpus, with the retriever still to build; (3) to (6) are proposals.

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

The evaluation subset for stages 2 to 4 is `annotation_sample.csv` (120 complaints, ~30 per regulation), plus any held-out set the team adds.

## 1. Classifier output (implemented, Pair A)

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

`data/processed/reg_chunks.parquet` (`scripts/build_reg_corpus.py`; eCFR as of 2026-10-13; 4,070 chunks).

| Column | Type | Example |
|---|---|---|
| `chunk_id` | str, unique | `R:1026.13(b)`, `I:1026.13(b)(1)~1`, `A:1026 Appendix G~3`; `#k` suffix = word-window piece |
| `regulation` | str | `E`, `F`, `V`, `Z` |
| `part` | str | `1026` |
| `kind` | str | `regulation` (rule text), `interpretation` (Supplement I official commentary), `appendix` |
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
- Complaints whose gold label is `NONE` (no in-scope section) are excluded from precision@k and recall@k and reported separately.

## 3. Gold labels (annotation output, proposal)

`annotation/gold_labels.csv` (small, so commit it). One row per complaint and annotator.

| Column | Type | Notes |
|---|---|---|
| `complaint_id` | str | from `annotation_sample.csv` |
| `annotator` | str | initials, or `llm:<model-id>` |
| `gold_regulation` | str | `E`/`F`/`V`/`Z`/`NONE` |
| `gold_section` | str | `1026.13`, or empty for NONE; must exist in `annotation/regulation_sections.md` |
| `gold_paragraph` | str | optional, e.g. `1026.13(a)(1)` |
| `confidence` | int | 1 guess, 2 probable, 3 sure |
| `evidence_quote` | str | verbatim sentence of the section that applies (required for LLM labels) |
| `notes` | str | |

`annotation/gold_final.csv` holds the adjudicated label per complaint, with the same columns plus `adjudicator` and `agreement` (whether the annotators agreed).

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
