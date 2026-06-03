"""
Collector: Census ACS 1-year -- housing cost & property-tax reality for TX & CA.

Source : U.S. Census Bureau, American Community Survey (ACS) 1-year estimates, API.
Access : https://api.census.gov/data/{year}/acs/acs1 (free key -> CENSUS_API_KEY).
Docs   : https://www.census.gov/data/developers/data-sets/acs-1year.html

Counter-case to the "no income tax" draw: Texas funds itself with a much higher
effective property-tax rate than California (Prop 13 caps CA), so the cheap-housing
advantage is partly clawed back. This collector pulls the raw inputs; the effective
rate (taxes / value) is derived in the analysis layer (it is unitless and
inflation-robust). 2020 ACS1 was not released (COVID) and is absent from the series.

Metrics (per state per year), nominal current USD:
  median_home_value, median_real_estate_taxes, median_household_income

Never fabricates: ACS jam/annotation values (negative sentinels) are dropped.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "sources.yaml"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_CSV = PROCESSED_DIR / "census_acs_housing_tx_ca.csv"

BASE_URL = "https://api.census.gov/data"
SIGNUP_URL = "https://api.census.gov/data/key_signup.html"
SOURCE_LABEL = "Census ACS 1-year"

COLUMNS = [
    "geo_id", "geo_name", "geo_level", "year", "metric", "value", "unit",
    "real_or_nominal", "source", "source_url", "retrieved_at",
]

STUB_MESSAGE = f"""\
[Census ACS collector -- STUBBED: CENSUS_API_KEY is not set]

No data was pulled or estimated. To enable:
  1. Register a FREE Census API key: {SIGNUP_URL}
  2. Add CENSUS_API_KEY=your-key to .env
  3. Re-run:  python -m src.collect.census_acs
"""


class CensusError(RuntimeError):
    """Raised on an API or parsing problem."""


def get_api_key() -> str | None:
    load_dotenv(ROOT / ".env")
    key = os.getenv("CENSUS_API_KEY")
    return key.strip() if key else None


def load_acs_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["sources"]["census"]["acs"]


def fetch_year(year: int, var_codes: list[str], geo_fips: list[str],
               dataset: str, api_key: str, retrieved_at: str) -> list[dict]:
    url = f"{BASE_URL}/{year}/{dataset}"
    params = {
        "get": "NAME," + ",".join(var_codes),
        "for": "state:" + ",".join(geo_fips),
        "key": api_key,
    }
    resp = requests.get(url, params=params, timeout=60)
    if resp.status_code != 200:
        raise CensusError(f"ACS {year}: HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = retrieved_at[:10].replace("-", "")
    with open(RAW_DIR / f"census_acs1_{year}_{stamp}.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    header, *records = data
    return [dict(zip(header, rec)) for rec in records]


def to_rows(records: list[dict], year: int, code_to_metric: dict,
            retrieved_at: str) -> list[dict]:
    rows: list[dict] = []
    for rec in records:
        geo_id = str(rec.get("state", "")).zfill(2)
        geo_name = rec.get("NAME", "")
        for code, metric in code_to_metric.items():
            raw = rec.get(code)
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value < 0:        # ACS jam/annotation sentinel -> missing
                continue
            rows.append({
                "geo_id": geo_id,
                "geo_name": geo_name,
                "geo_level": "state",
                "year": year,
                "metric": metric,
                "value": value,
                "unit": "USD",
                "real_or_nominal": "nominal",
                "source": SOURCE_LABEL,
                "source_url": f"{BASE_URL}/{year}/{load_acs_config()['dataset']}",
                "retrieved_at": retrieved_at,
            })
    return rows


def main() -> int:
    api_key = get_api_key()
    if not api_key:
        print(STUB_MESSAGE)
        return 0

    cfg = load_acs_config()
    variables = cfg["variables"]               # metric_name -> code
    code_to_metric = {code: name for name, code in variables.items()}
    var_codes = list(code_to_metric.keys())
    geo_fips = [str(g) for g in cfg["geo_fips"]]
    years = [int(y) for y in cfg["years"]]
    dataset = cfg["dataset"]
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()

    all_rows: list[dict] = []
    for year in years:
        print(f"Fetching ACS1 {year} for {geo_fips} ...")
        records = fetch_year(year, var_codes, geo_fips, dataset, api_key, retrieved_at)
        all_rows.extend(to_rows(records, year, code_to_metric, retrieved_at))

    if not all_rows:
        raise CensusError("No usable rows parsed; refusing to write an empty file.")

    df = (pd.DataFrame(all_rows, columns=COLUMNS)
          .sort_values(["geo_name", "metric", "year"]).reset_index(drop=True))
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
    except CensusError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"NETWORK ERROR talking to Census: {exc}", file=sys.stderr)
        sys.exit(1)
