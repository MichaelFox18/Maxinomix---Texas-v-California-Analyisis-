"""
Analysis: the counter-case synthesis -- "Texas is winning, but at what cost?"

Folds the four counter-case sources into reproducible summary tables and a single
"counter-case scorecard" that pairs each Texas advantage with its documented catch.
Per CLAUDE.md: every "Texas wins" claim must surface the skeptic's data.

Writes to outputs/tables/:
  housing_tax_summary.csv, grid_summary.csv, wages_summary.csv,
  metro_housing_boombust.csv, counter_case_scorecard.csv
"""
from __future__ import annotations

import glob

import pandas as pd

from src.clean import harmonize as hz


def _latest(series: pd.Series):
    s = series.dropna()
    return (int(s.index.max()), float(s.loc[s.index.max()])) if len(s) else (None, None)


# ---------------------------------------------------------------- housing & tax
def build_housing_tax() -> pd.DataFrame:
    acs = hz.load_processed("census_acs_housing_tx_ca.csv")
    val = hz.metric_series(acs, "median_home_value")
    tax = hz.metric_series(acs, "median_real_estate_taxes")
    inc = hz.metric_series(acs, "median_household_income")
    t = pd.DataFrame(index=val.index)
    t.index.name = "year"
    t["home_value_ca"] = val["CA"]
    t["home_value_tx"] = val["TX"]
    t["eff_prop_tax_rate_ca_pct"] = tax["CA"] / val["CA"] * 100
    t["eff_prop_tax_rate_tx_pct"] = tax["TX"] / val["TX"] * 100
    t["tx_over_ca_rate"] = t["eff_prop_tax_rate_tx_pct"] / t["eff_prop_tax_rate_ca_pct"]
    t["prop_tax_pct_income_ca"] = tax["CA"] / inc["CA"] * 100
    t["prop_tax_pct_income_tx"] = tax["TX"] / inc["TX"] * 100
    return t.round(3)


# --------------------------------------------------------------------- grid
def build_grid() -> pd.DataFrame:
    eia = hz.load_processed("eia_electricity_tx_ca.csv")
    price = hz.metric_series(eia, "electricity_price_cents_per_kwh")
    sales = hz.metric_series(eia, "electricity_retail_sales_million_kwh")
    sw = hz.metric_series(eia, "saidi_with_med_minutes")
    so = hz.metric_series(eia, "saidi_without_med_minutes")
    t = pd.DataFrame(index=price.index)
    t.index.name = "year"
    t["price_ca_cents_kwh"] = price["CA"]
    t["price_tx_cents_kwh"] = price["TX"]
    t["demand_ca_twh"] = sales["CA"] / 1000
    t["demand_tx_twh"] = sales["TX"] / 1000
    t["saidi_wmed_ca_min"] = sw["CA"].reindex(t.index)
    t["saidi_wmed_tx_min"] = sw["TX"].reindex(t.index)
    t["saidi_womed_ca_min"] = so["CA"].reindex(t.index)
    t["saidi_womed_tx_min"] = so["TX"].reindex(t.index)
    return t.round(2)


# --------------------------------------------------------------------- wages
def build_wages() -> pd.DataFrame:
    bls = hz.load_processed("bls_qcew_wages_tx_ca.csv")
    tot = hz.metric_series(bls, "avg_pay_all_industries")
    info = hz.metric_series(bls, "avg_pay_information")
    pst = hz.metric_series(bls, "avg_pay_prof_sci_tech")
    emp = hz.metric_series(bls, "employment_information")
    t = pd.DataFrame(index=tot.index)
    t.index.name = "year"
    t["avg_pay_total_ca"] = tot["CA"]
    t["avg_pay_total_tx"] = tot["TX"]
    t["avg_pay_total_ca_over_tx"] = tot["CA"] / tot["TX"]
    t["avg_pay_info_ca"] = info["CA"]
    t["avg_pay_info_tx"] = info["TX"]
    t["avg_pay_info_ca_over_tx"] = info["CA"] / info["TX"]
    t["avg_pay_pst_ca"] = pst["CA"]
    t["avg_pay_pst_tx"] = pst["TX"]
    t["emp_info_ca"] = emp["CA"]
    t["emp_info_tx"] = emp["TX"]
    return t.round(3)


# ------------------------------------------------------- metro boom-and-bust
def build_metro_boombust() -> pd.DataFrame:
    """True monthly peak/bust per metro from the trimmed Zillow raw (most accurate)."""
    raw = sorted(glob.glob(str(hz.PROCESSED.parent / "raw" / "zillow_zhvi_metro_tx_ca_*.csv")))[-1]
    df = pd.read_csv(raw)
    id_cols = ["RegionID", "SizeRank", "RegionName", "RegionType", "StateName"]
    date_cols = [c for c in df.columns if c not in id_cols]
    long = df.melt(id_vars=["RegionName"], value_vars=date_cols,
                   var_name="date", value_name="zhvi").dropna(subset=["zhvi"])
    long["date"] = pd.to_datetime(long["date"])
    long = long[long["date"] >= "2019-01-01"]
    rows = []
    for name, g in long.groupby("RegionName"):
        g = g.sort_values("date")
        jan20 = g.loc[g["date"] == "2020-01-31", "zhvi"]
        peak_i = g["zhvi"].idxmax()
        peak_v, peak_d = g.loc[peak_i, "zhvi"], g.loc[peak_i, "date"]
        last_v = g.iloc[-1]["zhvi"]
        rows.append({
            "metro": name,
            "jan2020": round(float(jan20.iloc[0])) if len(jan20) else None,
            "peak": round(peak_v), "peak_month": peak_d.strftime("%Y-%m"),
            "boom_pct": round((peak_v / jan20.iloc[0] - 1) * 100, 1) if len(jan20) else None,
            "latest": round(last_v), "latest_month": g.iloc[-1]["date"].strftime("%Y-%m"),
            "pct_from_peak": round((last_v / peak_v - 1) * 100, 1),
        })
    return pd.DataFrame(rows).sort_values("pct_from_peak").reset_index(drop=True)


# --------------------------------------------------------- counter-case scorecard
def build_scorecard(ht, grid, wages, bb) -> pd.DataFrame:
    def at(df, col, year):
        return float(df.loc[year, col]) if year in df.index and pd.notna(df.loc[year, col]) else None

    hy, _ = _latest(ht["eff_prop_tax_rate_tx_pct"])
    wy, _ = _latest(wages["avg_pay_info_tx"])
    gy_price, _ = _latest(grid["price_tx_cents_kwh"])
    austin = bb.set_index("metro").loc["Austin, TX"]
    sf = bb.set_index("metro").loc["San Francisco, CA"]

    rows = [
        ("Housing", "Effective property-tax rate",
         round(at(ht, "eff_prop_tax_rate_tx_pct", hy), 2), round(at(ht, "eff_prop_tax_rate_ca_pct", hy), 2),
         "% of home value", hy, "TX taxes property ~1.9x CA's rate"),
        ("Housing", "Property tax as % of income",
         round(at(ht, "prop_tax_pct_income_tx", hy), 2), round(at(ht, "prop_tax_pct_income_ca", hy), 2),
         "% of income", hy, "burden essentially equal"),
        ("Housing", "Home value vs 2022 peak (Austin vs SF)",
         austin["pct_from_peak"], sf["pct_from_peak"],
         "% from peak", int(austin["latest_month"][:4]), "Austin corrected hardest of 8 metros"),
        ("Grid", "Outage minutes, with major events (2021 Uri)",
         at(grid, "saidi_wmed_tx_min", 2021), at(grid, "saidi_wmed_ca_min", 2021),
         "min/customer", 2021, "TX ~3.6x CA in catastrophe"),
        ("Grid", "Outage minutes, normal (no major events)",
         at(grid, "saidi_womed_tx_min", 2023), at(grid, "saidi_womed_ca_min", 2023),
         "min/customer", 2023, "TX on par / better day-to-day"),
        ("Grid", "Electricity price",
         round(at(grid, "price_tx_cents_kwh", gy_price), 2), round(at(grid, "price_ca_cents_kwh", gy_price), 2),
         "cents/kWh", gy_price, "TX much cheaper (the draw)"),
        ("Wages", "All-industry average pay",
         round(at(wages, "avg_pay_total_tx", wy)), round(at(wages, "avg_pay_total_ca", wy)),
         "$/year", wy, "CA pays ~1.24x"),
        ("Wages", "Information-sector average pay",
         round(at(wages, "avg_pay_info_tx", wy)), round(at(wages, "avg_pay_info_ca", wy)),
         "$/year", wy, "CA pays ~2.4x; gap widening (AI era)"),
    ]
    return pd.DataFrame(rows, columns=["theme", "dimension", "tx", "ca", "unit", "year", "takeaway"])


def main() -> int:
    ht, grid, wages, bb = build_housing_tax(), build_grid(), build_wages(), build_metro_boombust()
    sc = build_scorecard(ht, grid, wages, bb)
    for df, name, idx in [(ht, "housing_tax_summary.csv", True),
                          (grid, "grid_summary.csv", True),
                          (wages, "wages_summary.csv", True),
                          (bb, "metro_housing_boombust.csv", False),
                          (sc, "counter_case_scorecard.csv", False)]:
        path = hz.write_table(df, name, index=idx)
        print(f"  wrote {path.relative_to(hz.ROOT)}")
    print("\n=== COUNTER-CASE SCORECARD (Texas advantage -> the catch) ===")
    print(sc.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
