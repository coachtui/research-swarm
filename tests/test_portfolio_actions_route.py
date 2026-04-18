"""Integration tests for new portfolio endpoints: refresh-prices, cash, rebalance, add-position."""
import sys
import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

_prisma_stub = types.ModuleType("prisma")
_prisma_stub.Prisma = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("prisma", _prisma_stub)

import pytest
from fastapi.testclient import TestClient


def _make_user(tier="starter"):
    user = MagicMock()
    user.id = "user1"
    user.tier = tier
    user.is_admin = False
    return user


def _make_portfolio(positions=None):
    portfolio = MagicMock()
    portfolio.id = "portfolio1"
    portfolio.userId = "user1"
    portfolio.name = "Core"
    portfolio.mandate = "compounder"
    portfolio.cashBalance = 1000.0
    portfolio.cashUpdatedAt = None
    portfolio.createdAt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    portfolio.positions = positions or []
    return portfolio


def _make_position(ticker="NVDA"):
    pos = MagicMock()
    pos.id = "pos1"
    pos.ticker = ticker
    pos.shares = 10.0
    pos.lastKnownPrice = 100.0
    pos.lastPriceAt = None
    pos.targetWeight = 0.08
    pos.engineSuggestedWeight = 0.07
    pos.costBasis = 90.0
    pos.tierState = "none"
    pos.thesisState = "intact"
    pos.eligibilityState = "eligible"
    pos.ownershipStatus = "core_compounder"
    pos.entryDate = None
    pos.quartersHeld = 4
    pos.compounderScore = 0.72
    pos.lastDrawdown = None
    pos.latestRunId = "run1"
    pos.addTiersApplied = "[]"
    pos.portfolioId = "portfolio1"
    return pos


def _make_app(user):
    """Create a FastAPI test app with get_current_user dependency overridden."""
    from api.routes.portfolio import router
    from api.dependencies import get_current_user
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user
    return app


# ── POST /portfolio/{id}/refresh-prices ─────────────────────────────────────

def test_refresh_prices_returns_counts():
    user = _make_user()

    mock_db = MagicMock()
    mock_db.portfolio.find_unique = AsyncMock(return_value=_make_portfolio([_make_position()]))

    with patch("api.routes.portfolio.get_db", new_callable=AsyncMock, return_value=mock_db), \
         patch("api.routes.portfolio.refresh_position_prices", new_callable=AsyncMock, return_value=(1, 0)):
        app = _make_app(user)
        client = TestClient(app)
        resp = client.post("/api/portfolio/portfolio1/refresh-prices")

    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 1
    assert data["skipped"] == 0


# ── POST /portfolio/{id}/cash ────────────────────────────────────────────────

def test_update_cash_balance():
    user = _make_user()

    mock_db = MagicMock()
    mock_db.portfolio.find_unique = AsyncMock(return_value=_make_portfolio())
    mock_db.portfolio.update = AsyncMock()

    with patch("api.routes.portfolio.get_db", new_callable=AsyncMock, return_value=mock_db):
        app = _make_app(user)
        client = TestClient(app)
        resp = client.post("/api/portfolio/portfolio1/cash", json={"amount": 5000.0})

    assert resp.status_code == 200
    assert resp.json()["cash_balance"] == pytest.approx(5000.0)
    mock_db.portfolio.update.assert_called_once()


# ── POST /portfolio/{id}/positions (shares required) ────────────────────────

def test_add_position_requires_shares():
    user = _make_user()

    mock_db = MagicMock()
    mock_db.portfolio.find_unique = AsyncMock(return_value=_make_portfolio())

    with patch("api.routes.portfolio.get_db", new_callable=AsyncMock, return_value=mock_db), \
         patch("api.routes.portfolio.has_feature", return_value=True):
        app = _make_app(user)
        client = TestClient(app)
        # Missing shares → 422
        resp = client.post("/api/portfolio/portfolio1/positions",
                           json={"ticker": "AAPL"})

    assert resp.status_code == 422


# ── POST /portfolio/{id}/rebalance ──────────────────────────────────────────

def test_rebalance_expires_pending_and_creates_actions():
    user = _make_user()

    pos = MagicMock()
    pos.id = "pos1"
    pos.ticker = "AAPL"
    pos.shares = 10.0
    pos.lastKnownPrice = 100.0
    pos.lastPriceAt = None
    pos.targetWeight = 0.1
    pos.engineSuggestedWeight = 0.1
    pos.ownershipStatus = "active"
    pos.latestRunId = None  # skip stockresult query
    pos.thesisState = "intact"
    pos.costBasis = 90.0

    portfolio = _make_portfolio(positions=[pos])
    portfolio.id = "port1"
    portfolio.cashBalance = 0.0

    mock_action = MagicMock()
    mock_action.id = "act1"

    mock_db = MagicMock()
    mock_db.portfolio.find_unique = AsyncMock(return_value=portfolio)
    mock_db.portfolioaction.update_many = AsyncMock(return_value=None)
    mock_db.stockresult.find_first = AsyncMock(return_value=None)
    mock_db.portfolioaction.create = AsyncMock(return_value=mock_action)

    with patch("api.routes.portfolio.get_db", new_callable=AsyncMock, return_value=mock_db), \
         patch("api.routes.portfolio.has_feature", return_value=True):
        app = _make_app(user)
        client = TestClient(app)
        resp = client.post("/api/portfolio/port1/rebalance")

    assert resp.status_code == 200
    mock_db.portfolioaction.update_many.assert_called_once()
