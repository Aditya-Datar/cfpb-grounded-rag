"""Settings for the officer app, read from the environment or the repo's git-ignored .env.

    DATABASE_URL           Postgres URL (Neon). Unset: a local SQLite file under outputs/app/.
    CFPB_APP_SCHEMA        Postgres schema for the app's tables (default cfpb_app).
    CFPB_GENERATOR_MODEL   NVIDIA model id for drafting. The project's frozen model
                           (nvidia/nemotron-3-super-120b-a12b) reached end of life on
                           2026-10-03 (HTTP 410), so the default is the model Anirudh's
                           full runs used. Pending a team decision.
    CFPB_GENERATOR_MAX_TOKENS, CFPB_GENERATOR_TIMEOUT   as in those runs (16384, 600 s).
    CFPB_CHECKER           ensemble (default with an NVIDIA key): mean(DeBERTa NLI, Nemotron Ultra 550B judge)
                           >= CFPB_ENSEMBLE_CUTOFF (0.97378, chosen on checker set 1; set-2 balanced accuracy
                           0.829 vs 0.679 for DeBERTa alone; EXPERIMENT_LOG E12b). nli: DeBERTa alone at
                           CFPB_NLI_CUTOFF (default without a key).
    CFPB_NLI_CUTOFF        DeBERTa-only cutoff; default Atharva's T, frozen on checker set 1
                           (docs/tasks/results/atharva.md).
    CFPB_RETRIEVER         llm (default with an NVIDIA key): Nemotron embeddings + BM25 + regulation
                           prior, then Nemotron Super + rubric hints rerank the top 10 sections and
                           the drafter gets the top section's chunks (EXPERIMENT_LOG E5, E9; 2026-11-22); hybrid (H1 winner, mpnet with alpha 0.8; default without a key),
                           dense or bm25. CFPB_HYBRID_ALPHA sets alpha (docs/tasks/results/ishani.md).
    CFPB_RERANK_MODEL      reranker for CFPB_RETRIEVER=llm; default codex:gpt-5.6-sol (GPT through the Codex
                           CLI on the machine's Codex login; best dev reranker, hit@1 0.839 vs 0.774 for Super
                           with rubric hints, EXPERIMENT_LOG E9). An NVIDIA model id uses the NVIDIA API.
    CFPB_RERANK_FALLBACK   used when the reranker fails or gives no answer (default Super); "none" turns it off.
    CFPB_LOAD_NLI          0 to skip loading the NLI model (sentence checks then unavailable).
    CFPB_GATING_ROUNDS     verification gating rounds (default 2; 0 turns it off): sentences below the
                           cutoff go back to the drafter to be rewritten (EXPERIMENT_LOG E10).
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
HAS_NVIDIA_KEY = bool(setting("NVIDIA_API_KEY"))
RETRIEVER = setting("CFPB_RETRIEVER", "llm" if HAS_NVIDIA_KEY else "hybrid")
RERANK_MODEL = setting("CFPB_RERANK_MODEL", "codex:gpt-5.6-sol")
RERANK_FALLBACK = setting("CFPB_RERANK_FALLBACK", "nvidia/nemotron-3.5-super-vl-120b-a12b")
RERANK_FALLBACK = None if RERANK_FALLBACK.lower() == "none" else RERANK_FALLBACK
HYBRID_ALPHA = float(setting("CFPB_HYBRID_ALPHA", "0.8"))
LOAD_NLI = setting("CFPB_LOAD_NLI", "1") != "0"
CHECKER = setting("CFPB_CHECKER", "ensemble" if HAS_NVIDIA_KEY else "nli")
ENSEMBLE_CUTOFF = float(setting("CFPB_ENSEMBLE_CUTOFF", "0.9737792968749999"))
CHECK_CUTOFF = ENSEMBLE_CUTOFF if CHECKER == "ensemble" else NLI_CUTOFF  # the cutoff in force
GATING_ROUNDS = int(setting("CFPB_GATING_ROUNDS", "2"))

# CFPB: companies give an initial response within 15 calendar days, a final one within 60.
INITIAL_RESPONSE_DAYS = 15
FINAL_RESPONSE_DAYS = 60
