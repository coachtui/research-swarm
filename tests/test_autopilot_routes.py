"""Tests for api/routes/autopilot.py — outlook serializer + admin endpoint.

Importing the full app (api.index) has heavy side effects (loads every
research_swarm agent module) and currently fails to import outright under
this environment's Python/typing setup (a `X | None` union used elsewhere
in the app requires Python 3.10+). So endpoint tests build a minimal
FastAPI app that includes only autopilot.router, with require_admin and
get_db overridden/patched — no real DB, no real auth.
"""
import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Stub out prisma before any api.* import triggers the real Prisma client
# (prisma generate hasn't been run in this environment, so the real client
# raises RuntimeError on import).
_prisma_stub = types.ModuleType("prisma")
_prisma_stub.Prisma = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("prisma", _prisma_stub)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import require_admin
from api.routes.autopilot import MarketOutlookResponse, outlook_row_to_response, router

RUN_DATE = datetime(2026, 7, 6, tzinfo=timezone.utc)


def _make_row(**overrides) -> SimpleNamespace:
    """Build a fake Prisma MarketOutlook row (camelCase attrs)."""
    defaults = dict(
        id="outlook1",
        runDate=RUN_DATE,
        regime="risk_on",
        regimeMechanical="neutral",
        strategistOverride=True,
        strategistStatus="ok",
        conviction=0.65,
        sectorRankings=[{"etf": "XLE", "sector": "Energy", "score": 0.024}],
        rotationFlags=[],
        breadth={"pct_above_200dma": 63.6, "equal_weight_trend_3m": 0.8},
        reasoning="Breadth improving.",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── Pure serializer tests ───────────────────────────────────────────────────

class TestOutlookRowToResponse:
    def test_maps_camel_to_snake(self):
        row = _make_row()
        result = outlook_row_to_response(row)

        assert isinstance(result, MarketOutlookResponse)
        assert result.id == "outlook1"
        assert result.run_date == RUN_DATE
        assert result.regime == "risk_on"
        assert result.regime_mechanical == "neutral"
        assert result.strategist_override is True
        assert result.strategist_status == "ok"
        assert result.conviction == 0.65
        assert result.sector_rankings == [{"etf": "XLE", "sector": "Energy", "score": 0.024}]
        assert result.rotation_flags == []
        assert result.breadth == {"pct_above_200dma": 63.6, "equal_weight_trend_3m": 0.8}
        assert result.reasoning == "Breadth improving."

    def test_handles_null_conviction_and_reasoning(self):
        row = _make_row(
            conviction=None,
            reasoning=None,
            strategistStatus="fallback",
            strategistOverride=False,
        )
        result = outlook_row_to_response(row)

        assert result.conviction is None
        assert result.reasoning is None
        assert result.strategist_status == "fallback"
        assert result.strategist_override is False


# ── Endpoint tests ───────────────────────────────────────────────────────────

def _make_app() -> FastAPI:
    """Minimal FastAPI app with only autopilot.router mounted."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


class TestGetOutlookEndpoint:
    def test_returns_200_with_latest_outlook(self):
        row = _make_row()
        app = _make_app()
        app.dependency_overrides[require_admin] = lambda: MagicMock(is_admin=True)

        mock_db = MagicMock()
        mock_db.marketoutlook.find_first = AsyncMock(return_value=row)

        with patch(
            "api.routes.autopilot.get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            client = TestClient(app)
            resp = client.get("/api/autopilot/outlook")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "outlook1"
        assert data["regime"] == "risk_on"
        assert data["strategist_override"] is True
        assert data["conviction"] == 0.65

    def test_returns_404_when_no_outlook(self):
        app = _make_app()
        app.dependency_overrides[require_admin] = lambda: MagicMock(is_admin=True)

        mock_db = MagicMock()
        mock_db.marketoutlook.find_first = AsyncMock(return_value=None)

        with patch(
            "api.routes.autopilot.get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            client = TestClient(app)
            resp = client.get("/api/autopilot/outlook")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "No outlook available yet"


# ── Phase 2: broker link / status / resume ──────────────────────────────────

def _admin_app() -> FastAPI:
    """Minimal FastAPI app with only autopilot.router, admin override included."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id="admin1", is_admin=True)
    return app


def _patch_db():
    """Patch autopilot's get_db to a MagicMock db (no real prisma)."""
    return patch("api.routes.autopilot.get_db", new=AsyncMock(return_value=MagicMock()))


class TestBrokerLink:
    def test_link_validates_and_stores_encrypted(self):
        app = _admin_app()
        fake_summary = {"equity": 100000.0, "cash": 100000.0}
        with _patch_db(), \
             patch("api.routes.autopilot._alpaca_client_factory") as factory, \
             patch("api.routes.autopilot.upsert_alpaca_account", new=AsyncMock()) as upsert:
            factory.return_value.get_account_summary.return_value = fake_summary
            client = TestClient(app)
            resp = client.post("/api/autopilot/broker/link",
                               json={"api_key": "PK123", "api_secret": "SEC456"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "linked", "account_equity": 100000.0}
        upsert.assert_awaited_once()

    def test_link_rejects_bad_keys_without_storing(self):
        app = _admin_app()
        with _patch_db(), \
             patch("api.routes.autopilot._alpaca_client_factory") as factory, \
             patch("api.routes.autopilot.upsert_alpaca_account", new=AsyncMock()) as upsert:
            factory.return_value.get_account_summary.side_effect = RuntimeError("401")
            client = TestClient(app)
            resp = client.post("/api/autopilot/broker/link",
                               json={"api_key": "bad", "api_secret": "bad"})
        assert resp.status_code == 400
        upsert.assert_not_awaited()


class TestBrokerStatus:
    def test_status_unlinked(self):
        app = _admin_app()
        with _patch_db(), \
             patch("api.routes.autopilot.get_active_alpaca_account",
                   new=AsyncMock(return_value=None)):
            resp = TestClient(app).get("/api/autopilot/broker/status")
        assert resp.status_code == 200
        assert resp.json()["linked"] is False


class TestSleeveResume:
    def test_resume_reactivates_halted_sleeve(self):
        app = _admin_app()
        state = SimpleNamespace(sleeve="B", status="halted", statusReason="cb")
        with _patch_db(), \
             patch("api.routes.autopilot.get_sleeve_state",
                   new=AsyncMock(return_value=state)), \
             patch("api.routes.autopilot.set_sleeve_status", new=AsyncMock()) as setter:
            resp = TestClient(app).post("/api/autopilot/sleeve/B/resume")
        assert resp.status_code == 200
        assert resp.json() == {"sleeve": "B", "status": "active"}
        setter.assert_awaited_once()

    def test_resume_unknown_sleeve_404(self):
        app = _admin_app()
        resp = TestClient(app).post("/api/autopilot/sleeve/X/resume")
        assert resp.status_code == 404
