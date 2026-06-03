"""
Analysis: migration -- people (Census PEP) and money (IRS SOI AGI).

"What moves" side of the thesis: Texas gains people and income. Combines PEP net
domestic/international migration with IRS interstate AGI flows and the CA<->TX
bilateral flow.

Real-vs-nominal: IRS AGI is nominal (current $, in thousands). For valid cross-year
comparison without a deflator, net AGI is also expressed as a share of nominal GDP
(numerator and denominator are same-year nominal, so the ratio is inflation-robust).

Output: outputs/tables/migration_summary.csv (one row per year).
"""
from __future__ import annotations

import pandas as pd

from src.clean import harmonize as hz


def build() -> pd.DataFrame:
    pep = hz.load_processed("census_pep_tx_ca.csv")
    irs = hz.load_processed("irs_soi_migration_tx_ca.csv")
    gdp = hz.load_processed("bea_gdp_tx_ca.csv")

    nom = hz.metric_series(gdp, "gdp_nominal")          # millions current $
    dom = hz.metric_series(pep, "domestic_migration")    # persons
    intl = hz.metric_series(pep, "international_migration")
    in_agi = hz.metric_series(irs, "domestic_in_agi")    # thousands current $
    out_agi = hz.metric_series(irs, "domestic_out_agi")
    in_ppl = hz.metric_series(irs, "domestic_in_individuals")
    out_ppl = hz.metric_series(irs, "domestic_out_individuals")
    ca_tx_agi = hz.metric_series(irs, "out_to_TX_agi").get("CA")     # CA -> TX
    tx_ca_agi = hz.metric_series(irs, "out_to_CA_agi").get("TX")     # TX -> CA
    ca_tx_ppl = hz.metric_series(irs, "out_to_TX_individuals").get("CA")
    tx_ca_ppl = hz.metric_series(irs, "out_to_CA_individuals").get("TX")

    idx = pd.Index(sorted(set(dom.index) | set(in_agi.index)), name="year")
    t = pd.DataFrame(index=idx)

    # --- people (PEP) ---
    t["pep_net_domestic_mig_ca"] = dom["CA"].reindex(idx)
    t["pep_net_domestic_mig_tx"] = dom["TX"].reindex(idx)
    t["pep_net_intl_mig_ca"] = intl["CA"].reindex(idx)
    t["pep_net_intl_mig_tx"] = intl["TX"].reindex(idx)

    # --- money (IRS), net interstate = inflow - outflow ---
    net_agi_ca = (in_agi["CA"] - out_agi["CA"]).reindex(idx)
    net_agi_tx = (in_agi["TX"] - out_agi["TX"]).reindex(idx)
    t["irs_net_interstate_agi_ca_kusd"] = net_agi_ca
    t["irs_net_interstate_agi_tx_kusd"] = net_agi_tx
    t["irs_net_interstate_people_ca"] = (in_ppl["CA"] - out_ppl["CA"]).reindex(idx)
    t["irs_net_interstate_people_tx"] = (in_ppl["TX"] - out_ppl["TX"]).reindex(idx)
    # inflation-robust: net AGI as % of nominal GDP (same-year nominal / nominal)
    t["irs_net_agi_pct_of_gdp_ca"] = net_agi_ca * 1e3 / (nom["CA"].reindex(idx) * 1e6) * 100
    t["irs_net_agi_pct_of_gdp_tx"] = net_agi_tx * 1e3 / (nom["TX"].reindex(idx) * 1e6) * 100

    # --- CA <-> TX bilateral ---
    t["ca_to_tx_agi_kusd"] = ca_tx_agi.reindex(idx) if ca_tx_agi is not None else pd.NA
    t["tx_to_ca_agi_kusd"] = tx_ca_agi.reindex(idx) if tx_ca_agi is not None else pd.NA
    t["net_ca_to_tx_agi_kusd"] = t["ca_to_tx_agi_kusd"] - t["tx_to_ca_agi_kusd"]
    t["ca_to_tx_people"] = ca_tx_ppl.reindex(idx) if ca_tx_ppl is not None else pd.NA
    t["tx_to_ca_people"] = tx_ca_ppl.reindex(idx) if tx_ca_ppl is not None else pd.NA
    t["net_ca_to_tx_people"] = t["ca_to_tx_people"] - t["tx_to_ca_people"]

    return t.round(2)


def main() -> int:
    t = build()
    path = hz.write_table(t, "migration_summary.csv")
    print(f"Wrote {len(t)} years -> {path.relative_to(hz.ROOT)}")
    cols = ["pep_net_domestic_mig_ca", "pep_net_domestic_mig_tx",
            "irs_net_interstate_agi_ca_kusd", "net_ca_to_tx_agi_kusd"]
    print(t[cols].to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
