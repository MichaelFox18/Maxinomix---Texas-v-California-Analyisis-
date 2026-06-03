"""
Analysis: private capital -- SEC Form D offerings by state.

"What stays put" side: California's capital moat. Form D covers ALL Reg D exempt
offerings (VC, PE, real estate, funds) -- a broad private-capital proxy, NOT VC
alone. Offering COUNT is the robust proxy; amount sold ($) is nominal and noisy.

Output: outputs/tables/capital_summary.csv (one row per year).
Note: the most recent year may be partial (the collector pulls all published
quarters); rows are not annualized -- a partial final year is left as-is.
"""
from __future__ import annotations

import pandas as pd

from src.clean import harmonize as hz


def build() -> pd.DataFrame:
    fd = hz.load_processed("edgar_formd_tx_ca.csv")
    cnt = hz.metric_series(fd, "formd_offerings_count")
    amt = hz.metric_series(fd, "formd_amount_sold_usd")     # nominal USD

    t = pd.DataFrame(index=cnt.index)
    t.index.name = "year"
    t["formd_count_ca"] = cnt["CA"]
    t["formd_count_tx"] = cnt["TX"]
    t["formd_count_ca_over_tx"] = cnt["CA"] / cnt["TX"]
    t["formd_amount_ca_busd"] = amt["CA"] / 1e9
    t["formd_amount_tx_busd"] = amt["TX"] / 1e9
    t["formd_amount_ca_over_tx"] = amt["CA"] / amt["TX"]

    return t.round(3)


def main() -> int:
    t = build()
    path = hz.write_table(t, "capital_summary.csv")
    print(f"Wrote {len(t)} years -> {path.relative_to(hz.ROOT)}")
    print(t.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
