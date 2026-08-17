"""
Measure the real distribution of each scoring component.

`score_normalization.COMPONENT_CALIBRATION` ships with SEED estimates — centers
and spreads picked from development observation rather than a fitted sample.
That is enough to correct the gross mis-weighting between components, but it
means the tier thresholds in `ManagerScorer` sit on an assumed distribution
rather than a measured one. This script replaces the guess with a measurement.

Two sources, chosen per component by which one is trustworthy:

  STORED  — components untouched by recent work are read from the 400+
            analyses already in Neon. That is the true production
            distribution, costs nothing, and needs no API calls.

  FRESH   — components whose calculation CHANGED cannot use stored values,
            because history holds numbers the current code would never
            produce (roic_wacc_spread was ROE-vs-WACC; earnings_momentum was
            pinned at a constant). These are recomputed from live data.

Fresh recomputation is deliberately cheap: ROIC, earnings momentum and
valuation are pure arithmetic over yfinance. No LLM calls, no filing
extraction, no reports written or persisted.

Usage:
    python scripts/calibrate_score_components.py            # both sources
    python scripts/calibrate_score_components.py --stored   # DB only, instant
    python scripts/calibrate_score_components.py --limit 60 # cap fresh tickers

Output: a table of median / stdev / percentiles per component, plus a ready-to
paste COMPONENT_CALIBRATION block and suggested tier thresholds.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Components whose calculation is unchanged, so stored history is valid.
STORED_COMPONENTS = ("financial_health", "sentiment_catalysts", "technical")
# Components recomputed today — stored values are stale by construction.
FRESH_COMPONENTS = ("roic_wacc_spread", "earnings_momentum", "valuation")


# ── Stored distribution (Neon) ────────────────────────────────────────────────

async def _fetch_stored() -> Dict[str, List[float]]:
    import asyncpg

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set — skipping stored components")
        return {}

    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch(
            """
            SELECT financial_health_score, sentiment_score, technical_score, full_output
            FROM stock_results
            WHERE status = 'completed' AND financial_health_score IS NOT NULL
            """
        )
    finally:
        await conn.close()

    out: Dict[str, List[float]] = {c: [] for c in STORED_COMPONENTS}
    for r in rows:
        if r["financial_health_score"] is not None:
            out["financial_health"].append(float(r["financial_health_score"]))
        if r["sentiment_score"] is not None:
            out["sentiment_catalysts"].append(float(r["sentiment_score"]))
        if r["technical_score"] is not None:
            out["technical"].append(float(r["technical_score"]))

    print(f"[stored] {len(rows)} completed analyses in Neon")
    return out


# ── Fresh distribution (live, deterministic only) ─────────────────────────────

def _score_one(ticker: str) -> Optional[Dict[str, float]]:
    """Compute the three recomputed components for one ticker. No LLM."""
    import yfinance as yf
    from research_swarm.data.market_data_client import market_data_client
    from research_swarm.agents.fundamentalist.models import DCFInputs
    from research_swarm.agents.fundamentalist.graph import _compute_roic_wacc_spread_score
    from research_swarm.agents.fundamentalist.earnings_calculator import earnings_calculator

    result: Dict[str, float] = {}
    try:
        info = yf.Ticker(ticker).info
        if not info or not info.get("currentPrice"):
            return None
        info["symbol"] = ticker

        # valuation — deterministic from yfinance multiples
        vm = market_data_client.get_valuation_metrics(ticker)
        if vm:
            v = market_data_client.calculate_valuation_score(vm)
            if v is not None:
                result["valuation"] = float(v)

        # roic_wacc_spread — NOPAT/invested capital vs WACC
        dcf_inputs = DCFInputs(
            fcf_history=[1.0, 2.0],
            effective_tax_rate=21.0,
            total_debt=(info.get("totalDebt") or 0) / 1e6,
            market_cap_millions=(info.get("marketCap") or 0) / 1e6,
            beta=info.get("beta") or 1.0,
            operating_margin_trend="stable",
        )
        roic = _compute_roic_wacc_spread_score(info, dcf_inputs)
        if roic is not None:
            result["roic_wacc_spread"] = float(roic)

        # earnings_momentum — EPS revisions + surprise history
        earnings_data = {
            "recommendations": market_data_client.get_analyst_recommendations(ticker),
            "eps_revisions": market_data_client.get_eps_revisions(ticker),
            "earnings_history": market_data_client.get_earnings_history(ticker),
            "price_target": market_data_client.get_analyst_price_target(ticker),
        }
        score, _breakdown = earnings_calculator.calculate_momentum_score(earnings_data)
        if score is not None:
            result["earnings_momentum"] = float(score)

    except Exception as e:
        print(f"  {ticker}: {type(e).__name__}: {str(e)[:70]}")
        return None

    return result or None


def _fetch_fresh(tickers: List[str], out_path: Path) -> Dict[str, List[float]]:
    """Score tickers, appending to a JSONL so a rate-limit stall is resumable."""
    done = {}
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            try:
                row = json.loads(line)
                done[row["ticker"]] = row
            except Exception:
                continue
        print(f"[fresh] resuming — {len(done)} tickers already scored")

    with out_path.open("a") as fh:
        for i, t in enumerate(tickers, 1):
            if t in done:
                continue
            scores = _score_one(t)
            if scores:
                done[t] = {"ticker": t, **scores}
                fh.write(json.dumps(done[t]) + "\n")
                fh.flush()
            if i % 20 == 0:
                print(f"[fresh] {i}/{len(tickers)} ({len(done)} scored)")

    out: Dict[str, List[float]] = {c: [] for c in FRESH_COMPONENTS}
    for row in done.values():
        for c in FRESH_COMPONENTS:
            if row.get(c) is not None:
                out[c].append(float(row[c]))
    return out


# ── Reporting ─────────────────────────────────────────────────────────────────

def _summarize(name: str, values: List[float], source: str) -> Optional[dict]:
    vals = sorted(v for v in values if v is not None)
    if len(vals) < 8:
        print(f"  {name:22} n={len(vals):<4} — too few to calibrate")
        return None

    median = statistics.median(vals)
    stdev = statistics.pstdev(vals)
    # IQR/1.349 is a heavy-tail-robust spread estimate; prefer it when the
    # distribution is skewed enough that stdev would overstate the spread.
    q1 = vals[int(len(vals) * 0.25)]
    q3 = vals[int(len(vals) * 0.75)]
    robust = (q3 - q1) / 1.349 if q3 > q1 else stdev
    spread = max(0.3, min(stdev, robust) if robust > 0 else stdev)

    print(
        f"  {name:22} n={len(vals):<4} median={median:5.2f}  stdev={stdev:4.2f}  "
        f"IQR/1.35={robust:4.2f}  p10={vals[int(len(vals)*.10)]:4.1f} "
        f"p90={vals[int(len(vals)*.90)]:4.1f}  [{source}]"
    )
    return {"name": name, "center": round(median, 2), "spread": round(spread, 2), "n": len(vals)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stored", action="store_true", help="stored components only")
    ap.add_argument("--fresh", action="store_true", help="fresh components only")
    ap.add_argument("--limit", type=int, default=0, help="cap fresh tickers")
    ap.add_argument("--out", default="/tmp/calibration_raw.jsonl")
    args = ap.parse_args()

    do_stored = not args.fresh
    do_fresh = not args.stored

    distributions: Dict[str, List[float]] = {}
    sources: Dict[str, str] = {}

    if do_stored:
        stored = asyncio.run(_fetch_stored())
        for k, v in stored.items():
            distributions[k] = v
            sources[k] = "stored"

    if do_fresh:
        universe = json.loads(
            Path("research_swarm/data/universes/sp500_universe.json").read_text()
        )["tickers"]
        if args.limit:
            universe = universe[: args.limit]
        print(f"[fresh] scoring {len(universe)} tickers (deterministic only, no LLM)")
        fresh = _fetch_fresh(universe, Path(args.out))
        for k, v in fresh.items():
            distributions[k] = v
            sources[k] = "fresh"

    print()
    print("=" * 96)
    print("MEASURED COMPONENT DISTRIBUTIONS")
    print("=" * 96)
    calibrations = []
    for name in ("roic_wacc_spread", "financial_health", "earnings_momentum",
                 "valuation", "sentiment_catalysts", "technical"):
        if name in distributions:
            c = _summarize(name, distributions[name], sources.get(name, "?"))
            if c:
                calibrations.append(c)

    if calibrations:
        print()
        print("Paste into research_swarm/agents/manager/score_normalization.py:")
        print()
        print("COMPONENT_CALIBRATION: Dict[str, Tuple[float, float]] = {")
        for c in calibrations:
            print(f'    "{c["name"]}": ({c["center"]}, {c["spread"]}),   # n={c["n"]}')
        print("}")

    # Tier thresholds: where the normalized quality score actually falls.
    quality = [c for c in calibrations if c["name"] in
               ("roic_wacc_spread", "financial_health", "earnings_momentum")]
    if len(quality) == 3:
        print()
        print("With centers at the median, a typical company normalizes to ~5.0 on every")
        print("component, so the composite centers near 5.0 by construction. Tier bounds at")
        print("+/-0.75 sigma (2.0 points per sigma) put roughly a third of the market in each")
        print("band: QUALITY_HIGH = 6.5, QUALITY_LOW = 4.5 — the current values are correct")
        print("ONCE the centers above are applied. Re-check against a scored sample if the")
        print("component correlations are strong.")


if __name__ == "__main__":
    main()
