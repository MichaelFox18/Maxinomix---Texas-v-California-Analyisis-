"""
Analysis: figures -- the visual backbone for the explainer video.

Renders consistent California-vs-Texas charts from the analyze-layer summaries to
outputs/figures/. Every figure carries a source caption (CLAUDE.md: cite every
number); nominal-dollar charts are labeled as nominal.

Run from the repo root:  python -m src.analyze.figures
"""
from __future__ import annotations

import datetime as dt

import matplotlib
matplotlib.use("Agg")          # headless / no display
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analyze import capital as cap_mod
from src.analyze import counter_case as cc_mod
from src.analyze import gdp as gdp_mod
from src.analyze import migration as mig_mod
from src.analyze import scorecard as sc_mod
from src.clean import harmonize as hz

FIGDIR = hz.ROOT / "outputs" / "figures"
CA = "#1f77b4"   # California — blue
TX = "#d62728"   # Texas — red

plt.rcParams.update({
    "axes.grid": True, "grid.alpha": 0.3,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 120,
})


def _save(fig, name: str, source: str):
    fig.text(0.99, 0.005, source, ha="right", va="bottom", fontsize=7, color="gray")
    FIGDIR.mkdir(parents=True, exist_ok=True)
    path = FIGDIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {path.relative_to(hz.ROOT)}")


def _fmt(v: float) -> str:
    """Human-readable: thousands separators for big numbers, compact for small."""
    return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:g}"


def fig_gdp_levels(g):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(g.index, g.real_gdp_ca_musd / 1e6, color=CA, marker="o", label="California")
    ax.plot(g.index, g.real_gdp_tx_musd / 1e6, color=TX, marker="o", label="Texas")
    ax.set_title("Total Real GDP: California vs Texas")
    ax.set_xlabel("Year"); ax.set_ylabel("Real GDP ($ trillions, chained 2017)")
    ax.legend()
    _save(fig, "01_gdp_levels.png", "Source: BEA Regional SAGDP1 (real, chained 2017 $)")


def fig_gdp_per_capita(g):
    d = g.dropna(subset=["real_pc_gdp_ca_usd"])
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(d.index, d.real_pc_gdp_ca_usd / 1e3, color=CA, marker="o", label="California")
    ax.plot(d.index, d.real_pc_gdp_tx_usd / 1e3, color=TX, marker="o", label="Texas")
    ax.set_title("Real GDP per Capita: California vs Texas  (the counter-case)")
    ax.set_xlabel("Year"); ax.set_ylabel("Real GDP per capita ($ thousands, chained 2017)")
    ax.legend()
    _save(fig, "02_gdp_per_capita.png", "Source: BEA SAGDP1 / Census PEP population")


def fig_net_domestic_migration(m):
    fig, ax = plt.subplots(figsize=(9, 5))
    yrs = m.index.values.astype(float); w = 0.4
    ax.bar(yrs - w / 2, m.pep_net_domestic_mig_ca / 1e3, w, color=CA, label="California")
    ax.bar(yrs + w / 2, m.pep_net_domestic_mig_tx / 1e3, w, color=TX, label="Texas")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Net Domestic Migration: California vs Texas")
    ax.set_xlabel("Year"); ax.set_ylabel("Net domestic migration (thousands of people / yr)")
    ax.legend()
    _save(fig, "03_net_domestic_migration.png", "Source: Census PEP (components of change)")


def fig_net_interstate_agi(m):
    d = m.dropna(subset=["irs_net_interstate_agi_ca_real_kusd"])
    fig, ax = plt.subplots(figsize=(9, 5))
    yrs = d.index.values.astype(float); w = 0.4
    ax.bar(yrs - w / 2, d.irs_net_interstate_agi_ca_real_kusd / 1e6, w, color=CA, label="California")
    ax.bar(yrs + w / 2, d.irs_net_interstate_agi_tx_real_kusd / 1e6, w, color=TX, label="Texas")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Net Interstate Migration of Income (AGI): California vs Texas")
    ax.set_xlabel("Year"); ax.set_ylabel("Net AGI flow ($ billions, real 2017)")
    ax.legend()
    _save(fig, "04_net_interstate_agi.png",
          "Source: IRS SOI Migration; deflated to real 2017 $ (US GDP deflator). Flows peaked 2021.")


def fig_bilateral(m):
    d = m.dropna(subset=["ca_to_tx_agi_real_kusd"])
    fig, ax = plt.subplots(figsize=(9, 5))
    yrs = d.index.values.astype(float); w = 0.4
    ax.bar(yrs - w / 2, d.ca_to_tx_agi_real_kusd / 1e6, w, color=TX, label="CA → TX")
    ax.bar(yrs + w / 2, d.tx_to_ca_agi_real_kusd / 1e6, w, color=CA, label="TX → CA")
    ax.plot(yrs, d.net_ca_to_tx_agi_real_kusd / 1e6, color="black", marker="o", lw=1.5,
            label="Net (CA → TX)")
    ax.set_title("Income on the Move: California ↔ Texas AGI Flows")
    ax.set_xlabel("Year"); ax.set_ylabel("AGI ($ billions, real 2017)")
    ax.legend()
    _save(fig, "05_ca_tx_bilateral_agi.png",
          "Source: IRS SOI Migration; deflated to real 2017 $ (US GDP deflator).")


def fig_formd(c):
    cur = dt.datetime.now().year
    d = c[c.index < cur]   # full years only (exclude partial current year)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.plot(d.index, d.formd_count_ca, color=CA, marker="o", label="California")
    ax1.plot(d.index, d.formd_count_tx, color=TX, marker="o", label="Texas")
    ax1.set_title("Form D offerings (new, per year)")
    ax1.set_xlabel("Year"); ax1.set_ylabel("New offerings"); ax1.legend()
    ax2.plot(d.index, d.formd_amount_ca_busd, color=CA, marker="o", label="California")
    ax2.plot(d.index, d.formd_amount_tx_busd, color=TX, marker="o", label="Texas")
    ax2.set_title("Form D capital raised ($B, nominal)")
    ax2.set_xlabel("Year"); ax2.set_ylabel("$ billions"); ax2.legend()
    fig.suptitle("California's Private-Capital Moat: SEC Form D (all Reg D)", fontsize=13)
    _save(fig, "06_formd_capital.png",
          "Source: SEC EDGAR Form D. Broad private-capital proxy (VC+PE+RE+funds); $ nominal; full years only.")


def fig_scorecard(sc):
    rows = []
    for _, r in sc.iterrows():
        ca = float(r.ca) if pd.notna(r.ca) else 0.0
        tx = float(r.tx) if pd.notna(r.tx) else 0.0
        denom = abs(ca) + abs(tx)
        lead = (ca - tx) / denom if denom else 0.0       # +1 = CA, -1 = TX
        rows.append((r.dimension, lead, ca, tx, r.unit, r.winner))
    rows.sort(key=lambda x: x[1])                          # TX-leaning at bottom -> CA at top
    labels = [x[0] for x in rows]
    leads = [x[1] for x in rows]
    colors = [CA if x[1] > 0 else TX for x in rows]

    fig, ax = plt.subplots(figsize=(11, 6))
    y = np.arange(len(rows))
    ax.barh(y, leads, color=colors, alpha=0.85)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.axvline(0, color="black", lw=0.9)
    ax.set_xlim(-1.15, 1.15)
    ax.set_xlabel("←  Texas leads            normalized lead            California leads  →")
    ax.set_title("The Split Decision: What MOVES (Texas) vs What STAYS (California)", fontsize=13)
    ax.grid(axis="y", visible=False)
    for yi, (_, lead, ca, tx, unit, _w) in zip(y, rows):
        txt = f"CA {_fmt(ca)} / TX {_fmt(tx)} {unit}"
        ha = "left" if lead < 0 else "right"
        xoff = 0.02 if lead < 0 else -0.02
        ax.text(xoff if lead == 0 else (0.02 if lead < 0 else -0.02), yi,
                txt, va="center", ha=ha, fontsize=7.5, color="black")
    _save(fig, "07_split_decision_scorecard.png",
          "Sources: BEA, Census PEP, IRS SOI, SEC EDGAR. Bars = normalized (CA-TX)/(|CA|+|TX|).")


# =============================================================== counter-cases
def fig_property_tax(ht):
    d = ht.dropna(subset=["eff_prop_tax_rate_ca_pct"])
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(d.index, d.eff_prop_tax_rate_ca_pct, color=CA, marker="o", label="California")
    ax.plot(d.index, d.eff_prop_tax_rate_tx_pct, color=TX, marker="o", label="Texas")
    ax.set_title("Effective Property-Tax Rate: Texas ~2x California")
    ax.set_xlabel("Year"); ax.set_ylabel("Median property tax / median home value (%)")
    ax.set_ylim(0, None); ax.legend()
    _save(fig, "08_effective_property_tax.png",
          "Source: Census ACS 1-year (median real-estate taxes / median home value)")


def fig_austin_boombust():
    z = hz.load_processed("zillow_zhvi_metro_tx_ca.csv")
    piv = z[z.metric == "zhvi"].pivot_table(index="year", columns="geo_name", values="value")
    metros = {"Austin, TX": TX, "Dallas-Fort Worth, TX": "#ff9896",
              "Houston, TX": "#e377c2", "San Francisco, CA": CA}
    base = piv.loc[2019]
    fig, ax = plt.subplots(figsize=(9, 5))
    for m, color in metros.items():
        if m in piv.columns:
            ax.plot(piv.index, piv[m] / base[m] * 100, marker="o", label=m, color=color)
    ax.axhline(100, color="black", lw=0.6, ls="--")
    ax.set_title("Austin's Boom and Bust: Home Values Indexed to 2019 = 100")
    ax.set_xlabel("Year"); ax.set_ylabel("ZHVI index (2019 = 100)")
    ax.legend(fontsize=8)
    _save(fig, "09_austin_boom_bust.png",
          "Source: Zillow Research ZHVI (year-end), indexed to 2019. Used with attribution.")


def fig_grid_saidi(grid):
    d = grid.dropna(subset=["saidi_wmed_ca_min"])
    fig, ax = plt.subplots(figsize=(9, 5))
    yrs = d.index.values.astype(float); w = 0.38
    ax.bar(yrs - w / 2, d.saidi_wmed_ca_min, w, color=CA, label="California")
    ax.bar(yrs + w / 2, d.saidi_wmed_tx_min, w, color=TX, label="Texas")
    ax.set_title("Grid Reliability: Outage Minutes per Customer (incl. major events)")
    ax.set_xlabel("Year"); ax.set_ylabel("SAIDI with major event days (minutes/yr)")
    ax.set_xticks(yrs); ax.legend()
    _save(fig, "10_grid_saidi.png",
          "Source: EIA-861, customer-weighted. 2021 spike = Winter Storm Uri. "
          "(Excluding major events, TX is on par or better.)")


def fig_wage_gap(wages):
    d = wages.dropna(subset=["avg_pay_info_ca"])
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(d.index, d.avg_pay_info_ca / 1e3, color=CA, marker="o", label="California — Information")
    ax.plot(d.index, d.avg_pay_info_tx / 1e3, color=TX, marker="o", label="Texas — Information")
    ax.plot(d.index, d.avg_pay_total_ca / 1e3, color=CA, marker="s", ls="--", alpha=0.5, label="California — all industries")
    ax.plot(d.index, d.avg_pay_total_tx / 1e3, color=TX, marker="s", ls="--", alpha=0.5, label="Texas — all industries")
    ax.set_title("California's Wage Moat: Information-Sector Average Pay (widening)")
    ax.set_xlabel("Year"); ax.set_ylabel("Average annual pay ($ thousands, nominal)")
    ax.legend(fontsize=8)
    _save(fig, "11_wage_gap_information.png",
          "Source: BLS QCEW (annual average pay). Nominal $.")


def main() -> int:
    g, m, c, sc = gdp_mod.build(), mig_mod.build(), cap_mod.build(), sc_mod.build()
    print("Rendering figures -> outputs/figures/")
    fig_gdp_levels(g)
    fig_gdp_per_capita(g)
    fig_net_domestic_migration(m)
    fig_net_interstate_agi(m)
    fig_bilateral(m)
    fig_formd(c)
    fig_scorecard(sc)
    # counter-cases
    fig_property_tax(cc_mod.build_housing_tax())
    fig_austin_boombust()
    fig_grid_saidi(cc_mod.build_grid())
    fig_wage_gap(cc_mod.build_wages())
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
