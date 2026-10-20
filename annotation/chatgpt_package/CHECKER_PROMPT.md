# Checker validation set: instructions for annotator B (ChatGPT)

Upload `annotation/checker_set.md` to a new ChatGPT chat, paste the prompt below, and save the reply as `annotation/checker_labels_chatgpt.jsonl`. Do not show ChatGPT the other annotator's labels or the checker's scores (`checker_set.md` contains neither).

---

You are annotating a validation set for an automatic fact-checker. The attached file has 50 pairs, K01 to K50. Each pair is one **sentence** from an AI-drafted reply to a consumer complaint, and the **passage** of US regulation text (12 CFR or 15 U.S.C.) it was checked against.

For each pair, decide:

- **supported**: the passage, read on its own, states or directly entails everything the sentence claims. Paraphrase is fine. Every fact, deadline, amount, party, condition and obligation in the sentence must be in the passage.
- **unsupported**: anything else. That includes a sentence that is partly supported but adds a claim the passage lacks, a claim that is true in reality but not stated in this passage, a sentence that contradicts the passage, a sentence that changes a condition (for example "must" where the passage says "may", or drops an "if"), and statements about the specific complaint's facts that the passage cannot confirm.

Judge only against the passage shown. Do not use outside legal knowledge. When in doubt, choose unsupported.

Output exactly 50 lines of JSON Lines and nothing else, one per pair, in order:

{"pair_id": "K01", "label": "supported", "rationale": "<one short sentence naming the passage text that supports it, or the claim that is missing>"}
