# Midterm report: review notes (2026-10-26)

Reviewed: the Google Doc PDF (`NLP Midterm Report_test.pdf`) and the LaTeX draft (Intro + Related Work).

**Summary:**
- Every result in Sections 3–7 is correct, and all six figures are the final versions.
- Still to do:
  - merge the two versions;
  - fill the empty sections;
  - fix the cross-references, figure numbering and two captions;
  - apply three earlier fixes;
  - correct three Related Work claims, and add missing context to a fourth.

---

## 1. Merge the two versions

Use the **LaTeX** Introduction and Related Work, and the **Google Doc** Sections 3–7. The Google Doc intro is the older version. It still says the CFPB attributes "**much of**" the complaint growth to credit repair firms; the agency says "**part of**". It also doesn't say that "two in three / one in six" comes from the human-reviewed sample.

## 2. Missing or empty (Google Doc)

| Where | Problem | Fix |
|---|---|---|
| 2.1–2.5 Related Work | Headings only | Paste in the LaTeX Related Work |
| 8. Updated Milestones | Empty heading | Add the week 10–14 plan with owners |
| References | Empty heading | Use the LaTeX `.bib` |
| 4.1 System Overview | The line "Flagged sentences… go to a human" has no figure | Add the pipeline diagram (as on slide 2), or delete the line |
| 4.1 Response drafting | Footnote ¹ after "prompt v1-9d0f038c" has no text | Add the footnote or remove the marker |

## 3. Errors to fix (Google Doc)

| # | Where | Says | Should be |
|---|---|---|---|
| 1 | 4.1 Classification | "(111,527 narratives, **Sec. 3.1**)" | **Sec. 3.2** |
| 2 | 4.1 Retrieval | "(**Sec. 3.2**)" for the corpus | **Sec. 3.3** |
| 3 | 4.1 Sentence checking | "too lenient (**Sec. 6.3**)" | **Sec. 6.4** |
| 4 | Figures | Numbered 6, 2, 1, 5, 4, 3 in order of appearance | Renumber 1–6 in order of appearance (LaTeX does this automatically) |
| 5 | Fig. 3 caption | "The strict threshold was evaluated through five-fold cross-validation" | The 0.9966 line is the best cutoff **on these same 50 pairs**, so it's optimistic. Cross-validation produced the 0.78 / 0.55 numbers. Suggested: "The strict cutoff shown is the best on these 50 pairs (optimistic); cross-validated results are in Table X." |
| 6 | Fig. 1 caption | "95% confidence intervals from 10,000 **paired** bootstrap resamples" | The bar intervals are a bootstrap over complaints for each arm. "Paired" applies only to the gap. Write "bootstrap resamples over complaints" |
| 7 | 6.4 | "Most concerned omitted legal qualifications **or statements applying regulatory rules to specific facts**" | All 12 disagreements were about omitted qualifiers. Fact-application sentences were labelled unsupported by **both** annotators. Delete the second half |

## 4. Earlier fixes not yet applied (Google Doc)

| Where | Fix |
|---|---|
| 3.4 Gold Annotation | The top-up was drawn from specific **sub-issues** (round-robin), not "issue types" |
| 3.2 Complaint Data | Add: none of the 198 gold complaints is in the classifier test set, but **96 are in the classifier training set**. No reported number is affected, because the classifier is scored only on the test set and doesn't filter retrieval |
| 3.3 Regulation Corpus | Add: the corpus is regulation text only and excludes the Supplement I official interpretations and the appendices |

## 5. Related Work claims (LaTeX), checked against the papers

**Fix these four:**

| Claim | Problem | Suggested text |
|---|---|---|
| Zheng et al.: "BM25 finds only 18.3% of the relevant passages in its top 10" | 18.3% is the share of questions where **all** gold passages are in the top 10; 40.8% have at least one | "BM25 retrieves every relevant passage in its top 10 for only 18.3% of questions (at least one for 40.8%)" |
| How Our Work Differs: the gap is "**exactly** what Magesh et al. call misgrounded" | Overclaim. We check whether the cited passage is from the correct section, not Magesh's full grounding criteria | "closely corresponds to what Magesh et al. call misgrounded" |
| Gao et al. 2023 | Reads like a relief-prediction paper. Its purpose is detecting systematic non-meritorious complaints (Bank of America credit and prepaid cards, TF-IDF, SVM) | Add "…to flag systematic non-meritorious complaints" |
| Airani et al. | The paper says five classes and a balanced test set, but not "merged" | "five product groups" |

**Verified, keep as is:**
- BSARD: 1,108 questions; BM25 51.3% R@100; fine-tuned 74.8%.
- Zheng et al.: query–passage word overlap 0.09 vs 0.27 for Natural Questions.
- ObliQA: questions written by GPT-4 (gpt-4-turbo); BM25 recall@10 76.1 vs best 79.5.
- RePASs: support, contradiction and obligation coverage.
- MiniCheck: SummaC-CV 71.3 → 62.1 without a tuned cutoff (−9.2); MiniCheck-FT5 74.7 vs GPT-4 75.3.
- ALCE: oracle passages chosen from the retriever's top 100 to maximise recall (Sec. 4.2 is correct).
- Legal RAG Bench: Victorian (Australian) criminal law; "retrieval sets the ceiling".
- Kim & Lee: 1,039 Korean civil complaints.
- Wang et al.: 176,942 checking/savings complaints, XGBoost, AUC 0.78.
- Airani et al.: DistilBERT macro-F1 0.860.

**Not checked:** volume, issue and page numbers in the `.bib` (e.g. Magesh 22(2):216–242, Dahl 16(1):64–93), Wang et al.'s author first names, and Kim & Lee's "12 pipeline versions" detail. Confirm them on the publisher pages.

## 6. LaTeX build

- `\ref{sec:results}` needs `\label{sec:results}` on the results section, or it prints "??".
- Compile and check the page count against the course limit.

## 7. Verified correct (no change needed)

- **Data:** 6,809,200 → 469,659 → 276,378; splits 111,527 / 14,022 / 13,905.
- **Corpus and gold set:** 2,954 chunks over 167 sections; gold set 127 + 71; kappa 0.904 / 0.845 / 0.898.
- **Classifier:** 0.808 / 0.843; 0.325 / 0.581; 0.538 on 39 issues; per-class 0.95 / 0.51 / 0.70.
- **BM25:** table; 0.473 → 0.396; AUROC 0.43; 228 vs 164 words.
- **Pilot:** 77.7 / 83.8 / +6.1 (−6.6 to +19.7); 19.0 / 83.8 / +64.9 (+52.3 to +76.8); human 36 / 68 and 16 / 68.
- **Cutoff sensitivity and per regulation:** +64.9 / +60.1 / +37.0 / +14.5; E, F, FCRA, V, Z values.
- **Checker:** AUROC 0.84; 0.63 / 0.26 / 25%; 0.78 / 0.55 / 75%; 76.0%, kappa 0.54, 12 disagreements (4 / 8).

**Sources used for Section 5:** [Gao et al. 2023](https://arxiv.org/abs/2308.11138) · [Wang et al. 2026](https://arxiv.org/abs/2606.22664) · [Legal RAG Bench](https://arxiv.org/abs/2603.01710) · [Kim & Lee, CIKM 2025](https://koasas.kaist.ac.kr/handle/10203/335835) · [BSARD](https://aclanthology.org/2022.acl-long.468.pdf) · [ALCE](https://arxiv.org/html/2305.14627) · [Zheng et al.](https://arxiv.org/html/2505.03970v1) · [MiniCheck](https://arxiv.org/html/2404.10774) · [RIRAG / ObliQA](https://arxiv.org/html/2409.05677) · [Airani et al.](https://scitepress.org/Papers/2025/131739/131739.pdf)
