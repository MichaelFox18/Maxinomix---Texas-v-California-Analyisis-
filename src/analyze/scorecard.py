"""
Analysis: the split-decision scorecard -- the spine of the whole project.

Lines up each thesis dimension as a single row: who leads, the latest figures for
CA and TX, the period, and which side of the thesis it belongs to ("what moves"
-> Texas vs "what stays put" -> California). Reads the other analyze modules so the
scorecard can never drift from the underlying summaries.

Output: outputs/tables/split_decision_scorecard.csv
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from src.analyze import capital as cap_mod
from src.analyze import gdp as gdp_mod
from src.analyze import migration as mig_mod
from src.clean import harmonize as hz

COLUMNS = ["dimension", "thesis_side", "ca", "tx", "unit", "period", "winner"]


def _span(series: pd.Series) -> str:
    yrs = series.dropna().index
    return f"{int(yrs.min())}-{int(yrs.max())}" if len(yrs) else "n/a"


def _row(dimension, side, ca, tx, unit, period, winner):
    rnd = lambda v: round(float(v), 2) if isinstance(v, (int, float)) and pd.notna(v) else v
    return dict(dimension=dimension, thesis_side=side, ca=rnd(ca), tx=rnd(tx),
                unit=unit, period=period, winner=winner)


def build() -> pd.DataFrame:
    g = gdp_mod.build()
    m = mig_mod.build()
    c = cap_mod.build()

    rows = []

    # --- GDP (stays -> CA), with the growth-rate counter (moves -> TX) ---
    gy = int(g["real_gdp_ca_musd"].dropna().index.max())
    base = int(g.index.min())
    rows.append(_row("Total real GDP", "stays -> CA",
                     g.loc[gy, "real_gdp_ca_musd"] / 1e6, g.loc[gy, "real_gdp_tx_musd"] / 1e6,
                     "$T real (chained 2017)", str(gy), "CA"))
    py = int(g["real_pc_gdp_ca_usd"].dropna().index.max())
    rows.append(_row("Real GDP per capita", "stays -> CA",
                     g.loc[py, "real_pc_gdp_ca_usd"], g.loc[py, "real_pc_gdp_tx_usd"],
                     "$ real (chained 2017)", str(py), "CA"))
    ca_grow = (g.loc[gy, "real_gdp_ca_musd"] / g.loc[base, "real_gdp_ca_musd"] - 1) * 100
    tx_grow = (g.loc[gy, "real_gdp_tx_musd"] / g.loc[base, "real_gdp_tx_musd"] - 1) * 100
    rows.append(_row("Real GDP growth (cumulative)", "moves -> TX",
                     ca_grow, tx_grow, "% over period", f"{base}-{gy}", "TX"))

    # --- migration (moves -> TX) ---
    rows.append(_row("Net domestic migration (cumulative)", "moves -> TX",
                     m["pep_net_domestic_mig_ca"].sum(), m["pep_net_domestic_mig_tx"].sum(),
                     "persons", _span(m["pep_net_domestic_mig_ca"]), "TX"))
    rows.append(_row("Net interstate AGI (cumulative)", "moves -> TX",
                     m["irs_net_interstate_agi_ca_real_kusd"].sum() / 1e6,
                     m["irs_net_interstate_agi_tx_real_kusd"].sum() / 1e6,
                     "$B real (2017)", _span(m["irs_net_interstate_agi_ca_real_kusd"]), "TX"))
    net_ca_tx = m["net_ca_to_tx_agi_real_kusd"].sum() / 1e6
    rows.append(_row("Net AGI flow, CA->TX (cumulative)", "moves -> TX",
                     -net_ca_tx, net_ca_tx, "$B real 2017 (TX gain / CA loss)",
                     _span(m["net_ca_to_tx_agi_real_kusd"]), "TX"))

    # --- private capital (stays -> CA); use latest FULL year (exclude partial) ---
    cur = dt.datetime.now().year
    full = [y for y in c.index if y < cur]
    cy = int(max(full) if full else c.index.max())
    rows.append(_row("Form D offerings (new)", "stays -> CA",
                     c.loc[cy, "formd_count_ca"], c.loc[cy, "formd_count_tx"],
                     "offerings", str(cy), "CA"))
    rows.append(_row("Form D capital raised", "stays -> CA",
                     c.loc[cy, "formd_amount_ca_busd"], c.loc[cy, "formd_amount_tx_busd"],
                     "$B nominal", str(cy), "CA"))

    # --- corporate HQ relocations (moves -> TX), curated + EDGAR-verified ---
    hq = pd.read_csv(hz.PROCESSED / "edgar_hq_relocations_tx_ca.csv")
    n_tx = int(((hq["to_state_expected"] == "TX") & hq["verified_in_to_state"]).sum())
    rows.append(_row("HQ relocations verified in TX (curated)", "moves -> TX",
                     None, n_tx, "companies", "current", "TX"))

    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> int:
    t = build()
    path = hz.write_table(t, "split_decision_scorecard.csv", index=False)
    print(f"Wrote {len(t)} dimensions -> {path.relative_to(hz.ROOT)}\n")
    print(t.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
