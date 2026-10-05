# CLAUDE.md: CSCI 544 Group 36 Course Project

Context file for Claude sessions working on this project. Read it fully before helping. It records what the team has decided, what has been verified, and where work stands as of October 4, 2026.

## 1. Project at a glance

- **Course:** CSCI 544, Applied Natural Language Processing, USC.
- **Team:** Group 36, six members: Aditya Datar, Ujjwal Puri, Ishani Bhadlikar, Atharva Thorat, Anirudh Joshi, Gagan Shivanna.
- **Title:** Regulation-Grounded Triage and Response Drafting for CFPB Consumer Complaints.
- **Type:** Application-focused, with an evaluation component.
- **One-line summary:** Given a consumer complaint filed with the Consumer Financial Protection Bureau (CFPB), classify it, retrieve the federal regulation section that governs it, draft a response citing that section, then check every drafted sentence against the cited text and flag unsupported ones for a human reviewer.

The tool assists a compliance officer; it never replaces one. Frame it that way in all writing, since generating regulatory responses sits close to giving legal advice.

## 2. Why this direction (decisions already made)

Three directions were considered. Do not reopen these without a team decision.

- **VoiceTrust** (voice customer-service agent with ASR uncertainty and escalation): rejected. No public dataset pairs call audio with policy-verification and escalation labels. A Kaggle "call center speech" set turned out to be a vendor sample with the full corpus behind a sales form, and it is ASR-only anyway.
- **Context compression study** (repeated compression and faithfulness decay): rejected after the professor questioned its motivation, which the team could not answer convincingly.
- **CFPB pipeline:** chosen. Fully public data, obvious real-world motivation (legal response deadlines, rising complaint volume), and room for a genuine evaluation contribution.

## 3. Pipeline and methods

1. **Classify** product and issue: fine-tuned DistilBERT. Report per-category F1 (macro-F1, given heavy imbalance).
2. **Retrieve** the governing regulation section: Sentence-BERT embeddings in a FAISS index. Baselines: BM25 (sparse floor) and a dense plus sparse hybrid. Report precision@k and recall@k (k = 1, 5, 10) against gold labels.
3. **Generate** a draft response citing the retrieved section: hosted LLM (Claude, Gemini, or GPT) or local Llama/Mistral. Pick ONE target model early and keep it fixed; switching mid-project invalidates collected numbers.
4. **Verify** each generated sentence: sentence-level NLI following the SummaC methodology, implemented with an off-the-shelf DeBERTa-v3 MNLI checkpoint (for example `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`). Report the percentage of sentences supported, and the checker's agreement with human labels.

**Attribution experiment (the core contribution):** run each complaint through the generator twice, once with the retrieved passage and once with the hand-labeled correct ("oracle") passage. The faithfulness gap between the two runs is attributable to retrieval; unfaithfulness that remains with the correct passage is attributable to generation. This tells practitioners where to invest: better chunking and hybrid search if retrieval dominates, constrained decoding or verification gating if generation does.

**Demo:** Streamlit app showing category, retrieved passage with citation, draft response, and a per-sentence faithfulness report (supported vs flagged).

## 4. Data

- **Complaints:** CFPB Consumer Complaint Database, public domain.
  - Bulk CSV: https://files.consumerfinance.gov/ccdb/complaints.csv.zip
  - API docs: https://cfpb.github.io/api/ccdb/api.html
  - Labeled by product, sub-product, issue, sub-issue, company, and company response. Consumer narratives exist only on the opt-in subset and are redacted with `XXXX` placeholders, so a cleaning pass is required.
  - The CFPB announced in August 2026 that it will stop publishing new narratives; previously published ones remain obtainable through its FOIA Reading Room. Download a snapshot now and work from it.
- **Regulations:** eCFR Title 12, bulk XML, public domain (https://www.govinfo.gov/bulkdata/ECFR, plus the ecfr.gov API). Scoped to four parts only:
  - Regulation E, 12 CFR 1005 (electronic fund transfers)
  - Regulation Z, 12 CFR 1026 (truth in lending)
  - Regulation V, 12 CFR 1022 (fair credit reporting)
  - Regulation F, 12 CFR 1006 (debt collection)
  - Together roughly a few thousand chunks, small enough to diagnose retrieval errors by hand. Regulations nest deeply and cross-reference each other, so chunk by section structure, not fixed token windows.
- **Distribution warning:** credit and consumer reporting made up 88% of 2025 complaints. Sample gold labels **stratified, about 30 per regulation**, not by natural frequency, or Reg E, Z, and F will have too few cases to evaluate.

## 5. Annotation (everyone participates)

- **Gold retrieval set:** about 120 complaint-to-regulation-section pairs, stratified across the four regulations. Serves as retrieval ground truth and as the oracle context for the attribution experiment.
- **Checker validation set:** about 50 (regulation passage, generated sentence) pairs labeled supported or unsupported.
- **Process:** two people draft a written rubric first; then all six annotate with overlap so inter-annotator agreement can be computed. Roughly 8 to 10 person-hours per set.
- **Human labels are ground truth.** The NLI checker is what gets validated against them, never the other way round. If the checker agrees poorly with humans, replace it with an LLM-based entailment judge benchmarked the same way.
- **Fallback:** if annotators cannot agree on specific provisions, drop to coarser regulation-family labels (E vs Z vs V vs F).

## 6. Milestones and work split

- **Week 2:** freeze interfaces between stages (classifier output, retrieved-chunk format, verifier input and output). Every pair builds against stubs after this.
- **Week 3:** benchmark the NLI checker against the 50 human-labeled pairs. Earliest kill signal; switch to the LLM judge if it fails.
- **Milestone 1 (week 5):** regulation corpus chunked, classifier fine-tuned and scored, 120 gold pairs annotated with agreement reported, checker validated against human labels.
- **Milestone 2 (week 9):** full pipeline running end to end on a held-out set, reporting retrieval precision@k and the measured retrieved-vs-oracle faithfulness gap.
- **Weeks 10 to 14:** ablations (chunking strategy, retriever type), error analysis, Streamlit demo, final report.

Suggested split into three pairs (member assignments still to be decided by the team):

- **Pair A, data and classification:** CFPB snapshot, profiling, cleaning, DistilBERT classifier. Finishes early, then leads the demo.
- **Pair B, regulation corpus and retrieval:** eCFR parsing and chunking, FAISS, BM25, hybrid, retrieval evaluation.
- **Pair C, generation and verification:** LLM wrapper with response caching, NLI verifier, checker benchmark, the attribution experiment.

**Open decisions:** pair assignments, the single target LLM, who owns the repo and the shared evaluation script (one owner, so results stay comparable), and who drafts the annotation rubric.

**Resources:** all data free; DistilBERT and NLI runs fit in a single T4 or A100 session (Colab or USC CARC), GPU-hours not GPU-days; FAISS runs in memory; LLM API spend capped under $100 for the team by scoping evaluation to 300 to 500 complaints, or zero with a local model.

## 7. Course deliverables and constraints

- **Proposal:** 1 page, single-spaced, 10pt. Rubric (20 pts): Project Idea and Objectives 4, Related Work 3, Novelty and Impact 5, Risk 2, Resources 2, Milestones 2, Clarity 2. Already finalized.
- **Paper Review Report (individual, due October 6):** 2 pages of main content; references may go on page 3. Graded on five questions, 100 points total:
  1. Problem, motivation, contribution (15): includes distinguishing the authors' novelty claims from unsupported "no prior work" assertions.
  2. How the approach works (25): core approach 10, technical reasoning 10, assumptions and trade-offs 5.
  3. Evidence and findings (25): setup 10, findings with traceable evidence (cite table, figure, or section) 10, purpose of the evidence 5.
  4. Strengths, limitations, judgment (25): limitations must go beyond the authors' own list.
  5. Follow-up question and investigation (10).
  - The project-based option requires at least two papers.
  - **This is an individual assignment, written in the student's own words.** Help a teammate understand papers, check facts, and give feedback on their draft, but do not write their review for them. Aditya's review covers Magesh et al. and RAGAS; teammates should write their own analysis even if they use the same papers.

## 8. Related work (verified against primary sources)

Cite locations in IEEE style inside the bracket, for example `[1, Sec. 5.4]` or `[1, Table 6]`.

- **Magesh et al. 2024**, "Hallucination-free? Assessing the reliability of leading AI legal research tools." https://arxiv.org/abs/2405.20362 (published in Journal of Empirical Legal Studies, 2025; table numbers above refer to the arXiv version).
  - Three tools from **two** companies: Lexis+ AI (LexisNexis); Westlaw AI-Assisted Research and Ask Practical Law AI (both Thomson Reuters, which owns Westlaw). GPT-4 is a closed-book baseline, not a legal tool. The paper's shorthand "Thomson Reuters" means Ask Practical Law AI.
  - 202 preregistered queries: 80 general, 70 jurisdiction or time-specific, 22 false premise, 30 factual recall (Table 2).
  - Accuracy: Lexis+ AI 65%, Westlaw 41%, Ask Practical Law AI about 19% (20% after revalidation). Hallucination: more than 1 in 6 for Lexis+ AI and Practical Law, about 1 in 3 for Westlaw.
  - **Incomplete rates 18 / 25 / 62% mean refusals OR correct-but-uncited answers. Do not describe 62% as "refuses to answer."**
  - Two-axis coding: correctness (correct, incorrect, refusal) and groundedness (grounded, misgrounded, ungrounded). Hallucinated = incorrect or misgrounded (Sec. 4, Table 1).
  - Inter-rater reliability: Cohen's kappa 0.77, 85.4% agreement on 48 responses, final label only (Sec. 5.4). Cause attributions in Table 6 (naive retrieval, inapplicable authority, reasoning error, sycophancy) have no reported reliability.
  - Evaluates retrieval and generation jointly, so it cannot say which stage failed. That gap motivates our attribution experiment.
- **Es et al. 2024 (RAGAS)**, EACL System Demonstrations, pp. 150 to 158. https://aclanthology.org/2024.eacl-demo.16/
  - Reference-free metrics scored by gpt-3.5-turbo-16k: faithfulness, answer relevance (Eq. 1), context relevance (Eq. 2).
  - WikiEval: 50 Wikipedia pages; agreement with humans 0.95 / 0.78 / 0.70 vs GPT Score 0.72 / 0.52 / 0.63 and GPT Ranking 0.54 / 0.40 / 0.52 (Table 4).
  - **Key tension with our domain:** RAGAS "faithfulness" means consistent with whatever was retrieved. Magesh et al. reject that definition for law (Sec. 4.2): an answer that faithfully repeats an overruled case scores perfectly on RAGAS but is a hallucination legally. Its weakest metric (context relevance, 0.70) is the retrieval-side one.
- **Laban et al. 2022 (SummaC)**, TACL vol. 10. https://arxiv.org/abs/2111.09525. Sentence-level NLI for inconsistency detection; SummaC-Conv 74.4% and SummaC-ZS 72.1% balanced accuracy (Table 2). Our verifier follows this method. Caveat from Tang et al. 2023 (AggreFact, ACL 2023): performance drops to roughly 63 on summaries from modern systems.
- **Dahl et al. 2024**, "Large legal fictions," Journal of Legal Analysis. https://arxiv.org/abs/2401.01301. General-purpose LLM legal hallucination.
- **Barnett et al. 2024**, "Seven failure points when engineering a RAG system," CAIN. https://arxiv.org/abs/2401.05856. RAG failure taxonomy for error analysis.
- **Pipitone and Alami 2024 (LegalBench-RAG).** https://arxiv.org/abs/2408.10343. Legal retrieval benchmark, but private contracts only, not regulations.
- **Prior CFPB NLP work:** Gao et al. 2023, anomaly detection over narratives, https://arxiv.org/abs/2308.11138; Wang et al. 2026, monetary relief prediction, https://arxiv.org/abs/2606.22664. Neither links complaints to regulation sections.
- **Motivation figures:** CFPB complaints rose from about 1.6M (2023) to 3.2M (2024) to 6.6M (2025), per the CFPB's 2025 Consumer Response Annual Report (https://files.consumerfinance.gov/f/documents/cfpb_2025-cr-annual-report_2026-03.pdf). The CFPB attributes part of the surge to credit repair organizations and automated submissions, so acknowledge that if the growth figure is used. Companies owe an initial response within 15 calendar days, up to 60 for a final response.

## 9. Pitfalls already caught (do not repeat)

- Novelty: write "we found no published work that links complaints to specific regulation sections," never "no work exists."
- Do not merge distinct tools or companies (see Magesh notes above).
- Do not treat RAGAS faithfulness as legal correctness.
- Paraphrasing tools have repeatedly introduced meaning errors into our drafts (for example "answering in the negative" for refusals, "founded" for "grounded," circular definitions). Reread any paraphrased text against the source.
- **Jev (TypeSafe AI, released September 15, 2026):** a calibrated decision model, no text generation, limited early access. Allowed only as an optional extra verifier in the week 3 benchmark, contingent on access. Never a dependency.

## 10. How Claude should work on this project

- Verify every number, quote, and author list against the primary source before it enters a team document, and cite the specific section, table, or figure.
- Do not invent datasets, papers, links, or statistics. If something cannot be verified, say so.
- Keep scope tight: four regulations, one target LLM, a curated evaluation subset.
- Respect page limits strictly (proposal 1 page; review 2 pages plus references). Compile LaTeX and check page breaks rather than estimating.
- For individual graded work, coach and check; do not ghostwrite.

## 11. Immediate next steps

1. Download the CFPB CSV snapshot and eCFR Title 12 XML; record download dates.
2. Assign pairs, the target LLM, and the repo and evaluation-script owner.
3. Draft the annotation rubric and freeze stage interfaces by week 2.
4. Profile narratives (count, length, redaction density) and parse Parts 1005, 1026, 1022, 1006.
