# Final presentation (Group 36): slide text and speaker notes

Readable copy of the 5-slide final deck (5 min talk + 1 min Q&A). Source files are in `project/` (Claude artifact Slides format: `deck.json` sets slide order, `slides/*.html` hold the slides, `deck.css` the styling). Charts are inline SVG; their data is listed under each slide. Every number comes from `results/` and `docs/EXPERIMENT_LOG.md` on `final-experiments` (commit 8e424b4).

## Slide 1: Which stage fails when AI drafts a regulatory reply?

CSCI 544 · Group 36 · Final presentation
Complaint input text
Classify DistilBERT
Retrieve governing section
Draft cites the section
Check every sentence
Officer reviews flags
Prior work
Magesh et al. 2024: legal AI tools hallucinate 17–33%, but are scored end to end, so the failing stage is unknown.
RAGAS (Es et al. 2024): "faithful" means it matches what was retrieved, not that it is legally correct.
SummaC (Laban et al. 2022): sentence-level NLI checking, our checker's starting point.
What we add: the attribution experiment
B − A = what retrieval costs · 1 − B = what generation costs.
We found no published work linking complaints to specific regulation sections.

**Chart:** Each complaint is drafted twice, from the retrieved passage (score A) and from the correct passage (score B)

**Speaker notes:** ~50 seconds. The problem: a compliance officer has 15 days to answer each CFPB consumer complaint, and must know which federal rule governs it. Input: the complaint text. Output: the governing regulation section, a draft reply that cites it, and every sentence marked supported or flagged. The tool assists an officer; it never replaces one. Prior work: Magesh et al. found that commercial legal AI tools (Lexis+ AI, Westlaw) still hallucinate 17 to 33 percent of the time, but they score the whole system, so you cannot tell whether retrieval or generation failed. RAGAS calls an answer faithful if it matches what was retrieved, which is not legal correctness. SummaC gives us sentence-level checking. What we add is the attribution experiment, in the diagram: draft every complaint twice, once from what our retriever found (score A) and once from the correct passage (score B). The difference B minus A is what retrieval costs; whatever is still wrong with the correct passage is generation's fault.

## Slide 2: Plan delivered, and the bottleneck moved

Progress since the midterm
Midterm plan → done
✓ Dense + hybrid retrieval vs BM25, then LLM rerank
✓ Attribution on all 127 complaints, held-out half
✓ Chunking ablation: section chunks win (+0.15 hit@5)
✓ Out-of-scope detector: AUROC 0.43 → 0.74
✓ Streamlit demo → full officer web app
Changed, and why
→ NLI checker failed validation (0.70), so we added an LLM judge
→ Once retrieval was fixed, generation became the bottleneck, so flagged sentences are rewritten
→ Credit-bureau duties are in the FCRA statute, so we added it
Midterm Final (held-out)
Held-out: 65 complaints; checker: 100 labelled pairs. The midterm accuracy used the lenient 0.5 checker, which flatters it. EXPERIMENT_LOG H1–H5, E12, E17.

**Chart:** Midterm to final: retrieval top-1 6% to 77%; checker balanced accuracy 61% to 83%; final accuracy 18% to 69%; retrieval gap 70 to 11 points

**Speaker notes:** ~55 seconds. Left: the plan we showed at the midterm, and every item is done. We added dense and hybrid retrieval and then an LLM reranker; ran the attribution experiment on all 127 complaints and once on an untouched held-out half; the chunking ablation shows chunks cut at section boundaries beat fixed 200-word windows by about 15 points hit@5; the detector for complaints no regulation in our corpus covers went from AUROC 0.43 to 0.74; and the demo became a full officer web app. Three changes of direction, each for a reason: the NLI checker only reached 0.70 against our labels, so we paired it with an LLM judge; once retrieval improved, generation became the bottleneck, so we rewrite flagged sentences; and credit-bureau duties are in the FCRA statute, not Reg V, so we added it. Right: the four headline numbers, midterm to final. Retrieval top-1 from 6 to 77 percent; checker agreement from 61 to 83; fully correct sentences from 18 to 69; and the gap caused by retrieval from 70 points down to 11.

## Slide 3: Each stage beats its baseline on the held-out half

Experimental setup and results by stage
Data 6.8M complaints → 276K narratives; 2,954 regulation chunks.
Gold labels 198 complaints, κ 0.85–0.90. Dev 62 tunes; held-out 65 tests.
Baselines BM25; NLI checker alone (SummaC); correct passage as ceiling.
Final accuracy Sentence is supported and cites the right section.
95% bootstrap CIs, paired over complaints. Also tested: BGE, E5, HHEM, AlignScore, FactCG (none better). EXPERIMENT_LOG H1, E9, E12, E15, E16.

**Chart:** Retrieval top-1: BM25 6%, hybrid 20%, Nemotron embed plus prior 34%, Nemotron rerank 54%, GPT rerank 77%

**Chart:** Checker balanced accuracy: NLI at 0.5 61%, tuned NLI 70%, Ultra judge 75%, MiniCheck plus Ultra 80%, NLI plus Ultra 83%

**Speaker notes:** ~60 seconds. Setup, top row: public CFPB complaints and eCFR regulations plus the FCRA statute; 198 complaints labelled by two different LLMs under our rubric, every disagreement resolved by a team member, kappa 0.85 to 0.90; every design choice was made on a 62-complaint dev half, and the 65-complaint held-out half was run once per pre-registered rule. Baselines: BM25 for retrieval, the NLI checker alone as in SummaC, and the correct passage as the upper bound. Our main metric is strict: a sentence counts only if the passage supports it AND it cites the right section, which is the legal definition from Magesh et al. Left chart: BM25, the midterm retriever, found the right section first only 6 percent of the time. Hybrid search, a prior toward the classifier's regulation, and an LLM reranker that reads the complaint took it to 54, and GPT with our labelling rubric to 77. Right chart: the SummaC-style NLI checker reached only 70 percent balanced accuracy on regulation text; averaging it with the Nemotron Ultra judge reached 83, a significant 15-point gain. Specialised checkers such as MiniCheck, HHEM and AlignScore did not beat the pair.

## Slide 4: Errors moved from retrieval to generation

Main result · attribution experiment (65 held-out complaints)
Correct Lost to retrieval Lost to generation (wrong even with the correct passage)
Error analysis: section each sentence cites
Ablations
+25 pts from rewriting flagged sentences
0.56 instead of 0.69 if NLI alone picks what to rewrite
+17 pts from a "quote the provision" prompt, ≈0 on top of rewriting (dev)
Same drafter (Nemotron Super), checker and rewriting on both sides; gap = oracle − retrieved, paired bootstrap (per complaint); bars are per sentence. Midterm row: all 127 complaints. EXPERIMENT_LOG H2, E13, E16, E17.

**Chart:** Midterm: 18% correct, 69% lost to retrieval, 13% lost to generation. Final before rewriting: 44% correct, 7% retrieval, 48% generation. Final with rewriting: 69% correct, 11% retrieval, 19% generation.

**Chart:** Sentences cite the gold section 77%, an accepted equivalent 4%, a wrong section of the right law 7%, a wrong law 12%

**Speaker notes:** ~75 seconds, the main slide. Each bar is all the sentences our drafts produced. Blue is correct: supported and citing the right section. Orange is what retrieval costs: the gap between drafting from the retrieved passage and from the correct one. Purple is what is still wrong even with the correct passage, so it is generation's fault. At the midterm, with BM25, the orange part was 70 points: retrieval was the problem. With the final retriever it shrinks to 7 points before rewriting, not significant, and generation is now the big purple block. So we check every sentence and rewrite the flagged ones from the passage: correct sentences go from 44 to 69 percent, a 25-point gain, and the retrieval gap is 11 points, CI 0.00 to 0.23. Ablations: if the NLI checker alone decides what to rewrite, we only reach 0.56, so the validated checker is what makes rewriting work. A prompt telling the drafter to quote the provision helps by 17 points alone but adds nothing on top of rewriting. Error analysis: 77 percent of sentences cite the gold section, 4 an accepted equivalent, 7 the wrong section of the right law and 12 a different law. If asked why the correct passage still is not 100 percent: the drafter applies the rule to the complaint's facts or drops a condition, which the passage alone cannot support.

## Slide 5: Fix retrieval, then check every sentence

Takeaways and limitations
70 → 11 points of error from retrieval Reranking fixed retrieval; most remaining errors happen with the correct passage.
+25 points from check + rewrite The largest single gain. Prompt changes add nothing once it is on.
75% acceptable drafts Magesh et al.: 65% for Lexis+ AI on another task with lawyer judges. Same range, not head to head.
Limitations
- The same checker drives rewrites and scores them; a human check of 24 rewrites is in progress
- Rewriting makes drafts address the complaint less often (48% → 34%)
- 65 held-out complaints, so CIs are wide; 100 of 150 checker labels are AI-assisted
- The best reranker is a hosted GPT model; drafts assist an officer and are not legal advice

**Speaker notes:** ~40 seconds, then Q&A. Three takeaways. One: the attribution experiment tells practitioners where to spend effort, and the answer changed as the system improved: retrieval cost 70 points at the midterm and 11 now. Two: once retrieval is fixed, verification is the lever; checking and rewriting flagged sentences gave the largest single gain, 25 points. Three: 75 percent of drafts are acceptable. Magesh et al. report 65 percent for Lexis+ AI, but on open-ended legal research graded by lawyers, so this is the same range, not a head-to-head. Limitations: the rewrite step and the score share a checker, so part of the gain could be rewrites tuned to the checker; we are labelling 24 rewritten sentences by hand to test that. Rewriting also makes drafts address the complaint less often. Q&A prep: dev was used for every choice and held-out was run once per pre-registered rule; gold kappa 0.85 to 0.90; the checker cutoff was chosen on set 1 and tested on set 2.
