# Instructions for Annotator B (ChatGPT): regulation labels for CFPB complaints

You are the **second, independent annotator** on a university research project (CSCI 544, USC). For each consumer complaint, decide which section of our legal corpus governs the company's obligation for the consumer's main grievance, or answer **NONE** if the governing law is outside the corpus. These are **research labels, not legal advice**. Another model (Annotator A) labelled the same complaints. You will compare with it only in Step 2, so in Step 1 work blind.

**Corpus:**
- Regulations **E** (12 CFR 1005), **F** (1006), **V** (1022), and **Z** (1026), from eCFR as of 2026-10-13.
- The **Fair Credit Reporting Act** statute (**FCRA**, 15 U.S.C. 1681-1681x, U.S. Code 2024 edition).

**Labels:** `E`, `F`, `V`, `Z`, `FCRA`, or `NONE`.

## Files you have

| File | What it is |
|---|---|
| `01_INSTRUCTIONS.md` | this rubric |
| `02_complaints.md` | the __N_ITEMS__ complaints (Item 1 to __N_ITEMS__), cleaned; `[REDACTED]` and `[DATE]` are privacy masks |
| `03_regulation_sections.md` | every valid section number and title (FCRA sections are written "15 U.S.C. 1681i"; label them as "1681i") |
| `04_reg_E_1005.md`, `05_reg_F_1006.md`, `06_reg_V_1022.md`, `07_reg_Z_1026.md` | full rule text of Regulations E, F, V, Z |
| `08_FCRA_1681.md` | full text of the FCRA statute |
| `09_claude_labels.md` | Annotator A's labels: **Step 2 only** |

## Hard rules

1. **Cite only sections listed in `03_regulation_sections.md`**, and only after reading that section's text in the files. Never cite from memory.
2. **`evidence_quote` must be copied verbatim** from the regulation or statute files. A script checks this and rejects paraphrases. Use `null` for NONE.
3. **Label by the facts, not the laws the consumer cites.** Many complaints are template letters that cite statutes regardless of the facts.
4. **NONE is a normal answer** and is evaluated as abstention. Name the governing law in `governing_law_if_none`.
5. **Work in order** and output every item in your batch, even when the facts are thin. In that case, use confidence 1.

## Method for each complaint

1. **Facts.** Identify:
   - the respondent type: bank, card issuer, CRA, furnisher, third-party debt collector or debt buyer, mortgage servicer, money transmitter or app, prepaid provider, other
   - the product
   - the **main grievance**: what the consumer asks the company to fix
2. **Coverage.** Use the conventions below to choose 1 to 3 candidate sections. Check defined terms when coverage depends on them.
3. **Read** each candidate section's text.
4. **Elements test.** Mark each condition of the provision `met`, `not met`, or `unknown`. A section governs only if no condition is `not met`.
5. **Conclusion.** Choose ONE section: the duty section for the main grievance. Add a paragraph only if you are sure, a verbatim quote, a runner-up that is a *different* section, and a confidence.

## Labelling conventions (shared rubric; copied from the team's annotator skill)

__CONVENTIONS__

## Output format (JSON Lines, one object per complaint, inside one code block)

```
{"complaint_id": "16625083", "annotator": "llm:chatgpt-<model name>", "date": "YYYY-MM-DD", "main_grievance": "one sentence", "company_type": "bank|card_issuer|cra|furnisher|debt_collector|mortgage_servicer|money_transmitter|prepaid_provider|other", "gold_regulation": "E|F|V|Z|FCRA|NONE", "gold_section": "1026.13 or 1681i or null", "gold_paragraph": "1026.13(a)(4) or null", "confidence": 1, "elements": [{"condition": "...", "status": "met|not met|unknown"}], "evidence_quote": "verbatim text or null", "governing_law_if_none": "law name or null", "runner_up_section": "section or null", "rationale": "at most 2 sentences"}
```

Confidence: **3** = every element met from stated facts. **2** = best fit, but some elements unknown. **1** = a guess, or the facts are too thin.
