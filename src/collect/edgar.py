"""
Collector: SEC EDGAR -- two corporate-side beats for the TX vs CA thesis.

Source : U.S. Securities and Exchange Commission, EDGAR.
Access : No API key, but SEC REQUIRES a descriptive User-Agent header
         (read from SEC_USER_AGENT in .env; falls back to a configured default).
Docs   : https://www.sec.gov/search-filings/edgar-application-programming-interfaces

Two sub-collectors (run both by default; `python -m src.collect.edgar hq|formd`):

1. HQ relocations ("what moves" -> Texas)
   Verifies a curated list of widely-reported CA->TX corporate relocations against
   PRIMARY EDGAR data: each company's CURRENT principal-office state/city and state
   of incorporation, via the submissions API. Writes a REFERENCE table (not the
   numeric tidy contract -- this is event/verification data):
     data/processed/edgar_hq_relocations_tx_ca.csv
   move_announced_year / from_state are curated metadata (cite separately); the
   EDGAR-derived current state is the primary-source fact, summarized in
   `verified_in_to_state`.

2. Form D by state ("what stays" -> California's capital moat)
   Aggregates SEC Form D exempt-offering notices by primary-issuer state (CA vs TX)
   per filing year: OFFERING COUNT (primary proxy) and TOTAL AMOUNT SOLD (noisy $,
   caveated). Form D spans ALL Reg D offerings (VC, PE, real estate, funds) -- a
   broad private-capital proxy, NOT VC alone. Writes the tidy contract:
     data/processed/edgar_formd_tx_ca.csv

Never fabricates: missing/suppressed values are dropped, not imputed.
"""
from __future__ import annotations

import datetime as dt
import io
import os
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv

# --- paths ---
ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "sources.yaml"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
HQ_CSV = PROCESSED_DIR / "edgar_hq_relocations_tx_ca.csv"
FORMD_CSV = PROCESSED_DIR / "edgar_formd_tx_ca.csv"

# State abbrev -> (geo_id FIPS, geo_name) for the two anchor states.
STATE_MAP = {"CA": ("06", "California"), "TX": ("48", "Texas")}

# Tidy-data contract (CLAUDE.md) -- used by the Form D output.
TIDY_COLUMNS = [
    "geo_id", "geo_name", "geo_level", "year", "metric", "value", "unit",
    "real_or_nominal", "source", "source_url", "retrieved_at",
]


class EDGARError(RuntimeError):
    """Raised on a download/parse problem."""


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["sources"]["edgar"]


def get_user_agent(cfg: dict) -> str:
    load_dotenv(ROOT / ".env")
    ua = os.getenv(cfg.get("user_agent_env", "SEC_USER_AGENT"), "")
    ua = (ua or "").strip()
    if not ua:
        ua = cfg["default_user_agent"]
        print(f"[note] SEC_USER_AGENT not set in .env; using default UA "
              f"({ua!r}). SEC just needs a descriptive contact.")
    return ua


# ============================================================ 1) HQ relocations
def collect_hq(cfg: dict, ua: str, retrieved_at: str) -> int:
    companies = cfg["hq_relocations"]["companies"]
    rows: list[dict] = []
    stamp = retrieved_at[:10].replace("-", "")

    for c in companies:
        cik10 = f"{int(c['cik']):010d}"
        url = cfg["submissions_url"].format(cik10=cik10)
        resp = requests.get(url, headers={"User-Agent": ua}, timeout=60)
        resp.raise_for_status()
        j = resp.json()
        (RAW_DIR / f"edgar_submissions_CIK{cik10}_{stamp}.json").write_bytes(resp.content)

        biz = (j.get("addresses") or {}).get("business") or {}
        biz_state = (biz.get("stateOrCountry") or "").strip()
        recent = (j.get("filings") or {}).get("recent") or {}
        dates = recent.get("filingDate") or []
        latest_filing = dates[0] if dates else ""

        rows.append({
            "cik": cik10,
            "company": c["name"],
            "from_state": c["from_state"],
            "to_state_expected": c["to_state"],
            "move_announced_year": c["move_announced_year"],
            "edgar_entity_name": j.get("name", ""),
            "edgar_business_state": biz_state,
            "edgar_business_city": (biz.get("city") or "").strip(),
            "edgar_state_of_incorporation": (j.get("stateOfIncorporation") or "").strip(),
            "latest_filing_date": latest_filing,
            "verified_in_to_state": biz_state == c["to_state"],
            "source": "SEC EDGAR submissions API",
            "source_url": url,
            "retrieved_at": retrieved_at,
        })
        flag = "OK " if rows[-1]["verified_in_to_state"] else "!! "
        print(f"  {flag}{c['name']:28s} -> EDGAR biz state {biz_state or '?':2s} "
              f"({rows[-1]['edgar_business_city']})")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows).sort_values(["to_state_expected", "company"]).reset_index(drop=True)
    df.to_csv(HQ_CSV, index=False)
    n_ok = int(df["verified_in_to_state"].sum())
    print(f"\nWrote {len(df)} companies -> {HQ_CSV.relative_to(ROOT)} "
          f"({n_ok}/{len(df)} verified in expected destination state)")
    return 0


# =============================================================== 2) Form D by state
def _quarters(start_year: int, end_year: int):
    for y in range(start_year, end_year + 1):
        for q in (1, 2, 3, 4):
            yield y, q


def _get_with_retry(url: str, headers: dict, timeout: int = 180,
                    tries: int = 4) -> requests.Response:
    """GET with backoff on SEC rate-limit / transient errors (403/429/5xx)."""
    r = None
    for i in range(tries):
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200 or r.status_code == 404:
            return r
        if r.status_code in (403, 429, 500, 502, 503, 504):
            time.sleep(1.5 * (i + 1))
            continue
        return r
    return r


def _read_tsv(z: zipfile.ZipFile, suffix: str) -> pd.DataFrame | None:
    name = next((n for n in z.namelist() if n.upper().endswith(suffix.upper())), None)
    if name is None:
        return None
    return pd.read_csv(z.open(name), sep="\t", dtype=str, encoding="latin-1",
                       on_bad_lines="skip")


def collect_formd(cfg: dict, ua: str, retrieved_at: str) -> int:
    fd = cfg["form_d"]
    states = [s.upper() for s in fd["issuer_states"]]
    sub_types = set(fd.get("submission_types", ["D"]))
    start_year = int(fd["start_year"])
    end_year = int(retrieved_at[:4])
    headers = {"User-Agent": ua}

    scoped: list[pd.DataFrame] = []   # CA/TX offering rows (trimmed raw)
    for y, q in _quarters(start_year, end_year):
        url = fd["dataset_url"].format(yyyy=y, q=q)
        r = _get_with_retry(url, headers)
        time.sleep(0.25)  # be polite to SEC between requests
        if r.status_code == 404:
            continue  # quarter not published yet
        if r.status_code != 200:
            print(f"  [skip] {y}Q{q}: HTTP {r.status_code}")
            continue
        try:
            z = zipfile.ZipFile(io.BytesIO(r.content))
        except zipfile.BadZipFile:
            print(f"  [warn] {y}Q{q}: bad zip, skipping")
            continue

        issuers = _read_tsv(z, "ISSUERS.tsv")
        offering = _read_tsv(z, "OFFERING.tsv")
        submission = _read_tsv(z, "FORMDSUBMISSION.tsv")
        if issuers is None or offering is None or submission is None:
            print(f"  [warn] {y}Q{q}: missing a TSV, skipping")
            continue

        # primary issuer in CA/TX
        # NOTE: the flag is "YES"/"NO" (not "Y"/"N"); accept common truthy forms.
        prim = issuers[issuers["IS_PRIMARYISSUER_FLAG"].astype(str).str.strip()
                       .str.upper().isin(["YES", "Y", "TRUE", "1"])]
        prim = prim[prim["STATEORCOUNTRY"].astype(str).str.strip().str.upper().isin(states)]
        prim = prim[["ACCESSIONNUMBER", "STATEORCOUNTRY", "ENTITYNAME"]].copy()
        prim["STATEORCOUNTRY"] = prim["STATEORCOUNTRY"].str.strip().str.upper()

        sub = submission[submission["SUBMISSIONTYPE"].astype(str).str.strip().isin(sub_types)]
        sub = sub[["ACCESSIONNUMBER", "FILING_DATE"]].copy()

        off = offering[["ACCESSIONNUMBER", "TOTALAMOUNTSOLD"]].copy()

        merged = prim.merge(sub, on="ACCESSIONNUMBER", how="inner") \
                     .merge(off, on="ACCESSIONNUMBER", how="left")
        if merged.empty:
            continue
        # The quarterly dataset IS organized by filing quarter, so the year is the
        # loop year -- robust against FILING_DATE format changes across vintages.
        merged["filing_year"] = y
        merged["amount_sold"] = pd.to_numeric(merged["TOTALAMOUNTSOLD"], errors="coerce")
        scoped.append(merged)
        print(f"  {y}Q{q}: {len(merged)} CA/TX primary-issuer new offerings")

    if not scoped:
        raise EDGARError("No Form D quarters processed; refusing to write empty file.")

    allrows = pd.concat(scoped, ignore_index=True)
    allrows = allrows[allrows["filing_year"].notna()]
    allrows["filing_year"] = allrows["filing_year"].astype(int)

    # save trimmed raw (CA/TX rows only -- sanctioned by the large-file guardrail)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = retrieved_at[:10].replace("-", "")
    allrows.to_csv(RAW_DIR / f"edgar_formd_ca_tx_offerings_{stamp}.csv", index=False)

    # aggregate by state-year
    rows: list[dict] = []
    src_url = cfg["docs_url"]
    for state_abbr, grp in allrows.groupby("STATEORCOUNTRY"):
        if state_abbr not in STATE_MAP:
            continue
        geo_id, geo_name = STATE_MAP[state_abbr]
        for year, yg in grp.groupby("filing_year"):
            base = dict(geo_id=geo_id, geo_name=geo_name, geo_level="state",
                        year=int(year), source="SEC EDGAR Form D data sets",
                        source_url=src_url, retrieved_at=retrieved_at)
            rows.append({**base, "metric": "formd_offerings_count",
                         "value": float(len(yg)), "unit": "offerings",
                         "real_or_nominal": "n/a"})
            amt = yg["amount_sold"].dropna()
            amt = amt[amt >= 0]
            rows.append({**base, "metric": "formd_amount_sold_usd",
                         "value": float(amt.sum()), "unit": "USD",
                         "real_or_nominal": "nominal"})

    df = (pd.DataFrame(rows, columns=TIDY_COLUMNS)
          .sort_values(["geo_name", "metric", "year"]).reset_index(drop=True))
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(FORMD_CSV, index=False)
    print(f"\nWrote {len(df)} rows -> {FORMD_CSV.relative_to(ROOT)}")
    print(f"  states : {sorted(df['geo_name'].unique())}")
    print(f"  years  : {df['year'].min()}-{df['year'].max()}")
    print(f"  metrics: {sorted(df['metric'].unique())}")
    return 0


def main(argv: list[str]) -> int:
    cfg = load_config()
    ua = get_user_agent(cfg)
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    which = argv[0].lower() if argv else "both"

    if which in ("hq", "both"):
        print("== HQ relocations (EDGAR submissions API) ==")
        collect_hq(cfg, ua, retrieved_at)
    if which in ("formd", "both"):
        print("\n== Form D offerings by state ==")
        collect_formd(cfg, ua, retrieved_at)
    if which not in ("hq", "formd", "both"):
        print(f"Unknown target {which!r}; use: hq | formd | both")
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except EDGARError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"NETWORK ERROR talking to SEC: {exc}", file=sys.stderr)
        sys.exit(1)
