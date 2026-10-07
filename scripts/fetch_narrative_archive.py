"""Download the CFPB FOIA narrative archive exports for our window (~281 MB).

Usage (from repo root, venv active):
    python scripts/fetch_narrative_archive.py

Saves to data/raw/foia_archive/ (git-ignored), skips files already present
with the right size, and writes download_log.json with the date and sizes.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.config import ARCHIVE_BASE_URL, ARCHIVE_DIR, ARCHIVE_FILES  # noqa: E402

# The CDN (Akamai) rejects requests without an Accept header.
HEADERS = {"User-Agent": "csci544-group36-cfpb-research/0.1", "Accept": "*/*"}


def fetch(name: str) -> dict:
    url = ARCHIVE_BASE_URL + name
    path = ARCHIVE_DIR / name
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS),
                                timeout=600) as resp:
        size = int(resp.headers["Content-Length"])
        if path.exists() and path.stat().st_size == size:
            print(f"  have  {name}")
            return {"file": name, "bytes": size, "status": "cached"}
        tmp = path.with_suffix(".part")
        with open(tmp, "wb") as f:
            while block := resp.read(1 << 20):
                f.write(block)
    if tmp.stat().st_size != size:
        raise IOError(f"{name}: got {tmp.stat().st_size} bytes, expected {size}")
    tmp.replace(path)
    print(f"  saved {name} ({size / 1e6:.1f} MB)")
    return {"file": name, "bytes": size, "status": "downloaded"}


def main() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    log = {"downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "source": ARCHIVE_BASE_URL, "files": [fetch(n) for n in ARCHIVE_FILES]}
    (ARCHIVE_DIR / "download_log.json").write_text(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
