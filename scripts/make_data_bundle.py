"""Zip the git-ignored files teammates need for the final experiments (docs/tasks/README.md).

    python scripts/make_data_bundle.py        # -> outputs/cfpb_data_bundle.zip (upload to the team Drive)

Unzip at the repo root; paths inside the zip are repo-relative. Never includes .env
or any key: the NVIDIA key is shared privately, not through the bundle.
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.config import OUTPUT_DIR, ROOT  # noqa: E402

INCLUDE = [
    "data/processed/annotation_sample.csv",      # complaint text for the gold set (120)
    "data/processed/annotation_topup.csv",       # and the 78 top-up items
    "data/raw/fcra",                             # FCRA statute HTML (chunker input for the chunking ablation)
    "outputs/generation/cache",                  # Nemotron responses already paid for
    "outputs/pipeline_runs/pilot-bm25",          # midterm pilot runs (checker set was sampled from these)
    "outputs/pipeline_runs/pilot-oracle",
    "outputs/retrieval/bm25/ranked.parquet",
    "outputs/retrieval/bm25_no_fcra/ranked.parquet",
]


def main() -> None:
    out = OUTPUT_DIR / "cfpb_data_bundle.zip"
    files = []
    for rel in INCLUDE:
        p = ROOT / rel
        if not p.exists():
            sys.exit(f"missing {rel}")
        files += sorted(f for f in p.rglob("*") if f.is_file()) if p.is_dir() else [p]
    assert not any(f.name == ".env" for f in files)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.relative_to(ROOT).as_posix())
    print(f"wrote {out}: {len(files)} files, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
