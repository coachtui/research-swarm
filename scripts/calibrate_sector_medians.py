"""
Measure GICS sector median multiples from the S&P 500.

`MarketDataClient.SECTOR_MEDIAN_PE` / `SECTOR_MEDIAN_EV_EBITDA` ship as
curated estimates. They anchor the valuation score (P/E vs sector is 50% of
it) and every "vs sector median" column in the report, so they should be
measured, not assumed — same principle as the component-score calibration.

Method:
  - Universe: research_swarm/data/universes/sp500_constituents.json — the
    actual constituent list with CANONICAL GICS sectors (Wikipedia-sourced,
    refreshed by scripts/build_sp500_constituents.py). Grouping uses those
    sectors, never yfinance's taxonomy, so misfilings cannot leak in.
  - One yfinance info fetch per constituent for trailing P/E and EV/EBITDA
    (threaded, resumable JSONL).
  - Median of POSITIVE multiples per sector, capped at 500x. Loss-makers
    are excluded — a negative P/E is not a valuation, and a distorted one
    would poison the benchmark it is later compared against.

Run quarterly, ~6 weeks into the quarter (after most constituents report,
so TTM denominators are fresh). Review the printed drift vs the shipped
table before pasting — a large silent move is a data problem until proven
otherwise.

Usage:
    python scripts/calibrate_sector_medians.py             # full universe
    python scripts/calibrate_sector_medians.py --limit 60  # smoke test

Output: per-sector medians with sample sizes and quartiles, drift vs the
shipped constants, and a ready-to-paste pair of table literals.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research_swarm.data.market_data_client import MarketDataClient

CONSTITUENTS = Path("research_swarm/data/universes/sp500_constituents.json")
OUT_PATH = Path("scripts/.sector_medians_progress.jsonl")
_write_lock = threading.Lock()


def _fetch_one(ticker: str) -> Optional[dict]:
    import yfinance as yf

    try:
        info = yf.Ticker(ticker).info
        if not info:
            return None
        return {
            "ticker": ticker,
            "pe": info.get("trailingPE"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
        }
    except Exception as e:
        print(f"  [warn] {ticker}: {e}")
        return None


def _collect(tickers: List[str], workers: int = 6) -> Dict[str, dict]:
    done: Dict[str, dict] = {}
    if OUT_PATH.exists():
        for line in OUT_PATH.read_text().splitlines():
            row = json.loads(line)
            done[row["ticker"]] = row
        print(f"resuming — {len(done)} tickers already fetched")

    todo = [t for t in tickers if t not in done]
    with OUT_PATH.open("a") as fh, ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(_fetch_one, t): t for t in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            row = fut.result()
            if row:
                with _write_lock:
                    fh.write(json.dumps(row) + "\n")
                    fh.flush()
                done[row["ticker"]] = row
            if i % 50 == 0:
                print(f"  {i}/{len(todo)} fetched")
    return done


def _median_block(rows: List[dict], sectors: Dict[str, str], field: str) -> Dict[str, dict]:
    by_sector: Dict[str, List[float]] = {}
    for r in rows:
        sector = sectors.get(r["ticker"])
        v = r.get(field)
        # positive multiples only, capped so one distorted name cannot skew
        if sector and isinstance(v, (int, float)) and 0 < v < 500:
            by_sector.setdefault(sector, []).append(float(v))

    out = {}
    for sector, vals in sorted(by_sector.items()):
        vals.sort()
        out[sector] = {
            "median": statistics.median(vals),
            "n": len(vals),
            "p25": vals[len(vals) // 4],
            "p75": vals[(3 * len(vals)) // 4],
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    data = json.loads(CONSTITUENTS.read_text())
    constituents = data["constituents"]
    if args.limit:
        constituents = constituents[: args.limit]
    sectors = {c["ticker"]: c["sector"] for c in constituents}
    tickers = list(sectors)

    print(f"measuring sector medians over {len(tickers)} constituents "
          f"(list as of {data.get('as_of')})")
    done = _collect(tickers)
    rows = [done[t] for t in tickers if t in done]
    print(f"\n{len(rows)} constituents fetched")

    pe = _median_block(rows, sectors, "pe")
    ev = _median_block(rows, sectors, "ev_ebitda")

    print(f"\n{'Sector':<26}{'P/E med':>9}{'n':>5}{'p25–p75':>15}"
          f"{'EV/EBITDA':>11}{'n':>5}   drift vs shipped")
    for sector in sorted(set(pe) | set(ev)):
        p, e = pe.get(sector), ev.get(sector)
        shipped = MarketDataClient.SECTOR_MEDIAN_PE.get(sector)
        drift = f"P/E {p['median'] - shipped:+.1f}" if p and shipped else "—"
        pe_part = (f"{p['median']:>9.1f}{p['n']:>5}{p['p25']:>8.1f}–{p['p75']:<6.1f}"
                   if p else f"{'—':>29}")
        ev_part = f"{e['median']:>11.1f}{e['n']:>5}" if e else f"{'—':>16}"
        print(f"{sector:<26}{pe_part}{ev_part}   {drift}")

    print("\n# ── ready to paste (MarketDataClient) ──")
    print("    # MEASURED from S&P 500 constituents (see scripts/calibrate_sector_medians.py).")
    print("    # Refresh quarterly, ~6 weeks into the quarter; update SECTOR_MEDIANS_AS_OF too.")
    print("    SECTOR_MEDIAN_PE = {")
    for sector, d in sorted(pe.items()):
        print(f'        "{sector}": {d["median"]:.1f},   # n={d["n"]}')
    print("    }")
    print("\n    SECTOR_MEDIAN_EV_EBITDA = {")
    for sector, d in sorted(ev.items()):
        print(f'        "{sector}": {d["median"]:.1f},   # n={d["n"]}')
    print("    }")


if __name__ == "__main__":
    main()
