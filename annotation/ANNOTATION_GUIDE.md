# Annotation Guide and LLM Cross-Check Prompts

Draft, 2026-10-07. The **rubric decisions marked TBD belong to the two rubric drafters** (CLAUDE.md Sec. 5). Everything else is procedure.

> **Update 2026-10-15: the TA allowed LLM annotation.** The course TA told the team that annotation may be done with LLMs (Claude Code, ChatGPT, and so on), and that LLM bias is acceptable given the team's lack of legal expertise. This supersedes the ground rule below, which stays for history. Labels produced this way are **silver labels** and must be reported as such. Protocol:
>
> 1. **Annotator A:** Claude Code with the project skill `.claude/skills/regulation-annotator/`. It reads the eCFR text through `scripts/reg_lookup.py`, runs an elements test, and quotes verbatim. Output goes to `annotation/llm_labels_<model>.jsonl`, checked by `scripts/check_llm_labels.py` (quote verbatim, section exists).
> 2. **Annotator B:** a **different model family** (for example ChatGPT), labelling blind with the same rubric and access to the same regulation text. Inter-annotator agreement becomes Cohen's kappa between A and B, at regulation and section level.
> 3. **Adjudication:** every A/B disagreement goes to a human team member, who uses Prompt 2 below with the full section text and makes the final call.
> 4. **Human spot-check:** a team member re-checks a random 20 of the agreed items, which estimates the precision of the silver labels.
> 5. **Circularity:** if the target generator or LLM judge is the same family as an annotator, say so in the report.
>
> A 3-item pilot by Annotator A is in `annotation/llm_labels_claude-opus-5-5.jsonl` (`"batch": "pilot"`).

**Ground rule (CLAUDE.md Sec. 5, before 2026-10-15): human labels are ground truth.** LLMs (Claude, and optionally Jev) only *flag* items for a human to re-check. An LLM answer never overwrites a human label, and an item is never labeled by an LLM alone.

---

## 1. What we annotate

### Set A: gold retrieval set (120 items)

- **Input:** `data/processed/annotation_sample.csv`, made by `scripts/run_data_pipeline.py`. It has 30 complaints per candidate regulation (E, F, V, Z).
- **Question per complaint:** *Which section of Reg E, Z, V, or F most directly governs what the company was obliged to do about this consumer's main grievance?*
- **Columns annotators fill:**

| Column | Values | Example |
|---|---|---|
| `gold_regulation` | `E`, `Z`, `V`, `F`, or `NONE` | `Z` |
| `gold_section` | section number, or blank if NONE | `1026.13` |
| `gold_paragraph` | most specific paragraph you are sure of (optional) | `1026.13(d)(1)` |
| `annotator` | your initials | `AD` |
| `confidence` | `1` guess, `2` probable, `3` sure | `2` |
| `notes` | one line: why, plus any second plausible section | "Also 1026.12(b) unauthorized use" |

- **Reference text:** the official eCFR, https://www.ecfr.gov/current/title-12 (Parts 1005, 1026, 1022, 1006). Cite only sections you have actually opened and read, never from memory.

### Set B: checker validation set (50 items)

- **Input:** pairs of (regulation passage, generated sentence). Produce them once the generation stage can draft responses, even a rough version.
- **Label:** `SUPPORTED` if the passage alone entails the sentence; otherwise `UNSUPPORTED`. Background knowledge does not count.
- **Purpose:** the week 3 benchmark of the NLI checker (and optionally Jev) against human judgment.

## 2. Rubric decisions the drafters must make (TBD)

1. **Main grievance.** When a complaint raises several problems, which one counts? Suggested: the one the consumer asks the company to fix.
2. **NONE label.** When to use it, for example when the governing law is the FCRA statute (15 U.S.C. 1681i bureau disputes), RESPA/Reg X, Reg DD, or state law, none of which is in our corpus. Expect this often for credit-reporting complaints (CLAUDE_PROGRESS Sec. 5).
3. **Granularity.** Is section level the gold unit, with paragraph optional? Suggested: yes. Retrieval is scored at section level.
4. **Ties.** If two sections apply, pick the one imposing the *company's* duty (for example, an error-resolution procedure) over a definitions section.
5. **Commentary.** Can a label point to Official Interpretations (Supplement I)? Suggested: no; label the regulation section the commentary interprets.
6. **Statute names in the text.** Template letters often name the FDCPA or FCRA. Label by the facts described, not by the statute the consumer cites.

## 3. Procedure

1. **Pilot (1 hour):** all six label the same 10 items, then discuss disagreements and fix the rubric. Pilot items are relabeled afterwards, and their pilot labels are not used.
2. **Main pass:** every item gets **two independent annotators** (120 items x 2 = 240 labels, 40 per person). Do not discuss items or look at others' sheets until both labels are in. Suggested split: rotate pairs so every annotator overlaps with several others.
3. **Agreement:** Cohen's kappa at regulation level (E/Z/V/F/NONE) and exact-match plus kappa at section level. Report both.
4. **LLM cross-check (Sec. 4):** run *after* both human labels exist, so no one is anchored by the LLM.
5. **Adjudication:** a third person resolves every item where the two humans disagree, and every item the LLM flags. The adjudicated label is the gold label. Record whether the adjudicator changed anything.
6. **Fallback (CLAUDE.md Sec. 5):** if section-level kappa is poor, use regulation-family labels as gold.

Report the LLM's agreement with the final gold labels only as a secondary statistic. Never use it to define gold. If Claude is later chosen as the generator or the entailment judge, note in the report that the same model family helped flag annotations.

---

## 4. Prompt 1: blind third annotator (Set A)

**Use:** for each complaint, *without* showing the human labels. Compare the LLM's answer with the humans' afterwards, and flag any item where the LLM disagrees with either human or reports confidence 1.

**Give the LLM:** this prompt, then the **list of section numbers and headings** for Parts 1005, 1026, 1022, and 1006 (the table of contents from eCFR; Pair B's corpus can generate it), then a batch of 5 to 10 complaints from `annotation_sample.csv` (`complaint_id`, `product`, `issue`, `sub_issue`, `narrative_clean`).

Do not give it `regulation_candidate`, which is our sampling heuristic and would bias it.

```text
You are helping a university research team (CSCI 544, USC) check human
annotations for a dataset that links U.S. consumer financial complaints to
the federal regulation section that governs them. You are a second opinion,
not the ground truth. Your output will be used only to flag items for a
human to re-check.

TASK
For each complaint, identify the ONE section of the following regulations
that most directly governs what the company was obliged to do about the
consumer's main grievance:
  - Regulation E, 12 CFR Part 1005 (electronic fund transfers)
  - Regulation Z, 12 CFR Part 1026 (truth in lending, credit cards, mortgages)
  - Regulation V, 12 CFR Part 1022 (fair credit reporting)
  - Regulation F, 12 CFR Part 1006 (debt collection)

RULES
1. Choose sections ONLY from the SECTION LIST provided below. Never cite a
   section that is not on the list. If you are unsure a section exists,
   do not use it.
2. The main grievance is the problem the consumer asks the company to fix.
3. Judge by the facts described, not by any statute the consumer names.
   Many complaints are template letters citing the FDCPA or FCRA.
4. Use NONE when the governing rule is outside these four parts, for
   example the FCRA statute itself (such as credit bureau dispute
   investigations under 15 U.S.C. 1681i), RESPA / Regulation X, Regulation
   DD, or state law. NONE is a normal, expected answer, not a failure.
5. Prefer the section that imposes the company's duty (for example an
   error-resolution procedure) over a definitions section.
6. Placeholders such as [REDACTED] and [DATE] are privacy masks. Ignore them.
7. Do not give legal advice. You are labeling data.

OUTPUT
Return one JSON object per complaint, one per line, nothing else:
{"complaint_id": "...",
 "regulation": "E|Z|V|F|NONE",
 "section": "e.g. 1026.13, or null",
 "confidence": 1|2|3,          // 1 guess, 2 probable, 3 sure
 "main_grievance": "one sentence",
 "runner_up_section": "section or null",
 "reason": "at most two sentences, referring to facts in the complaint"}

SECTION LIST
<paste the section numbers and headings for Parts 1005, 1026, 1022, 1006>

COMPLAINTS
<paste 5-10 rows: complaint_id, product, issue, sub_issue, narrative_clean>
```

## 5. Prompt 2: adjudication helper (Set A disagreements only)

**Use:** for items where humans disagree, or where the LLM flagged them. A human adjudicator reads the output and decides. This prompt includes the **full text of each candidate section**, copied from eCFR, so the model reasons from the text and not from memory. Magesh et al. show legal tools hallucinating even with retrieval.

```text
You are assisting a human adjudicator on a research annotation project.
The adjudicator makes the final decision. Your job is to lay out the
evidence, not to decide.

Below are one consumer complaint and two or more candidate regulation
sections chosen by different annotators, with each section's full text.

For each candidate section:
 1. Quote the specific sentence(s) of the section, verbatim, that would make
    it apply to this complaint, or say "no sentence applies".
 2. State which facts in the complaint satisfy or fail that sentence's
    conditions (for example: is this a "consumer credit card account"? Is
    the company a "debt collector" as defined? Was there an "electronic fund
    transfer"?).
Then say which candidate fits best, or whether NONE fits better, and give
confidence 1-3. Quote only from the section text provided. If the provided
text is insufficient to decide, say so.

COMPLAINT
<complaint_id, product, issue, narrative_clean>

CANDIDATE SECTIONS
[A] <section number> - annotator <initials>
<full section text from ecfr.gov>
[B] <section number> - annotator <initials>
<full section text from ecfr.gov>
```

## 6. Prompt 3: support check (Set B)

**Use:** as a blind second opinion on the 50 sentence pairs, after humans label them. Flag disagreements for re-check.

```text
You are checking whether a regulation passage supports a sentence, for a
research dataset. Use ONLY the passage. Do not use outside knowledge, even
if you know the sentence is true.

SUPPORTED   = a careful reader of the passage alone would conclude the
              sentence is true (paraphrase and direct implication count).
UNSUPPORTED = the passage contradicts the sentence, is silent on it, or the
              sentence adds details (deadlines, amounts, conditions, section
              numbers) the passage does not contain.

Return one JSON object per pair, one per line:
{"pair_id": "...", "label": "SUPPORTED|UNSUPPORTED", "confidence": 1|2|3,
 "evidence": "verbatim quote from the passage, or null",
 "missing_or_conflicting": "what the passage lacks or contradicts, or null"}

PAIRS
<pair_id, passage, sentence>
```

## 7. Running the prompts

- **Claude.ai (no code):** start a new chat, paste the prompt, the section list, and 5 to 10 complaints. Copy the JSON lines into `annotation/llm_check_<setname>.jsonl`. Use a **fresh chat per batch** so earlier items do not influence later ones. Record the model name and date.
- **API (scripted, later):** the same prompts, with temperature 0 and a cached response per item, can run through the Pair C LLM wrapper once it exists.
- **Jev (optional; see CLAUDE_PROGRESS Sec. 5):** Jev cannot explain itself, but it returns calibrated probabilities. Prompt 1 maps onto a Jev *choice* question (options E/Z/V/F/NONE), and Prompt 3 onto a *yes/no* question. Treat it as one more flagging signal, never as a label.
