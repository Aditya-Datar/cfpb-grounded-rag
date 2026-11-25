# Final presentation (Group 36): slide text and speaker notes

Readable copy of the 5-slide final deck (5 min talk + 1 min Q&A). The source files are in `project/` (Claude artifact Slides format: `deck.json` sets slide order, `slides/*.html` hold the slides, `deck.css` the styling). Every number comes from `results/` and `docs/EXPERIMENT_LOG.md` on the `final-experiments` branch (commit a6f4707).

## Slide 1: Drafting regulation-cited replies to CFPB complaints, and measuring which stage fails

CSCI 544 · Group 36 · Final presentation
Complaint: consumer narrative (input)
Classify: DistilBERT: product, issue
Retrieve: embed + BM25, GPT reranks
Draft: Nemotron Super cites the section
Check + rewrite: each sentence vs the cited text
Officer: draft + flagged sentences (output)
**Prior work:** Magesh et al. 2024: commercial legal RAG tools hallucinate 17–33%, but are scored end to end, so nobody can say which stage failed.
RAGAS (Es et al. 2024): "faithful" = matches whatever was retrieved, which is not legal correctness. SummaC: our sentence-level checker method.
**What we add:** Attribution: run every complaint with the retrieved passage and with the correct (oracle) passage; the gap is retrieval's fault, what remains is generation's.
We found no published work linking complaints to specific regulation sections.
**Midterm plan → done:** ✓ Dense + hybrid vs BM25, then LLM rerank
✓ Attribution on 127 complaints, held-out half
✓ Chunking ablation: section chunks beat fixed 200-token (+0.15 hit@5)
✓ "Any regulation apply?" detector, AUROC 0.74
✓ Demo → officer web app
Changed: NLI checker failed validation → NLI + LLM judge; generation became the bottleneck → rewrite flagged sentences; added the FCRA statute (credit-bureau duties live there).

**Speaker notes:** ~60 seconds. Input: a consumer complaint filed with the CFPB. Output: product/issue, the federal regulation section that governs it, a draft reply citing that section, and a per-sentence report that flags unsupported sentences for a compliance officer. The tool assists an officer; it never replaces one. Prior work: Magesh et al. show commercial legal tools (Lexis+ AI, Westlaw) still hallucinate, but they score the whole system, so they cannot say whether retrieval or generation failed. RAGAS defines faithfulness relative to the retrieved text, which Magesh et al. reject for law. Our contribution is the attribution experiment: same complaint, retrieved vs correct passage. Since the midterm, against the plan we showed then: the midterm had only BM25 and a pilot with an unvalidated checker. We did each planned item: dense and hybrid retrieval plus an LLM reranker; the full attribution experiment on 127 complaints with a held-out half; the chunking ablation (structure-aware section chunks beat fixed 200-token windows by about 15 points hit@5); and a detector for complaints no corpus regulation governs (AUROC 0.74). The Streamlit demo became an officer web app. Three changes, each for a reason: the NLI checker scored only 0.70 against our labels, so we paired it with an LLM judge; once retrieval improved, generation became the bottleneck, so we added rewriting of flagged sentences; and credit-bureau dispute duties are in the FCRA statute rather than Reg V, so we added it to the corpus.

## Slide 2: Public data, hand-checked gold labels, one untouched held-out half

Experimental setup
Data
CFPB complaints: 6.8M rows → 276,378 usable narratives; classifier trained on 111,527, tested on 13,905.
Regulations: Regs E, F, V, Z + FCRA, 2,954 chunks over 167 sections.
Gold: 198 complaints (127 in scope), section labels with κ 0.85–0.90. Split dev 62 / held-out 65; every choice made on dev.
Checker labels: 150 sentence–passage pairs.
Baselines
Retrieval: BM25 (floor), dense and hybrid (MPNet, BGE, E5).
Checker: DeBERTa NLI alone, as in SummaC.
Upper bound: the oracle passage (correct section given by hand).
Pipeline: no rewriting; rewriting driven by NLI alone.
Metrics
Retrieval: hit@k, MRR.
Checker: balanced accuracy vs labels.
Final accuracy: share of draft sentences that are supported by the passage and cite the gold section (or an accepted equivalent).
Acceptable draft: ≥1 correct cited sentence and ≥50% of sentences OK. All with 95% bootstrap CIs.

**Speaker notes:** ~45 seconds. Data is fully public: CFPB Consumer Complaint Database and eCFR Title 12 plus the FCRA statute. Gold labels: 198 complaints, stratified across regulations (credit reporting is 88% of complaints, so natural sampling would starve Regs E, Z, F). Agreement kappa 0.904 / 0.845 / 0.898. We split complaints into a dev half used for every design choice and a held-out half run once per pre-registered rule. Final accuracy is strict: a sentence only counts if the checker says the passage supports it AND the passage is from the right section. Supported-but-wrong-law counts as a failure, which is the legal point Magesh et al. make against RAGAS.

## Slide 3: Retrieval went from 6% to 77% top-1; the validated checker beats NLI alone

Results 1 · each stage against its baseline (held-out)
Finding the governing section (65 complaints)
Retrieve: r | top-1 | hit@5 | MRR |
BM25 (midterm) | 0.06 | 0.25 | 0.16 |
Hybrid MPNet + BM25 | 0.20 | 0.66 | 0.40 |
+ Nemotron embed, regulation prior | 0.34 | 0.74 | 0.51 |
+ LLM rerank (Nemotron) | 0.54 | 0.88 | 0.66 |
+ GPT rerank with rubric (final) | 0.77 | – | – |
GPT picks one section, so only top-1 applies. Same rubric with Nemotron Super: 0.63.
Checking each sentence (100 held-out pairs)
Checker | balanced acc. |
DeBERTa NLI, cutoff 0.5 | 0.61 |
DeBERTa NLI, tuned cutoff (SummaC-style) | 0.70 |
LLM judge alone (Nemotron Ultra) | 0.75 |
Best alternative: MiniCheck-7B + Ultra | 0.80 |
DeBERTa + Ultra, averaged (final) | 0.83 |
+0.15 over tuned NLI, 95% CI [+0.07, +0.24]. Cutoff chosen on the other 50 pairs.
Held-out half; settings chosen on dev. HHEM and AlignScore also tested (0.74, 0.75 with Ultra). EXPERIMENT_LOG E9, E12, E15, E16.

**Speaker notes:** ~60 seconds. Left: retrieval, the stage that dominated failures at the midterm. BM25 found the governing section first only 6% of the time. Dense plus BM25 hybrid tripled that; adding a prior toward the regulation the classifier predicts, then an LLM reranker that reads the complaint, took top-1 to 54%, and GPT with our labelling rubric to 77%. All settings were chosen on dev, held-out run once. Right: the checker. The SummaC-style NLI checker was only 70% balanced accuracy on regulation text; it misses dropped legal qualifiers. Averaging it with an LLM judge reached 83%, a significant +15 points. We also tried HHEM, AlignScore and Bespoke-MiniCheck; none beat the pair. If asked about labels: set 1 (50) human-adjudicated, set 2 (100) silver, AI-assisted then accepted by a team member.

## Slide 4: Retrieval's share of the error fell from 70 points to 11; generation is now the bigger part

Results 2 · attribution experiment, end to end (65 held-out complaints)
Final accuracy (supported + correct section) | Retrieved | Oracle | Gap, 95% CI |
Midterm: BM25, lenient checker | 0.18 | 0.87 | +0.70 [0.64, 0.77] |
Final pipeline, no rewriting | 0.44 | 0.52 | +0.07 [−0.03, 0.18] |
Final pipeline + rewrite flagged sentences | 0.69 | 0.81 | +0.11 [0.00, 0.23] |
Acceptable drafts, with rewriting | 0.75 | 0.89 |  |
Ablation | Effect on final accuracy |
Rewrite flagged sentences, judged by DeBERTa + Ultra | +0.25 (0.44 → 0.69) |
Same rewriting judged by DeBERTa alone | 0.56 instead of 0.69 |
Drafter prompt: quote the provision (dev) | +0.17 alone, −0.01 with rewriting |
Error analysis: which section each sentence cites
77% gold section
4% accepted equivalent section
7% · 12% wrong section of the right law · wrong law
Midterm row: BM25, DeBERTa at 0.5, all 127 complaints. Paired bootstrap over complaints. Same drafter (Nemotron Super), checker and rewriting on both sides. EXPERIMENT_LOG H2, E17.

**Speaker notes:** ~75 seconds, the main slide. Each complaint is drafted twice: once with what our retriever found, once with the correct passage. The gap is what retrieval costs; what is still missing with the correct passage is generation's fault. At the midterm, with BM25, the gap was 70 points: retrieval was the problem. With the final retriever it is 7 points before rewriting (not significant) and 11 with rewriting. So with the correct passage, about 19% of sentences still fail; generation is now the larger error source, and that is why the rewrite step matters: checking each sentence and rewriting flagged ones added 25 points. Rewriting judged by NLI alone only reached 0.56, so the validated checker is what makes it work. Prompt tweaks help only without rewriting. Error analysis on the right: 77% of sentences cite the gold section, 4% an accepted equivalent, 7% a wrong section of the right law and 12% another law. If asked why oracle is not 100%: even with the correct passage, the checker still finds sentences the passage does not support after two rewrite rounds.

## Slide 5: Fix retrieval first, then let a validated checker gate the draft

Takeaways and limitations
**1 · Where to invest:** Retrieval was the bottleneck (gap +70 points). After reranking it is +11; most remaining errors happen with the correct passage, in generation.
**2 · The checker is the lever:** Checking and rewriting flagged sentences adds 25 points. Prompt changes add nothing once it is on.
**3 · Where this lands:** 75% acceptable drafts. Magesh et al. report 65% accuracy for Lexis+ AI on a different task with lawyer judges: same range, not a head-to-head.
Limitations
- The same checker drives the rewrites and scores them; a human check of 24 rewritten sentences is in progress.
- Rewriting makes drafts address the complaint less often (48% → 34%).
- 65 held-out complaints: wide CIs. 100 of 150 checker labels are AI-assisted.
- Best reranker is a hosted GPT model.
- Drafts assist a compliance officer; they are not legal advice.

**Speaker notes:** ~45 seconds, then Q&A. Main takeaway: the attribution experiment tells practitioners where to spend effort, and the answer changed as we improved the system. First retrieval dominated; after reranking, generation dominates, so the right investment became verification gating, which gave the largest single gain. Be honest about the comparison with Magesh et al.: they graded open-ended legal research answers with lawyers; we score complaint replies with a validated checker against our gold sections. Limitations: the rewrite step and the score share a checker, so part of the gain could be rewrites tuned to the checker; we are labelling 24 rewritten sentences by hand to check. Rewriting also reduces how directly the draft responds to the complaint. Q&A prep: dev was used for every choice, held-out run once per pre-registered rule; κ 0.85–0.90 on gold; checker cutoff chosen on set 1 and tested on set 2.
