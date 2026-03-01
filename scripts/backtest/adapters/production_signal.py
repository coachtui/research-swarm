"""
Production Signal Adapter
==========================

Replaces the backtest-only simplified signal proxy with a wrapper that
calls the DVRG production deterministic pipeline:

  1. ``BlendedValuationCalculator.calculate_fair_value()``
       → PriceTargetScenarios (base / bull / bear + confidence score)
  2. ``MoatScoreBreakdown`` component proxies (deterministic from fundamentals)
       → moat_score via the v2.0 weighted formula
  3. ``enrich_with_decision_intelligence()``
       → conviction_position.recommended_pct (position sizing)

BACKTEST_MODE guarantees
─────────────────────────
• No LLM calls.
• No network calls (all data comes from PITFundamentals which was already
  fetched from yfinance and cached with FUND_LAG_DAYS enforcement).
• Identical output for identical inputs (deterministic).
• The ``_currency_normalized`` sentinel bypasses the USD guard in
  blended_valuation so no FX fetch is triggered.

Signal parity vs live StockResult
───────────────────────────────────
• Price targets: same BlendedValuationCalculator (identical logic).
• Moat score: deterministic proxy (ROE / FCF / growth / D/E / net margin)
  instead of LLM-assigned component scores.  Expect ±1–2 point deltas.
• Recommended weight: DI enrichment uses the same strategy_calculator and
  decision_intelligence_calculator, but with no quant/news signals (both
  default to neutral 5.0).  Expect ±0.5% delta.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional, Tuple

from scripts.backtest.config import (
    RISK_LEVEL_ENCODE,
    _ACCUMULATE_RATINGS,
)
from scripts.backtest.data.fundamentals import PITFundamentals

logger = logging.getLogger(__name__)


# ── Public entry point ─────────────────────────────────────────────────────────


def compute_signal_production(
    ticker: str,
    as_of: date,
    fund: PITFundamentals,
    current_price: float,
    beta: float,
) -> Optional[dict]:
    """
    Compute T1 signal fields using the DVRG production valuation engine.

    Returns a dict compatible with the ``SignalRow`` dataclass fields, or
    None if the production engine cannot produce a valid signal.

    Parameters
    ----------
    ticker        : ticker symbol
    as_of         : rebalance date (for metadata only — PIT already enforced)
    fund          : PITFundamentals (already lag-filtered)
    current_price : closing price on or before as_of
    beta          : rolling 252-day beta vs SPY

    Returns None if:
    - current_price <= 0
    - data_quality == "insufficient"
    - BlendedValuationCalculator returns None AND proxy also fails
    """
    if current_price <= 0:
        return None
    if fund.data_quality == "insufficient":
        return None

    warnings: list[str] = []

    # ── Step 1: Build production pipeline inputs ──────────────────────────────
    from scripts.backtest.adapters.pit_inputs_builder import (
        build_dcf_inputs,
        build_historical_eps,
        build_stock_info,
        build_valuation_metrics,
        compute_quarterly_margin_std,
    )

    stock_info = build_stock_info(fund, current_price, beta)
    valuation_metrics = build_valuation_metrics(fund, current_price)
    dcf_inputs = build_dcf_inputs(fund)
    historical_eps = build_historical_eps(fund)
    quarterly_margin_std = compute_quarterly_margin_std(fund)

    # ── Step 2: Call production BlendedValuationCalculator ────────────────────
    from research_swarm.agents.fundamentalist.blended_valuation import (
        BlendedValuationCalculator,
    )

    calc = BlendedValuationCalculator()
    try:
        pts = calc.calculate_fair_value(
            ticker=ticker,
            current_price=current_price,
            valuation_metrics=valuation_metrics,
            dcf_inputs=dcf_inputs,
            stock_info=stock_info,
            historical_eps=historical_eps,
            sbc_ratio=None,              # not tracked in PITFundamentals
            quarterly_margin_std=quarterly_margin_std,
            ten_year_yield=None,         # historical PIT yield not available
            effective_probabilities=None,  # no LLM scenario weighting
        )
    except Exception as exc:
        logger.debug(
            "BlendedValuationCalculator failed for %s on %s: %s — falling back to proxy",
            ticker, as_of, exc,
        )
        pts = None

    if pts is None:
        warnings.append("Production valuation returned None — using proxy targets")
        _record_fallback(ticker, as_of, used_fallback=True)
        return _proxy_signal_dict(ticker, as_of, fund, current_price, beta, warnings)

    # ── Step 3: Extract price target fields from PriceTargetScenarios ─────────
    base_target = pts.base_target
    bull_target = pts.bull_target
    bear_target = pts.bear_target

    # Sanity: bull > base > bear (production engine enforces this, but guard anyway)
    if not (bear_target < base_target < bull_target):
        warnings.append(
            f"Scenario ordering violated: bear={bear_target:.2f} "
            f"base={base_target:.2f} bull={bull_target:.2f} — using proxy"
        )
        _record_fallback(ticker, as_of, used_fallback=True)
        return _proxy_signal_dict(ticker, as_of, fund, current_price, beta, warnings)

    # Probability-weighted expected value from production engine
    ev_price = pts.expected_value()  # base*0.5 + bull*0.25 + bear*0.25 (default probs)
    expected_value = (ev_price - current_price) / current_price

    confidence_score = float(pts.confidence_score)

    # ── Step 4: Deterministic moat score (v2.0 formula components) ────────────
    moat_score = _compute_production_moat_score(fund)

    # ── Step 5: Rating from moat score ────────────────────────────────────────
    rating = _moat_to_rating(moat_score)
    rating_label = "Accumulate" if rating in _ACCUMULATE_RATINGS else rating

    # ── Step 6: Risk level ────────────────────────────────────────────────────
    risk_level_int, risk_level_str = _compute_risk_level(moat_score, fund, beta)

    # ── Step 7: Asymmetry + Downside ─────────────────────────────────────────
    upside = max(bull_target - current_price, 0.0)
    downside_denom = max(current_price - bear_target, 0.01)
    asymmetry_ratio = upside / downside_denom
    downside_severity = (current_price - bear_target) / current_price

    # ── Step 8: Recommended weight via DI enrichment ──────────────────────────
    recommended_weight = _get_recommended_weight_via_di(
        ticker=ticker,
        current_price=current_price,
        pts=pts,
        moat_score=moat_score,
        risk_level_str=risk_level_str,
        rating=rating,
    )

    # Record production success (not a fallback)
    _record_fallback(ticker, as_of, used_fallback=False)

    # Extract per-method values for parity reporting
    method_values = pts.method_values or {}

    return dict(
        ticker=ticker,
        as_of_date=as_of,
        rating=rating,
        rating_label=rating_label,
        expected_value=round(expected_value, 6),
        confidence_score=round(confidence_score, 2),
        risk_level=risk_level_int,
        risk_level_str=risk_level_str,
        asymmetry_ratio=round(asymmetry_ratio, 4),
        downside_severity=round(downside_severity, 4),
        recommended_weight=round(recommended_weight, 6),
        moat_score=round(moat_score, 4),
        current_price=current_price,
        ev_price=round(ev_price, 4),
        base_target=round(base_target, 4),
        bull_target=round(bull_target, 4),
        bear_target=round(bear_target, 4),
        beta=round(beta, 4),
        fundamentals_period=fund.reporting_period,
        data_quality=fund.data_quality,
        # Valuation component breakdown (for parity reporting)
        fair_value_mid=round(pts.fair_value_mid, 4),
        pe_target=round(method_values.get("pe", 0.0), 4) if method_values.get("pe") else None,
        ev_ebitda_target=round(method_values.get("ev_ebitda", 0.0), 4) if method_values.get("ev_ebitda") else None,
        dcf_target=round(method_values.get("dcf", 0.0), 4) if method_values.get("dcf") else None,
        reporting_currency=fund.reporting_currency,
        currency_converted=fund.currency_converted,
        inputs_used={
            "fund_period": fund.reporting_period.isoformat(),
            "fund_lag_days": (as_of - fund.reporting_period).days,
            "eps_ttm": fund.eps_ttm,
            "fcf_per_share": fund.fcf_per_share,
            "quarters_available": fund.quarters_available,
            "beta": beta,
            "mode": "production_adapter",
            "pts_confidence": pts.confidence_score,
            "pts_methodology": pts.methodology,
            "reporting_currency": fund.reporting_currency,
            "currency_converted": fund.currency_converted,
        },
        data_warnings=warnings,
    )


# ── Moat score computation (deterministic v2.0 formula proxy) ──────────────────


def _compute_production_moat_score(fund: PITFundamentals) -> float:
    """
    Deterministic proxy for MoatScoreBreakdown.weighted_average().

    Uses the v2.0 formula weights:
        earnings_momentum × 0.25 + financial_health × 0.25
        + valuation × 0.20 + technical_strength × 0.15
        + sentiment_catalysts × 0.15

    Components are computed from PITFundamentals; technical_strength and
    sentiment_catalysts default to 5.0 (neutral — no real data available
    historically).
    """
    earnings_momentum = _score_earnings_momentum(fund)
    financial_health = _score_financial_health(fund)
    valuation_component = _score_valuation_component(fund)
    technical_strength = 5.0   # neutral — no historical technical data
    sentiment_catalysts = 5.0  # neutral — no historical news data

    score = (
        earnings_momentum * 0.25
        + financial_health * 0.25
        + valuation_component * 0.20
        + technical_strength * 0.15
        + sentiment_catalysts * 0.15
    )
    return max(0.0, min(10.0, score))


def _score_earnings_momentum(fund: PITFundamentals) -> float:
    """Proxy for earnings_momentum (0–10) from EPS trend + revenue growth."""
    score = 5.0

    # Revenue growth proxy
    if fund.revenue_growth_yoy is not None:
        if fund.revenue_growth_yoy > 20:
            score += 2.0
        elif fund.revenue_growth_yoy > 12:
            score += 1.2
        elif fund.revenue_growth_yoy > 5:
            score += 0.6
        elif fund.revenue_growth_yoy < 0:
            score -= 1.5
        elif fund.revenue_growth_yoy < -5:
            score -= 2.5

    # EPS trend: compare most recent quarter to prior
    if len(fund.eps_series) >= 2:
        latest = fund.eps_series[0]
        prior = fund.eps_series[1]
        if prior != 0:
            eps_qoq = (latest - prior) / abs(prior)
            if eps_qoq > 0.10:
                score += 1.0
            elif eps_qoq > 0.03:
                score += 0.5
            elif eps_qoq < -0.10:
                score -= 1.0
            elif eps_qoq < -0.03:
                score -= 0.5

    # Positive TTM EPS bonus
    if fund.eps_ttm is not None:
        if fund.eps_ttm > 0:
            score += 0.5
        else:
            score -= 1.5

    return max(0.0, min(10.0, score))


def _score_financial_health(fund: PITFundamentals) -> float:
    """Proxy for financial_health (0–10) from FCF, D/E, ROE, margins."""
    score = 5.0

    # FCF margin (quality of earnings)
    if fund.fcf_margin is not None:
        if fund.fcf_margin > 20:
            score += 2.0
        elif fund.fcf_margin > 12:
            score += 1.2
        elif fund.fcf_margin > 5:
            score += 0.5
        elif fund.fcf_margin < 0:
            score -= 1.5

    # ROE
    if fund.roe is not None:
        if fund.roe > 25:
            score += 1.5
        elif fund.roe > 15:
            score += 0.8
        elif fund.roe < 0:
            score -= 1.2

    # Leverage (D/E)
    if fund.de_ratio is not None:
        if fund.de_ratio < 0.2:
            score += 1.0
        elif fund.de_ratio < 0.6:
            score += 0.4
        elif fund.de_ratio > 2.5:
            score -= 1.5
        elif fund.de_ratio > 1.5:
            score -= 0.8

    # Net margin
    if fund.net_margin is not None:
        if fund.net_margin > 20:
            score += 0.5
        elif fund.net_margin > 10:
            score += 0.25
        elif fund.net_margin < 0:
            score -= 0.8

    return max(0.0, min(10.0, score))


def _score_valuation_component(fund: PITFundamentals) -> float:
    """
    Proxy for valuation component (0–10).

    High score = trading cheap relative to intrinsic value.
    Low score  = premium / overvalued.

    Uses FCF yield (FCF/share relative to typical 4–5% threshold) and
    earnings yield (inverse of P/E) as valuation proxies.
    """
    score = 5.0

    # FCF yield proxy: higher FCF margin + positive FCF → better value signal
    if fund.fcf_margin is not None:
        if fund.fcf_margin > 15:
            score += 1.0
        elif fund.fcf_margin > 8:
            score += 0.4
        elif fund.fcf_margin < 0:
            score -= 0.8

    # Revenue growth × margin as value-quality combo
    if fund.revenue_growth_yoy is not None and fund.net_margin is not None:
        peg_proxy = fund.revenue_growth_yoy / max(abs(fund.net_margin), 0.01)
        if peg_proxy > 2.5:  # growing faster than margin (high quality growth)
            score += 0.8
        elif peg_proxy < 0.5:  # low growth relative to margin
            score -= 0.4

    # Positive FCF per share (positive-yielding asset)
    if fund.fcf_per_share is not None:
        if fund.fcf_per_share > 0:
            score += 0.5
        else:
            score -= 0.8

    return max(0.0, min(10.0, score))


# ── Rating + risk helpers ──────────────────────────────────────────────────────


def _moat_to_rating(moat_score: float) -> str:
    if moat_score >= 8.5:
        return "STRONG BUY"
    elif moat_score >= 7.0:
        return "BUY"
    elif moat_score >= 5.0:
        return "HOLD"
    elif moat_score >= 3.5:
        return "SELL"
    else:
        return "STRONG SELL"


def _compute_risk_level(
    moat_score: float,
    fund: PITFundamentals,
    beta: float,
) -> Tuple[int, str]:
    risk = 2  # default: Medium

    low_conditions = [
        moat_score >= 7.0,
        fund.de_ratio is None or fund.de_ratio < 0.5,
        beta < 1.3,
    ]
    if all(low_conditions):
        risk = 1

    high_conditions = [
        moat_score < 4.0,
        fund.de_ratio is not None and fund.de_ratio > 2.5,
        beta > 1.8,
    ]
    if any(high_conditions):
        risk = 3

    inv_map = {1: "Low", 2: "Medium", 3: "High"}
    return risk, inv_map[risk]


# ── DI enrichment for recommended weight ──────────────────────────────────────


def _get_recommended_weight_via_di(
    ticker: str,
    current_price: float,
    pts,   # PriceTargetScenarios
    moat_score: float,
    risk_level_str: str,
    rating: str,
) -> float:
    """
    Call ``enrich_with_decision_intelligence()`` with a minimal synthetic
    full_output dict to extract ``conviction_position.recommended_pct``.

    Falls back to the deterministic weight table if DI enrichment fails.
    """
    try:
        from api.lib.decision_intelligence import enrich_with_decision_intelligence

        price_targets_dict = {
            "base_target": pts.base_target,
            "bull_target": pts.bull_target,
            "bear_target": pts.bear_target,
            "base_probability": pts.base_probability,
            "bull_probability": pts.bull_probability,
            "bear_probability": pts.bear_probability,
            "confidence_score": pts.confidence_score,
            "fair_value_mid": pts.fair_value_mid,
        }

        full_output: dict = {
            "ticker": ticker,
            "rating": rating,
            "risk_level": risk_level_str,
            "confidence": 0.7,    # neutral confidence for DI strategy calc
            "signal_breakdown": None,
            "fundamentalist_output": {
                "valuation_metrics": {
                    "current_price": current_price,
                    "valuation_category": "Fair",
                },
                "price_targets": price_targets_dict,
            },
            "quant_output": {
                "technical_indicators": {},
            },
            "news_hound_output": {},
        }

        enriched = enrich_with_decision_intelligence(full_output, moat_score)
        di = enriched.get("decision_intelligence") or {}
        cp = di.get("conviction_position") or {}
        rec_pct = cp.get("recommended_pct")
        if rec_pct is not None and float(rec_pct) > 0:
            return float(rec_pct) / 100.0

    except Exception as exc:
        logger.debug(
            "DI enrichment failed for %s (moat=%.2f): %s — using fallback table",
            ticker, moat_score, exc,
        )

    return _fallback_weight(moat_score)


def _fallback_weight(moat_score: float) -> float:
    """Deterministic weight table (mirrors signal_snapshot.py proxy)."""
    if moat_score >= 8.5:
        return 0.055
    if moat_score >= 7.5:
        return 0.045
    if moat_score >= 7.0:
        return 0.035
    if moat_score >= 6.0:
        return 0.025
    return 0.0


# ── Fallback recording helper ─────────────────────────────────────────────────


def _record_fallback(ticker: str, as_of: date, *, used_fallback: bool) -> None:
    """Delegate to the global fallback_tracker singleton (thread-safe)."""
    from scripts.backtest.adapters.fallback_tracker import fallback_tracker as _ft
    _ft.record(ticker, as_of, used_fallback=used_fallback)


# ── Proxy fallback (when production engine returns None) ──────────────────────


def _proxy_signal_dict(
    ticker: str,
    as_of: date,
    fund: PITFundamentals,
    current_price: float,
    beta: float,
    warnings: list[str],
) -> Optional[dict]:
    """
    Thin wrapper around the original backtest proxy logic.
    Called only when BlendedValuationCalculator returns None.
    """
    from scripts.backtest.signal_snapshot import (
        _compute_confidence,
        _compute_moat_score,
        _compute_price_targets,
        _compute_risk_level as _snap_risk_level,
        _recommended_weight,
    )

    moat_score = _compute_moat_score(fund, warnings)
    targets = _compute_price_targets(fund, moat_score, current_price, warnings)
    if targets is None:
        return None

    base_target, bull_target, bear_target = targets
    ev_price = base_target * 0.50 + bull_target * 0.25 + bear_target * 0.25
    expected_value = (ev_price - current_price) / current_price
    confidence_score = _compute_confidence(fund, warnings)
    risk_level_int, risk_level_str = _snap_risk_level(moat_score, fund, beta)

    rating = _moat_to_rating(moat_score)
    rating_label = "Accumulate" if rating in _ACCUMULATE_RATINGS else rating

    upside = max(bull_target - current_price, 0.0)
    downside_denom = max(current_price - bear_target, 0.01)
    asymmetry_ratio = upside / downside_denom
    downside_severity = (current_price - bear_target) / current_price
    recommended_weight = _recommended_weight(moat_score)

    warnings.append("proxy_fallback")
    return dict(
        ticker=ticker,
        as_of_date=as_of,
        rating=rating,
        rating_label=rating_label,
        expected_value=round(expected_value, 6),
        confidence_score=round(confidence_score, 2),
        risk_level=risk_level_int,
        risk_level_str=risk_level_str,
        asymmetry_ratio=round(asymmetry_ratio, 4),
        downside_severity=round(downside_severity, 4),
        recommended_weight=round(recommended_weight, 6),
        moat_score=round(moat_score, 4),
        current_price=current_price,
        ev_price=round(ev_price, 4),
        base_target=round(base_target, 4),
        bull_target=round(bull_target, 4),
        bear_target=round(bear_target, 4),
        beta=round(beta, 4),
        fundamentals_period=fund.reporting_period,
        data_quality=fund.data_quality,
        inputs_used={
            "fund_period": fund.reporting_period.isoformat(),
            "fund_lag_days": (as_of - fund.reporting_period).days,
            "eps_ttm": fund.eps_ttm,
            "quarters_available": fund.quarters_available,
            "beta": beta,
            "mode": "proxy_fallback",
        },
        data_warnings=warnings,
    )
