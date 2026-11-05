"""Run the single-complaint pipeline from the command line and print JSON.

    python scripts/analyze_complaint.py --text "My bank refused my unauthorized-charge claim ..."
    python scripts/analyze_complaint.py --file complaint.txt
    python scripts/analyze_complaint.py --text "..." --abstain      # exercise the NONE path

Same code path as the Streamlit demo (cfpb.pipeline). Stages that are not
built yet run as stubs and are listed under "stubbed_stages". Uses the
classifier in outputs/classifier/<label>/best if present; --require-models
fails instead of falling back to the stub.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.pipeline import load_pipeline  # noqa: E402
from cfpb.pipeline.core import DEFAULT_ISSUE_MODEL, DEFAULT_PRODUCT_MODEL  # noqa: E402
from cfpb.pipeline.stages import StubRetriever  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--text")
    src.add_argument("--file", type=Path)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--product-model", type=Path, default=DEFAULT_PRODUCT_MODEL)
    ap.add_argument("--issue-model", type=Path, default=DEFAULT_ISSUE_MODEL)
    ap.add_argument("--require-models", action="store_true")
    ap.add_argument("--abstain", action="store_true", help="stub retriever abstains (NONE)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    pipe = load_pipeline(args.product_model, args.issue_model, args.require_models, args.k)
    if args.abstain:
        pipe.retriever = StubRetriever(abstain=True)
    text = args.text if args.text is not None else args.file.read_text(encoding="utf-8")
    print(json.dumps(pipe.analyze(text).to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
