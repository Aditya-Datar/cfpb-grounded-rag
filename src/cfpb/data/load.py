"""Stream the raw CFPB CSV (multi-GB) into a compact Parquet file.

The full export is ~2 GB / 7M rows, so we read it in chunks, keep only the
columns we need, and write Parquet incrementally. Everything is stored as
string; dates are parsed later where needed.
"""
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from cfpb.config import COLUMN_MAP, KEEP_COLUMNS

SCHEMA = pa.schema([(c, pa.string()) for c in KEEP_COLUMNS])


def _read_header(csv_path: Path) -> list[str]:
    return list(pd.read_csv(csv_path, nrows=0).columns)


def load_narratives(path: Path) -> pd.DataFrame:
    """Load a side file of (Complaint ID, narrative), e.g. a fresh CFPB export
    that still has the narrative column. Returns complaint_id -> narrative."""
    df = pd.read_csv(path, dtype=str,
                     usecols=["Complaint ID", "Consumer complaint narrative"])
    df = df.rename(columns=COLUMN_MAP).dropna(subset=["narrative"])
    return df.drop_duplicates("complaint_id").set_index("complaint_id")


def csv_to_parquet(csv_path: Path, out_path: Path, chunksize: int = 500_000,
                   narratives_path: Path | None = None,
                   require_narrative: bool = False) -> int:
    """Convert csv_path to Parquet at out_path. Returns rows written.

    If the CSV lacks a narrative column, narratives_path can supply one,
    joined on Complaint ID. With require_narrative=True, rows without a
    narrative are dropped (what the classifier and retriever need).
    """
    header = _read_header(csv_path)
    usecols = [c for c in header if COLUMN_MAP.get(c) in KEEP_COLUMNS]
    has_narrative = "Consumer complaint narrative" in header
    side = load_narratives(narratives_path) if narratives_path else None
    if not has_narrative and side is None:
        print("WARNING: no 'Consumer complaint narrative' column and no "
              "--narratives file. Output will have empty narratives.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with pq.ParquetWriter(out_path, SCHEMA) as writer:
        for chunk in pd.read_csv(csv_path, dtype=str, usecols=usecols,
                                 chunksize=chunksize):
            chunk = chunk.rename(columns=COLUMN_MAP)
            if side is not None:
                joined = chunk["complaint_id"].map(side["narrative"])
                chunk["narrative"] = (chunk["narrative"].fillna(joined)
                                      if "narrative" in chunk else joined)
            for col in KEEP_COLUMNS:
                if col not in chunk:
                    chunk[col] = None
            chunk = chunk[KEEP_COLUMNS]
            if require_narrative:
                chunk = chunk[chunk["narrative"].notna()
                              & (chunk["narrative"].str.strip() != "")]
            writer.write_table(pa.Table.from_pandas(chunk, schema=SCHEMA,
                                                    preserve_index=False))
            written += len(chunk)
            print(f"  ... {written:,} rows written", end="\r")
    print()
    return written
