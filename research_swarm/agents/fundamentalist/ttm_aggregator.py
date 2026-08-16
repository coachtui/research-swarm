"""Deterministic TTM aggregation from per-filing extractions (Phase B).

The old pipeline asked Haiku to extract four quarters AND do the arithmetic
(TTM sums, margins, growth, trends) in one mega-prompt — including silently
treating a 10-K's full-year figures as "Q4". This module does the arithmetic
in Python from the per-filing extractions:

- Q4 derivation: the annual filing gives fiscal-year totals; each 10-Q gives
  its prior-year comparative quarter. Q4(FY) = FY − Σ(comparative quarters),
  computed per metric only when all three comparatives exist. If the 10-K
  explicitly presents Q4 figures, those win.
- YoY revenue growth: Σ(current three quarters) vs Σ(their prior-year
  comparatives) — a true like-for-like nine-month comparison. Null when
  comparatives are missing (the existing yfinance fallback then applies).
- Trends and sequential growth from the quarterly series.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from research_swarm.logger import logger
from research_swarm.agents.fundamentalist.models import (
    QuarterlyMetrics,
    QuarterlyTrends,
    TTMMetrics,
)

_METRIC_KEYS = [
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "free_cash_flow",
]


def _metrics_of(extraction: Optional[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    metrics = (extraction or {}).get("metrics") or {}
    return {k: metrics.get(k) for k in _METRIC_KEYS}


def _derive_q4(
    annual: Dict[str, Any],
    quarterly_extractions: List[Dict[str, Any]],
) -> Dict[str, Optional[float]]:
    """Q4 three-month figures from an annual filing.

    Preference order: the filing's own q4_metrics; else FY minus the three
    10-Qs' prior-year comparatives (revenue / net_income only — comparatives
    don't carry the other metrics); else None per metric.
    """
    q4_explicit = annual.get("q4_metrics") or {}
    fy = _metrics_of(annual)
    derived: Dict[str, Optional[float]] = {}

    for key in _METRIC_KEYS:
        if q4_explicit.get(key) is not None:
            derived[key] = q4_explicit[key]
            continue
        if key in ("revenue", "net_income") and fy.get(key) is not None:
            comparatives = [
                ((e.get("prior_year_metrics") or {}).get(key))
                for e in quarterly_extractions
            ]
            if len(comparatives) == 3 and all(c is not None for c in comparatives):
                derived[key] = round(fy[key] - sum(comparatives), 1)
                continue
        derived[key] = None
    return derived


def aggregate_ttm(
    quarter_labels: List[str],
    extractions_by_quarter: Dict[str, Optional[Dict[str, Any]]],
) -> Tuple[List[QuarterlyMetrics], TTMMetrics, QuarterlyTrends]:
    """Build quarterly metrics, TTM totals, and trends from per-filing
    extractions. `quarter_labels` is chronological (oldest first, the annual
    filing's quarter typically first)."""

    quarterly_only = [
        extractions_by_quarter[q]
        for q in quarter_labels
        if (extractions_by_quarter.get(q) or {}).get("period_type") == "quarter"
    ]

    # ── Per-quarter metric rows ────────────────────────────────────────────
    per_quarter: Dict[str, Dict[str, Optional[float]]] = {}
    annual_fy: Optional[Dict[str, Optional[float]]] = None
    for label in quarter_labels:
        extraction = extractions_by_quarter.get(label)
        if extraction is None:
            per_quarter[label] = {k: None for k in _METRIC_KEYS}
            continue
        if extraction.get("period_type") == "fiscal_year":
            annual_fy = _metrics_of(extraction)
            per_quarter[label] = _derive_q4(extraction, quarterly_only)
            if per_quarter[label].get("revenue") is None:
                logger.warning(
                    f"[TTM] Q4 not derivable for {label} "
                    "(no explicit Q4 data and incomplete comparatives)"
                )
        else:
            per_quarter[label] = _metrics_of(extraction)

    quarterly_metrics = [
        QuarterlyMetrics(quarter=label, **per_quarter[label]) for label in quarter_labels
    ]

    # ── TTM sums ───────────────────────────────────────────────────────────
    def _ttm_sum(key: str) -> Optional[float]:
        values = [per_quarter[q].get(key) for q in quarter_labels]
        present = [v for v in values if v is not None]
        if len(present) == len(quarter_labels) and present:
            return round(sum(present), 1)
        # Fallback: trailing fiscal year as the best available approximation
        # (the old LLM path silently made the same class of approximation).
        if annual_fy is not None and annual_fy.get(key) is not None:
            logger.warning(f"[TTM] Using trailing-FY fallback for {key}")
            return annual_fy[key]
        return None

    ttm_values = {f"ttm_{k}": _ttm_sum(k) for k in
                  ["revenue", "gross_profit", "operating_income", "net_income", "free_cash_flow"]}

    def _margin(numerator: Optional[float]) -> Optional[float]:
        rev = ttm_values["ttm_revenue"]
        if numerator is None or not rev:
            return None
        return round(numerator / rev * 100, 2)

    # ── YoY growth: current three quarters vs their prior-year comparatives ─
    revenue_growth_yoy = None
    if len(quarterly_only) >= 3:
        current = [(_metrics_of(e)).get("revenue") for e in quarterly_only]
        prior = [((e.get("prior_year_metrics") or {}).get("revenue")) for e in quarterly_only]
        if all(v is not None for v in current) and all(v is not None for v in prior) and sum(prior):
            revenue_growth_yoy = round((sum(current) / sum(prior) - 1) * 100, 2)

    ttm_metrics = TTMMetrics(
        quarters_included=quarter_labels,
        **ttm_values,
        gross_margin=_margin(ttm_values["ttm_gross_profit"]),
        operating_margin=_margin(ttm_values["ttm_operating_income"]),
        net_margin=_margin(ttm_values["ttm_net_income"]),
        revenue_growth_yoy=revenue_growth_yoy,
    )

    # ── Trends ─────────────────────────────────────────────────────────────
    revenue_trend = [per_quarter[q].get("revenue") for q in quarter_labels]
    margin_trend = []
    for q in quarter_labels:
        rev, gp = per_quarter[q].get("revenue"), per_quarter[q].get("gross_profit")
        margin_trend.append(round(gp / rev * 100, 2) if rev and gp is not None else None)

    sequential_growth: List[Optional[float]] = []
    for prev, curr in zip(revenue_trend, revenue_trend[1:]):
        if prev and curr is not None:
            sequential_growth.append(round((curr / prev - 1) * 100, 2))
        else:
            sequential_growth.append(None)

    known = [g for g in sequential_growth if g is not None]
    if not known:
        trend_direction = "stable"
    elif sum(1 for g in known if g > 0) > len(known) / 2:
        trend_direction = "improving"
    elif sum(1 for g in known if g < 0) > len(known) / 2:
        trend_direction = "declining"
    else:
        trend_direction = "stable"

    quarterly_trends = QuarterlyTrends(
        revenue_trend=revenue_trend,
        margin_trend=margin_trend,
        trend_direction=trend_direction,
        sequential_growth_rates=sequential_growth,
    )

    return quarterly_metrics, ttm_metrics, quarterly_trends
