# Project Summary — Texas vs California Economic Analysis (for resume tailoring)

> Source description for resume generation. Written to be accurate to the actual
> state of the work — a tailored resume should not claim beyond what is listed here.

## One-line description

A reproducible, source-of-truth data pipeline comparing the Texas and California
state economies (2015–present) using authoritative U.S. federal economic data.

## Elevator summary

A from-scratch data-analysis project that answers "Can Texas actually beat
California?" by pulling, cleaning, and comparing economic indicators for the two
largest U.S. state economies. The work emphasizes **data engineering rigor over
narrative**: a config-driven source registry, a strict tidy-data contract, full
provenance on every value, reproducible environments, and a hard rule against
fabricating or silently estimating missing data. The analytical framing is a
deliberate "split decision" thesis — comparing metrics that *move* (migration,
relocations, income flows) against those that *stay put* (total GDP, capital,
workforce) — which required disciplined handling of flow-vs-stock,
real-vs-nominal, and per-capita-vs-absolute distinctions.

## What was actually built (current state)

- **Project scaffold**: standardized `collect → clean → analyze` package layout,
  committed raw/interim/processed data tiers, config registry, tests, and outputs
  directories; Git repo wired to GitHub.
- **Source registry** (`config/sources.yaml`): 9 federal/public data sources
  catalogued with endpoints, dataset codes, auth requirements, and query params
  (BEA, BLS, Census, IRS SOI, EIA, SEC EDGAR, USPTO PatentsView, FHFA, Zillow).
- **Four production collectors** (`src/collect/`), each isolating one source and
  writing a tidy, fully-provenanced dataset:
  - **`bea.py`** — state real & nominal GDP (BEA Regional **API**). Resolves table
    line codes at runtime from the API's own metadata (`GetParameterValuesFiltered`)
    instead of hardcoding fragile magic numbers — which caught a real trap (nominal
    GDP is line code 3, not the intuitive 2, which is a quantity index). Real/nominal
    labels and the chained-dollar base year are read from the response so they
    can't drift.
  - **`census_pep.py`** — population + components of change (net / domestic /
    international migration) from Census PEP **flat files**. Diagnosed that the
    Census API is frozen pre-2022, then pivoted to the official CSV vintages and
    harmonized two of them across the 2020-census re-basing boundary.
  - **`irs_soi.py`** — state-to-state migration of people *and* adjusted gross
    income ("follow the money"), including the CA↔TX bilateral flow. Handles a real
    data trap where one aggregate code is reused for two different totals
    (disambiguated by label).
  - **`edgar.py`** — SEC EDGAR: verifies corporate HQ relocations against primary
    filing data (submissions API) and aggregates ~45 quarterly **Form D** datasets
    (zip/TSV) into private-capital activity by state, with retry/backoff and
    defensive parsing of cross-vintage schema changes.
  Cross-cutting engineering: an **11-column tidy-data contract** with provenance on
  every row; **no-fabrication guarantees** (missing/suppressed values dropped, never
  imputed; a missing API key triggers a clean stub with remediation steps); and
  **validation** (e.g. an internal-consistency check that real = nominal in the GDP
  base year, plus sanity checks against published figures).
- **Reproducibility**: Python virtual environment, pinned dependencies locked to
  the actually-resolved versions, secrets managed via `.env` (gitignored) with a
  committed `.env.example` template.

## Languages

- **Python** (3.11+; built/run on 3.14) — primary
- **YAML** — configuration / source registry
- **SQL-style / tabular data modeling** (long "tidy" format) — conceptual
- **Markdown** — documentation
- **Git** — version control

## Core technical skills demonstrated

- **Data engineering / ETL pipeline design**: clean separation of collection,
  cleaning, and analysis; raw-immutable / processed-derived data tiers.
- **REST API integration**: authenticated calls, query construction, JSON
  parsing, error handling, and **API-metadata introspection** to make collectors
  resilient to schema changes.
- **Data modeling & governance**: tidy/long-format contracts, one-observation-
  per-row design, FIPS/GEOID-based geographic keying (never name-string joins),
  and end-to-end data provenance.
- **Reproducible environments**: virtualenv, dependency pinning, environment-
  variable secrets management, portable committed datasets.
- **Data quality & validation**: missing-data handling, no-fabrication policy,
  internal-consistency and external sanity checks.
- **Economic / quantitative data literacy**: real vs nominal (inflation
  adjustment, deflators, base years), flow vs stock, per-capita vs absolute,
  multi-year comparison hygiene.
- **Analytical rigor & communication**: every figure cited to a primary source
  and year; deliberate inclusion of the counter-case for any claim.

## Tools, libraries & data sources

- **Libraries**: pandas, requests, python-dotenv, PyYAML
- **Tooling**: Git/GitHub, virtualenv/pip, VS Code, CLI
- **Data sources**: U.S. Bureau of Economic Analysis (BEA Regional), Bureau of
  Labor Statistics (BLS), U.S. Census Bureau, IRS SOI Migration, EIA, SEC EDGAR,
  USPTO PatentsView, FHFA, Zillow Research

## Relevant career factors / positioning

- **Target roles**: Data Analyst, Data Engineer, Data Scientist, Research/
  Quantitative Analyst, Economic/Policy Analyst.
- **Differentiators a resume can emphasize**:
  - Builds *trustworthy* data products — provenance, reproducibility, and an
    explicit anti-fabrication discipline (valuable for regulated, research, or
    decision-support settings).
  - Comfortable with messy, real-world government/public data and the API quirks
    that come with it.
  - Pairs engineering with genuine domain reasoning (economics: inflation
    adjustment, flow vs stock), not just plumbing.
  - Self-directed: defined the problem, designed the architecture, and shipped a
    working, validated component end-to-end.
- **Status note for honest framing**: an active, in-progress portfolio project —
  the architecture and four data collectors (BEA GDP, Census population/migration,
  IRS income migration, SEC EDGAR HQ + Form D) are complete and validated; the
  cleaning/harmonization and comparative-analysis layers are planned/ongoing.

## Sample resume bullets (ready to tailor)

- Designed and built a reproducible Python data pipeline comparing two state
  economies, ingesting authoritative federal economic data via REST APIs into a
  governed, tidy-format dataset with full provenance.
- Engineered a resilient API collector that resolves dataset schema at runtime
  from provider metadata instead of hardcoded codes, preventing silent data
  errors and adapting automatically to source changes.
- Enforced data-quality guarantees (no imputation of missing values, source
  citation on every record, internal-consistency validation) and reproducible
  environments (pinned dependencies, isolated virtualenv, secret management).
- Applied economic data rigor — real vs nominal inflation adjustment, flow vs
  stock, and per-capita vs absolute distinctions — to keep multi-year, cross-
  state comparisons valid.
- Integrated four heterogeneous government sources (REST APIs, CSV vintages, and
  zipped TSV datasets), reconciling source-specific quirks — frozen API versions,
  reused aggregate codes, and cross-vintage schema/format changes — into one
  consistent, validated dataset.
