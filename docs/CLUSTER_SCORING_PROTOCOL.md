# Protocol: cluster-based scoring of drafted responses

Status: DRAFT, 2026-11-19. Author: Aditya, with Claude. Decisions in Sec. 2 were made by Aditya on 2026-11-19.
Nothing in this protocol has been run. The clusters must be built and frozen (Sec. 6) before any run is scored with them.

## 1. Why this exists

The current end-to-end metric (`scripts/attribution_pilot.py`, lines 83-88) counts a drafted sentence as correct only if:
- the NLI checker says its cited passage supports it, **and**
- the cited passage belongs to the **single** gold section of the complaint.

That is the right instrument for the attribution experiment (retrieved vs oracle context, both scored the same way). It is the wrong instrument for "does the system work", because one consumer complaint often engages several duties at once.

Example, complaint 15284705 (identity theft; gold 1681c-2):
- The draft states supported duties under 1681c-2 (block), 1681i (reinvestigation), 1681s-2 (furnisher investigation) and 1022.43 (direct disputes).
- It scores 20%, because only the 1681c-2 sentence matches the gold section.

On the full-llm_rerank run:
- 58% of sentences cite another section of the gold regulation, and 90% of those are supported.
- Only 25% score as correct under the strict rule.

The strict score therefore understates whether the drafts are usable. This protocol defines a second score that credits sections which legitimately govern the same complaint issue, while keeping it strict enough that a draft of off-topic provisions still fails.

**Disclosure (must appear in the report).** This metric was designed after the strict results were seen. Both scores are reported. The strict score stays the metric for the attribution experiment (H2/H3).

## 2. Decisions taken

| Question | Decision |
|---|---|
| What anchors a cluster | The complaint's **CFPB issue category** (the `issue` field), scoped by its gold section. One cluster per distinct (issue, gold section) pair: 55 clusters over the 127 attribution complaints. |
| Where cluster members come from | CFPB examination procedures (topic modules), explicit cross-references in the rule text, and the official interpretations, read through the `regulation-annotator` skill. |
| Who builds and reviews | No further human annotation (Aditya, 2026-11-19). The `regulation-annotator` skill (Claude) builds each cluster; a second, different LLM reviews it (Sec. 5). |
| "Draft must address the main issue" rule | Yes, as a complaint-level secondary score (Sec. 7). |

## 3. Why anchor on the CFPB issue

CFPB routes and publishes every complaint by product and issue, and the company's response (due within 15 days) answers that issue. A compliance officer reads a complaint as "what must we do about this problem", not "which single paragraph is it". A cluster keyed to (issue, gold section) asks exactly that: which provisions impose duties on this company for this kind of problem.

The CFPB's own examination procedures group provisions the same way, by topical module:
- FCRA procedures: Modules 1-5 [1].
- Consumer reporting larger-participant procedures: ten modules, with Module 6 on consumer disputes and reinvestigation [2].
- EFTA procedures: error resolution as one unit [3].

These are the authority for "these sections belong together". The 2012 FCRA and 2019 EFTA documents are the versions found on 2026-11-19. The builder must use the current editions listed on the manual page [4] and record which edition it used.

## 4. What may be in a cluster

A section is a member of the cluster for (issue I, gold section G) only if **all** of these hold:

1. **It imposes a duty on the company type** in the complaint (CRA, furnisher, card issuer, financial institution, debt collector).
2. **The duty is triggered by the facts typical of issue I**, for example a dispute, an error notice, an identity-theft report or a validation request.
3. **It is in the corpus:** Reg E, Z, V, F or the FCRA, with the section listed in `annotation/regulation_sections.md`.
4. **It is not a definitions, scope, effective-date, general-provision or model-form section.** Examples: 1005.2, 1026.2, 1006.2, 1022.41, 1681a and 1005.1.
5. **The builder quotes verbatim the sentence of the rule that creates the duty,** and names its link to G. The link type is one of:
   - cross-reference
   - same examination module, with the module named
   - an official interpretation that pairs them
   - the same triggering event

Size cap: at most **6 members** besides G. If more qualify, keep the six most directly triggered and list the rest as "considered, excluded".

G is always a member. Each member carries a tier label:
- `core`: G itself, plus any section that sets the same duty for a different respondent. Example: 1681i for a CRA and 1681s-2(b) for a furnisher on the same dispute.
- `related`: a duty that can also apply to the same complaint, but is not the main one.

## 5. How clusters are built and checked

**Inputs to the builder.** Only the cluster key: issue text, gold section, gold regulation, and the respondent type from the gold set. Plus the regulation text through `scripts/reg_lookup.py`.
- The builder never sees drafts, retrieved lists, run outputs or this project's results files. This keeps the clusters independent of what the system happened to cite.
- The input file is generated by a script that reads only `annotation/gold_final.jsonl` and the complaint metadata.

**Builder:** the `regulation-annotator` skill, which applies its method (Sec. "Method") to the cluster question. For each candidate it:
- prints the section text (`--interp` for regulations),
- runs the five membership tests above,
- records each test as met or not met, with the verbatim duty quote.

Output: `annotation/clusters_claude.jsonl`, one line per cluster:
`{key, issue, gold_section, members:[{section, tier, link_type, link_evidence, duty_quote}], excluded:[{section, reason}], edition_notes}`.

**Reviewer.** A second, different LLM reviews each proposed member, following the skill's silver-label rule (cross-check by a different model).
- **Model:** `mistralai/mistral-large-4-1t-a52b` through the NVIDIA API, the judge model already benchmarked in H4 (`results/llm_judge_mistral-large-4-1t-a52b_v2.json`).
- **What it sees:** the key, the member's section text and the builder's duty quote.
- **What it answers:** accept or reject, with a one-line reason.
- **Blindness:** it does not see the builder's other members.

**Resolution.**
- A member enters the frozen cluster only if **both** models accept it. This conservative choice limits leniency.
- Report agreement (percent and Cohen's kappa) between the builder and the reviewer over all proposed members.
- Rejected members are kept in the file with the reviewer's reason, for transparency.

**Label status.** These are silver labels made by LLMs, not human-validated. Per `annotation/ANNOTATION_GUIDE.md` (line 69), the report must say that Claude helped produce the evaluation labels. The generator (Nemotron) and the checker (DeBERTa) are different model families from both cluster models.

## 6. Freeze

Before any run is scored:
1. Commit `annotation/clusters_frozen.jsonl` (the members both models accepted).
2. Record its SHA-256 and the commit hash in `results/cluster_freeze.json`.

The scorer refuses to run if the file's hash does not match. No cluster may change after freezing. A needed correction becomes a new version, with both versions reported.

## 7. Scoring

Each drafted sentence gets exactly one tier, from the sections of its premise chunks (cited passages, or all passages when it cites none, as the checker already does). The sentence takes the **best** tier among its premises.

| Tier | The sentence's premise includes | Counts as correct |
|---|---|---|
| 1 | The gold section G | yes |
| 2 | A frozen cluster member of the complaint's (issue, G) key | yes |
| 3 | Another section of the gold regulation (FCRA and V treated as one family) | no |
| 4 | Only sections of other regulations, or `[NONE]` | no |

**Headline: final accuracy.** The share of drafted sentences that are supported by the checker **and** in tier 1 or 2, micro-averaged over all sentences of the 127 attribution complaints.
- Reported at both checker cutoffs, 0.5 and T = 0.99658203125.
- 95% CIs by bootstrap over complaints.
- This is the single "does the system work" number.

**Secondary scores** (reported, not headline):
- **Complaint-level acceptable draft:** at least one supported tier-1 sentence, or a tier-2 sentence of tier label `core`, so that the main issue is addressed; **and** at least half of its sentences supported and in tiers 1-2.
- **Tier distribution** of all sentences (1/2/3/4), with the share supported in each.
- **Strict score** (tier 1 only), the current metric, for continuity and for H2/H3.
- **Retrieval, cluster hit@5:** a cluster member or G among the five retrieved sections. Reported beside the strict hit@5, not instead of it.

**Runs to score:**
- full-llm_rerank (5 distinct sections)
- full-llm_top1 (top section only; checker running now)
- full-oracle-local (oracle)
- full-hybrid_mpnet (H1), if its `sentences.parquet` is recovered from Anirudh's Drive. Otherwise it is reported as strict-only.

**Selection rule.** If the cluster score is used to choose between run configurations, choose on the dev half (`metrics.half == 0`) and report the held-out half.

## 8. Known risks and how they are handled

| Risk | Handling |
|---|---|
| Clusters too broad, so everything passes | Duty-only membership, the 6-member cap, both models must accept, and tier-3 sentences still fail |
| Clusters bent to fit system output | The builder is blind to outputs; the freeze comes before scoring |
| Only LLMs judge relevance | Disclosed as silver labels; second-model cross-check with agreement reported; human spot-check deliberately omitted (decision in Sec. 2) |
| Legal-advice framing | The clusters are evaluation labels, not legal conclusions; the tool still assists a compliance officer and never replaces one |
| Post-hoc metric | Disclosed; strict score always reported beside it |

## 9. Work plan (after this protocol is approved)

1. **Key file:** script writes `annotation/cluster_keys.jsonl`, 55 keys from gold and metadata only.
2. **Builder:** `regulation-annotator` skill builds `annotation/clusters_claude.jsonl`, in batches of about 10 keys.
3. **Reviewer:** script calls `mistralai/mistral-large-4-1t-a52b` for each member and writes `annotation/clusters_review_mistral.jsonl`.
4. **Merge and freeze:** script merges, computes agreement, writes `clusters_frozen.jsonl` and the freeze record. Commit (needs Aditya's approval).
5. **Scorer:** `scripts/score_clusters.py` scores the runs in Sec. 7 and writes `results/final_accuracy_clusters.json`.
6. **Report:** add to `results/final_results.json`; the app's About page shows the headline number with the strict score beside it.

## References

[1] CFPB, Fair Credit Reporting Act examination procedures (Oct. 2012). https://files.consumerfinance.gov/f/documents/102012_cfpb_fair-credit-reporting-act-fcra_procedures.pdf
[2] CFPB, Consumer reporting larger participants examination procedures. https://www.consumerfinance.gov/compliance/supervision-examinations/consumer-reporting-larger-participants-examination-procedures/
[3] CFPB, EFTA examination procedures incl. remittances (Mar. 2019). https://files.consumerfinance.gov/f/documents/cfpb_supervision-and-examination-manual_efta-exam-procedures-incl-remittances_2019-03.pdf
[4] CFPB, Supervision and Examination Manual. https://www.consumerfinance.gov/compliance/supervision-exam-manual/

## Amendments (before any freeze or scoring)

- 2026-11-19: the reviewer runs with `reasoning_effort: "low"` and `max_tokens` 4096. At the default effort, each call took about 3 minutes (a trivial prompt took 195 s), so 230 reviews would have taken about 14 hours; at low effort, one call took 4 s. The 16 reviews made at default effort were discarded, so every review uses the same settings.
- 2026-11-19: builder-reviewer kappa is undefined, because the builder proposes only members it accepts. In its place, the reviewer also judges one control per cluster, the definitions section of the gold section's law, which the rules exclude. Report the member acceptance rate together with the control rejection rate.
- 2026-11-19: no member cites an examination module as its link. The builder did not check each pairing against a module text, so it claims only `cross_reference` (the rule text names the other section) or `same_trigger`.
