"""
Collector: BLS QCEW (open data) -- average pay & employment by industry, TX & CA.

Source : BLS Quarterly Census of Employment and Wages (QCEW), annual averages.
Access : QCEW "Open Data" area CSVs (no key required). The BLS_API_KEY is reserved
         for future CES/LAUS/OEWS series via the registration API.
Docs   : https://www.bls.gov/cew/  ;  https://www.bls.gov/cew/about-data/

Job-quality counter-case (Act 2 for California): Texas gains people and jobs, but
California keeps the high-WAGE knowledge economy. Compares average annual pay overall
and in high-wage sectors (Information, Professional/Scientific/Technical, Manufacturing).

Metrics (per state per year): avg_pay_* (nominal USD/year), employment_* (jobs).
Output: data/processed/bls_qcew_wages_tx_ca.csv. Never fabricates (suppressed rows skipped).
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
OUTPUT_CSV = PROCESSED_DIR / "bls_qcew_wages_tx_ca.csv"
UA = {"User-Agent": "TX-vs-CA economic research"}
NAME = {"06000": "California", "48000": "Texas"}

COLUMNS = [
    "geo_id", "geo_name", "geo_level", "year", "metric", "value", "unit",
    "real_or_nominal", "source", "source_url", "retrieved_at",
]


class BLSError(RuntimeError):
    pass


def load_qcew_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["sources"]["bls"]["qcew"]


def main() -> int:
    cfg = load_qcew_config()
    tpl = cfg["area_url_template"]
    areas = [str(a) for a in cfg["area_fips"]]
    measures = cfg["measures"]
    start_year = int(cfg["start_year"])
    end_year = dt.datetime.now(dt.timezone.utc).year
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    stamp = retrieved_at[:10].replace("-", "")

    rows: list[dict] = []
    trimmed: list[pd.DataFrame] = []
    for area in areas:
        fips2 = area[:2]
        for year in range(start_year, end_year + 1):
            url = tpl.format(year=year, area=area)
            r = requests.get(url, headers=UA, timeout=120)
            if r.status_code != 200:
                continue  # year not published yet
            df = pd.read_csv(io.BytesIO(r.content), dtype=str)

            for metric, spec in measures.items():
                sel = df[(df["own_code"] == spec["own_code"])
                         & (df["industry_code"] == spec["industry_code"])
                         & (df["agglvl_code"] == spec["agglvl_code"])]
                if len(sel) != 1:
                    continue
                raw = sel.iloc[0].get(spec["field"])
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    continue
                if value <= 0:        # 0 = disclosure-suppressed -> skip
                    continue
                is_pay = spec["field"] == "avg_annual_pay"
                rows.append({
                    "geo_id": area, "geo_name": NAME.get(area, area), "geo_level": "state",
                    "year": year, "metric": metric, "value": value,
                    "unit": "USD per year" if is_pay else "jobs",
                    "real_or_nominal": "nominal" if is_pay else "n/a",
                    "source": "BLS QCEW (annual averages)",
                    "source_url": url, "retrieved_at": retrieved_at,
                })
                sel2 = sel.copy(); sel2["_metric"] = metric
                trimmed.append(sel2)
            print(f"  QCEW {NAME.get(area, area)} {year}: ok")

    if not rows:
        raise BLSError("No usable QCEW rows; refusing to write an empty file.")

    if trimmed:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        pd.concat(trimmed, ignore_index=True).to_csv(
            RAW_DIR / f"bls_qcew_tx_ca_rows_{stamp}.csv", index=False)

    out = (pd.DataFrame(rows, columns=COLUMNS)
           .sort_values(["geo_name", "metric", "year"]).reset_index(drop=True))
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_CSV, index=False)
    print(f"\nWrote {len(out)} rows -> {OUTPUT_CSV.relative_to(ROOT)}")
    print(f"  years  : {out['year'].min()}-{out['year'].max()}")
    print(f"  metrics: {sorted(out['metric'].unique())}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BLSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"NETWORK ERROR talking to BLS: {exc}", file=sys.stderr)
        sys.exit(1)
