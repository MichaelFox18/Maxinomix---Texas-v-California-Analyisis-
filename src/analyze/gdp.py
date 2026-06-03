"""
Analysis: GDP -- levels, real GDP per capita, growth, and CA-TX gaps/ratios.

"What stays put" side of the thesis: California's total output and per-capita
wealth. Real GDP is already in chained 2017 dollars (no deflator needed); per
capita = real GDP / July-1 population (Census PEP).

Output: outputs/tables/gdp_summary.csv (one row per year).
Note: population covers through the latest PEP vintage, so per-capita columns are
blank for any GDP year beyond that (left as NaN, never extrapolated).
"""
from __future__ import annotations

import pandas as pd

from src.clean import harmonize as hz


def build() -> pd.DataFrame:
    gdp = hz.load_processed("bea_gdp_tx_ca.csv")
    pep = hz.load_processed("census_pep_tx_ca.csv")

    real = hz.metric_series(gdp, "gdp_real")       # millions, chained 2017 $
    nom = hz.metric_series(gdp, "gdp_nominal")      # millions, current $
    pop = hz.metric_series(pep, "population")        # persons, July 1

    t = pd.DataFrame(index=real.index)
    t.index.name = "year"
    t["real_gdp_ca_musd"] = real["CA"]
    t["real_gdp_tx_musd"] = real["TX"]
    t["nominal_gdp_ca_musd"] = nom["CA"]
    t["nominal_gdp_tx_musd"] = nom["TX"]
    t["pop_ca"] = pop["CA"].reindex(t.index)
    t["pop_tx"] = pop["TX"].reindex(t.index)
    t["real_pc_gdp_ca_usd"] = t["real_gdp_ca_musd"] * 1e6 / t["pop_ca"]
    t["real_pc_gdp_tx_usd"] = t["real_gdp_tx_musd"] * 1e6 / t["pop_tx"]
    t["real_gdp_gap_ca_minus_tx_musd"] = t["real_gdp_ca_musd"] - t["real_gdp_tx_musd"]
    t["real_pc_gap_ca_minus_tx_usd"] = t["real_pc_gdp_ca_usd"] - t["real_pc_gdp_tx_usd"]
    t["real_gdp_ca_over_tx"] = t["real_gdp_ca_musd"] / t["real_gdp_tx_musd"]
    t["real_gdp_yoy_ca_pct"] = t["real_gdp_ca_musd"].pct_change() * 100
    t["real_gdp_yoy_tx_pct"] = t["real_gdp_tx_musd"].pct_change() * 100

    return t.round(2)


def main() -> int:
    t = build()
    path = hz.write_table(t, "gdp_summary.csv")
    print(f"Wrote {len(t)} years -> {path.relative_to(hz.ROOT)}")
    cols = ["real_gdp_ca_musd", "real_gdp_tx_musd",
            "real_pc_gdp_ca_usd", "real_pc_gdp_tx_usd", "real_gdp_ca_over_tx"]
    print(t[cols].to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
