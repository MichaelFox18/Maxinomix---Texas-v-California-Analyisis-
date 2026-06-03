"""
Collector: Census PEP -- state population and components of change for TX & CA.

Source : U.S. Census Bureau, Population Estimates Program (PEP).
Access : Official PEP flat-file CSVs. The Census Data API is frozen at Vintage 2021
         for PEP and exposes NO components/migration past 2019 (the 2022-2024 API
         endpoints return 404), so the API cannot supply a current 2015->latest
         series with net migration -- the flat files can. No API key required.
Files  : Vintage 2019 (2010-2019) -> used for 2015-2019
         Vintage 2024 (2020-2024) -> used for 2020-latest
         (exact URLs live in config/sources.yaml)
Docs   : https://www.census.gov/programs-surveys/popest.html

Metrics (per state per year): population, net_migration, domestic_migration,
international_migration, births, deaths, natural_change.

Year semantics (flagged via the `unit` column, per CLAUDE.md flow-vs-stock rule):
  - population  -> STOCK: population on July 1 of the year (unit "persons").
  - all others  -> FLOW : change over the year ending July 1 (unit "persons/year").
The 2019->2020 boundary is a vintage break (post-2020-census re-basing); each row
records its vintage in `source` and the exact file in `source_url` for provenance.

Never fabricates: missing columns/values are skipped, never imputed.
"""
from __future__ import annotations

import datetime as dt
import io
import re
import sys
from pathlib import Path

import pandas as pd
import requests
import yaml

# --- paths (this file lives at <root>/src/collect/census_pep.py) ---
ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "sources.yaml"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_CSV = PROCESSED_DIR / "census_pep_tx_ca.csv"

SOURCE_LEVEL = "state"
REAL_OR_NOMINAL = "n/a"   # population/migration are counts, not dollar values

# Tidy-data contract (CLAUDE.md). Order is the written CSV column order.
COLUMNS = [
    "geo_id", "geo_name", "geo_level", "year", "metric", "value", "unit",
    "real_or_nominal", "source", "source_url", "retrieved_at",
]


class CensusError(RuntimeError):
    """Raised on a download or parsing problem."""


def load_pep_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    pep = cfg["sources"]["census"]["pep"]
    start_year = int(cfg.get("time", {}).get("start_year", 2015))
    return {"pep": pep, "start_year": start_year}


def download(url: str, retrieved_at: str) -> tuple[pd.DataFrame, Path]:
    """Download a PEP CSV, save the untouched bytes to data/raw/, return a frame."""
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = retrieved_at[:10].replace("-", "")
    base = url.rsplit("/", 1)[-1].replace(".csv", "")
    raw_path = RAW_DIR / f"census_pep_{base}_{stamp}.csv"
    raw_path.write_bytes(resp.content)
    # Read everything as string to preserve FIPS leading zeros and avoid coercing
    # large population counts; values are cast to float at row-build time.
    df = pd.read_csv(io.BytesIO(resp.content), dtype=str, encoding="latin-1")
    return df, raw_path


def _years_in_file(df: pd.DataFrame, stem: str = "POPESTIMATE") -> list[int]:
    pat = re.compile(rf"^{stem}(\d{{4}})$")
    return sorted(int(m.group(1)) for c in df.columns if (m := pat.match(c)))


def parse_vintage(df: pd.DataFrame, vintage: dict, metric_stems: dict,
                  geo_fips: list[str], sumlev_state: str,
                  start_year: int, retrieved_at: str) -> list[dict]:
    df = df.copy()
    df["SUMLEV"] = df["SUMLEV"].astype(str).str.zfill(3)
    df["STATE"] = df["STATE"].astype(str).str.zfill(2)
    states = df[(df["SUMLEV"] == sumlev_state) & (df["STATE"].isin(geo_fips))]

    file_max = _years_in_file(df)[-1] if _years_in_file(df) else None
    y_min = max(int(vintage["year_min"]), start_year)
    y_max = int(vintage.get("year_max") or file_max)
    if file_max is not None:
        y_max = min(y_max, file_max)
    years = list(range(y_min, y_max + 1))

    rows: list[dict] = []
    for _, rec in states.iterrows():
        geo_id, geo_name = rec["STATE"], rec["NAME"]
        for metric, spec in metric_stems.items():
            for year in years:
                col = next((f"{s}{year}" for s in spec["stems"]
                            if f"{s}{year}" in df.columns), None)
                if col is None:
                    continue
                raw = rec.get(col)
                if pd.isna(raw) or str(raw).strip() == "":
                    continue
                try:
                    value = float(str(raw).strip())
                except ValueError:
                    continue  # unparseable -> skip, never guess
                rows.append({
                    "geo_id": geo_id,
                    "geo_name": geo_name,
                    "geo_level": SOURCE_LEVEL,
                    "year": year,
                    "metric": metric,
                    "value": value,
                    "unit": spec["unit"],
                    "real_or_nominal": REAL_OR_NOMINAL,
                    "source": vintage["label"],
                    "source_url": vintage["url"],
                    "retrieved_at": retrieved_at,
                })
    return rows


def main() -> int:
    cfg = load_pep_config()
    pep = cfg["pep"]
    geo_fips = [str(g) for g in pep["geo_fips"]]
    sumlev_state = str(pep["sumlev_state"])
    metric_stems = pep["metric_stems"]
    start_year = cfg["start_year"]
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()

    all_rows: list[dict] = []
    for vintage in pep["vintages"]:
        print(f"Downloading {vintage['label']} ...")
        df, raw_path = download(vintage["url"], retrieved_at)
        print(f"  raw -> {raw_path.relative_to(ROOT)}  ({len(df)} rows, {len(df.columns)} cols)")
        rows = parse_vintage(df, vintage, metric_stems, geo_fips,
                             sumlev_state, start_year, retrieved_at)
        yrs = sorted({r["year"] for r in rows})
        print(f"  parsed {len(rows)} rows for years {yrs[0]}-{yrs[-1]}" if yrs
              else "  parsed 0 rows")
        all_rows.extend(rows)

    if not all_rows:
        raise CensusError("No usable rows parsed; refusing to write an empty file.")

    df_out = (pd.DataFrame(all_rows, columns=COLUMNS)
              .drop_duplicates()
              .sort_values(["geo_name", "metric", "year"])
              .reset_index(drop=True))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(OUTPUT_CSV, index=False)

    print(f"\nWrote {len(df_out)} rows -> {OUTPUT_CSV.relative_to(ROOT)}")
    print(f"  states : {sorted(df_out['geo_name'].unique())}")
    print(f"  years  : {df_out['year'].min()}-{df_out['year'].max()}")
    print(f"  metrics: {sorted(df_out['metric'].unique())}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CensusError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"NETWORK ERROR talking to Census: {exc}", file=sys.stderr)
        sys.exit(1)
