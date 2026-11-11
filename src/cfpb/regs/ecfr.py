"""Download regulation text from the eCFR API (https://www.ecfr.gov/developers).

Full-text XML per part:   /api/versioner/v1/full/<date>/title-12.xml?part=<n>
Table of contents (JSON): /api/versioner/v1/structure/<date>/title-12.json?part=<n>
The full-text endpoint requires a compressed response (HTTP 406 otherwise), so
we send Accept-Encoding: gzip and decompress. Verified 2026-10-15.
"""
import gzip
import json
import urllib.request
from pathlib import Path

API = "https://www.ecfr.gov/api/versioner/v1"
HEADERS = {"User-Agent": "csci544-group36-cfpb-research/0.1", "Accept-Encoding": "gzip"}

# Our four regulations (CLAUDE.md Sec. 4).
PARTS = {"1005": "E", "1006": "F", "1022": "V", "1026": "Z"}


def _get(url: str, accept: str) -> bytes:
    req = urllib.request.Request(url, headers={**HEADERS, "Accept": accept})
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    return body


def latest_date(title: int = 12) -> str:
    """Date the eCFR says the title is up to date as of (YYYY-MM-DD)."""
    titles = json.loads(_get(f"{API}/titles.json", "application/json"))["titles"]
    return next(t for t in titles if t["number"] == title)["up_to_date_as_of"]


def fetch_part(part: str, date: str, out_dir: Path) -> Path:
    """Save title-12 part XML as of `date`; skip if already downloaded."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"title-12_part-{part}_{date}.xml"
    if not path.exists():
        body = _get(f"{API}/full/{date}/title-12.xml?part={part}", "application/xml")
        tmp = path.with_suffix(".part")
        tmp.write_bytes(body)
        tmp.replace(path)
    return path
