"""Unit tests for allocation pure functions."""
import sys
import types
from unittest.mock import MagicMock

# Stub prisma before any api import
_prisma_stub = types.ModuleType("prisma")
_prisma_stub.Prisma = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("prisma", _prisma_stub)

import pytest
from api.services.allocation import (
    compute_allocation_pct,
    compute_market_value,
    compute_portfolio_total,
    compute_portfolio_breakdown,
)
from api.models.portfolio import PositionResponse


def _make_pos(ticker, shares, price, target_weight=0.05):
    """Build a mock Position prisma record."""
    p = MagicMock()
    p.ticker = ticker
    p.shares = shares
    p.lastKnownPrice = price
    p.lastPriceAt = None
    p.targetWeight = target_weight
    p.engineSuggestedWeight = None
    p.costBasis = None
    p.tierState = "none"
    p.thesisState = "intact"
    p.eligibilityState = "pending"
    p.ownershipStatus = "watch"
    p.entryDate = None
    p.quartersHeld = 0
    p.compounderScore = None
    p.lastDrawdown = None
    p.latestRunId = None
    return p


# ── compute_market_value ─────────────────────────────────────────────────────

def test_market_value_normal():
    assert compute_market_value(10, 100.0) == pytest.approx(1000.0)

def test_market_value_null_price():
    assert compute_market_value(10, None) is None

def test_market_value_zero_shares():
    assert compute_market_value(0, 100.0) == pytest.approx(0.0)


# ── compute_portfolio_total ──────────────────────────────────────────────────

def test_portfolio_total_normal():
    positions = [_make_pos("NVDA", 10, 100.0), _make_pos("AAPL", 5, 200.0)]
    total = compute_portfolio_total(positions, cash_balance=500.0)
    assert total == pytest.approx(2500.0)  # 1000 + 1000 + 500

def test_portfolio_total_all_null_prices():
    positions = [_make_pos("NVDA", 10, None), _make_pos("AAPL", 5, None)]
    total = compute_portfolio_total(positions, cash_balance=0.0)
    assert total == pytest.approx(0.0)

def test_portfolio_total_zero_everything():
    assert compute_portfolio_total([], cash_balance=0.0) == pytest.approx(0.0)

def test_portfolio_total_cash_only():
    assert compute_portfolio_total([], cash_balance=10000.0) == pytest.approx(10000.0)


# ── compute_allocation_pct ───────────────────────────────────────────────────

def test_allocation_pct_normal():
    pos = _make_pos("NVDA", 10, 100.0)
    pct = compute_allocation_pct(pos, total_value=1000.0)
    assert pct == pytest.approx(1.0)  # 1000 / 1000 = 100%

def test_allocation_pct_partial():
    pos = _make_pos("NVDA", 10, 100.0)
    pct = compute_allocation_pct(pos, total_value=2000.0)
    assert pct == pytest.approx(0.5)

def test_allocation_pct_null_price():
    pos = _make_pos("NVDA", 10, None)
    assert compute_allocation_pct(pos, total_value=1000.0) is None

def test_allocation_pct_zero_total():
    pos = _make_pos("NVDA", 10, 100.0)
    assert compute_allocation_pct(pos, total_value=0.0) is None

def test_allocation_pct_zero_shares():
    pos = _make_pos("NVDA", 0, 100.0)
    assert compute_allocation_pct(pos, total_value=1000.0) == pytest.approx(0.0)


# ── compute_portfolio_breakdown ──────────────────────────────────────────────

def test_breakdown_normal():
    _positions = [_make_pos("NVDA", 10, 100.0), _make_pos("AAPL", 5, 200.0)]

    class FakePortfolio:
        id = "p1"
        name = "Core"
        mandate = "compounder"
        cashBalance = 500.0
        cashUpdatedAt = None
        createdAt = None
        positions = _positions

    breakdown = compute_portfolio_breakdown(FakePortfolio())
    assert breakdown.total_value == pytest.approx(2500.0)
    assert breakdown.cash_pct == pytest.approx(0.2)  # 500 / 2500 = 0.2
    assert len(breakdown.positions) == 2
    nvda = next(p for p in breakdown.positions if p.ticker == "NVDA")
    assert nvda.allocation_pct == pytest.approx(0.4)  # 1000 / 2500
    assert nvda.market_value == pytest.approx(1000.0)

def test_breakdown_zero_portfolio():
    class FakePortfolio:
        id = "p1"
        name = "Core"
        mandate = "compounder"
        cashBalance = 0.0
        cashUpdatedAt = None
        createdAt = None
        positions = []

    breakdown = compute_portfolio_breakdown(FakePortfolio())
    assert breakdown.total_value == pytest.approx(0.0)
    assert breakdown.cash_pct == pytest.approx(0.0)
