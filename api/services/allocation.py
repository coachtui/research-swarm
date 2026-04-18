"""
Portfolio allocation pure functions.

All functions are stateless — no DB reads. Pass in Prisma records (or mocks).
"""

from __future__ import annotations

from typing import Optional

from api.models.portfolio import PortfolioBreakdown, PositionResponse


def compute_market_value(shares: float, last_known_price: Optional[float]) -> Optional[float]:
    """Return shares * price, or None if price is unavailable."""
    if last_known_price is None:
        return None
    return shares * last_known_price


def compute_portfolio_total(positions, cash_balance: float) -> float:
    """Sum market values of all positions (skipping null prices) plus cash."""
    total = cash_balance
    for pos in positions:
        mv = compute_market_value(pos.shares or 0.0, pos.lastKnownPrice)
        if mv is not None:
            total += mv
    return total


def compute_allocation_pct(position, total_value: float) -> Optional[float]:
    """
    Return position's allocation as a fraction (0.0-1.0).

    Returns None if lastKnownPrice is None or total_value is 0.
    Returns 0.0 if shares is 0.
    """
    if total_value == 0.0:
        return None
    mv = compute_market_value(position.shares or 0.0, position.lastKnownPrice)
    if mv is None:
        return None
    return mv / total_value


def _position_to_response(position, allocation_pct: Optional[float], market_value: Optional[float]) -> PositionResponse:
    return PositionResponse(
        ticker=position.ticker,
        shares=position.shares or 0.0,
        cost_basis=position.costBasis,
        last_known_price=position.lastKnownPrice,
        last_price_at=position.lastPriceAt,
        allocation_pct=allocation_pct,
        market_value=market_value,
        target_weight=position.targetWeight or 0.0,
        engine_suggested_weight=position.engineSuggestedWeight,
        tier_state=position.tierState,
        thesis_state=position.thesisState,
        eligibility_state=position.eligibilityState,
        ownership_status=position.ownershipStatus,
        entry_date=position.entryDate,
        quarters_held=position.quartersHeld,
        compounder_score=position.compounderScore,
        last_drawdown=position.lastDrawdown,
        latest_run_id=position.latestRunId,
    )


def compute_portfolio_breakdown(portfolio) -> PortfolioBreakdown:
    """
    Compute full portfolio breakdown: total value, cash %, and per-position allocations.

    Returns a PortfolioBreakdown with PositionResponse objects that include
    computed allocation_pct and market_value.
    """
    positions = portfolio.positions or []
    cash = portfolio.cashBalance or 0.0
    total = compute_portfolio_total(positions, cash)

    position_responses = []
    for pos in positions:
        mv = compute_market_value(pos.shares or 0.0, pos.lastKnownPrice)
        alloc_pct = compute_allocation_pct(pos, total)
        position_responses.append(_position_to_response(pos, alloc_pct, mv))

    cash_pct = (cash / total) if total > 0 else 0.0

    return PortfolioBreakdown(
        total_value=total,
        cash_balance=cash,
        cash_pct=cash_pct,
        positions=position_responses,
    )
