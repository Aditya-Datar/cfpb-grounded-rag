"""Stage 4 alternative: an LLM entailment judge (CLAUDE.md Sec. 5 fallback, H4).

Same interface as NLIVerifier, so it drops into the pipeline
(run_pipeline_batch.py --verifier judge) and into the checker benchmark
(scripts/llm_judge.py). The judge must not be the generator's model family
(self-preference); the default is DeepSeek V4.1 Flash on the NVIDIA API catalog,
which uses the same NVIDIA_API_KEY as the generator.

Per sentence, the judge sees the cited passages (or all context if none are
cited) and returns {"label", "support_probability"}; entail_prob = support_probability / 100. Calls are cached on disk by
(model, prompt version, premise, sentence) and spaced to stay under the
API's 40 requests per minute.
"""
import hashlib
import json
import re
import time
from pathlib import Path

from cfpb.config import OUTPUT_DIR
from cfpb.generate.nemotron import NemotronGenerator
from cfpb.pipeline.schema import SUPPORTED, UNSUPPORTED, Draft, RetrievedChunk, SentenceCheck, Verification

DEFAULT_JUDGE = "deepseek-ai/deepseek-v4.1-flash"  # 2026-11-02: tested end to end (30-120 s per call)
SECOND_JUDGE = "mistralai/mistral-large-4-1t-a52b"  # answers, but a reasoning model: slow, needs >1,024 tokens
DEFAULT_CACHE = OUTPUT_DIR / "judge" / "cache"

JUDGE_PROMPT = """You check a sentence drafted for a compliance officer against regulation passages.

The sentence is SUPPORTED only if the passages, read on their own, state or directly entail everything it claims. Background knowledge, plausible inferences, and facts that are true but not stated in the passages do not count: such a sentence is UNSUPPORTED. A sentence that applies a stated rule to the complaint's situation is supported if the rule as stated covers it.

Reply with JSON only, no other text:
{"label": "supported" or "unsupported", "support_probability": integer 0-100}
support_probability is how likely the sentence is SUPPORTED (high for supported, low for unsupported), not how sure you are of your label."""

USER = """Passages:
{premise}

Sentence:
{sentence}"""

JUDGE_PROMPT_VERSION = "judge-v1-" + hashlib.sha1((JUDGE_PROMPT + USER).encode()).hexdigest()[:8]
_THINK = re.compile(r"<think>.*?</think>", re.S)


def parse(text: str) -> tuple[str | None, float | None]:
    """(label, confidence in [0, 1]) from the judge's reply; None where unreadable."""
    text = _THINK.sub("", text or "")
    label = re.search(r'"label"\s*:\s*"(supported|unsupported)"', text, re.I)
    conf = re.search(r'"support_probability"\s*:\s*"?(\d+(?:\.\d+)?)', text)
    lab = label.group(1).lower() if label else None
    c = min(max(float(conf.group(1)) / 100, 0.0), 1.0) if conf else None
    return lab, c


class LLMJudgeVerifier:
    is_stub = False

    def __init__(self, model: str = DEFAULT_JUDGE, threshold: float = 0.5, max_tokens: int = 4096,
                 cache_dir: Path = DEFAULT_CACHE, min_interval: float = 1.6):
        self.model_name, self.threshold = model, threshold
        self.cache_dir, self.min_interval = Path(cache_dir), min_interval
        self._client = NemotronGenerator(model=model, max_tokens=max_tokens)  # reuses the HTTP + retry code
        self._last_call = 0.0

    def _reply(self, premise: str, sentence: str) -> str:
        key = hashlib.sha1(json.dumps([self.model_name, JUDGE_PROMPT_VERSION, premise, sentence],
                                      ensure_ascii=False).encode()).hexdigest()
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            time.sleep(max(0.0, self._last_call + self.min_interval - time.monotonic()))
            self._last_call = time.monotonic()
            data = self._client._call([{"role": "system", "content": JUDGE_PROMPT},
                                       {"role": "user", "content": USER.format(premise=premise, sentence=sentence)}])
            if not data["choices"][0]["message"].get("content"):
                return ""  # e.g. a reasoning model ran out of tokens: not cached, so a rerun retries it
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        return data["choices"][0]["message"].get("content") or ""

    def score(self, premises: list[str], sentence: str) -> tuple[float, str]:
        """(probability supported, raw label). Falls back to the label when no confidence is given;
        an unreadable reply counts as unsupported."""
        label, conf = parse(self._reply("\n\n".join(premises), sentence))
        if conf is None:
            conf = 1.0 if label == "supported" else 0.0
        return conf, label or "unreadable"

    def verify(self, draft: Draft, context: list[RetrievedChunk]) -> Verification:
        by_id = {c.chunk_id: c for c in context}
        all_ids = [c.chunk_id for c in context]
        checks = []
        for i, (sentence, cited) in enumerate(zip(draft.sentences, draft.cited_chunk_ids)):
            premise_ids = [cid for cid in cited if cid in by_id] or all_ids
            p, _ = self.score([by_id[cid].text for cid in premise_ids], sentence)
            checks.append(SentenceCheck(i, sentence, premise_ids, p, None,
                                        SUPPORTED if p >= self.threshold else UNSUPPORTED))
        return Verification(checks, verifier=f"llm-judge:{self.model_name}:{JUDGE_PROMPT_VERSION}",
                            threshold=self.threshold)
