# Maxinomix — Texas vs California economic analysis

**Question:** *Can Texas actually beat California?* A head-to-head comparison of the
two state economies. Working thesis is a **split decision** — Texas wins what can
**move** (net migration, HQ relocations, income migration, exports); California wins
what **stays put** (total GDP, venture capital, tech workforce, productivity).

Project conventions, the data-source registry, and the analysis principles live in
[CLAUDE.md](CLAUDE.md). Read it first — rigor and sourcing come before narrative, and
nothing is ever fabricated or silently estimated.

## Setup

Requires **Python 3.11+**.

```bash
# from the repo root
python -m venv venv
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env      # then add your free API keys (see registration links inside)
```

## Repo layout

```
config/        sources.yaml — registry of endpoints, dataset codes, params
data/raw/      untouched, timestamped API/CSV pulls (committed, never hand-edited)
data/interim/  cleaned, not yet final
data/processed/ tidy, analysis-ready long-format CSVs
src/collect/   one module per source (bea.py, bls.py, ...)
src/clean/     geography + time harmonization, real/nominal conversion
src/analyze/   metric construction, TX-vs-CA comparisons
outputs/       figures/ and tables/
notebooks/     exploratory only — final logic lives in src/
tests/
```

## Tidy-data contract

Every file in `data/processed/` is **long format**, one observation per row:

```
geo_id, geo_name, geo_level, year, metric, value, unit, real_or_nominal,
source, source_url, retrieved_at
```

## Collectors

| Collector | Source | Output | Needs |
|---|---|---|---|
| `src/collect/bea.py` | BEA Regional SAGDP1 — state real & nominal GDP, 2015→latest | `bea_gdp_tx_ca.csv` | `BEA_API_KEY` |
| `src/collect/census_pep.py` | Census PEP flat files — population + components of change (net/domestic/intl migration, births, deaths), 2015→latest | `census_pep_tx_ca.csv` | none |
| `src/collect/irs_soi.py` | IRS SOI Migration — interstate flows of returns/people/AGI + CA↔TX bilateral, 2015-16→latest | `irs_soi_migration_tx_ca.csv` | none |
| `src/collect/edgar.py` | SEC EDGAR — HQ-relocation verification (submissions API) + Form D offerings by state | `edgar_hq_relocations_tx_ca.csv`, `edgar_formd_tx_ca.csv` | `SEC_USER_AGENT` (descriptive UA; falls back to a default) |

Run a collector as a module from the repo root:

```bash
python -m src.collect.bea
python -m src.collect.census_pep
python -m src.collect.irs_soi
python -m src.collect.edgar           # both EDGAR sub-collectors (or: edgar hq | edgar formd)
```

If a required key is missing, an API-keyed collector **stubs out** — it prints exactly
which free key to register for and where, and writes no data. Nothing is ever estimated.

### Collector notes

- **`bea.py`** resolves SAGDP1 `LineCode`s for *Real GDP* and *Current-dollar GDP* from
  BEA's own metadata at runtime (no guessed codes); units and the chained-dollar base
  year come from each record's `CL_UNIT`.
- **`census_pep.py`** uses the official PEP CSV vintages because the Census API is frozen
  pre-2022 for PEP; it splits the series at the 2020-census re-basing boundary.
- **`irs_soi.py`** disambiguates the IRS aggregate code `97` (reused for *Total
  Migration-US* and *Same-State*) by label; AGI is nominal, in thousands of USD.
- **`edgar.py`** verifies each curated relocation's current principal-office state via
  the submissions API, and aggregates ~45 quarterly Form D datasets (count + $ raised)
  by issuer state. Form D = all Reg D offerings (a broad private-capital proxy, not VC
  alone). Across all collectors, missing/suppressed values are dropped, never filled.
