"""
Collector: BEA Regional -- state-level real & nominal GDP for Texas and California.

Source     : U.S. Bureau of Economic Analysis (BEA), Regional dataset.
Table      : SAGDP1 -- state annual GDP summary (real GDP in chained dollars,
             current-dollar/nominal GDP, and the chain-type quantity index).
Dataset doc: https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf
Signup     : https://apps.bea.gov/API/signup/   (free, instant UserID -> BEA_API_KEY)
Endpoint   : https://apps.bea.gov/api/data

What this does
--------------
1. Resolves the SAGDP1 LineCode values for "Real GDP" and "Current-dollar GDP"
   at runtime from BEA's own metadata (GetParameterValuesFiltered) -- no hardcoded
   guessed line numbers. Units and the chained-dollar base year come from the
   response itself (each record's CL_UNIT).
2. Pulls those two measures for California (GeoFips 06000) and Texas (48000),
   all years, then keeps >= start_year (default 2015).
3. Saves each untouched JSON pull to data/raw/ (timestamped, committed, sacred).
4. Writes a tidy long-format CSV to data/processed/ per the CLAUDE.md contract.

Principles (CLAUDE.md): never fabricate or silently estimate. If BEA_API_KEY is
absent, this prints exact registration instructions and exits WITHOUT writing data.
Suppressed/missing BEA values ((NA), (D), ...) are dropped, never filled.
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

# --- paths (this file lives at <root>/src/collect/bea.py) ---
ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "sources.yaml"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_CSV = PROCESSED_DIR / "bea_gdp_tx_ca.csv"

# --- constants ---
BASE_URL = "https://apps.bea.gov/api/data"
DATASET = "Regional"
SIGNUP_URL = "https://apps.bea.gov/API/signup/"
SOURCE_LABEL = "BEA Regional SAGDP1"
DEFAULT_START_YEAR = 2015

# Tidy-data contract (CLAUDE.md). Order is the written CSV column order.
COLUMNS = [
    "geo_id", "geo_name", "geo_level", "year", "metric", "value", "unit",
    "real_or_nominal", "source", "source_url", "retrieved_at",
]

# DataValue strings that mean "no value" -- never coerce these to numbers.
MISSING_FLAGS = {"(NA)", "(D)", "(L)", "(NM)", "N/A", "NA", ""}

STUB_MESSAGE = f"""\
[BEA collector -- STUBBED: BEA_API_KEY is not set]

No data was pulled, and nothing was estimated.

To enable this collector:
  1. Register a FREE BEA API key (an instantly-emailed "UserID"):
         {SIGNUP_URL}
  2. Copy .env.example to .env and add the key:
         BEA_API_KEY=your-key-here
  3. Re-run from the repo root:
         python -m src.collect.bea
"""


class BEAError(RuntimeError):
    """Raised on a BEA API-level error or an unusable response."""


# --------------------------------------------------------------------------- io
def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_api_key() -> str | None:
    load_dotenv(ROOT / ".env")
    key = os.getenv("BEA_API_KEY")
    return key.strip() if key else None


# ------------------------------------------------------------------- BEA client
def _check_error(api: dict) -> None:
    """BEA reports request errors inside the JSON body, not via HTTP status."""
    err = api.get("Error")
    if not err:
        results = api.get("Results")
        if isinstance(results, dict):
            err = results.get("Error")
    if not err:
        return
    if isinstance(err, list):
        err = err[0] if err else {}
    if isinstance(err, str):
        raise BEAError(f"BEA API error: {err}")
    code = err.get("APIErrorCode", "?")
    desc = err.get("APIErrorDescription") or err.get("ErrorDetail") or str(err)
    raise BEAError(f"BEA API error {code}: {desc}")


def _bea_get(params: dict) -> dict:
    """GET the BEA API and return the full parsed JSON payload. Raises on error."""
    query = dict(params)
    query.setdefault("ResultFormat", "JSON")
    resp = requests.get(BASE_URL, params=query, timeout=60)
    resp.raise_for_status()
    try:
        payload = resp.json()
    except ValueError as exc:  # non-JSON body (e.g. an HTML error page)
        raise BEAError(f"BEA returned non-JSON content: {resp.text[:300]}") from exc
    _check_error(payload.get("BEAAPI") or {})
    return payload


def _results(payload: dict) -> dict:
    """Pull the Results object out of a BEA payload (it may be a dict or a list)."""
    results = (payload.get("BEAAPI") or {}).get("Results")
    if isinstance(results, list):
        results = results[0] if results else {}
    return results or {}


def resolve_line_codes(api_key: str, table_name: str, match_map: dict) -> dict:
    """
    Resolve LineCode numbers from BEA metadata by matching official descriptions.

    Returns {kind: (line_code, description)} for each kind in `match_map`, where
    each spec is {include: [...substrings...], exclude: [...substrings...]}.
    """
    payload = _bea_get({
        "UserID": api_key,
        "method": "GetParameterValuesFiltered",
        "datasetname": DATASET,
        "TargetParameter": "LineCode",
        "TableName": table_name,
    })
    values = _results(payload).get("ParamValue", [])
    if isinstance(values, dict):
        values = [values]

    def desc_of(v: dict) -> str:
        return str(v.get("Desc", v.get("Description", "")))

    def code_of(v: dict) -> str:
        return str(v.get("Key", v.get("LineCode", "")))

    resolved: dict[str, tuple[str, str]] = {}
    for kind, spec in match_map.items():
        includes = [s.lower() for s in spec.get("include", [])]
        excludes = [s.lower() for s in spec.get("exclude", [])]
        cands = [
            v for v in values
            if any(inc in desc_of(v).lower() for inc in includes)
            and not any(exc in desc_of(v).lower() for exc in excludes)
        ]
        if not cands:
            available = [desc_of(v) for v in values]
            raise BEAError(
                f"No LineCode in {table_name} matched '{kind}' "
                f"(include={includes}, exclude={excludes}). Available: {available}"
            )
        if len(cands) > 1:
            cands.sort(key=lambda v: len(desc_of(v)))  # prefer the headline total
            print(f"  [warn] multiple LineCodes matched '{kind}'; "
                  f"using shortest: {[desc_of(c) for c in cands]}")
        chosen = cands[0]
        resolved[kind] = (code_of(chosen), desc_of(chosen))
    return resolved


def fetch_table(api_key: str, table_name: str, line_code: str,
                geo_fips: list[str], year: str = "ALL") -> dict:
    """One GetData call: a single LineCode across the given states and years."""
    return _bea_get({
        "UserID": api_key,
        "method": "GetData",
        "datasetname": DATASET,
        "TableName": table_name,
        "LineCode": line_code,
        "GeoFips": ",".join(geo_fips),
        "Year": year,
    })


# ----------------------------------------------------------------- persistence
def save_raw(payload: dict, tag: str, retrieved_at: str) -> Path:
    """Write the untouched JSON pull to data/raw/, timestamped."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = retrieved_at[:10].replace("-", "")
    path = RAW_DIR / f"bea_sagdp1_{tag}_{stamp}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return path


# ----------------------------------------------------------------- transform
def records_to_rows(payload: dict, retrieved_at: str,
                    start_year: int = DEFAULT_START_YEAR) -> list[dict]:
    """
    Map BEA Data records to tidy rows. real_or_nominal and unit are read from the
    response's CL_UNIT (the source of truth), so the labels can never drift from
    what BEA actually returned. Missing/suppressed values are skipped, not filled.
    """
    rows: list[dict] = []
    for rec in _results(payload).get("Data", []):
        raw_value = str(rec.get("DataValue", "")).strip()
        if raw_value in MISSING_FLAGS:
            continue
        try:
            value = float(raw_value.replace(",", ""))
        except ValueError:
            continue  # unparseable -> drop, don't guess

        try:
            year = int(str(rec.get("TimePeriod", "")).strip())
        except ValueError:
            continue
        if year < start_year:
            continue

        unit = str(rec.get("CL_UNIT", "")).strip()
        unit_l = unit.lower()
        if "chained" in unit_l:
            real_or_nominal = "real"
        elif "current" in unit_l:
            real_or_nominal = "nominal"
        else:
            # e.g. a quantity index ("Fisher index"); out of scope for $ GDP -> skip
            continue

        rows.append({
            "geo_id": str(rec.get("GeoFips", "")).strip(),
            "geo_name": str(rec.get("GeoName", "")).strip(),
            "geo_level": "state",
            "year": year,
            "metric": f"gdp_{real_or_nominal}",
            "value": value,
            "unit": unit,
            "real_or_nominal": real_or_nominal,
            "source": SOURCE_LABEL,
            "source_url": BASE_URL,
            "retrieved_at": retrieved_at,
        })
    return rows


# ----------------------------------------------------------------------- main
def main() -> int:
    api_key = get_api_key()
    if not api_key:
        print(STUB_MESSAGE)
        return 0  # clean exit: stubbed, nothing written

    cfg = load_config()
    table = cfg["sources"]["bea"]["tables"]["sagdp1"]
    table_name = table["table_name"]
    geo_fips = [str(g) for g in table["geo_fips"]]
    year = str(table.get("year", "ALL"))
    start_year = int(cfg.get("time", {}).get("start_year", DEFAULT_START_YEAR))

    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()

    print(f"Resolving {table_name} line codes from BEA metadata ...")
    codes = resolve_line_codes(api_key, table_name, table["line_code_match"])
    for kind, (code, desc) in codes.items():
        print(f"  {kind:8s} -> LineCode {code}: {desc}")

    all_rows: list[dict] = []
    for kind, (code, _desc) in codes.items():
        print(f"Fetching {kind} GDP (LineCode {code}) for {geo_fips}, years={year} ...")
        payload = fetch_table(api_key, table_name, code, geo_fips, year=year)
        raw_path = save_raw(payload, kind, retrieved_at)
        print(f"  raw -> {raw_path.relative_to(ROOT)}")
        all_rows.extend(records_to_rows(payload, retrieved_at, start_year))

    if not all_rows:
        raise BEAError("No usable rows returned; refusing to write an empty file.")

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
    print(f"  units  : {sorted(df['unit'].unique())}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BEAError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"NETWORK ERROR talking to BEA: {exc}", file=sys.stderr)
        sys.exit(1)
