"""Settings for the officer app, read from the environment or the repo's git-ignored .env.

    DATABASE_URL           Postgres URL (Neon). Unset: a local SQLite file under outputs/app/.
    CFPB_APP_SCHEMA        Postgres schema for the app's tables (default cfpb_app).
    CFPB_GENERATOR_MODEL   NVIDIA model id for drafting. The project's frozen model
                           (nvidia/nemotron-3-super-120b-a12b) reached end of life on
                           2026-10-03 (HTTP 410), so the default is the model Anirudh's
                           full runs used. Pending a team decision.
    CFPB_GENERATOR_MAX_TOKENS, CFPB_GENERATOR_TIMEOUT   as in those runs (16384, 600 s).
    CFPB_NLI_CUTOFF        entailment cutoff for "supported"; default Atharva's T, frozen
                           on checker set 1 (docs/tasks/results/atharva.md).
    CFPB_RETRIEVER         bm25 (default), dense or hybrid; CFPB_HYBRID_ALPHA for hybrid.
    CFPB_LOAD_NLI          0 to skip loading the NLI model (sentence checks then unavailable).
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app"
ARTIFACTS = APP_DIR / "backend" / "artifacts"
FRONTEND_DIST = APP_DIR / "frontend" / "dist"


def _dotenv() -> dict[str, str]:
    path = ROOT / ".env"
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, sep, value = line.partition("=")
            if sep and not name.strip().startswith("#"):
                out[name.strip()] = value.strip().strip('"').strip("'")
    return out


_ENV = _dotenv()


def setting(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name) or _ENV.get(name) or default


DATABASE_URL = setting("DATABASE_URL") or f"sqlite:///{(ROOT / 'outputs' / 'app' / 'app.db').as_posix()}"
SCHEMA = setting("CFPB_APP_SCHEMA", "cfpb_app")
GENERATOR_MODEL = setting("CFPB_GENERATOR_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")
GENERATOR_MAX_TOKENS = int(setting("CFPB_GENERATOR_MAX_TOKENS", "16384"))
GENERATOR_TIMEOUT = int(setting("CFPB_GENERATOR_TIMEOUT", "600"))
NLI_CUTOFF = float(setting("CFPB_NLI_CUTOFF", "0.99658203125"))
RETRIEVER = setting("CFPB_RETRIEVER", "bm25")
HYBRID_ALPHA = float(setting("CFPB_HYBRID_ALPHA", "0.5"))
LOAD_NLI = setting("CFPB_LOAD_NLI", "1") != "0"
HAS_NVIDIA_KEY = bool(setting("NVIDIA_API_KEY"))

# CFPB: companies give an initial response within 15 calendar days, a final one within 60.
INITIAL_RESPONSE_DAYS = 15
FINAL_RESPONSE_DAYS = 60
