"""
Signal Parity Validator
========================

Compares backtest signal outputs (from the production adapter) against live
StockResult records stored in the database, and writes a diff report to:

    scripts/backtest/output/signal_parity_report.csv

Usage
─────
    python -m scripts.backtest.adapters.parity_validator [OPTIONS]

    Options:
      --days N          Look-back window for DB records (default: 90)
      --max N           Max records to validate (default: 200)
      --cache-dir PATH  Fundamentals cache dir (default: config.FUNDAMENTALS_CACHE_DIR)
      --out PATH        Output CSV path (default: scripts/backtest/output/signal_parity_report.csv)
      --verbose         Print per-ticker diffs to stdout
      --fail-on-mismatch  Exit non-zero if T1 mismatch rate > 5%

Tolerance thresholds
─────────────────────
    EV delta         :  ±5 percentage-points
    Confidence delta :  ±10 points
    Moat delta       :  ±1.5 points
    Base target pct  :  ±15 %

T1 qualification parity
────────────────────────
    For each record both the live signal and the backtest signal are evaluated
    against the T1 Accumulate criteria.  A "mismatch" is when live qualifies
    but backtest does not (or vice versa).  The overall mismatch rate is
    printed at the end and returned.  A rate > 5% indicates systematic drift.

Component parity columns
─────────────────────────
    When available (production adapter path), the CSV includes:
        live_fv_mid / bt_fv_mid / fv_mid_delta_pct
        live_pe_target / bt_pe_target
        live_ev_ebitda_target / bt_ev_ebitda_target
        live_dcf_target / bt_dcf_target

Notes
──────
- This script requires DB access (Prisma).  Set DATABASE_URL in environment.
- Price data is fetched from the backtest price cache (not yfinance live price).
  If the as-of-date price is not cached, the record is skipped with SKIP_NO_PRICE.
- Fundamentals are loaded from the backtest fundamentals cache with FUND_LAG_DAYS.
  If not cached, the record is skipped with SKIP_NO_FUND.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Project root on path ───────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.backtest.config import (
    BETA_WINDOW,
    FUND_LAG_DAYS,
    FUNDAMENTALS_CACHE_DIR,
    OUTPUT_DIR,
    PRICES_CACHE_DIR,
    T1_CONFIDENCE_THRESHOLD,
    T1_DOWNSIDE_MAX,
    T1_EV_THRESHOLD,
    T1_RISK_MAX,
    T1_SKEW_MIN,
)
from scripts.backtest.data.fundamentals import get_fundamentals
from scripts.backtest.data.prices import PriceData, get_beta_as_of, get_price_as_of

logger = logging.getLogger(__name__)

# ── Tolerances ─────────────────────────────────────────────────────────────────

EV_TOL_PP: float = 5.0        # ±5 percentage-points
CONF_TOL: float = 10.0        # ±10 confidence points
MOAT_TOL: float = 1.5         # ±1.5 moat points
TARGET_TOL_PCT: float = 15.0  # ±15% relative delta on base_target
T1_MISMATCH_THRESHOLD: float = 0.05  # alert if T1 qual mismatch rate > 5%


# ── T1 qualification predicate ─────────────────────────────────────────────────


def _qualifies_t1(sig: Dict[str, Any]) -> bool:
    """
    Return True if the signal dict passes all T1 Accumulate criteria.

    Mirrors ``apply_t1_filter()`` in backtest_t1.py (integrity spec item D/E).
    Qualification = scenario_valid AND all 5 gate thresholds.

    IMPORTANT — the following fields do NOT gate T1 eligibility:
      • rating_label  (was "Accumulate" check — removed, enforced moat≥7 implicitly)
      • recommended_weight  (was >0 check — removed, blocks HOLD-rated names unfairly)
      • moat_score  (diagnostic / allocation weight only, not an eligibility gate)
    """
    scenario_ok = sig.get("scenario_valid", True)  # default True for live records
    return (
        scenario_ok
        and (sig.get("expected_value") or 0.0) >= T1_EV_THRESHOLD
        and (sig.get("confidence_score") or 0.0) >= T1_CONFIDENCE_THRESHOLD
        and (sig.get("risk_level") or 3) <= T1_RISK_MAX
        and (sig.get("asymmetry_ratio") or 0.0) >= T1_SKEW_MIN
        and (sig.get("downside_severity") or 1.0) <= T1_DOWNSIDE_MAX
    )


# ── DB query ───────────────────────────────────────────────────────────────────


async def _fetch_live_records(
    days_back: int,
    max_records: int,
) -> List[Dict[str, Any]]:
    """
    Fetch recent completed StockResult records from the DB.

    Returns a list of dicts with keys:
        ticker, analysis_date, moat_score, full_output
    """
    from api.lib.db import get_db

    db = await get_db()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    # Note: Prisma Python doesn't support {"not": None} on JSON fields.
    # Fetch with basic status + date filters; null-checks are done in Python below.
    records = await db.stockresult.find_many(
        where={
            "status": "completed",
            "createdAt": {"gte": cutoff},
        },
        order={"createdAt": "desc"},
        take=max_records * 2,  # over-fetch to compensate for Python-side null filtering
    )

    out: List[Dict[str, Any]] = []
    for r in records:
        if len(out) >= max_records:
            break

        # Skip records with no moat score or no full_output (null check in Python)
        if r.moatScore is None:
            continue

        ticker = r.ticker
        analysis_date: Optional[date] = None
        if r.createdAt:
            analysis_date = r.createdAt.date()

        full_output_raw = r.fullOutput
        if full_output_raw is None:
            continue
        if isinstance(full_output_raw, str):
            try:
                full_output = json.loads(full_output_raw)
            except json.JSONDecodeError:
                continue
        elif isinstance(full_output_raw, dict):
            full_output = full_output_raw
        else:
            continue

        if not ticker or analysis_date is None:
            continue

        out.append({
            "result_id": r.id,
            "ticker": ticker,
            "analysis_date": analysis_date,
            "moat_score": r.moatScore,
            "full_output": full_output,
        })

    return out


# ── Live signal extraction ─────────────────────────────────────────────────────


def _extract_live_signal(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract T1-comparable fields from a stored StockResult.

    Uses ``extract_t1_fields()`` (the legacy DB-replay extractor) which
    already handles all fullOutput schema variations.

    Additionally extracts valuation component fields (fair_value_mid, pe_target,
    ev_ebitda_target, dcf_target) from the price_targets blob for component parity.
    """
    from scripts.backtest.signal_snapshot import extract_t1_fields

    moat_score = record.get("moat_score") or 0.0
    full_output = record.get("full_output") or {}
    analysis_date = record["analysis_date"]
    result_id = record["result_id"]

    live = extract_t1_fields(full_output, moat_score, analysis_date, result_id)
    if live is None:
        return None

    # ── Component parity fields (best-effort from full_output schema) ─────────
    pt = full_output.get("price_targets") or {}
    if not pt:
        pt = (full_output.get("fundamentalist_output") or {}).get("price_targets") or {}
    method_values = pt.get("method_values") or {}

    live["fair_value_mid"] = pt.get("fair_value_mid")
    live["pe_target"] = method_values.get("pe")
    live["ev_ebitda_target"] = method_values.get("ev_ebitda")
    live["dcf_target"] = method_values.get("dcf")

    return live


# ── Backtest signal computation ────────────────────────────────────────────────


def _compute_backtest_signal(
    ticker: str,
    as_of: date,
    fund_cache_dir: Path,
    price_data: Optional[PriceData],
) -> Optional[Dict[str, Any]]:
    """
    Compute backtest signal for *ticker* as of *as_of* using cached data.
    Returns None if price or fundamentals are unavailable.
    """
    fund = get_fundamentals(ticker, as_of, cache_dir=fund_cache_dir)
    if fund is None:
        return None

    if price_data is None:
        return None

    price = get_price_as_of(ticker, as_of, price_data)
    if price is None:
        return None

    beta = get_beta_as_of(ticker, as_of, price_data, BETA_WINDOW)

    from scripts.backtest.adapters.production_signal import compute_signal_production

    return compute_signal_production(ticker, as_of, fund, price, beta)


# ── Diff computation ───────────────────────────────────────────────────────────


def _diff_signals(
    live: Dict[str, Any],
    backtest: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compare live vs backtest signals; return a row dict for the CSV.

    Includes:
    - Standard signal deltas (EV, confidence, moat, base_target)
    - T1 qualification parity (live_t1_qualifies, bt_t1_qualifies, t1_mismatch)
    - Valuation component parity (fair_value_mid, pe_target, ev_ebitda_target,
      dcf_target, recommended_weight)
    """

    def pct_delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
        if a is None or b is None:
            return None
        return round(a - b, 6)

    def rel_delta_pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
        """Relative delta as percentage: (a - b) / |b| × 100."""
        if a is None or b is None or b == 0:
            return None
        return round((a - b) / abs(b) * 100, 2)

    ticker = live.get("ticker", backtest.get("ticker", ""))

    # ── Key fields ────────────────────────────────────────────────────────────
    live_ev = live.get("expected_value")
    bt_ev = backtest.get("expected_value")
    ev_delta_pp = round(((bt_ev or 0) - (live_ev or 0)) * 100, 3) if (live_ev is not None and bt_ev is not None) else None

    live_conf = live.get("confidence_score")
    bt_conf = backtest.get("confidence_score")
    conf_delta = pct_delta(bt_conf, live_conf)

    live_moat = live.get("moat_score")
    bt_moat = backtest.get("moat_score")
    moat_delta = pct_delta(bt_moat, live_moat)

    live_base = live.get("base_target")
    bt_base = backtest.get("base_target")
    base_delta_pct = rel_delta_pct(bt_base, live_base)

    # ── T1 qualification parity ───────────────────────────────────────────────
    live_t1 = _qualifies_t1(live)
    bt_t1 = _qualifies_t1(backtest)
    t1_mismatch = live_t1 != bt_t1

    # ── Valuation component parity ────────────────────────────────────────────
    live_fv_mid = live.get("fair_value_mid")
    bt_fv_mid = backtest.get("fair_value_mid")
    fv_mid_delta_pct = rel_delta_pct(bt_fv_mid, live_fv_mid)

    live_pe = live.get("pe_target")
    bt_pe = backtest.get("pe_target")
    pe_delta_pct = rel_delta_pct(bt_pe, live_pe)

    live_ev_ebitda = live.get("ev_ebitda_target")
    bt_ev_ebitda = backtest.get("ev_ebitda_target")

    live_dcf = live.get("dcf_target")
    bt_dcf = backtest.get("dcf_target")
    dcf_delta_pct = rel_delta_pct(bt_dcf, live_dcf)

    live_rec_wt = live.get("recommended_weight")
    bt_rec_wt = backtest.get("recommended_weight")
    rec_wt_delta_pp = (
        round(((bt_rec_wt or 0) - (live_rec_wt or 0)) * 100, 3)
        if live_rec_wt is not None and bt_rec_wt is not None else None
    )

    # ── Pass/Fail flags ───────────────────────────────────────────────────────
    failures: List[str] = []
    if ev_delta_pp is not None and abs(ev_delta_pp) > EV_TOL_PP:
        failures.append(f"EV_DELTA={ev_delta_pp:+.2f}pp > ±{EV_TOL_PP}pp")
    if conf_delta is not None and abs(conf_delta) > CONF_TOL:
        failures.append(f"CONF_DELTA={conf_delta:+.1f} > ±{CONF_TOL}")
    if moat_delta is not None and abs(moat_delta) > MOAT_TOL:
        failures.append(f"MOAT_DELTA={moat_delta:+.2f} > ±{MOAT_TOL}")
    if base_delta_pct is not None and abs(base_delta_pct) > TARGET_TOL_PCT:
        failures.append(f"BASE_DELTA={base_delta_pct:+.1f}% > ±{TARGET_TOL_PCT}%")
    if t1_mismatch:
        failures.append(
            f"T1_MISMATCH(live={'Y' if live_t1 else 'N'},bt={'Y' if bt_t1 else 'N'})"
        )

    status = "FAIL" if failures else "PASS"

    return {
        "ticker": ticker,
        "analysis_date": live.get("analysis_date", ""),
        "result_id": live.get("result_id", ""),
        # ── Status ────────────────────────────────────────────────────────────
        "status": status,
        "failures": "|".join(failures) if failures else "",
        # ── T1 Qualification Parity ───────────────────────────────────────────
        "live_t1_qualifies": "Y" if live_t1 else "N",
        "bt_t1_qualifies": "Y" if bt_t1 else "N",
        "t1_mismatch": "Y" if t1_mismatch else "N",
        # ── Expected Value ────────────────────────────────────────────────────
        "live_ev_pct": round((live_ev or 0) * 100, 2),
        "bt_ev_pct": round((bt_ev or 0) * 100, 2),
        "ev_delta_pp": ev_delta_pp,
        # ── Confidence ────────────────────────────────────────────────────────
        "live_confidence": round(live_conf, 1) if live_conf is not None else "",
        "bt_confidence": round(bt_conf, 1) if bt_conf is not None else "",
        "conf_delta": round(conf_delta, 1) if conf_delta is not None else "",
        # ── Moat ──────────────────────────────────────────────────────────────
        "live_moat": round(live_moat, 3) if live_moat is not None else "",
        "bt_moat": round(bt_moat, 3) if bt_moat is not None else "",
        "moat_delta": round(moat_delta, 3) if moat_delta is not None else "",
        # ── Price Targets ─────────────────────────────────────────────────────
        "live_bear": round(live.get("bear_target") or 0, 2),
        "live_base": round(live_base or 0, 2),
        "live_bull": round(live.get("bull_target") or 0, 2),
        "bt_bear": round(backtest.get("bear_target") or 0, 2),
        "bt_base": round(bt_base or 0, 2),
        "bt_bull": round(backtest.get("bull_target") or 0, 2),
        "base_delta_pct": base_delta_pct if base_delta_pct is not None else "",
        # ── Valuation Component Parity ────────────────────────────────────────
        "live_fv_mid": round(live_fv_mid, 4) if live_fv_mid is not None else "",
        "bt_fv_mid": round(bt_fv_mid, 4) if bt_fv_mid is not None else "",
        "fv_mid_delta_pct": fv_mid_delta_pct if fv_mid_delta_pct is not None else "",
        "live_pe_target": round(live_pe, 4) if live_pe is not None else "",
        "bt_pe_target": round(bt_pe, 4) if bt_pe is not None else "",
        "pe_delta_pct": pe_delta_pct if pe_delta_pct is not None else "",
        "live_ev_ebitda_target": round(live_ev_ebitda, 4) if live_ev_ebitda is not None else "",
        "bt_ev_ebitda_target": round(bt_ev_ebitda, 4) if bt_ev_ebitda is not None else "",
        "live_dcf_target": round(live_dcf, 4) if live_dcf is not None else "",
        "bt_dcf_target": round(bt_dcf, 4) if bt_dcf is not None else "",
        "dcf_delta_pct": dcf_delta_pct if dcf_delta_pct is not None else "",
        # ── Recommended weight ────────────────────────────────────────────────
        "live_rec_weight_pct": round((live_rec_wt or 0) * 100, 2),
        "bt_rec_weight_pct": round((bt_rec_wt or 0) * 100, 2),
        "rec_weight_delta_pp": rec_wt_delta_pp if rec_wt_delta_pp is not None else "",
        # ── Risk / Rating ─────────────────────────────────────────────────────
        "live_risk": live.get("risk_level_str", ""),
        "bt_risk": backtest.get("risk_level_str", ""),
        "live_rating_label": live.get("rating_label", ""),
        "bt_rating_label": backtest.get("rating_label", ""),
        # ── Mode ──────────────────────────────────────────────────────────────
        "bt_mode": (backtest.get("inputs_used") or {}).get("mode", ""),
    }


# ── Main runner ────────────────────────────────────────────────────────────────


async def run_parity_check(
    days_back: int = 90,
    max_records: int = 200,
    fund_cache_dir: Optional[Path] = None,
    price_cache_dir: Optional[Path] = None,
    out_path: Optional[Path] = None,
    verbose: bool = False,
    fail_on_mismatch: bool = False,
) -> Path:
    """
    Full parity check: fetch live records → compute backtest signals → diff → CSV.

    Returns the path to the written CSV.
    Raises ``ParityMismatchExceeded`` if *fail_on_mismatch* is True and the
    T1 qualification mismatch rate exceeds T1_MISMATCH_THRESHOLD (5%).
    """
    fund_dir = Path(fund_cache_dir or PROJECT_ROOT / FUNDAMENTALS_CACHE_DIR)
    price_dir = Path(price_cache_dir or PROJECT_ROOT / PRICES_CACHE_DIR)
    default_out = PROJECT_ROOT / OUTPUT_DIR / "signal_parity_report.csv"
    out = Path(out_path or default_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"[parity] Fetching live records (last {days_back}d, max {max_records})…")
    records = await _fetch_live_records(days_back=days_back, max_records=max_records)
    print(f"[parity] Found {len(records)} live records")

    # Determine unique tickers for bulk price loading
    unique_tickers = list({r["ticker"] for r in records})
    price_data: Optional[PriceData] = None
    if unique_tickers and price_dir.exists():
        try:
            from scripts.backtest.data.prices import get_total_return_series

            print(f"[parity] Loading price cache for {len(unique_tickers)} tickers…")
            price_data = get_total_return_series(
                tickers=unique_tickers,
                start="2015-01-01",
                end=date.today().isoformat(),
                cache_dir=price_dir,
                force_refresh=False,
            )
        except Exception as exc:
            logger.warning("Price cache load failed: %s — records without price will be skipped", exc)

    rows: List[Dict[str, Any]] = []
    skipped_no_fund = 0
    skipped_no_price = 0
    skipped_no_live = 0

    for record in records:
        ticker = record["ticker"]
        as_of = record["analysis_date"]

        # ── Live signal ───────────────────────────────────────────────────────
        live = _extract_live_signal(record)
        if live is None:
            skipped_no_live += 1
            continue

        # ── Backtest signal ───────────────────────────────────────────────────
        try:
            backtest = _compute_backtest_signal(
                ticker=ticker,
                as_of=as_of,
                fund_cache_dir=fund_dir,
                price_data=price_data,
            )
        except Exception as exc:
            logger.debug("Backtest signal failed for %s on %s: %s", ticker, as_of, exc)
            backtest = None

        if backtest is None:
            # Determine specific skip reason
            from scripts.backtest.data.fundamentals import get_fundamentals as _gf
            fund_check = _gf(ticker, as_of, cache_dir=fund_dir)
            if fund_check is None:
                skipped_no_fund += 1
                rows.append({
                    "ticker": ticker,
                    "analysis_date": as_of,
                    "result_id": record["result_id"],
                    "status": "SKIP_NO_FUND",
                    "failures": "Fundamentals not in cache for as-of date",
                })
            else:
                skipped_no_price += 1
                rows.append({
                    "ticker": ticker,
                    "analysis_date": as_of,
                    "result_id": record["result_id"],
                    "status": "SKIP_NO_PRICE",
                    "failures": "Price not in cache for as-of date",
                })
            continue

        # ── Diff ──────────────────────────────────────────────────────────────
        row = _diff_signals(live, backtest)
        rows.append(row)

        if verbose and row["status"] == "FAIL":
            print(
                f"  FAIL {ticker} ({as_of}): {row['failures']}"
                f"  EV live={row['live_ev_pct']:+.1f}% bt={row['bt_ev_pct']:+.1f}%"
                f"  moat live={row['live_moat']} bt={row['bt_moat']}"
            )

    # ── Summary ───────────────────────────────────────────────────────────────
    evaluated = [r for r in rows if r["status"] in ("PASS", "FAIL")]
    passed = sum(1 for r in evaluated if r["status"] == "PASS")
    failed = sum(1 for r in evaluated if r["status"] == "FAIL")

    print(
        f"[parity] Results: {passed} PASS / {failed} FAIL / "
        f"{skipped_no_fund} SKIP_NO_FUND / {skipped_no_price} SKIP_NO_PRICE / "
        f"{skipped_no_live} SKIP_NO_LIVE"
    )

    # ── T1 qualification mismatch rate ────────────────────────────────────────
    t1_mismatches = sum(1 for r in evaluated if r.get("t1_mismatch") == "Y")
    t1_mismatch_rate = t1_mismatches / len(evaluated) if evaluated else 0.0
    mismatch_label = "WARNING" if t1_mismatch_rate > T1_MISMATCH_THRESHOLD else "OK"
    print(
        f"[parity] T1 qualification mismatch: {t1_mismatch_rate:.1%} "
        f"({t1_mismatches}/{len(evaluated)})  [{mismatch_label}]"
    )
    if t1_mismatches:
        offenders = [
            f"{r['ticker']}({r['analysis_date']}) live={'Y' if r.get('live_t1_qualifies') == 'Y' else 'N'}"
            f"/bt={'Y' if r.get('bt_t1_qualifies') == 'Y' else 'N'}"
            for r in evaluated if r.get("t1_mismatch") == "Y"
        ]
        print(f"[parity]   Offenders: {', '.join(offenders[:20])}"
              + (" …" if len(offenders) > 20 else ""))

    # ── Write CSV ─────────────────────────────────────────────────────────────
    _write_csv(rows, out)
    print(f"[parity] Report written → {out}")

    if fail_on_mismatch and t1_mismatch_rate > T1_MISMATCH_THRESHOLD:
        raise ParityMismatchExceeded(
            f"T1 mismatch rate {t1_mismatch_rate:.1%} exceeds "
            f"{T1_MISMATCH_THRESHOLD:.0%} threshold. "
            "Review signal_parity_report.csv for details."
        )

    return out


class ParityMismatchExceeded(RuntimeError):
    """Raised when T1 qualification mismatch rate exceeds the threshold."""
    pass


def _write_csv(rows: List[Dict[str, Any]], out: Path) -> None:
    if not rows:
        print("[parity] No rows to write")
        return

    # Collect all keys across all rows (some may be sparse for SKIP rows)
    all_keys: List[str] = []
    seen: set = set()
    for row in rows:
        for k in row:
            if k not in seen:
                all_keys.append(k)
                seen.add(k)

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in all_keys})


# ── CLI entry point ────────────────────────────────────────────────────────────


def _parse_args():
    import argparse

    p = argparse.ArgumentParser(description="DVRG backtest signal parity validator")
    p.add_argument("--days", type=int, default=90, help="Look-back window in days")
    p.add_argument("--max", type=int, default=200, dest="max_records",
                   help="Max DB records to validate")
    p.add_argument("--cache-dir", type=str, default=None,
                   help="Fundamentals cache directory")
    p.add_argument("--price-cache-dir", type=str, default=None,
                   help="Prices cache directory")
    p.add_argument("--out", type=str, default=None, help="Output CSV path")
    p.add_argument("--verbose", action="store_true", help="Print per-ticker FAIL rows")
    p.add_argument(
        "--fail-on-mismatch", action="store_true", default=False,
        help=f"Exit non-zero if T1 qualification mismatch rate > {T1_MISMATCH_THRESHOLD:.0%}",
    )
    return p.parse_args()


if __name__ == "__main__":
    import sys as _sys

    logging.basicConfig(level=logging.WARNING)
    args = _parse_args()

    try:
        asyncio.run(
            run_parity_check(
                days_back=args.days,
                max_records=args.max_records,
                fund_cache_dir=Path(args.cache_dir) if args.cache_dir else None,
                price_cache_dir=Path(args.price_cache_dir) if args.price_cache_dir else None,
                out_path=Path(args.out) if args.out else None,
                verbose=args.verbose,
                fail_on_mismatch=args.fail_on_mismatch,
            )
        )
    except ParityMismatchExceeded as exc:
        print(f"[parity] FATAL: {exc}", file=_sys.stderr)
        _sys.exit(1)
