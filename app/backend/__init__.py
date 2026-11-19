"""Officer app backend (FastAPI). The pipeline code lives in src/cfpb, so put it on the path."""
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[2] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
