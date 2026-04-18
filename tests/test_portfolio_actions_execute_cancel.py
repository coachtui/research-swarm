"""Tests for portfolio action execute and cancel endpoints."""
import sys
import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

_prisma_stub = types.ModuleType("prisma")
_prisma_stub.Prisma = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("prisma", _prisma_stub)

import pytest
from fastapi.testclient import TestClient


def _make_user():
    user = MagicMock()
    user.id = "user1"
    user.tier = "investor"
    user.is_admin = False
    return user


def _make_action(
    action_id="act1",
    trigger_condition="immediate",
    status="pending",
    children=None,
):
    action = MagicMock()
    action.id = action_id
    action.userId = "user1"
    action.triggerCondition = trigger_condition
    action.status = status
    action.children = children if children is not None else []
    return action


def _make_child(child_id="child1"):
    child = MagicMock()
    child.id = child_id
    child.status = "pending"
    return child


def _make_app(user):
    """Create a FastAPI test app with get_current_user dependency overridden."""
    from api.routes.portfolio_actions import router
    from api.dependencies import get_current_user
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user
    return app


# ── POST /actions/{action_id}/execute ────────────────────────────────────────


def test_execute_action_success():
    user = _make_user()
    action = _make_action(trigger_condition="immediate", status="pending")

    mock_db = MagicMock()
    mock_db.portfolioaction.find_unique = AsyncMock(return_value=action)
    mock_db.portfolioaction.update = AsyncMock(return_value=action)

    with patch("api.routes.portfolio_actions.get_db", new_callable=AsyncMock, return_value=mock_db):
        app = _make_app(user)
        client = TestClient(app)
        resp = client.post("/api/actions/act1/execute")

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["action_id"] == "act1"
    assert data["status"] == "executed"
    mock_db.portfolioaction.update.assert_called_once()


def test_execute_action_non_immediate_rejected():
    user = _make_user()
    action = _make_action(trigger_condition="price_above", status="pending")

    mock_db = MagicMock()
    mock_db.portfolioaction.find_unique = AsyncMock(return_value=action)

    with patch("api.routes.portfolio_actions.get_db", new_callable=AsyncMock, return_value=mock_db):
        app = _make_app(user)
        client = TestClient(app)
        resp = client.post("/api/actions/act1/execute")

    assert resp.status_code == 400
    assert "immediate" in resp.json()["detail"]


def test_execute_action_already_executed_rejected():
    user = _make_user()
    action = _make_action(trigger_condition="immediate", status="executed")

    mock_db = MagicMock()
    mock_db.portfolioaction.find_unique = AsyncMock(return_value=action)

    with patch("api.routes.portfolio_actions.get_db", new_callable=AsyncMock, return_value=mock_db):
        app = _make_app(user)
        client = TestClient(app)
        resp = client.post("/api/actions/act1/execute")

    assert resp.status_code == 400
    assert "executed" in resp.json()["detail"]


# ── POST /actions/{action_id}/cancel ─────────────────────────────────────────


def test_cancel_action_success():
    user = _make_user()
    child1 = _make_child("child1")
    child2 = _make_child("child2")
    action = _make_action(status="pending", children=[child1, child2])

    mock_db = MagicMock()
    mock_db.portfolioaction.find_unique = AsyncMock(return_value=action)
    mock_db.portfolioaction.update = AsyncMock()

    with patch("api.routes.portfolio_actions.get_db", new_callable=AsyncMock, return_value=mock_db):
        app = _make_app(user)
        client = TestClient(app)
        resp = client.post("/api/actions/act1/cancel")

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["action_id"] == "act1"
    assert data["cancelled_count"] == 3  # parent + 2 children


def test_cancel_already_cancelled_rejected():
    user = _make_user()
    action = _make_action(status="cancelled", children=[])

    mock_db = MagicMock()
    mock_db.portfolioaction.find_unique = AsyncMock(return_value=action)

    with patch("api.routes.portfolio_actions.get_db", new_callable=AsyncMock, return_value=mock_db):
        app = _make_app(user)
        client = TestClient(app)
        resp = client.post("/api/actions/act1/cancel")

    assert resp.status_code == 400
    assert "cancelled" in resp.json()["detail"]
