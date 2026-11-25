"""Drafter that answers through the Codex CLI (GPT on Aditya's ChatGPT Edu login).

Evaluation only (added 2026-11-20 at Aditya's request): it depends on one person's login,
so it must not become a dependency of the app. Same prompt (PROMPT_VERSION), parsing,
citation handling and on-disk cache as NemotronGenerator; only the transport differs.
The model name in the cache key is "codex:<model>", so its cache never mixes with Nemotron's.
"""
from cfpb.generate.nemotron import NemotronGenerator
from cfpb.verify.codex_client import CodexClient

DEFAULT_CODEX_MODEL = "gpt-5.6-sol"


class CodexGenerator(NemotronGenerator):
    def __init__(self, model: str = DEFAULT_CODEX_MODEL, **kw):
        super().__init__(model=f"codex:{model}", **kw)
        self._client = CodexClient(model)

    def _call(self, messages: list[dict]) -> dict:
        return self._client._call(messages)
