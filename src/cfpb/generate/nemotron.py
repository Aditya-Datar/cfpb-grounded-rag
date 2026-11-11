"""Stage 3: draft a response citing the given passages (CLAUDE.md Sec. 3).

Target LLM (team decision 2026-10-19, Aditya): NVIDIA Nemotron through the
NVIDIA API catalog (OpenAI-compatible chat completions). Keep the model fixed
for every reported number; changing it invalidates collected results.

The API key is read from the environment variable NVIDIA_API_KEY, or from a
git-ignored `.env` file at the repo root (line `NVIDIA_API_KEY=...`).

Every call is cached on disk by cache_key = SHA-1 of (model, prompt_version,
decoding settings, complaint text, context chunk ids and texts), so reruns
and the retrieved/oracle conditions never pay twice for the same input.
"""
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from cfpb.config import OUTPUT_DIR, ROOT
from cfpb.pipeline.schema import Draft, RetrievedChunk
from cfpb.pipeline.stages import citation

API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
DEFAULT_CACHE = OUTPUT_DIR / "generation" / "cache"
MAX_COMPLAINT_WORDS = 1200  # long narratives are cut; the passages matter more

SYSTEM_PROMPT = """You draft responses to consumer complaints for a compliance officer at a US financial company. The officer reviews every draft before anything is sent.

Use ONLY the regulation passages provided. Rules:
1. Write 3 to 6 sentences explaining which obligations in the passages apply to this complaint and what the company must do under them.
2. End every sentence with the tag of each passage that supports it, for example [P1] or [P1][P3].
3. Do not state any fact, deadline, amount or right that is not in the passages.
4. If the passages do not address the complaint, write one sentence saying so, tagged [NONE].
5. No greeting, no sign-off, no headings, no lists. Output only the response text."""

USER_TEMPLATE = """Complaint:
{complaint}

Regulation passages:
{passages}"""

PROMPT_VERSION = "v1-" + hashlib.sha1((SYSTEM_PROMPT + USER_TEMPLATE).encode()).hexdigest()[:8]

_TAG = r"\[(?:P\d+|NONE)\]"
_THINK = re.compile(r"<think>.*?</think>", re.S)


def api_key() -> str:
    key = os.environ.get("NVIDIA_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "NVIDIA_API_KEY":
                key = value.strip().strip('"').strip("'")
    if not key:
        raise RuntimeError("Set NVIDIA_API_KEY in the environment or in .env at the repo root.")
    return key


def format_passages(context: list[RetrievedChunk]) -> str:
    return "\n\n".join(f"[P{i}] {citation(c)}. {c.heading}\n{c.text}".strip()
                       for i, c in enumerate(context, 1))


def split_sentences(response: str, context: list[RetrievedChunk]) -> tuple[list[str], list[list[str]]]:
    """Sentences with their [P#] tags removed, and the chunk ids each one cites."""
    text = _THINK.sub("", response).strip()
    text = re.sub(rf"([.!?])((?:\s*{_TAG})+)", r"\2\1", text)  # "x. [P1]" -> "x [P1]."
    sentences, cited = [], []
    # Line breaks always end a sentence (lists and paragraphs that lack final punctuation);
    # leading list markers ("- ", "* ", "2. ") are dropped.
    pieces = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", line) for line in re.split(r"\n+", text)]
    for raw in (r for line in pieces for r in re.split(r"(?<=[.!?])\s+(?=[A-Z\"(])", line)):
        tags = re.findall(r"\[P(\d+)\]", raw)
        ids = [context[int(t) - 1].chunk_id for t in dict.fromkeys(tags) if 0 < int(t) <= len(context)]
        clean = re.sub(r"\s+([.!?,;:])", r"\1", re.sub(rf"\s*{_TAG}", "", raw)).strip()
        if clean:
            sentences.append(clean)
            cited.append(ids)
    return sentences, cited


class NemotronGenerator:
    is_stub = False

    def __init__(self, model: str = DEFAULT_MODEL, temperature: float = 0.0, max_tokens: int = 4096,
                 cache_dir: Path = DEFAULT_CACHE, timeout: int = 180, retries: int = 5):
        self.model, self.temperature, self.max_tokens = model, temperature, max_tokens
        self.cache_dir, self.timeout, self.retries = Path(cache_dir), timeout, retries

    def messages(self, narrative_clean: str, context: list[RetrievedChunk]) -> list[dict]:
        complaint = " ".join(narrative_clean.split()[:MAX_COMPLAINT_WORDS])
        return [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(complaint=complaint,
                                                                 passages=format_passages(context))}]

    def cache_key(self, narrative_clean: str, context: list[RetrievedChunk]) -> str:
        payload = [self.model, PROMPT_VERSION, self.temperature, self.max_tokens, narrative_clean,
                   [(c.chunk_id, c.text) for c in context]]
        return hashlib.sha1(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()

    def _call(self, messages: list[dict]) -> dict:
        body = json.dumps({"model": self.model, "messages": messages, "temperature": self.temperature,
                           "max_tokens": self.max_tokens}).encode()
        headers = {"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json",
                   "Accept": "application/json"}
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(API_URL, data=body, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code not in (429, 500, 502, 503, 504) or attempt == self.retries - 1:
                    raise RuntimeError(f"NVIDIA API HTTP {e.code}: {e.read()[:300]!r}") from None
            except (urllib.error.URLError, TimeoutError):
                if attempt == self.retries - 1:
                    raise
            time.sleep(2 ** attempt * 5)
        raise RuntimeError("unreachable")

    def raw_response(self, narrative_clean: str, context: list[RetrievedChunk]) -> tuple[str, str]:
        """(response text, cache_key); calls the API only on a cache miss."""
        key = self.cache_key(narrative_clean, context)
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = self._call(self.messages(narrative_clean, context))
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        return data["choices"][0]["message"].get("content") or "", key

    def generate(self, narrative_clean: str, context: list[RetrievedChunk]) -> Draft:
        response, _ = self.raw_response(narrative_clean, context)
        sentences, cited = split_sentences(response, context)
        return Draft(response=" ".join(sentences), sentences=sentences, cited_chunk_ids=cited,
                     context_chunk_ids=[c.chunk_id for c in context], model=self.model,
                     prompt_version=PROMPT_VERSION, is_referral=False)
