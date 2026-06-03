"""
Collector: Zillow ZHVI -- metro home values for the "Austin boom-and-bust" counter-case.

Source : Zillow Research, Zillow Home Value Index (ZHVI; all homes, smoothed,
         seasonally adjusted), metro-level monthly CSV.
Access : Public CSV download, no key. ATTRIBUTION REQUIRED (see config/sources.yaml).
Docs   : https://www.zillow.com/research/data/

The non-redundant housing story: in-migration bid Austin up sharply (2020-22), then
it became one of the worst-correcting major US metros (2022-24) -- the affordability
that drew people in is partly self-undermining. Compares the four TX metros vs four
CA metros in scope.

Output: data/processed/zillow_zhvi_metro_tx_ca.csv -- year-END (December, or latest
available month for the current year) ZHVI per metro. ZHVI is NOMINAL $. geo_id is
the federal CBSA code. Never fabricates: missing months are skipped.
"""
from __future__ import annotations

import datetime as dt
import io
import sys
from pathlib import Path

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "sources.yaml"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_CSV = PROCESSED_DIR / "zillow_zhvi_metro_tx_ca.csv"
SOURCE_LABEL = "Zillow Research ZHVI"
ID_COLS = ["RegionID", "SizeRank", "RegionName", "RegionType", "StateName"]

COLUMNS = [
    "geo_id", "geo_name", "geo_level", "year", "metric", "value", "unit",
    "real_or_nominal", "source", "source_url", "retrieved_at",
]


class ZillowError(RuntimeError):
    pass


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["sources"]["zillow"]


def main() -> int:
    cfg = load_config()
    url = cfg["zhvi_metro_url"]
    start_year = int(cfg["start_year"])
    metric = cfg["metric"]
    metros = {int(m["region_id"]): m for m in cfg["metros"]}
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    stamp = retrieved_at[:10].replace("-", "")

    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (TX-vs-CA research)"}, timeout=180)
    resp.raise_for_status()
    df = pd.read_csv(io.BytesIO(resp.content))

    df = df[df["RegionID"].isin(metros)]
    if df.empty:
        raise ZillowError("None of the configured metro RegionIDs were found in the Zillow file.")

    # save trimmed raw (our metros only, full monthly history) -- sanctioned by guardrail
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW_DIR / f"zillow_zhvi_metro_tx_ca_{stamp}.csv", index=False)

    date_cols = [c for c in df.columns if c not in ID_COLS]
    long = df.melt(id_vars=["RegionID"], value_vars=date_cols,
                   var_name="date", value_name="zhvi").dropna(subset=["zhvi"])
    long["date"] = pd.to_datetime(long["date"], errors="coerce")
    long = long.dropna(subset=["date"])
    long["year"] = long["date"].dt.year
    long = long[long["year"] >= start_year]

    # year-end snapshot: the latest available month within each year (Dec for full years)
    idx = long.groupby(["RegionID", "year"])["date"].idxmax()
    yearend = long.loc[idx]

    rows = []
    for _, r in yearend.iterrows():
        meta = metros[int(r["RegionID"])]
        rows.append({
            "geo_id": meta["cbsa"],
            "geo_name": meta["name"],
            "geo_level": "metro",
            "year": int(r["year"]),
            "metric": metric,
            "value": round(float(r["zhvi"]), 2),
            "unit": "USD",
            "real_or_nominal": "nominal",
            "source": SOURCE_LABEL,
            "source_url": url,
            "retrieved_at": retrieved_at,
        })

    out = (pd.DataFrame(rows, columns=COLUMNS)
           .sort_values(["geo_name", "year"]).reset_index(drop=True))
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_CSV, index=False)

    print(f"Wrote {len(out)} rows -> {OUTPUT_CSV.relative_to(ROOT)}")
    print(f"  metros: {sorted(out['geo_name'].unique())}")
    print(f"  years : {out['year'].min()}-{out['year'].max()}")
    print(f"  [attribution] {cfg.get('attribution', '')}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ZillowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"NETWORK ERROR talking to Zillow: {exc}", file=sys.stderr)
        sys.exit(1)
