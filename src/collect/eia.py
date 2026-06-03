"""
Collector: EIA -- electricity price & demand (v2 API) + grid reliability (EIA-861).

Source : U.S. Energy Information Administration.
Access : v2 API (free key -> EIA_API_KEY) for price/demand; annual EIA-861
         spreadsheets (no key) for reliability/SAIDI.
Docs   : https://www.eia.gov/opendata/  ;  https://www.eia.gov/electricity/data/eia861/

The grid counter-case has two honest halves:
  - "the draw"  : Texas electricity is far cheaper than California's (price favors TX).
  - "the catch" : Texas consumes far more power AND its grid is less reliable -- SAIDI
                  (avg outage minutes per customer) spiked catastrophically in 2021
                  (Winter Storm Uri). SAIDI is customer-weighted from EIA-861 utility
                  filings to the state level.

Metrics (per state per year): electricity_price_cents_per_kwh (nominal),
electricity_retail_sales_million_kwh, saidi_with_med_minutes, saidi_without_med_minutes.

Output: data/processed/eia_electricity_tx_ca.csv. Never fabricates ("." -> dropped).
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "sources.yaml"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_CSV = PROCESSED_DIR / "eia_electricity_tx_ca.csv"
SIGNUP_URL = "https://www.eia.gov/opendata/register.php"
UA = {"User-Agent": "Mozilla/5.0 (TX-vs-CA economic research)"}

COLUMNS = [
    "geo_id", "geo_name", "geo_level", "year", "metric", "value", "unit",
    "real_or_nominal", "source", "source_url", "retrieved_at",
]
NAME = {"06": "California", "48": "Texas"}


class EIAError(RuntimeError):
    pass


def load_cfg() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["sources"]["eia"]


def get_api_key() -> str | None:
    load_dotenv(ROOT / ".env")
    key = os.getenv("EIA_API_KEY")
    return key.strip() if key else None


# --------------------------------------------------------------- API: price/demand
def collect_api(cfg: dict, key: str, retrieved_at: str) -> list[dict]:
    base = cfg["base_url"].rstrip("/")
    s2f = cfg["stateid_to_fips"]
    start, end = int(cfg["start_year"]), int(retrieved_at[:4])
    params = {
        "frequency": "annual", "data[]": ["price", "sales"],
        "facets[stateid][]": list(s2f.keys()), "facets[sectorid][]": ["ALL"],
        "start": str(start), "end": str(end), "length": "5000", "api_key": key,
    }
    resp = requests.get(f"{base}/{cfg['retail_sales_path']}", params=params, timeout=90)
    if resp.status_code != 200:
        raise EIAError(f"retail-sales HTTP {resp.status_code}: {resp.text[:200]}")
    payload = resp.json()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = retrieved_at[:10].replace("-", "")
    with open(RAW_DIR / f"eia_retail_sales_{stamp}.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    rows: list[dict] = []
    for rec in payload.get("response", {}).get("data", []):
        fips = s2f.get(rec.get("stateid"))
        if not fips:
            continue
        year = int(rec["period"])
        for metric, key_, unit, ron in [
            ("electricity_price_cents_per_kwh", "price", "cents per kWh", "nominal"),
            ("electricity_retail_sales_million_kwh", "sales", "million kWh", "n/a"),
        ]:
            raw = rec.get(key_)
            if raw in (None, ""):
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            rows.append({
                "geo_id": fips, "geo_name": NAME[fips], "geo_level": "state",
                "year": year, "metric": metric, "value": value, "unit": unit,
                "real_or_nominal": ron, "source": "EIA v2 API (retail sales)",
                "source_url": f"{base}/{cfg['retail_sales_path']}",
                "retrieved_at": retrieved_at,
            })
    return rows


# ----------------------------------------------------- EIA-861: reliability / SAIDI
def _parse_reliability(xlsx_bytes: bytes) -> pd.DataFrame | None:
    """Per-utility SAIDI (with/without major event days) + customers, by header labels."""
    raw = pd.read_excel(io.BytesIO(xlsx_bytes), header=None, dtype=object)
    hdr = None
    for i in range(min(8, len(raw))):
        vals = [str(x).strip().lower() for x in raw.iloc[i].tolist()]
        if "data year" in vals and "state" in vals:
            hdr = i
            break
    if hdr is None or hdr < 2:
        return None

    sub = raw.iloc[hdr].astype(str).str.strip()
    grp = raw.iloc[hdr - 1].ffill().astype(str).str.strip()
    std = raw.iloc[hdr - 2].ffill().astype(str).str.strip()
    ncol = raw.shape[1]

    def find(pred):
        for j in range(ncol):
            if pred(std.iloc[j], grp.iloc[j], sub.iloc[j]):
                return j
        return None

    col_state = find(lambda s, g, b: b.lower() == "state")
    if col_state is None:
        return None

    def saidi_and_customers(standard: str, withmed: bool):
        grp_t = "All Events (With Major Event Days)" if withmed else "Without Major Event Days"
        cs = find(lambda s, g, b: s == standard and g == grp_t and b.startswith("SAIDI"))
        cc = find(lambda s, g, b: s == standard and b.startswith("Number of Customers"))
        return cs, cc

    iw_s, iw_c = saidi_and_customers("IEEE Standard", True)
    io_s, _ = saidi_and_customers("IEEE Standard", False)
    ow_s, ow_c = saidi_and_customers("Other Standard", True)
    oo_s, _ = saidi_and_customers("Other Standard", False)

    data = raw.iloc[hdr + 1:].reset_index(drop=True)

    def num(col):
        if col is None:
            return pd.Series([float("nan")] * len(data))
        return pd.to_numeric(data[col], errors="coerce")

    df = pd.DataFrame({"state": data[col_state].astype(str).str.strip()})
    saidi_w_ieee, cust_ieee = num(iw_s), num(iw_c)
    saidi_w_oth, cust_oth = num(ow_s), num(ow_c)
    df["saidi_wmed"] = saidi_w_ieee.fillna(saidi_w_oth)
    df["saidi_womed"] = num(io_s).fillna(num(oo_s))
    df["customers"] = cust_ieee.where(saidi_w_ieee.notna(), cust_oth)
    return df


def collect_reliability(cfg: dict, retrieved_at: str) -> list[dict]:
    rel = cfg["reliability_861"]
    s2f = cfg["stateid_to_fips"]
    stamp = retrieved_at[:10].replace("-", "")
    trimmed: list[pd.DataFrame] = []
    rows: list[dict] = []

    for year in rel["years"]:
        url = rel["url_template"].format(year=year)
        r = requests.get(url, headers=UA, timeout=180)
        if r.status_code != 200:
            print(f"  [skip] EIA-861 {year}: HTTP {r.status_code}")
            continue
        try:
            z = zipfile.ZipFile(io.BytesIO(r.content))
        except zipfile.BadZipFile:
            print(f"  [skip] EIA-861 {year}: not a zip")
            continue
        relfile = next((n for n in z.namelist() if "reli" in n.lower()
                        and n.lower().endswith((".xlsx", ".xls"))), None)
        if not relfile:
            print(f"  [skip] EIA-861 {year}: no reliability file")
            continue
        df = _parse_reliability(z.read(relfile))
        if df is None:
            print(f"  [skip] EIA-861 {year}: could not parse header")
            continue
        df = df[df["state"].isin(s2f.keys())].copy()
        df["year"] = year
        trimmed.append(df)

        for stateid, fips in s2f.items():
            s = df[(df["state"] == stateid) & (df["customers"] > 0)]
            for metric, col in [("saidi_with_med_minutes", "saidi_wmed"),
                                ("saidi_without_med_minutes", "saidi_womed")]:
                v = s[s[col].notna()]
                tot = v["customers"].sum()
                if tot > 0:
                    wsaidi = float((v[col] * v["customers"]).sum() / tot)
                    rows.append({
                        "geo_id": fips, "geo_name": NAME[fips], "geo_level": "state",
                        "year": year, "metric": metric, "value": round(wsaidi, 1),
                        "unit": "minutes per year", "real_or_nominal": "n/a",
                        "source": f"EIA-861 Reliability {year} (customer-weighted)",
                        "source_url": url, "retrieved_at": retrieved_at,
                    })
        print(f"  EIA-861 {year}: {len(df)} CA/TX utilities")

    if trimmed:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        pd.concat(trimmed, ignore_index=True).to_csv(
            RAW_DIR / f"eia861_reliability_tx_ca_utilities_{stamp}.csv", index=False)
    return rows


def main(argv: list[str]) -> int:
    cfg = load_cfg()
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    which = argv[0].lower() if argv else "both"
    rows: list[dict] = []

    if which in ("api", "both"):
        key = get_api_key()
        if not key:
            print(f"[note] EIA_API_KEY not set; skipping price/demand. Register: {SIGNUP_URL}")
        else:
            print("== EIA API: price & demand ==")
            rows += collect_api(cfg, key, retrieved_at)
    if which in ("reliability", "both"):
        print("== EIA-861: reliability (SAIDI) ==")
        rows += collect_reliability(cfg, retrieved_at)

    if not rows:
        raise EIAError("No rows collected; refusing to write an empty file.")

    df = (pd.DataFrame(rows, columns=COLUMNS)
          .sort_values(["geo_name", "metric", "year"]).reset_index(drop=True))
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nWrote {len(df)} rows -> {OUTPUT_CSV.relative_to(ROOT)}")
    print(f"  metrics: {sorted(df['metric'].unique())}")
    print(f"  years  : {df['year'].min()}-{df['year'].max()}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except EIAError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"NETWORK ERROR talking to EIA: {exc}", file=sys.stderr)
        sys.exit(1)
