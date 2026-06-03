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
- **Eight production collectors** (`src/collect/`), each isolating one source and
  writing a tidy, fully-provenanced dataset. The thesis side ("what moves" → Texas):
  - **`bea.py`** — state real & nominal GDP (BEA Regional **API**); resolves table
    line codes at runtime from the API's metadata (`GetParameterValuesFiltered`)
    rather than hardcoding magic numbers — caught a real trap (nominal GDP is line
    code 3, not 2). Units/base-year read from the response so labels can't drift.
  - **`census_pep.py`** — population + components of change from Census PEP **flat
    files** (diagnosed the API is frozen pre-2022; harmonized two vintages across
    the 2020-census re-basing boundary).
  - **`irs_soi.py`** — interstate migration of people *and* adjusted gross income
    ("follow the money") incl. the CA↔TX bilateral flow; disambiguated an aggregate
    code reused for two different totals.
  - **`edgar.py`** — SEC EDGAR: HQ-relocation verification (submissions API) +
    ~45 quarterly **Form D** datasets (zip/TSV) aggregated to private-capital by
    state, with retry/backoff.
  And the counter-case side ("at what cost", under a strict no-one-sided-result rule):
  - **`census_acs.py`** — ACS housing & property-tax reality (effective tax rate).
  - **`zillow.py`** — metro home-value index (ZHVI), CBSA-keyed, with attribution.
  - **`eia.py`** — electricity price & demand (v2 API) + grid reliability/SAIDI
    parsed and customer-weighted from EIA-861 **spreadsheets** (Excel).
  - **`bls.py`** — QCEW average pay & employment by industry (the wage-quality gap).
  Cross-cutting engineering: an **11-column tidy-data contract** with provenance on
  every row; **no-fabrication guarantees** (missing/suppressed values dropped, never
  imputed; a missing API key triggers a clean stub with remediation steps); and
  **validation** against published figures + internal-consistency checks.
- **Cleaning & analysis layer** (`src/clean/`, `src/analyze/`): canonical geography
  harmonization across all sources; a **US GDP price deflator** for real-dollar
  conversion; metric construction (real GDP per capita, growth, net migration, net
  AGI flows); and **two scorecards** — the "split decision" and a counter-case
  "at what cost" synthesis.
- **Visualization** (`src/analyze/figures.py`): 11 reproducible, source-captioned
  matplotlib charts, including a normalized "tug-of-war" of who wins each dimension.
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
  and year; deliberate inclusion of the counter-case for any claim (a one-sided
  result is treated as a bug).
- **Data visualization**: clear, consistently-styled, source-captioned CA-vs-TX
  charts in matplotlib, including a normalized "split-decision" scorecard.
- **Heterogeneous-source integration**: REST APIs, CSV/flat-file vintages, zipped
  TSV datasets, and Excel spreadsheets — reconciled into one harmonized dataset.

## Tools, libraries & data sources

- **Libraries**: pandas, requests, python-dotenv, PyYAML, matplotlib, openpyxl
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
- **Status note for honest framing**: an active portfolio project. Eight validated
  data collectors, the cleaning/harmonization + real-dollar-deflator layer, the
  comparative analysis (split-decision and counter-case scorecards), and 11 charts
  are complete; remaining work is narrative/scripting and optional metro-level depth.

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
- Integrated eight heterogeneous government/public sources (REST APIs, CSV
  vintages, zipped TSV datasets, and Excel spreadsheets), reconciling source-specific
  quirks — frozen API versions, reused aggregate codes, cross-vintage schema/format
  changes — into one harmonized, validated dataset.
- Built the analysis and visualization layer: real-dollar deflation, per-capita and
  flow metrics, and 11 source-cited charts, plus a balanced "split-decision" vs
  "at what cost" scorecard that pairs every advantage with its documented trade-off.
