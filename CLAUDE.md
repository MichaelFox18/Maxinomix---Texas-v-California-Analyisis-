# CLAUDE.md — Texas vs California economic analysis

## Project

A data analysis project answering one question: **"Can Texas actually beat California?"**
The deliverable is a set of clean datasets, charts, and written insights that could
support a data-driven explainer video.

**Thesis (the spine of every analysis):** a *split decision*.
- Texas wins what can **move** — net migration, HQ relocations, income migration, exports.
- California wins what **stays put** — total GDP, venture capital, tech workforce, productivity.
- The open question the analysis keeps returning to: do the people/companies eventually
  drag the output with them, or does California's capital-and-AI moat hold?

Audience for the eventual output is data-literate, so **rigor and sourcing matter more
than a clean narrative.** Never overclaim beyond what the data shows.

## Scope (keep all pulls consistent)

- **Geographies:** Texas and California (states). Where metro detail helps, use:
  Austin, Dallas–Fort Worth, Houston, San Antonio vs San Francisco, San Jose,
  Los Angeles, San Diego. Always key on FIPS / GEOID, never on name strings alone.
- **Time window:** 2015 → latest available year.
- **Dollars:** for any multi-year comparison use **real (inflation-adjusted) dollars**
  and record the deflator/base year. Always label nominal vs real in the data and in
  any chart. Flag per-capita vs absolute and flow vs stock explicitly.

## Repo structure

```
.
├── CLAUDE.md
├── README.md
├── .env.example          # API-key placeholders (committed)
├── .env                  # real keys (NEVER committed)
├── .gitignore
├── requirements.txt
├── config/
│   └── sources.yaml      # registry of sources, endpoints, dataset codes, params
├── data/
│   ├── raw/              # untouched API/CSV pulls, timestamped (committed)
│   ├── interim/          # cleaned, not yet final
│   └── processed/        # tidy, analysis-ready CSVs
├── src/
│   ├── collect/          # one module per source: bea.py, bls.py, census.py,
│   │                     #   irs_soi.py, eia.py, edgar.py, patentsview.py
│   ├── clean/            # geography + time harmonization, real/nominal conversion
│   └── analyze/          # metric construction, TX-vs-CA comparisons
├── notebooks/            # exploratory only — final logic lives in src/
├── outputs/
│   ├── figures/
│   └── tables/
└── tests/
```

## Data-source registry

All federal sources below are free. Register keys before coding the collectors that need them.

| Source | What it gives | Access | Key? |
|---|---|---|---|
| **BEA Regional** | GDP by state/metro (SAGDP, SQGDP, CAGDP), personal income (SAINC), price parities (SARPP) | `https://apps.bea.gov/api/data` | Yes (free) |
| **BLS** | Employment & wages (QCEW), state/metro jobs (SAE/CES), unemployment (LAUS), wages by occupation (OEWS) | `https://api.bls.gov/publicAPI/v2/` | Yes (free, v2) |
| **Census** | Population & components of change (PEP), demographics & migration (ACS), business formation (BFS), establishments (CBP), state/local govt finance | `https://api.census.gov/data` | Yes (free) |
| **IRS SOI Migration** | State- and county-level migration flows incl. adjusted gross income — the "follow the money" data | CSV downloads (no API) | No |
| **EIA** | Electricity prices and generation mix by state | `https://api.eia.gov/v2/` | Yes (free) |
| **SEC EDGAR** | Company filings — principal office address + state of incorporation | `https://data.sec.gov/` + full-text search; set a descriptive User-Agent header | No |
| **USPTO PatentsView** | Patents by state (innovation proxy) | `https://search.patentsview.org/api/v1/` | Yes (free) |
| **FHFA HPI** | House Price Index by state/metro | CSV downloads | No |
| **Zillow Research** | Home values (ZHVI), rents (ZORI) | CSV downloads | No |

> Verify exact dataset codes and query params against each source's current docs before
> coding — endpoints and table IDs change. Do not hardcode guessed parameters.

## Tidy-data contract

Every file written to `data/processed/` is **long format**, one observation per row, with
these columns:

`geo_id, geo_name, geo_level, year, metric, value, unit, real_or_nominal, source, source_url, retrieved_at`

## Conventions

- **Python 3.11+.** Use the project venv. Core deps: `pandas`, `requests`,
  `python-dotenv`, `pyyaml`. Pin everything in `requirements.txt`.
- **Secrets:** load keys from `.env` via `python-dotenv`. Keep placeholders in
  `.env.example`. Never print or commit a real key.
- **Raw is committed but sacred:** save every pull untouched to `data/raw/` with a date
  stamp and commit it — the data is small and public, so the repo stays portable across
  machines. Never hand-edit a raw file; all transforms happen in code in `src/clean/`.
- **Provenance:** each collector starts with a comment stating the source, dataset
  code, and docs URL. Each processed file carries the source columns above.
- **One source per collector module.** Keep collection, cleaning, and analysis separate.

## Analysis principles (always do these)

1. **Cite every number** with its primary source and year. No uncited figures in outputs.
2. **Always include the counter-case.** For any "Texas is winning" claim, surface the
   skeptic's data: property-tax burden, grid reliability, affordability erosion, the
   GDP-per-capita gap. A one-sided result is a bug.
3. **Never fabricate or silently estimate.** If data is missing or a key is absent, say
   so and stub the function — do not fill gaps with made-up values.
4. **Label the metric type** (real/nominal, per-capita/absolute, flow/stock) wherever a
   number appears, because the whole thesis turns on flow-vs-stock.

## Guardrails

- Never commit `.env`, API keys, or the venv (these stay gitignored). **Data is committed**
  for portability — it's small and public. Use Git LFS for any single file over ~50 MB
  (trim IRS/Zillow national files to TX/CA first), and if the repo is public, mind the
  terms of non-government sources like Zillow and keep their attribution.
- Always propose a plan before pulling data or restructuring the repo; wait for my go-ahead.
- Prefer real (inflation-adjusted) dollars for any comparison spanning more than one year.
