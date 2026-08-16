"""
Signal Extractor — bridges StockResult.fullOutput to CompounderEngine SignalInput.

Converts the report-driven agent output into the signal contract consumed by
the portfolio engine. This is the translation layer between the research pipeline
and the ownership system.

Usage:
    from api.services.signal_extractor import extract_signal_from_full_output

    signal = extract_signal_from_full_output(
        ticker="AAPL",
        full_output=stock_result.fullOutput,
        moat_score=stock_result.moatScore or 0.0,
        sector="Technology",
        current_price=175.50,
    )
"""

from __future__ import annotations

import logging
from typing import Optional

from api.lib.compounder_owner_v3 import SignalInput
from api.lib.verdict import resolve_engine_verdict, resolve_fair_value

logger = logging.getLogger(__name__)


def extract_signal_from_full_output(
    ticker: str,
    full_output: dict,
    moat_score: float,
    sector: str = "Unknown",
    current_price: float = 0.0,
) -> SignalInput:
    """
    Convert a StockResult's full_output dict to a SignalInput for the CompounderEngine.

    Extracts from three agent output dicts:
      - fundamentalist_output → financial metrics (revenue, margins, FCF)
      - quant_output → technical indicators (52-week high, 200DMA)
      - news_hound_output → earnings revision signal

    Returns a SignalInput dataclass ready for engine consumption.
    """
    fund = full_output.get("fundamentalist_output") or {}
    quant = full_output.get("quant_output") or {}
    news = full_output.get("news_hound_output") or {}

    # ── Report-level verdict and fair value — primary authority ──────────────
    # Resolved from decision_intelligence.rating / rating via the shared helper
    # (the previously-read "verdict" and fundamentalist "valuation" keys never
    # existed, which hardcoded every signal to hold with no fair value).
    verdict = resolve_engine_verdict(full_output)
    fair_value = resolve_fair_value(full_output)

    # ── Financial metrics from fundamentalist ────────────────────────────────
    fm = fund.get("financial_metrics") or {}

    # Not produced by the pipeline yet; SignalInput treats None as "unknown"
    revenue_3y_cagr = None
    revenue_growth_yoy = _safe_float(fm.get("revenue_growth_yoy"))
    gross_margin = _safe_float(fm.get("gross_margin"))

    # FCF margin: derived — FinancialMetricsOutput carries only the absolutes
    fcf_margin = None
    fcf = _safe_float(fm.get("free_cash_flow"))
    revenue = _safe_float(fm.get("revenue"))
    if fcf is not None and revenue:
        fcf_margin = round(fcf / revenue * 100.0, 2)

    trends = fund.get("quarterly_trends") or {}
    revenue_growth_persistence = _persistence_from_trends(trends)
    margin_trend = _extract_margin_trend(trends, fund)

    # ── Earnings revision from news hound ────────────────────────────────────
    earnings_est = news.get("earnings_estimates") or {}
    eps_revision_positive = bool(earnings_est.get("net_positive_revisions", False))
    # Fallback: check revision direction
    if not eps_revision_positive:
        revisions = earnings_est.get("revisions") or {}
        up = revisions.get("up_last_30d", 0) or 0
        down = revisions.get("down_last_30d", 0) or 0
        eps_revision_positive = up > down

    # ── Technical indicators from quant ──────────────────────────────────────
    ti = quant.get("technical_indicators") or {}
    ma = ti.get("moving_averages") or {}

    high_252d = _safe_float(
        ti.get("high_52_week")
        or ti.get("week_52_high")
        or ma.get("high_252d")
    )
    ma_200d = _safe_float(
        ma.get("sma_200")
        or ti.get("sma_200")
        or ma.get("ma_200d")
    )

    # If current_price not provided, try to get from quant output
    if current_price <= 0:
        current_price = _safe_float(
            ma.get("current_price")
            or ti.get("current_price")
            or quant.get("current_price")
        ) or 0.0

    return SignalInput(
        ticker=ticker,
        revenue_3y_cagr=revenue_3y_cagr,
        revenue_growth_yoy=revenue_growth_yoy,
        revenue_growth_persistence=revenue_growth_persistence,
        gross_margin=gross_margin,
        fcf_margin=fcf_margin,
        moat_score=moat_score,
        margin_trend=margin_trend,
        eps_revision_positive=eps_revision_positive,
        sector=sector,
        current_price=current_price,
        high_252d=high_252d,
        ma_200d=ma_200d,
        verdict=verdict,
        fair_value=fair_value,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _safe_float(val) -> Optional[float]:
    """Safely convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _persistence_from_trends(trends: dict) -> Optional[int]:
    """Consecutive positive QoQ growth quarters, counted from the most recent
    quarter backwards, using QuarterlyTrends.sequential_growth_rates."""
    rates = trends.get("sequential_growth_rates") or []
    streak = 0
    for rate in reversed(rates):
        if rate is None or rate <= 0:
            break
        streak += 1
    return streak if rates else None


def _extract_margin_trend(trends: dict, fund: dict) -> str:
    """
    Determine margin trend from QuarterlyTrends.margin_trend (a series of
    margin values per quarter), falling back to the profitability score.
    """
    margins = [m for m in (trends.get("margin_trend") or []) if m is not None]
    if len(margins) >= 2:
        change = margins[-1] - margins[0]
        if change > 1.0:
            return "expanding"
        elif change < -1.0:
            return "contracting"
        else:
            return "stable"

    # Check score breakdown for clues
    score_breakdown = fund.get("score_breakdown") or {}
    profitability = _safe_float(score_breakdown.get("profitability"))
    if profitability is not None:
        if profitability >= 7.0:
            return "expanding"
        elif profitability <= 4.0:
            return "contracting"
        else:
            return "stable"

    return "unknown"
