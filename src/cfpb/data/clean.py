"""Narrative cleaning.

CFPB scrubs personal information before publishing narratives. Formats
seen in the FOIA archive (surveyed 2026-10-10 over 469,659 narratives):
  - names, account numbers, etc.: runs of X ("XXXX", "XXXXXXXX",
    "XXX-XX-XXXX"), sometimes glued to words ("informationXXXXReason")
  - dates: "XX/XX/XXXX", "XX/XX/2025", "XX/XX/25", and "XX/XX/year>" or
    "XX/XX/scrub>" (optionally followed by "/25"); ~24% of usable
    narratives contain the "year>" form
  - dollar amounts kept but braced: "{$250.00}", "{$.99}", "{>= $9,999,999}",
    occasionally unclosed ("{$1200.00") or nested ("{ {$10.00}")
  - "{ XXXX }" and "{ REMOVED }"
We replace redactions with explicit placeholder tokens so models see one
consistent symbol instead of varying-length X runs, and we record how much
of each narrative was redacted (redaction density) for profiling/filtering.
"""
import hashlib
import re

import pandas as pd

DATE_RE = re.compile(
    r"XX/XX/(?:XXXX|\d{2,4}|[a-z]+>(?:/\d{2,4})?)"  # full masked date
    r"|XX/XX/?(?![X\d/a-z])"                         # day/month, no year
    r"|(?<![X/])XX/\d{4}\b")                         # month/year, e.g. XX/2024
# One or more X-mask chunks separated by space, hyphen or slash collapse to a
# single placeholder. Chunks are 4+ X's (any case; consumers type "xxxx"
# too) or a standalone 2-3 uppercase X's (e.g. the "XXX-XX" of an SSN).
_CHUNK = r"(?:[Xx]{4,}|(?<![A-Za-z])X{2,3}(?![A-Za-z]))"
MASK_RE = re.compile(_CHUNK + r"(?:[\s\-/]+" + _CHUNK + r")*")
MONEY_RE = re.compile(r"\{\s*((?:[<>]=?\s*)?\$\s*[\d,]*(?:\.\d+)?)\s*\}?")
STRAY_BRACE_RE = re.compile(r"\{\s*(?=\$)")  # leftover "{ " from nested braces
BRACED_PLACEHOLDER_RE = re.compile(r"\{\s*(\[(?:REDACTED|DATE)\]|REMOVED)\s*\}")
WS_RE = re.compile(r"\s+")

DATE_TOKEN = "[DATE]"
REDACT_TOKEN = "[REDACTED]"


def _placeholder(token: str):
    """Replacement that pads with a space only where the mask was glued to a
    letter or digit, so "accountXXXX" -> "account [REDACTED]" while
    "XXXX," stays "[REDACTED]," (token counts for punctuation unchanged)."""
    def sub(m: re.Match) -> str:
        s, a, b = m.string, m.start(), m.end()
        left = " " if a > 0 and s[a - 1].isalnum() else ""
        right = " " if b < len(s) and s[b].isalnum() else ""
        return left + token + right
    return sub


def clean_narrative(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = DATE_RE.sub(_placeholder(DATE_TOKEN), text)
    text = MASK_RE.sub(_placeholder(REDACT_TOKEN), text)
    text = MONEY_RE.sub(r"\1", text)
    text = STRAY_BRACE_RE.sub("", text)
    text = BRACED_PLACEHOLDER_RE.sub(
        lambda m: REDACT_TOKEN if m.group(1) == "REMOVED" else m.group(1), text)
    return WS_RE.sub(" ", text).strip()


def redaction_density(cleaned: str) -> float:
    """Fraction of whitespace tokens that are placeholders."""
    tokens = cleaned.split()
    if not tokens:
        return 0.0
    n = sum(t.startswith((DATE_TOKEN, REDACT_TOKEN)) for t in tokens)
    return n / len(tokens)


def text_hash(text: str) -> str:
    """Stable hash of normalized text. One consumer often files the same
    narrative against several companies (e.g. all three credit bureaus);
    we dedupe on this so copies never straddle train and test."""
    norm = WS_RE.sub(" ", text.lower()).strip()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def add_clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["narrative_clean"] = df["narrative"].map(clean_narrative)
    df["n_words"] = df["narrative_clean"].str.split().str.len().fillna(0).astype(int)
    df["redaction_density"] = df["narrative_clean"].map(redaction_density)
    df["text_hash"] = df["narrative_clean"].map(text_hash)
    return df


def filter_narratives(df: pd.DataFrame, min_words: int = 20,
                      max_redaction: float = 0.5) -> pd.DataFrame:
    """Drop near-empty or mostly-redacted narratives and exact duplicates."""
    keep = (df["n_words"] >= min_words) & (df["redaction_density"] <= max_redaction)
    return df[keep].drop_duplicates("text_hash").reset_index(drop=True)
