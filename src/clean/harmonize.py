"""
Shared harmonization helpers for the analyze layer.

The processed files use the source's native geo id (BEA writes the 5-digit GeoFips
"06000"/"48000"; Census/IRS/EDGAR write the 2-digit FIPS "06"/"48"). This module
derives one canonical state key so every dataset joins cleanly, and provides small
load/pivot helpers used across src/analyze/.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"

FIPS_TO_ABBR = {"06": "CA", "48": "TX"}
ABBR_TO_NAME = {"CA": "California", "TX": "Texas"}


def canonical_state(df: pd.DataFrame) -> pd.DataFrame:
    """Add `state_fips` (2-digit) and `state_abbr` from whatever geo_id is present."""
    df = df.copy()
    df["state_fips"] = df["geo_id"].astype(str).str.zfill(2).str[:2]
    df["state_abbr"] = df["state_fips"].map(FIPS_TO_ABBR)
    return df


def load_processed(name: str) -> pd.DataFrame:
    """Load a data/processed/ CSV (geo_id as string) with the canonical state key."""
    df = pd.read_csv(PROCESSED / name, dtype={"geo_id": str})
    return canonical_state(df)


def metric_series(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Year-indexed wide frame (columns = state_abbr) for a single metric."""
    sub = df[df["metric"] == metric]
    return sub.pivot_table(index="year", columns="state_abbr", values="value")


def write_table(df: pd.DataFrame, name: str, index: bool = True) -> Path:
    TABLES.mkdir(parents=True, exist_ok=True)
    path = TABLES / name
    df.to_csv(path, index=index)
    return path
