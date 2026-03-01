"""
Historical Signal Computation Engine
======================================

Wraps the DVRG production signal pipeline (BlendedValuationCalculator +
enrich_with_decision_intelligence) with point-in-time safe data from
PITFundamentals.

No LLM calls.  No random components.  All data comes from the PIT cache.

Signal pipeline (BACKTEST_MODE)
────────────────────────────────
  1. PITFundamentals → synthetic stock_info / valuation_metrics / DCFInputs
     (via scripts.backtest.adapters.pit_inputs_builder)

  2. BlendedValuationCalculator.calculate_fair_value()
     → PriceTargetScenarios  (base / bull / bear + confidence_score)
     Same logic as live DVRG.  Missing inputs (EBITDA, historical sector
     multiples) cause partial degradation; the engine handles None gracefully.

  3. Deterministic moat score (v2.0 formula proxy)
     Component proxies: earnings_momentum, financial_health, valuation_component
     (all from fundamental metrics).  technical_strength and sentiment_catalysts
     default to 5.0 (neutral — no historical data available).

  4. enrich_with_decision_intelligence()
     → conviction_position.recommended_pct
     Identical DI logic to live pipeline, with a minimal synthetic full_output.

Proxy fallback
──────────────
If BlendedValuationCalculator returns None (insufficient data), signal_snapshot
falls back to the original simplified P/E + FCF proxy. The ``data_warnings``
field of SignalRow will contain "proxy_fallback".

LOOK-AHEAD GUARANTEE
─────────────────────
  • fundamentals.get_fundamentals(ticker, as_of) enforces FUND_LAG_DAYS lag.
  • Price used is the closing price on or before as_of (from price cache).
  • No forward estimates used (estimates.py returns None by default).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional, Tuple

from scripts.backtest.config import (
    BETA_WINDOW,
    FUND_LAG_DAYS,
    FUNDAMENTALS_WORKERS,
    RISK_LEVEL_ENCODE,
    _ACCUMULATE_RATINGS,
)
from scripts.backtest.data.fundamentals import PITFundamentals, get_fundamentals
from scripts.backtest.data.prices import PriceData, get_beta_as_of, get_price_as_of

logger = logging.getLogger(__name__)


# ── Universe signals result ────────────────────────────────────────────────────


@dataclass
class UniverseSignalsResult:
    """Aggregated outcome of computing signals for a full universe on one date."""

    all_signals: list             # list[SignalRow] — valid and invalid-scenario signals
    attempted_count: int          # tickers where fund+price existed (compute_signal called)
    no_fund_count: int            # tickers with no PIT fundamentals
    no_price_count: int           # tickers with fund but no price data
    exception_count: int          # unexpected exceptions


# ── Signal output ──────────────────────────────────────────────────────────────


@dataclass
class SignalRow:
    """All T1-relevant fields plus metadata for one ticker on one date."""

    ticker: str
    as_of_date: date

    # ── T1 filter fields ──────────────────────────────────────────────────────
    rating: str             # e.g. "BUY"
    rating_label: str       # "Accumulate" or "Hold" / "Sell"
    expected_value: float   # (ev_price − price) / price
    confidence_score: float # 0–100
    risk_level: int         # 1=Low, 2=Medium, 3=High
    risk_level_str: str
    asymmetry_ratio: float
    downside_severity: float
    recommended_weight: float

    # ── Ancillary ─────────────────────────────────────────────────────────────
    moat_score: float
    current_price: float
    ev_price: float
    base_target: float
    bull_target: float
    bear_target: float
    beta: float

    # ── Metadata ──────────────────────────────────────────────────────────────
    fundamentals_period: date
    data_quality: str
    inputs_used: dict = field(default_factory=dict)
    data_warnings: list[str] = field(default_factory=list)

    # ── Scenario validation (set by validate_scenarios) ───────────────────────
    scenario_valid: bool = True
    invalid_reason: str = ""

    # ── Diagnostic metadata (set from production signal output) ───────────────
    proxy_fallback: bool = False    # production engine fell back to proxy
    missing_ebitda: bool = False    # EV/EBITDA component unavailable
    dcf_value_used: bool = False    # DCF target contributed to blended FV
    pe_value_used: bool = False     # P/E target contributed to blended FV
    ev_value_used: bool = False     # EV/EBITDA target contributed to blended FV


# ── Scenario sanity validator ─────────────────────────────────────────────────


def validate_scenarios(
    signal_output: dict,
    current_price: float,
    min_ratio: float = 0.5,
    max_ratio: float = 2.0,
) -> Tuple[bool, str]:
    """
    Validate that price target scenarios are internally consistent and plausible.

    Returns (is_valid, reason) where reason is blank when valid.

    Marks INVALID if any of:
    - Any target is None or <= 0
    - Sentinel floor detected: any target < 0.02 while current_price > 5
    - Ordering violation: bull_target < base_target or base_target < bear_target
    - base_target / current_price outside [min_ratio, max_ratio]

    Parameters
    ----------
    signal_output  : dict returned by compute_signal_production
    current_price  : closing price at signal date
    min_ratio      : floor for base_target / current_price (default 0.5)
    max_ratio      : ceiling for base_target / current_price (default 2.0)
    """
    base = signal_output.get("base_target")
    bull = signal_output.get("bull_target")
    bear = signal_output.get("bear_target")

    # 1. None or non-positive
    if any(v is None or not isinstance(v, (int, float)) or v <= 0 for v in (base, bull, bear)):
        return False, "target_missing_or_nonpositive"

    base, bull, bear = float(base), float(bull), float(bear)

    # 2. Sentinel floor — near-zero targets while price is meaningful
    if current_price > 5.0 and min(base, bull, bear) < 0.02:
        return False, "sentinel_floor_detected"

    # 3. Ordering violations
    if bull < base:
        return False, "bull_lt_base"
    if base < bear:
        return False, "base_lt_bear"

    # 4. Plausibility ratio check
    if current_price > 0:
        ratio = base / current_price
        if ratio < min_ratio:
            return False, f"base_price_ratio_too_low:{ratio:.3f}"
        if ratio > max_ratio:
            return False, f"base_price_ratio_too_high:{ratio:.3f}"

    return True, ""


# ── Main computation ──────────────────────────────────────────────────────────


def compute_signal(
    ticker: str,
    as_of: date,
    fund: PITFundamentals,
    current_price: float,
    beta: float,
    scenario_sanity_check: bool = True,
    sanity_min_ratio: float = 0.5,
    sanity_max_ratio: float = 2.0,
) -> Optional[SignalRow]:
    """
    Compute a deterministic T1 signal for *ticker* as of *as_of*.

    Delegates to the production adapter (BlendedValuationCalculator +
    enrich_with_decision_intelligence) for valuation and position sizing,
    falling back to the internal proxy if the production engine returns None.

    Parameters
    ----------
    ticker               : ticker symbol
    as_of                : rebalance date
    fund                 : PITFundamentals (already lag-filtered)
    current_price        : closing price on or before as_of
    beta                 : rolling 252-day beta vs SPY
    scenario_sanity_check: run validate_scenarios on output (default True)
    sanity_min_ratio     : base_target/price lower bound (default 0.5)
    sanity_max_ratio     : base_target/price upper bound (default 2.0)

    Returns None if current_price <= 0 or no signal can be produced.
    Sets scenario_valid=False (with invalid_reason) rather than returning None
    when the production engine produces implausible scenario targets.
    """
    from scripts.backtest.adapters.production_signal import compute_signal_production

    result = compute_signal_production(ticker, as_of, fund, current_price, beta)
    if result is None:
        return None

    # ── Extract diagnostic metadata from production result ────────────────────
    warnings = result.get("data_warnings") or []
    proxy_fallback = "proxy_fallback" in warnings
    pe_value_used  = (result.get("pe_target") or 0) > 0
    ev_value_used  = (result.get("ev_ebitda_target") or 0) > 0
    dcf_value_used = (result.get("dcf_target") or 0) > 0
    missing_ebitda = not ev_value_used

    # ── Scenario sanity check ─────────────────────────────────────────────────
    scenario_valid = True
    invalid_reason = ""
    if scenario_sanity_check:
        scenario_valid, invalid_reason = validate_scenarios(
            result, current_price, sanity_min_ratio, sanity_max_ratio,
        )

    return SignalRow(
        ticker=result["ticker"],
        as_of_date=result["as_of_date"],
        rating=result["rating"],
        rating_label=result["rating_label"],
        expected_value=result["expected_value"],
        confidence_score=result["confidence_score"],
        risk_level=result["risk_level"],
        risk_level_str=result["risk_level_str"],
        asymmetry_ratio=result["asymmetry_ratio"],
        downside_severity=result["downside_severity"],
        recommended_weight=result["recommended_weight"],
        moat_score=result["moat_score"],
        current_price=result["current_price"],
        ev_price=result["ev_price"],
        base_target=result["base_target"],
        bull_target=result["bull_target"],
        bear_target=result["bear_target"],
        beta=result["beta"],
        fundamentals_period=result["fundamentals_period"],
        data_quality=result["data_quality"],
        inputs_used=result["inputs_used"],
        data_warnings=result["data_warnings"],
        # Validation and diagnostic fields
        scenario_valid=scenario_valid,
        invalid_reason=invalid_reason,
        proxy_fallback=proxy_fallback,
        missing_ebitda=missing_ebitda,
        dcf_value_used=dcf_value_used,
        pe_value_used=pe_value_used,
        ev_value_used=ev_value_used,
    )


def compute_universe_signals(
    tickers: list[str],
    as_of: date,
    price_data: PriceData,
    cache_dir: Path,
    scenario_sanity_check: bool = True,
    sanity_min_ratio: float = 0.5,
    sanity_max_ratio: float = 2.0,
) -> UniverseSignalsResult:
    """
    Compute signals for all *tickers* as of *as_of*, in parallel.

    Uses ThreadPoolExecutor since each ticker is independent and
    get_fundamentals() reads from local disk cache (I/O-bound).

    Returns a UniverseSignalsResult containing all SignalRow objects (including
    those with scenario_valid=False) plus counts of failure modes per stage.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    fund_cache = cache_dir / "fundamentals"

    # Status strings returned by _compute_one
    _NO_FUND    = "no_fund"
    _NO_PRICE   = "no_price"
    _NO_SIGNAL  = "no_signal"   # compute_signal returned None (insufficient data)
    _EXCEPTION  = "exception"
    _OK         = "ok"

    def _compute_one(ticker: str) -> Tuple[Optional[SignalRow], str]:
        try:
            fund = get_fundamentals(ticker, as_of, cache_dir=fund_cache)
            if fund is None:
                return None, _NO_FUND
            price = get_price_as_of(ticker, as_of, price_data)
            if price is None:
                return None, _NO_PRICE
            beta = get_beta_as_of(ticker, as_of, price_data, BETA_WINDOW)
            sig = compute_signal(
                ticker, as_of, fund, price, beta,
                scenario_sanity_check=scenario_sanity_check,
                sanity_min_ratio=sanity_min_ratio,
                sanity_max_ratio=sanity_max_ratio,
            )
            if sig is None:
                return None, _NO_SIGNAL
            return sig, _OK
        except Exception as exc:
            logger.debug("Signal compute failed for %s on %s: %s", ticker, as_of, exc)
            return None, _EXCEPTION

    all_signals: list = []
    attempted = no_fund = no_price = exceptions = 0

    with ThreadPoolExecutor(max_workers=FUNDAMENTALS_WORKERS) as executor:
        future_map = {executor.submit(_compute_one, t): t for t in tickers}
        for future in as_completed(future_map):
            sig, status = future.result()
            if status == _NO_FUND:
                no_fund += 1
            elif status == _NO_PRICE:
                no_price += 1
                attempted += 1   # had fundamentals; counts as attempted
            elif status == _EXCEPTION:
                exceptions += 1
            else:
                # _OK or _NO_SIGNAL — had fund + price, compute_signal was called
                attempted += 1
                if sig is not None:
                    all_signals.append(sig)

    return UniverseSignalsResult(
        all_signals=all_signals,
        attempted_count=attempted,
        no_fund_count=no_fund,
        no_price_count=no_price,
        exception_count=exceptions,
    )


# ── Moat score computation ────────────────────────────────────────────────────


def _compute_moat_score(fund: PITFundamentals, warnings: list[str]) -> float:
    score = 5.0

    # Profitability — ROE
    if fund.roe is not None:
        if fund.roe > 20:
            score += 1.0
        elif fund.roe > 12:
            score += 0.5
        elif fund.roe < 0:
            score -= 1.0
    else:
        warnings.append("ROE missing")

    # Cash flow quality — FCF margin
    if fund.fcf_margin is not None:
        if fund.fcf_margin > 15:
            score += 1.0
        elif fund.fcf_margin > 8:
            score += 0.5
        elif fund.fcf_margin < 0:
            score -= 1.0
    else:
        warnings.append("FCF margin missing")

    # Revenue growth
    if fund.revenue_growth_yoy is not None:
        if fund.revenue_growth_yoy > 15:
            score += 0.75
        elif fund.revenue_growth_yoy > 7:
            score += 0.35
        elif fund.revenue_growth_yoy < 0:
            score -= 0.5
    else:
        warnings.append("Revenue growth missing")

    # Balance sheet — D/E
    if fund.de_ratio is not None:
        if fund.de_ratio < 0.3:
            score += 0.75
        elif fund.de_ratio < 0.8:
            score += 0.35
        elif fund.de_ratio > 2.0:
            score -= 0.75
    else:
        warnings.append("D/E ratio missing")

    # Net margin
    if fund.net_margin is not None:
        if fund.net_margin > 20:
            score += 0.5
        elif fund.net_margin > 10:
            score += 0.25
        elif fund.net_margin < 0:
            score -= 0.5

    return max(0.0, min(10.0, score))


# ── Price targets ─────────────────────────────────────────────────────────────


def _compute_price_targets(
    fund: PITFundamentals,
    moat_score: float,
    current_price: float,
    warnings: list[str],
) -> Optional[tuple[float, float, float]]:
    """
    Return (base_target, bull_target, bear_target) or None if no method works.

    Methods:
      P/E:   base = EPS_TTM × base_pe   (requires eps_ttm > 0)
      FCF:   base = FCF/share / yield   (requires fcf_per_share > 0)
    Average available methods.
    """
    # base P/E multiple scales with moat (range: 10x at moat=0, 25x at moat=10)
    base_pe = 10.0 + moat_score * 1.5

    # FCF yield scales inversely with moat (high-quality = lower yield demanded)
    # range: 6.0% at moat=0, 2.0% at moat=10
    base_fcf_yield = 0.06 - moat_score * 0.004

    candidates: list[float] = []

    if fund.eps_ttm is not None and fund.eps_ttm > 0:
        candidates.append(fund.eps_ttm * base_pe)
    else:
        if fund.eps_ttm is not None:
            warnings.append("EPS_TTM negative — P/E method skipped")
        else:
            warnings.append("EPS_TTM missing — P/E method skipped")

    if fund.fcf_per_share is not None and fund.fcf_per_share > 0 and base_fcf_yield > 0:
        candidates.append(fund.fcf_per_share / base_fcf_yield)
    else:
        if fund.fcf_per_share is not None:
            warnings.append("FCF/share non-positive — FCF method skipped")
        else:
            warnings.append("FCF/share missing — FCF method skipped")

    if not candidates:
        return None

    base_target = sum(candidates) / len(candidates)

    # Sanity guard: don't produce wildly implausible targets
    # Cap at 5× current price and floor at 0.2× current price
    base_target = max(current_price * 0.2, min(current_price * 5.0, base_target))

    bull_target = base_target * 1.30
    bear_target = base_target * 0.80

    return base_target, bull_target, bear_target


# ── Confidence score ──────────────────────────────────────────────────────────


def _compute_confidence(fund: PITFundamentals, warnings: list[str]) -> float:
    score = 60.0

    # Data completeness
    if fund.quarters_available >= 12:
        score += 8
    elif fund.quarters_available >= 8:
        score += 4

    # Earnings sign
    if fund.eps_ttm is not None:
        if fund.eps_ttm > 0:
            score += 5
        else:
            score -= 15
            warnings.append("Negative EPS hurts confidence")

    # FCF quality
    if fund.fcf_margin is not None:
        if fund.fcf_margin > 0:
            score += 5
        else:
            score -= 5

    # Revenue growth
    if fund.revenue_growth_yoy is not None:
        if fund.revenue_growth_yoy > 5:
            score += 5
        elif fund.revenue_growth_yoy < 0:
            score -= 8

    # Leverage
    if fund.de_ratio is not None:
        if fund.de_ratio > 2.0:
            score -= 10
        elif fund.de_ratio < 0.5:
            score += 5

    # EPS volatility
    if len(fund.eps_series) >= 4:
        eps_pos = [abs(e) for e in fund.eps_series if e != 0]
        if len(eps_pos) >= 4:
            mean_eps = sum(eps_pos) / len(eps_pos)
            variance = sum((e - mean_eps) ** 2 for e in eps_pos) / len(eps_pos)
            std_eps = math.sqrt(variance)
            if mean_eps > 0 and (std_eps / mean_eps) > 0.5:
                score -= 10
                warnings.append("High EPS volatility reduces confidence")

    return max(20.0, min(90.0, score))


# ── Risk level ────────────────────────────────────────────────────────────────


def _compute_risk_level(
    moat_score: float,
    fund: PITFundamentals,
    beta: float,
) -> tuple[int, str]:
    risk = 2  # default: Medium

    # Downgrade to Low: all three conditions must hold
    low_conditions = [
        moat_score >= 7.0,
        fund.de_ratio is None or fund.de_ratio < 0.5,
        beta < 1.3,
    ]
    if all(low_conditions):
        risk = 1

    # Upgrade to High: any one condition triggers
    high_conditions = [
        moat_score < 4.0,
        fund.de_ratio is not None and fund.de_ratio > 2.5,
        beta > 1.8,
    ]
    if any(high_conditions):
        risk = 3

    inv_map = {1: "Low", 2: "Medium", 3: "High"}
    return risk, inv_map[risk]


# ── Recommended weight ────────────────────────────────────────────────────────


def _recommended_weight(moat_score: float) -> float:
    if moat_score >= 8.5:
        return 0.055
    if moat_score >= 7.5:
        return 0.045
    if moat_score >= 7.0:
        return 0.035
    if moat_score >= 6.0:
        return 0.025
    return 0.0


# ── Legacy DB-based extraction (preserved for compatibility) ──────────────────
# The original extract_t1_fields() from the old signal_snapshot.py is kept
# below so any existing test imports don't break.  It is NOT called by the
# historical backtest engine.

from scripts.backtest.config import _ACCUMULATE_RATINGS as _ACCUM_LEGACY  # noqa: E402


def extract_t1_fields(
    full_output: dict,
    moat_score: float,
    analysis_date: date,
    result_id: str,
) -> "Optional[dict]":
    """
    LEGACY — extracts T1 fields from a stored DB fullOutput blob.
    Used only when replaying existing StockResult records.
    Not called during historical backtest.
    """
    # Re-import from the original logic inline to avoid circular imports
    from scripts.backtest.config import RISK_LEVEL_ENCODE as _RLE

    if not full_output:
        return None
    ticker = full_output.get("ticker", "")
    if not ticker:
        return None

    # Locate price targets
    pt = full_output.get("price_targets") or {}
    if not pt:
        pt = (full_output.get("fundamentalist_output") or {}).get("price_targets") or {}
    if not pt:
        return None

    # Current price
    current_price: float = 0.0
    for src in [
        (full_output.get("decision_intelligence") or {}).get("current_price"),
        ((full_output.get("fundamentalist_output") or {}).get("valuation_metrics") or {}).get("current_price"),
        pt.get("current_price"),
    ]:
        if src and isinstance(src, (int, float)) and src > 0:
            current_price = float(src)
            break
    if current_price <= 0:
        return None

    base_target = float(pt.get("base_target") or pt.get("fair_value_mid") or 0)
    bull_target = float(pt.get("bull_target") or pt.get("fair_value_high") or 0)
    bear_target = float(pt.get("bear_target") or pt.get("fair_value_low") or 0)
    if not (base_target > 0 and bull_target > 0 and bear_target > 0):
        return None

    ev_raw = pt.get("expected_value")
    if ev_raw and float(ev_raw) > 0:
        ev_price = float(ev_raw)
    else:
        bp = float(pt.get("base_probability", 0.5))
        ulp = float(pt.get("bull_probability", 0.25))
        brp = float(pt.get("bear_probability", 0.25))
        ev_price = base_target * bp + bull_target * ulp + bear_target * brp
    expected_value = (ev_price - current_price) / current_price

    confidence_score = float(pt.get("confidence_score") or pt.get("valuation_confidence_score") or 0)
    rating = (full_output.get("rating") or full_output.get("recommendation") or "").upper().strip()
    rating_label = "Accumulate" if rating in _ACCUM_LEGACY else rating
    risk_level_str = (full_output.get("risk_level") or "Medium").strip()
    risk_level_int = _RLE.get(risk_level_str, 2)

    upside = max(bull_target - current_price, 0.0)
    downside = max(current_price - bear_target, 0.01)
    asymmetry_ratio = upside / downside
    downside_severity = (current_price - bear_target) / current_price

    di = full_output.get("decision_intelligence") or {}
    cp = di.get("conviction_position") or {}
    rec_pct = cp.get("recommended_pct")
    if rec_pct is not None:
        recommended_weight = float(rec_pct) / 100.0
    elif moat_score >= 8.0:
        recommended_weight = 0.06
    elif moat_score >= 7.0:
        recommended_weight = 0.045
    elif moat_score >= 6.0:
        recommended_weight = 0.025
    else:
        recommended_weight = 0.0

    return {
        "result_id": result_id,
        "ticker": ticker,
        "analysis_date": analysis_date,
        "rating": rating,
        "rating_label": rating_label,
        "expected_value": round(expected_value, 6),
        "confidence_score": confidence_score,
        "risk_level": risk_level_int,
        "risk_level_str": risk_level_str,
        "asymmetry_ratio": round(asymmetry_ratio, 4),
        "downside_severity": round(downside_severity, 4),
        "recommended_weight": round(recommended_weight, 6),
        "moat_score": moat_score,
        "conviction_level": cp.get("conviction_level", "Medium") if cp else "Medium",
        "current_price": current_price,
        "ev_price": ev_price,
        "base_target": base_target,
        "bull_target": bull_target,
        "bear_target": bear_target,
    }
