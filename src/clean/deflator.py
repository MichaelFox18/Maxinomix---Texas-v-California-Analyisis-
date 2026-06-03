"""
clean/deflator.py -- US GDP implicit price deflator (2017 = 1.0) for real-dollar conversion.

Pulls US (GeoFips 00000) real & nominal GDP from BEA SAGDP1 (reusing the bea
collector) and derives the implicit GDP deflator = nominal / real. Because BEA real
GDP is chained to 2017, the deflator is ~1.0 in 2017. Used to convert nominal dollars
(IRS AGI, SEC Form D) to real chained-2017 dollars, per CLAUDE.md's real-dollar rule.

Writes data/processed/us_gdp_deflator.csv and exposes load_deflator()/to_real().
Run:  python -m src.clean.deflator   (requires BEA_API_KEY)
"""
from __future__ import annotations

import datetime as dt
import sys

import pandas as pd

from src.collect import bea

PROCESSED = bea.ROOT / "data" / "processed"
DEFLATOR_CSV = PROCESSED / "us_gdp_deflator.csv"
US_GEOFIPS = "00000"
BASE_YEAR = 2017


def build_deflator() -> pd.DataFrame:
    key = bea.get_api_key()
    if not key:
        raise bea.BEAError(
            "BEA_API_KEY missing; cannot build the deflator. Register free at "
            f"{bea.SIGNUP_URL} and set BEA_API_KEY in .env.")
    table = bea.load_config()["sources"]["bea"]["tables"]["sagdp1"]
    tname = table["table_name"]
    codes = bea.resolve_line_codes(key, tname, table["line_code_match"])
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()

    rows = []
    for kind, (code, _desc) in codes.items():
        payload = bea.fetch_table(key, tname, code, [US_GEOFIPS], year="ALL")
        bea.save_raw(payload, f"us_{kind}", retrieved_at)
        rows += bea.records_to_rows(payload, retrieved_at, start_year=2015)
    if not rows:
        raise bea.BEAError(f"No US GDP rows returned for GeoFips {US_GEOFIPS}.")

    piv = pd.DataFrame(rows).pivot_table(index="year", columns="metric", values="value")
    out = pd.DataFrame(index=piv.index)
    out.index.name = "year"
    out["us_nominal_gdp_musd"] = piv["gdp_nominal"]
    out["us_real_gdp_musd"] = piv["gdp_real"]
    out["deflator_2017"] = (out["us_nominal_gdp_musd"] / out["us_real_gdp_musd"]).round(6)
    return out.reset_index()


def save() -> pd.DataFrame:
    out = build_deflator()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_csv(DEFLATOR_CSV, index=False)
    return out


def load_deflator() -> pd.Series:
    """Year-indexed implicit GDP deflator (2017 = 1.0)."""
    return pd.read_csv(DEFLATOR_CSV).set_index("year")["deflator_2017"]


def to_real(nominal: pd.Series, deflator: pd.Series | None = None) -> pd.Series:
    """Convert a year-indexed nominal series to real (chained-2017) dollars."""
    defl = load_deflator() if deflator is None else deflator
    return nominal / defl.reindex(nominal.index)


def main() -> int:
    out = save()
    print(f"Wrote {len(out)} years -> {DEFLATOR_CSV.relative_to(bea.ROOT)}")
    print(out.to_string(index=False))
    base = out.loc[out.year == BASE_YEAR, "deflator_2017"]
    if len(base):
        print(f"\nsanity: deflator[{BASE_YEAR}] = {float(base.iloc[0]):.4f} (expect ~1.0000)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except bea.BEAError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
