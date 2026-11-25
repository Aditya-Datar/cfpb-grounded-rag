"""Verification gating: flagged sentences go back to the drafter (docs/EXPERIMENT_LOG.md E10).

    sentences, cited, checks, info = gate_draft(narrative_clean, draft, context, generator, verifier,
                                                cutoff=T, rounds=2)

Every sentence whose checker entailment is below `cutoff` is sent back to the same drafter,
with the same passages and the whole draft (flagged sentences marked), to be rewritten from
the passages' wording or answered DROP. The checker re-scores each rewrite, and it replaces
the sentence only if it scores higher. Sentences still below the cutoff stay in the draft,
flagged (the "keep" policy; E10 found dropping them gave no held-out gain and removed 35%).

Held-out effect (E10, Super + rubric, 65 complaints): FINAL ACCURACY 0.657 -> 0.705 @0.5 and
0.402 -> 0.454 @T; a GPT-5.6 Sol judge confirmed the rewrites are better supported on dev.
Rewrites are near-verbatim statute text; whether they still address the complaint is not measured.

scripts/run_verification_gating.py uses the same prompt and cache, so the app reuses its answers.
"""
import hashlib
import json
import re

from cfpb.config import OUTPUT_DIR
from cfpb.generate.nemotron import MAX_COMPLAINT_WORDS, format_passages
from cfpb.pipeline.schema import SUPPORTED, UNSUPPORTED, SentenceCheck

CACHE = OUTPUT_DIR / "generation" / "gating_cache"

REVISE_SYSTEM = """You revise draft responses to consumer complaints for a compliance officer at a US financial company. An automatic checker flagged some sentences because the passages they cite do not clearly state what the sentence says.

For each flagged sentence, write a replacement that:
1. States only what the cited regulation passages say, using the passages' own wording wherever possible.
2. Still explains an obligation that applies to this complaint.
3. Adds no fact, deadline, amount, right or party that is not in the passages, and does not describe the consumer's situation.
4. Ends with the tag of each passage that supports it, for example [P1] or [P1][P3].
If no passage supports the point, answer DROP.

Output exactly one line per flagged sentence, in the form
S<number>: <replacement sentence with tags>
or
S<number>: DROP
Output nothing else."""

REVISE_USER = """Complaint:
{complaint}

Regulation passages:
{passages}

Draft (flagged sentences are marked FLAGGED):
{draft}"""

REVISE_VERSION = "rev1-" + hashlib.sha1((REVISE_SYSTEM + REVISE_USER).encode()).hexdigest()[:8]
_LINE = re.compile(r"^\s*S(\d+)\s*:\s*(.+?)\s*$")
_THINK = re.compile(r"<think>.*?</think>", re.S)


def revise_messages(narrative_clean: str, context, sentences: list[str], flagged: set[int]) -> list[dict]:
    draft = "\n".join(f"S{k + 1}{' (FLAGGED)' if k in flagged else ''}: {t}" for k, t in enumerate(sentences))
    complaint = " ".join(narrative_clean.split()[:MAX_COMPLAINT_WORDS])
    return [{"role": "system", "content": REVISE_SYSTEM},
            {"role": "user", "content": REVISE_USER.format(complaint=complaint, passages=format_passages(context),
                                                           draft=draft)}]


def cached_call(generator, messages: list[dict]) -> str:
    """Drafter call cached by (model, revise prompt version, messages)."""
    key = hashlib.sha1(json.dumps([generator.model, REVISE_VERSION, messages], ensure_ascii=False).encode()).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = generator._call(messages)
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return _THINK.sub("", data["choices"][0]["message"].get("content") or "")


def parse_answers(text: str, n: int, flagged: set[int]) -> dict[int, str]:
    """{sentence index: replacement text or 'DROP'} for flagged sentences only."""
    out = {}
    for line in text.splitlines():
        m = _LINE.match(line)
        if m and 0 < int(m.group(1)) <= n and int(m.group(1)) - 1 in flagged:
            out[int(m.group(1)) - 1] = m.group(2)
    return out


def strip_tags(text: str, context) -> tuple[str, list[str]]:
    tags = re.findall(r"\[P(\d+)\]", text)
    ids = [context[int(t) - 1].chunk_id for t in dict.fromkeys(tags) if 0 < int(t) <= len(context)]
    clean = re.sub(r"\s+([.!?,;:])", r"\1", re.sub(r"\s*\[(?:P\d+|NONE)\]", "", text)).strip()
    return clean, ids


def gate_draft(narrative_clean: str, draft, context, generator, verifier, cutoff: float, rounds: int = 2):
    """(sentences, cited chunk ids, SentenceChecks, per-sentence info) after gating.
    info[i] = {"original": text or None if unchanged, "round": n, "model_drop": bool}."""
    sentences, cited = list(draft.sentences), [list(c) for c in draft.cited_chunk_ids]
    checks = list(verifier.verify(draft, context).checks)
    info = [{"original": None, "round": 0, "model_drop": False} for _ in sentences]
    by_id = {c.chunk_id: c for c in context}
    for rnd in range(1, rounds + 1):
        flagged = {i for i, c in enumerate(checks) if c.entail_prob < cutoff and not info[i]["model_drop"]}
        if not flagged:
            break
        answers = parse_answers(cached_call(generator, revise_messages(narrative_clean, context, sentences, flagged)),
                                len(sentences), flagged)
        for i, text in answers.items():
            if text.strip().upper().startswith("DROP"):
                info[i]["model_drop"] = True
                continue
            clean, ids = strip_tags(text, context)
            pids = ids or list(by_id)
            e, k = verifier.score([by_id[p].text for p in pids], clean)
            if clean and e > checks[i].entail_prob:
                info[i]["original"] = info[i]["original"] or sentences[i]
                info[i]["round"] = rnd
                sentences[i], cited[i] = clean, ids
                checks[i] = SentenceCheck(i, clean, pids, e, k, SUPPORTED if e >= verifier.threshold else UNSUPPORTED)
    return sentences, cited, checks, info
