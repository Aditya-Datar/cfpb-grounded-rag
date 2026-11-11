# ChatGPT cross-check package (Annotator B)

Purpose: get a second, independent set of labels for all annotation items (120 stratified sample + 78 in-scope top-up = 198) from a **different model family**, so annotator agreement (Cohen's kappa) means something. This follows the TA-approved LLM annotation protocol in `../ANNOTATION_GUIDE.md`.

## Files

| File | Upload when |
|---|---|
| `generated/01_INSTRUCTIONS.md` | Step 1: the rubric. Built from `01_INSTRUCTIONS.template.md`, with the conventions copied from `.claude/skills/regulation-annotator/SKILL.md`, so both annotators share one rubric |
| `generated/02_complaints.md` | Step 1: the 198 complaints, **with no labels** |
| `generated/03_regulation_sections.md` | Step 1: the valid section list (Regs E/F/V/Z + FCRA) |
| `generated/04_reg_E_1005.md` ... `07_reg_Z_1026.md` | Step 1: full regulation rule text |
| `generated/08_FCRA_1681.md` | Step 1: full FCRA statute text |
| `generated/09_claude_labels.md` | **Step 2 only**: Annotator A's labels |
| `PROMPTS.md` | the exact prompts to paste (not uploaded) |

`generated/` is git-ignored. Rebuild it any time with:

```bash
.venv/Scripts/python scripts/make_chatgpt_package.py
```

## Why two steps instead of uploading everything at once

If ChatGPT sees Claude's labels first, it tends to agree with them (anchoring). The agreement score would then be inflated and could not be reported as inter-annotator agreement.

## After ChatGPT

```bash
.venv/Scripts/python scripts/check_llm_labels.py annotation/llm_labels_chatgpt.jsonl
.venv/Scripts/python scripts/compare_annotators.py annotation/llm_labels_claude-opus-5-5.jsonl annotation/llm_labels_chatgpt.jsonl --review annotation/chatgpt_review.jsonl
```

`check_llm_labels.py` rejects labels whose section does not exist or whose quote is not verbatim. If ChatGPT paraphrased quotes, ask it to redo those items.

**Note:** the conventions in the rubric were made while Annotator A (Claude) labelled the items. The team should review and accept them, since both annotators follow them.
