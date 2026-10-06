"""Narrative cleaning.

CFPB scrubs personal information before publishing narratives:
  - names, account numbers, etc. become runs of X ("XXXX", "XXXX XXXX")
  - dates become "XX/XX/XXXX" (sometimes "XX/XX/2025", year kept)
  - dollar amounts are kept but wrapped in braces, e.g. "{$250.00}"
We replace redactions with explicit placeholder tokens so models see one
consistent symbol instead of varying-length X runs, and we record how much
of each narrative was redacted (redaction density) for profiling/filtering.
"""
import hashlib
import re

import pandas as pd

DATE_RE = re.compile(r"\bXX/XX/(?:XXXX|\d{2,4})\b")
REDACT_RE = re.compile(r"\bX{2,}(?:[\s\-/]+X{2,})*\b", re.IGNORECASE)
MONEY_RE = re.compile(r"\{\s*(\$[\d,]+(?:\.\d+)?)\s*\}")
WS_RE = re.compile(r"\s+")

DATE_TOKEN = "[DATE]"
REDACT_TOKEN = "[REDACTED]"


def clean_narrative(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = DATE_RE.sub(DATE_TOKEN, text)
    text = REDACT_RE.sub(REDACT_TOKEN, text)
    text = MONEY_RE.sub(r"\1", text)
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
