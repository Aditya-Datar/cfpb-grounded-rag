# Atharva: H4, the checker cutoff, an LLM judge, and a second label set

Read [README.md](README.md) first (CARC setup, data bundle, rules, hand-back). You need the NVIDIA API key in `.env` (ask Aditya privately).

## Goal

Test **H4**: can the sentence checker be trusted to flag unsupported sentences? At the midterm the DeBERTa-v3 NLI checker was scored against 50 adjudicated (passage, sentence) pairs (`annotation/checker_set.jsonl`, `annotation/checker_gold.jsonl`, `results/checker_benchmark.json`): it ranked pairs reasonably (AUROC) but the fixed 0.5 cutoff was poorly placed, and a cutoff tuned on the same 50 pairs is optimistic. Three parts:

1. **LLM judge on set 1.** Benchmark an LLM entailment judge (`src/cfpb/verify/llm_judge.py`, `scripts/llm_judge.py`) against the same gold labels, side by side with NLI. The judge must come from a different model family than the Nemotron generator (self-preference bias). Default: `deepseek-ai/deepseek-v4.1-flash` (tested end to end on 2026-11-02, 30 to 120 s per call); second judge: `mistralai/mistral-large-4-1t-a52b` (answers, but it is a reasoning model and was very slow in testing; if it keeps timing out, report one judge and say why). Other NVIDIA-catalog models returned 404 or timed out.
2. **Cutoff T from set 1.** Take the 5-fold-CV cutoff analysis already in `results/checker_benchmark.json` and fix one cutoff T from set 1 (the in-sample best threshold is in `best_threshold_in_sample`; state which you choose and why). T is then frozen.
3. **Set 2, held out.** Sample a new, larger set from Anirudh's full attribution runs, label it with the same protocol as set 1, and score NLI at 0.5, NLI at the frozen T, and the judge on it. This is the honest test of H4: nothing was tuned on set 2.

## Steps

### Part 1: judge on set 1 (can start now)

```bash
python scripts/llm_judge.py                                             # DeepSeek V4.1 Flash
python scripts/llm_judge.py --model mistralai/mistral-large-4-1t-a52b   # second judge
```
API only, no GPU: run on the login node inside tmux (`tmux new -s judge`), since 50 slow calls take 30 to 90 minutes. 50 calls each, spaced to stay under 40 requests/minute; responses cached in `outputs/judge/cache`. Calls can be slow (tens of seconds). Check `unreadable_replies` in the output: if it is above 2 or 3, look at the cached replies (`outputs/judge/cache/*.json`) and tell Aditya what the model returns rather than editing the parser yourself.

### Part 2: frozen cutoff

Read `results/checker_benchmark.json`. Write down T and the reason in your write-up **before** looking at set 2.

### Part 3: set 2 (after Anirudh hands over `full-bm25` and `full-oracle-nli`)

1. Put his two run folders under `outputs/pipeline_runs/`.
2. Sample 50 pairs per condition, excluding anything already in set 1:
   ```bash
   python scripts/checker_benchmark.py sample --runs full-bm25 full-oracle-nli --tag v2 --per-condition 50 --exclude-tag ""
   ```
   Writes `annotation/checker_set_v2.jsonl` and `annotation/checker_set_v2.md` (the blind annotator view: no condition, no checker score).
3. Labels, same protocol as set 1 (see `CLAUDE_PROGRESS.md`, 2026-10-20): annotator A = Claude and annotator B = ChatGPT, each given only `checker_set_v2.md` and the instructions in `annotation/chatgpt_package/CHECKER_PROMPT.md` (change "50 pairs, K01 to K50" to the new count and ids), each producing `annotation/checker_labels_<annotator>_v2.jsonl` with one `{"pair_id", "label", "rationale"}` per line, label `supported` or `unsupported`. Rule (as for set 1): **supported only if the passage text alone entails the sentence**; background knowledge and plausible inferences are unsupported. Then:
   ```bash
   python scripts/checker_benchmark.py compare --a <annotatorA> --b <annotatorB> --tag v2
   ```
   A human (you; ask Aditya to check a few) fills `- **Adjudicated label:** supported` or `unsupported` for every item in `annotation/checker_disagreements_v2.md`, then:
   ```bash
   python scripts/checker_benchmark.py build-gold --a <annotatorA> --b <annotatorB> --tag v2
   python scripts/checker_benchmark.py score --tag v2 --tau T
   python scripts/llm_judge.py --tag v2 --nli-tau T
   python scripts/llm_judge.py --tag v2 --nli-tau T --model mistralai/mistral-large-4-1t-a52b
   ```
4. Give T to Anirudh for his `report --tau T` rerun.

## Sanity checks

- `scripts/checker_benchmark.py score` on set 1 (no tag) must reproduce `results/checker_benchmark.json` exactly; don't commit a changed copy of it.
- Set 2 must have 100 pairs and no sentence that is also in set 1.
- Annotator agreement (`compare` prints Cohen's kappa) goes in the write-up; low agreement is a finding, not something to hide.

## Deliverables

- `results/llm_judge_mistral-large-4-1t-a52b.json`, `results/llm_judge_deepseek-v4.1-flash.json` (set 1), the same with `_v2`, and `results/checker_benchmark_v2.json`.
- `annotation/checker_set_v2.*`, `annotation/checker_labels_*_v2.jsonl`, `annotation/checker_disagreements_v2.md`, `annotation/checker_gold_v2.jsonl`.
- `docs/tasks/results/atharva.md`: one table per set with rows NLI@0.5, NLI@T, judge A, judge B and columns balanced accuracy, kappa vs gold, recall of unsupported sentences, AUROC; the judge-minus-NLI difference with its CI; inter-annotator kappa on set 2; T and how it was chosen. Then: is H4 supported, and which checker should the final pipeline use?

## Do not

- Do not edit `annotation/checker_gold.jsonl`, `checker_disagreements.md` or any set-1 file.
- Do not change T after seeing set-2 results. If you think T was a bad choice, report both and say which was fixed in advance.
- Do not use Nemotron (any `nvidia/nemotron*` model) as the judge.
