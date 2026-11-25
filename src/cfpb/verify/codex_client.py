"""Chat client that answers through the Codex CLI (`codex exec`) on the user's ChatGPT login.

Evaluation only (added 2026-11-20 at Aditya's request): it depends on one person's
ChatGPT Edu login, so it must not become a dependency of the app or the pipeline.
`_call(messages)` returns an OpenAI-style dict, so LLMJudgeVerifier uses it unchanged
(model names "codex:<model>", e.g. "codex:gpt-5.6-sol").

Each call runs from an empty temporary directory with a read-only sandbox and is told
not to run commands or read files, so the model sees only the prompt.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

NO_TOOLS = "\n\nDo not run any commands or read any files; everything you need is above. Reply with the JSON only."


class CodexClient:
    def __init__(self, model: str, timeout: int = 600):
        self.model, self.timeout = model, timeout

    def _call(self, messages: list[dict]) -> dict:
        prompt = "\n\n".join(m["content"] for m in messages) + NO_TOOLS
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "answer.txt"
            r = subprocess.run(["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
                                "-m", self.model, "-o", str(out), "-"], input=prompt, cwd=d, capture_output=True,
                               text=True, encoding="utf-8", timeout=self.timeout, shell=sys.platform == "win32")
            text = out.read_text(encoding="utf-8") if out.exists() else ""
        if r.returncode != 0:
            raise RuntimeError(f"codex exec exited {r.returncode}")
        return {"choices": [{"message": {"role": "assistant", "content": text}}], "model": f"codex:{self.model}"}
