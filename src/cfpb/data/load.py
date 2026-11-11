"""Stream CFPB complaint exports into one compact Parquet file.

Inputs are the FOIA Reading Room narrative archive exports (zipped CSVs, see
config.ARCHIVE_FILES), which are the only public source of narratives since
the CFPB stopped publishing them on 2026-08-14. Plain CSVs work too. We read
in chunks, keep only the columns we need, filter by Date received, and write
Parquet incrementally. Everything is stored as string.
"""
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from cfpb.config import COLUMN_MAP, KEEP_COLUMNS

SCHEMA = pa.schema([(c, pa.string()) for c in KEEP_COLUMNS])


def _read_header(path: Path) -> list[str]:
    return list(pd.read_csv(path, nrows=0).columns)  # .zip is read transparently


def exports_to_parquet(paths: list[Path], out_path: Path, date_min: str | None = None,
                       date_max: str | None = None, chunksize: int = 500_000) -> int:
    """Convert CFPB export files (.csv or single-CSV .zip) to Parquet.

    date_min/date_max are inclusive YYYY-MM-DD bounds on Date received.
    Returns rows written. The same complaint can appear in more than one
    export, so downstream code drops duplicate complaint_ids.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with pq.ParquetWriter(out_path, SCHEMA) as writer:
        for path in paths:
            header = _read_header(path)
            if "Consumer complaint narrative" not in header:
                print(f"WARNING: {path.name} has no narrative column")
            usecols = [c for c in header if COLUMN_MAP.get(c) in KEEP_COLUMNS]
            for chunk in pd.read_csv(path, dtype=str, usecols=usecols, chunksize=chunksize):
                chunk = chunk.rename(columns=COLUMN_MAP)
                day = chunk["date_received"].str.slice(0, 10)
                if date_min:
                    chunk = chunk[day >= date_min]
                if date_max:
                    chunk = chunk[day.loc[chunk.index] <= date_max]
                for col in KEEP_COLUMNS:
                    if col not in chunk:
                        chunk[col] = None
                writer.write_table(pa.Table.from_pandas(chunk[KEEP_COLUMNS], schema=SCHEMA,
                                                        preserve_index=False))
                written += len(chunk)
                print(f"  {path.name}: {written:,} rows written so far", end="\r")
            print()
    return written
