"""
Collector: IRS SOI Migration -- state-to-state migration flows for TX & CA,
including adjusted gross income (the "follow the money" data).

Source : IRS Statistics of Income (SOI), state-to-state migration data, derived
         from year-to-year address changes on individual income tax returns.
Access : Direct CSV downloads (one inflow + one outflow file per year pair). No key.
Docs   : https://www.irs.gov/statistics/soi-tax-stats-migration-data

File columns
------------
inflow  (stateinflow{pair}.csv) : y2_statefips(dest), y1_statefips(origin),
        y1_state, y1_state_name, n1, n2, AGI
outflow (stateoutflow{pair}.csv): y1_statefips(origin), y2_statefips(dest),
        y2_state, y2_state_name, n1, n2, AGI
  n1  = number of returns       (proxy for households)   -- count
  n2  = number of individuals   (proxy for persons)      -- count
  AGI = adjusted gross income, THOUSANDS of current (nominal) USD

Aggregate-row codes (in the "other state" fips field)
-----------------------------------------------------
  96 = Total Migration-US and Foreign
  97 = Total Migration-US (interstate)  AND  Total Migration-Same State  <-- SHARED!
       We pick the interstate one by name (ends with "Total Migration-US").
  98 = Total Migration-Foreign

Emitted metrics (per anchor state, per ending year)
---------------------------------------------------
  domestic_in_{returns,individuals,agi}   : interstate inflow  (code 97 US)
  domestic_out_{returns,individuals,agi}  : interstate outflow (code 97 US)
  out_to_{CA|TX}_{returns,individuals,agi}: bilateral outflow to the other anchor

`year` = ending year of the pair (1516 -> 2016). AGI rows are flagged nominal;
count rows use real_or_nominal = "n/a". Suppressed/negative cells are dropped.
Never fabricates.
"""
from __future__ import annotations

import datetime as dt
import io
import sys
from pathlib import Path

import pandas as pd
import requests
import yaml

# --- paths ---
ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "sources.yaml"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_CSV = PROCESSED_DIR / "irs_soi_migration_tx_ca.csv"

# Project scope: the two anchor states. fips -> (name, postal abbrev).
ANCHORS = {"06": ("California", "CA"), "48": ("Texas", "TX")}

COLUMNS = [
    "geo_id", "geo_name", "geo_level", "year", "metric", "value", "unit",
    "real_or_nominal", "source", "source_url", "retrieved_at",
]

# (metric suffix, source column, unit, real_or_nominal)
MEASURES = [
    ("returns", "n1", "returns", "n/a"),
    ("individuals", "n2", "individuals", "n/a"),
    ("agi", "AGI", "thousands of current USD", "nominal"),
]


class IRSSOIError(RuntimeError):
    """Raised on a download or parsing problem."""


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg["sources"]["irs_soi"]


def fetch_csv(url: str, user_agent: str, retrieved_at: str, tag: str) -> pd.DataFrame:
    """Download a migration CSV, save untouched bytes to data/raw/, return a frame."""
    resp = requests.get(url, headers={"User-Agent": user_agent}, timeout=120)
    resp.raise_for_status()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = retrieved_at[:10].replace("-", "")
    (RAW_DIR / f"irs_soi_{tag}_{stamp}.csv").write_bytes(resp.content)
    df = pd.read_csv(io.BytesIO(resp.content), dtype=str, encoding="latin-1")
    for col in ("y1_statefips", "y2_statefips"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.zfill(2)
    return df


def _measure_values(row: pd.Series) -> dict:
    """Parse n1/n2/AGI from a single row. Negative = IRS suppression -> None."""
    vals = {}
    for col in ("n1", "n2", "AGI"):
        txt = str(row.get(col, "")).strip().replace(",", "")
        try:
            num = float(txt)
        except ValueError:
            num = None
        vals[col] = num if (num is not None and num >= 0) else None
    return vals


def _emit(rows: list, vals: dict, prefix: str, anchor_fips: str, anchor_name: str,
          year: int, source: str, source_url: str, retrieved_at: str) -> None:
    for suffix, col, unit, ron in MEASURES:
        value = vals.get(col)
        if value is None:
            continue  # missing/suppressed -> drop, never impute
        rows.append({
            "geo_id": anchor_fips,
            "geo_name": anchor_name,
            "geo_level": "state",
            "year": year,
            "metric": f"{prefix}_{suffix}",
            "value": value,
            "unit": unit,
            "real_or_nominal": ron,
            "source": source,
            "source_url": source_url,
            "retrieved_at": retrieved_at,
        })


def _pick_interstate_total(sub: pd.DataFrame, other_fips_col: str,
                           name_col: str) -> pd.Series | None:
    """
    The interstate 'Total Migration-US' row: code 97 whose name ends with
    'total migration-us' (excludes '...and foreign' [code 96] and the
    '...same state' row that ALSO uses code 97).
    """
    names = sub[name_col].astype(str).str.strip().str.lower()
    hit = sub[(sub[other_fips_col] == "97") & names.str.endswith("total migration-us")]
    if len(hit) == 1:
        return hit.iloc[0]
    return None  # ambiguous/missing -> caller skips rather than guess


def parse_pair(inflow: pd.DataFrame, outflow: pd.DataFrame, pair: str,
               inflow_url: str, outflow_url: str, retrieved_at: str) -> list[dict]:
    year = 2000 + int(pair[2:])
    source = f"IRS SOI Migration 20{pair[:2]}-20{pair[2:]}"
    rows: list[dict] = []

    for fips, (name, _abbr) in ANCHORS.items():
        # interstate inflow: anchor is the destination (y2 == fips)
        in_sub = inflow[inflow["y2_statefips"] == fips]
        in_row = _pick_interstate_total(in_sub, "y1_statefips", "y1_state_name")
        if in_row is not None:
            _emit(rows, _measure_values(in_row), "domestic_in", fips, name,
                  year, source, inflow_url, retrieved_at)

        # interstate outflow: anchor is the origin (y1 == fips)
        out_sub = outflow[outflow["y1_statefips"] == fips]
        out_row = _pick_interstate_total(out_sub, "y2_statefips", "y2_state_name")
        if out_row is not None:
            _emit(rows, _measure_values(out_row), "domestic_out", fips, name,
                  year, source, outflow_url, retrieved_at)

        # bilateral outflow to the *other* anchor state (CA<->TX)
        for other_fips, (_oname, other_abbr) in ANCHORS.items():
            if other_fips == fips:
                continue
            bil = out_sub[out_sub["y2_statefips"] == other_fips]
            if len(bil) == 1:
                _emit(rows, _measure_values(bil.iloc[0]), f"out_to_{other_abbr}",
                      fips, name, year, source, outflow_url, retrieved_at)
    return rows


def main() -> int:
    cfg = load_config()
    base = cfg["base_url"].rstrip("/")
    ua = cfg["user_agent"]
    pairs = [str(p) for p in cfg["year_pairs"]]
    tpl = cfg["file_templates"]
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()

    all_rows: list[dict] = []
    for pair in pairs:
        in_name = tpl["inflow"].format(pair=pair)
        out_name = tpl["outflow"].format(pair=pair)
        in_url, out_url = f"{base}/{in_name}", f"{base}/{out_name}"
        print(f"Downloading IRS SOI {pair} ...")
        inflow = fetch_csv(in_url, ua, retrieved_at, in_name.replace(".csv", ""))
        outflow = fetch_csv(out_url, ua, retrieved_at, out_name.replace(".csv", ""))
        rows = parse_pair(inflow, outflow, pair, in_url, out_url, retrieved_at)
        print(f"  parsed {len(rows)} rows (ending year {2000 + int(pair[2:])})")
        all_rows.extend(rows)

    if not all_rows:
        raise IRSSOIError("No usable rows parsed; refusing to write an empty file.")

    df = (pd.DataFrame(all_rows, columns=COLUMNS)
          .drop_duplicates()
          .sort_values(["geo_name", "metric", "year"])
          .reset_index(drop=True))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"\nWrote {len(df)} rows -> {OUTPUT_CSV.relative_to(ROOT)}")
    print(f"  states : {sorted(df['geo_name'].unique())}")
    print(f"  years  : {df['year'].min()}-{df['year'].max()}")
    print(f"  metrics: {sorted(df['metric'].unique())}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except IRSSOIError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"NETWORK ERROR talking to IRS: {exc}", file=sys.stderr)
        sys.exit(1)
