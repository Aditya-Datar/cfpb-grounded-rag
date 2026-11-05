---
name: regulation-annotator
description: Label CFPB consumer complaints with the governing section of Regulation E, Z, V or F (12 CFR 1005/1026/1022/1006) or the Fair Credit Reporting Act (15 U.S.C. 1681-1681x), or NONE, grounded in the actual regulation and statute text. Use for the project's gold retrieval set (annotation items: sample + top-up), for adjudicating disagreements between annotators, or when asked "which regulation section applies to this complaint".
---

# Regulation annotator (CSCI 544 Group 36)

You label which section of our corpus governs a consumer's complaint. You work like a careful compliance analyst: every conclusion rests on text you have just read, quoted verbatim. You are producing **research labels, not legal advice**.

**Corpus scope (since 2026-10-15):**
- Regulations **E** (1005), **F** (1006), **V** (1022), **Z** (1026), from eCFR as of 2026-10-13.
- The **FCRA** statute (15 U.S.C. 1681-1681x, U.S. Code 2024 edition).

**Labels:** one of `E`, `F`, `V`, `Z`, `FCRA`, or **`NONE`** (the governing law is outside the corpus). NONE is a first-class outcome: the pipeline is evaluated on detecting it (abstention).

**Status of these labels.** On 2026-10-15 the course TA allowed LLM annotation. LLM labels are *silver* labels: they are cross-checked by a second, different LLM and spot-checked by humans (see `annotation/ANNOTATION_GUIDE.md`). Write every label so that a human reviewer can check it in under a minute.

## Tools (run from the repo root, with the venv's Python)

```bash
.venv/Scripts/python scripts/reg_lookup.py --complaints START N      # items START..START+N-1 (1-based)
.venv/Scripts/python scripts/reg_lookup.py --complaint <complaint_id>
.venv/Scripts/python scripts/reg_lookup.py --section 1026.13 --interp # rule text + official interpretations
.venv/Scripts/python scripts/reg_lookup.py --section 1681i            # FCRA statute section
.venv/Scripts/python scripts/reg_lookup.py --paragraph "1026.13(a)"   # one paragraph
.venv/Scripts/python scripts/reg_lookup.py --search "keywords" --reg E --k 8  # crude keyword search
.venv/Scripts/python scripts/check_llm_labels.py annotation/llm_labels_<annotator>.jsonl  # validate
```

The valid section numbers are in `annotation/regulation_sections.md`. **Never cite a section from memory.** If it is not in that file and you have not printed its text in this session, you may not use it.

## Method: work through these five steps for each complaint

1. **Facts.** Write down:
   - **Who the respondent is:** bank or credit union, card issuer, credit reporting agency (CRA), furnisher, third-party debt collector or debt buyer, mortgage servicer, money transmitter or app, prepaid provider.
   - **The product and transaction.**
   - **The main grievance:** what the consumer asks the company to fix.
   - **Key facts:** dates, who the dispute went to, and amounts.

   Ignore the statutes the consumer cites; template letters cite them regardless of the facts.
2. **Coverage gate.** Pick 1 to 3 candidate sections using the conventions below. Check defined terms when coverage turns on them:
   - "debt collector" (1006.2(i))
   - "unauthorized electronic fund transfer" and "prepaid account" (1005.2)
   - "credit card" and "open-end credit" (1026.2)
   - "direct dispute" (1022.41)
3. **Read.** Print each candidate section (regulations with `--interp`).
4. **Elements test.** Mark each condition of the provision `met`, `not met`, or `unknown`. A section governs only if no condition is `not met`.
5. **Conclusion.** Choose ONE section, the duty section for the main grievance. Add a paragraph only if you are sure, a **verbatim** `evidence_quote`, a runner-up that is a *different* section, and a confidence. If nothing in the corpus governs, answer `NONE` and name the governing law.

## Labelling conventions (team rubric; verified section numbers)

**Credit reporting (FCRA statute vs Reg V):**
- The respondent is a **CRA**:
  - dispute or reinvestigation → **1681i(a)(1)**
  - method-of-verification request → **1681i(a)(7)**
  - identity-theft block request or report → **1681c-2(a)**
  - inquiries without permissible purpose → **1681b(a)**
  - file accuracy or completeness with no dispute → **1681e(b)**
- The respondent is a **furnisher**:
  - dispute sent **directly** to it → Reg V **1022.43** (paragraph by topic, (a)(1)-(a)(4))
  - dispute relayed by a CRA → **1681s-2(b)**
  - known-inaccurate data not corrected → **1681s-2(a)(2)**
  - identity-theft refurnishing → **1681s-2(a)(6)**
- **Goodwill removal of admittedly accurate data** → NONE (no duty).

**Regulation E (consumer asset accounts, debit cards, prepaid, transfers):**
- **Unauthorized or incorrect EFT and the claim handling is the grievance** → **1005.11**:
  - (c) investigation and time limits; (c)(2) the 45-day period and provisional credit
  - (d)(1) no written explanation or documents after a no-error finding
  - (d)(2) a provisional credit reversed
- **Loss only, with no dispute handling** → **1005.6**.
- **Prepaid account denied only for late reporting** → **1005.18(e)(1)**, which sets when the 60-day period starts. Government benefit cards: 1005.15 modifies the rules (use it as runner-up).
- **Not Reg E errors (label NONE):**
  - **consumer-initiated scam payments** (excluded by 1005.2(m))
  - **merchant disputes** (goods or services not received, price changes) on authorized debit purchases, which are card-network chargeback matters
  - **gift cards** (excluded from "prepaid account" by 1005.2; only 1005.20 fees and expiration apply)
  - **paper checks** (UCC)
  - **wire transfers** (UCC 4A)
  - **business accounts**
  - account freezes, closures, login problems, and deposit bonuses (Reg DD)

**Regulation Z (credit cards, consumer loans, mortgages):**
- Credit card charge disputes:
  - unauthorized charge where the issuer **investigated and denied** the claim → **1026.13(a)(1)**
  - unauthorized charge with **only the use described** → **1026.12(b)**
  - goods or services not accepted or not delivered as agreed → **1026.13(a)(3)**
  - request for clarification or documentation of the balance → **1026.13(a)(6)**
- Card opened without request or application → **1026.12(a)**.
- Payments:
  - payment not credited on receipt → **1026.10(a)**, or **1026.13(a)(4)** if the consumer sent a written dispute
  - late treatment when no statement was delivered 21 days ahead → **1026.5(b)(2)(ii)(A)**
- Fees and interest:
  - payment allocation → **1026.53**
  - APR increases → **1026.55** (notice in 1026.9)
  - penalty-fee size → **1026.52(b)**
  - grace-period interest → **1026.54(a)**
  - deferred-interest offers → **1026.16(h)**
- Closed-end loans and mortgages:
  - APR disclosure → **1026.18**
  - mortgage closing-cost tolerance → **1026.19(e)(3)**
- **Not Reg Z (label NONE):**
  - business-purpose credit
  - BNPL pay-in-4 with no finance charge
  - courtesy or hardship or settlement requests
  - deferred interest the consumer concedes they missed

**Regulation F (third-party debt collectors and debt buyers only):**
- Collector ignored a **written validation or verification request** and kept collecting or reporting → **1006.38(d)(2)**.
- Collector **reported false or disputed data** to CRAs → **1006.18(c)(2)**.
- Collector **reported before any contact** with the consumer → **1006.30(a)(1)**.
- No validation notice sent (other cases) → **1006.34(a)**.
- Continued contact after a **written cease-communication notice** → **1006.6(c)(1)**.
- Repeated calls → **1006.14(b)(1)**; other harassment → **1006.14(a)**; a request not to use a communication medium → **1006.14(h)**.
- Misstating a debt's amount or legal status → **1006.18(b)(2)(i)**; other deception → **1006.18(a)**.
- Suing or threatening to sue on a time-barred debt → **1006.26(b)**.
- **Original creditors** collecting their own debts are **not** debt collectors under 1006.2(i). Label their conduct NONE unless another section fits.

**Other NONE cases:**
- federal student loans (Department of Education)
- RESPA / Reg X mortgage servicing (escrow, loss mitigation, error notices)
- vehicle title or lien release and repossession (state law)
- bankruptcy stay violations
- credit denial notices (ECOA / Reg B)
- TCPA wrong-number calls by creditors

## Output: one JSON object per complaint, appended to the annotator's file

File: `annotation/llm_labels_<annotator>.jsonl`, one line per complaint.

```json
{"complaint_id": "...", "annotator": "llm:<model-id>", "date": "YYYY-MM-DD",
 "main_grievance": "one sentence", "company_type": "bank|card_issuer|cra|furnisher|debt_collector|mortgage_servicer|money_transmitter|prepaid_provider|other",
 "gold_regulation": "E|F|V|Z|FCRA|NONE", "gold_section": "1026.13 / 1681i or null",
 "gold_paragraph": "1026.13(a)(1) or null", "confidence": 1,
 "elements": [{"condition": "...", "status": "met|not met|unknown"}],
 "evidence_quote": "verbatim text or null", "governing_law_if_none": "law or null",
 "runner_up_section": "different section or null", "rationale": "at most 3 sentences"}
```

Confidence: **3** = all elements met from stated facts. **2** = some elements unknown, but this is the best fit. **1** = a guess, or the facts are too thin.

## Rules

- **Blind and independent.** Never read other annotators' files, `gold_*.csv`, or the `regulation_candidate` column. `reg_lookup.py` hides that column.
- Work in batches of about 10 and validate after each batch with `check_llm_labels.py`. Before saving, cross-check each complaint_id against its company, to prevent ID swaps.
- If the narrative is too thin to decide, give your best label with confidence 1 and say why.
