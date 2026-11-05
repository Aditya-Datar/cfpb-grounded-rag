# Prompts to paste into ChatGPT

Run `.venv/Scripts/python scripts/make_chatgpt_package.py` first, so `generated/` is up to date. Use a model with file upload and good reasoning, and write down which model you used.

---

## Step 1: blind labelling (do NOT upload `09_claude_labels.md` yet)

**Upload these 8 files from `generated/`:**
- `01_INSTRUCTIONS.md`
- `02_complaints.md`
- `03_regulation_sections.md`
- `04_reg_E_1005.md`, `05_reg_F_1006.md`, `06_reg_V_1022.md`, `07_reg_Z_1026.md`
- `08_FCRA_1681.md`

Then paste:

```text
You are Annotator B for a research annotation task. Read 01_INSTRUCTIONS.md completely and follow it exactly. It is your rubric.

Task: label the complaints in 02_complaints.md, Items 1 to 20 now. For every item, read the candidate sections' text in the uploaded regulation and statute files (04 to 08) before deciding. Cite only sections listed in 03_regulation_sections.md, and copy evidence_quote word for word from those files.

Output exactly 20 JSON lines, one per item, in Item order, inside a single code block, with no other text. Use "annotator": "llm:chatgpt-<your model name>" and today's date.
```

Then, for each next batch (21–40, 41–60, … 181–198), paste:

```text
Continue with Items 21 to 40, following the same rubric and output format exactly. Re-read the regulation text for each item; do not rely on earlier items.
```

If ChatGPT starts to lose track (wrong item numbers or skipped items), open a **new chat**, upload the same 8 files, and continue from the next item.

**Save:** copy every code block, in order, into one file: `annotation/llm_labels_chatgpt.jsonl`, with one JSON object per line and 198 lines in total. Do not edit the labels.

---

## Step 2: compare with Annotator A (after Step 1 is complete)

**Upload:** `generated/09_claude_labels.md` in the same chat (or in a new chat, together with the Step 1 files and your saved labels).

Then paste:

```text
Step 2. 09_claude_labels.md contains Annotator A's labels for the same items. Do NOT change your Step 1 labels.

Compare your label with Annotator A's for every item. Where you agree on the regulation AND section, write nothing. Where you disagree, re-read both sections' text and decide which label is better supported by the rubric and the facts.

Output one JSON line per DISAGREEMENT, in a single code block:
{"complaint_id": "...", "chatgpt_label": "Z 1026.10", "claude_label": "Z 1026.13", "preferred": "chatgpt|claude|neither", "preferred_label": "E|F|V|Z|FCRA|NONE + section", "reason": "max 2 sentences, citing the deciding element or quote"}
```

**Save:** `annotation/chatgpt_review.jsonl`.

---

## Step 3: hand back to Claude Code

Tell Claude: *"ChatGPT labels are in annotation/llm_labels_chatgpt.jsonl and the review is in annotation/chatgpt_review.jsonl."* Claude will:
1. Validate them (`check_llm_labels.py`).
2. Compute agreement (`compare_annotators.py`).
3. Produce `annotation/disagreements.md` for a human teammate to adjudicate.
