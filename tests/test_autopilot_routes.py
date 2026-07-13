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
from api.routes.autopilot import (
    MarketOutlookResponse, outlook_row_to_response, router,
    WeeklyBatchRunDetail, WeeklyBatchRunSummary,
    batch_run_row_to_summary, batch_run_row_to_detail,
)

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

    def test_extended_fields_none_for_legacy_rows(self):
        """Rows created before Phase 3A have no industry/size-style attrs."""
        result = outlook_row_to_response(_make_row())
        assert result.industry_rankings is None
        assert result.industry_rotations is None
        assert result.industry_missing is None
        assert result.size_style is None

    def test_extended_fields_flattened_when_present(self):
        industry = {
            "rankings": [{"etf": "XBI", "industry": "Biotech", "score": 0.033}],
            "rotations": [{"etf": "XBI", "industry": "Biotech",
                           "direction": "into", "rank_change": 6}],
            "missing": ["UFO"],
        }
        size_style = {"iwm": {"label": "small_cap", "composite": 0.013},
                      "mdy": {"label": "mid_cap", "composite": 0.005},
                      "tag": "small_caps_leading"}
        row = _make_row(industryRankings=industry, sizeStyle=size_style)
        result = outlook_row_to_response(row)
        assert result.industry_rankings == industry["rankings"]
        assert result.industry_rotations == industry["rotations"]
        assert result.industry_missing == ["UFO"]
        assert result.size_style == size_style

    def test_extended_fields_none_when_columns_null(self):
        row = _make_row(industryRankings=None, sizeStyle=None)
        result = outlook_row_to_response(row)
        assert result.industry_rankings is None
        assert result.size_style is None

    def test_theme_fields_included_when_present(self):
        theme = {
            "rankings": [{"slug": "photonics", "theme": "Photonics", "score": 0.02,
                          "rank_1m": 1, "rank_3m": 2, "rank_6m": 2, "rs_1m": 0.01,
                          "rs_3m": 0.02, "rs_6m": 0.03, "rank_change": 1, "etf": "photonics",
                          "confidence": 0.8, "constituent_count": 7}],
            "rotations": [], "missing": [], "history": {"photonics": []},
        }
        row = _make_row(themeRankings=theme)
        result = outlook_row_to_response(row)
        assert result.theme_rankings[0]["slug"] == "photonics"
        assert result.theme_rotations == []
        assert result.theme_missing == []
        assert result.theme_history == {"photonics": []}

    def test_theme_fields_none_for_legacy_rows(self):
        """Rows created before Phase 3B have no themeRankings attr."""
        result = outlook_row_to_response(_make_row())
        assert result.theme_rankings is None
        assert result.theme_rotations is None
        assert result.theme_missing is None
        assert result.theme_history is None

    def test_survives_partial_theme_blob(self):
        """A drifted/partial theme blob missing keys must not raise KeyError."""
        row = _make_row(themeRankings={"rankings": []})
        result = outlook_row_to_response(row)
        assert result.theme_rankings == []
        assert result.theme_rotations is None
        assert result.theme_missing is None
        assert result.theme_history is None

    def test_survives_partial_industry_blob(self):
        """3A rider: a drifted/partial industry blob missing keys must not raise KeyError."""
        row = _make_row(industryRankings={"rankings": []})
        result = outlook_row_to_response(row)
        assert result.industry_rankings == []
        assert result.industry_rotations is None
        assert result.industry_missing is None


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


# ── Phase 3B: engine report journal ─────────────────────────────────────────

def _make_report_row(**overrides) -> SimpleNamespace:
    """Build a fake Prisma EngineReport row (camelCase attrs)."""
    defaults = dict(
        id="r1",
        createdAt=datetime(2026, 7, 9, tzinfo=timezone.utc),
        type="membership_change",
        severity="info",
        source="theme_delta_weekly",
        title="t",
        body={"a": 1},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestEngineReportRowToResponse:
    def test_maps_camel_to_snake(self):
        from api.routes.autopilot import engine_report_row_to_response

        row = _make_report_row()
        resp = engine_report_row_to_response(row)
        assert resp.type == "membership_change"
        assert resp.body == {"a": 1}
        assert resp.id == "r1"
        assert resp.severity == "info"
        assert resp.source == "theme_delta_weekly"
        assert resp.title == "t"


class TestGetEngineReportsEndpoint:
    def test_returns_200_newest_first(self):
        newer = _make_report_row(id="r2", createdAt=datetime(2026, 7, 9, tzinfo=timezone.utc))
        older = _make_report_row(id="r1", createdAt=datetime(2026, 7, 8, tzinfo=timezone.utc))
        app = _make_app()
        app.dependency_overrides[require_admin] = lambda: MagicMock(is_admin=True)

        mock_db = MagicMock()
        mock_db.enginereport.find_many = AsyncMock(return_value=[newer, older])

        with patch(
            "api.routes.autopilot.get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            client = TestClient(app)
            resp = client.get("/api/autopilot/reports")

        assert resp.status_code == 200
        data = resp.json()
        assert [row["id"] for row in data] == ["r2", "r1"]
        _, kwargs = mock_db.enginereport.find_many.call_args
        assert kwargs["order"] == {"createdAt": "desc"}
        # Neither type nor severity supplied → empty where dict collapses to None
        assert kwargs["where"] is None

    def test_passes_type_and_severity_filters_into_where(self):
        app = _make_app()
        app.dependency_overrides[require_admin] = lambda: MagicMock(is_admin=True)

        mock_db = MagicMock()
        mock_db.enginereport.find_many = AsyncMock(return_value=[])

        with patch(
            "api.routes.autopilot.get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            client = TestClient(app)
            resp = client.get(
                "/api/autopilot/reports",
                params={"type": "breaker_event", "severity": "critical"},
            )

        assert resp.status_code == 200
        _, kwargs = mock_db.enginereport.find_many.call_args
        assert kwargs["where"] == {"type": "breaker_event", "severity": "critical"}

    def test_clamps_take_to_max_200(self):
        app = _make_app()
        app.dependency_overrides[require_admin] = lambda: MagicMock(is_admin=True)

        mock_db = MagicMock()
        mock_db.enginereport.find_many = AsyncMock(return_value=[])

        with patch(
            "api.routes.autopilot.get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            client = TestClient(app)
            resp = client.get("/api/autopilot/reports", params={"limit": 9999})

        assert resp.status_code == 200
        _, kwargs = mock_db.enginereport.find_many.call_args
        assert kwargs["take"] == 200

    def test_clamps_take_to_min_1(self):
        app = _make_app()
        app.dependency_overrides[require_admin] = lambda: MagicMock(is_admin=True)

        mock_db = MagicMock()
        mock_db.enginereport.find_many = AsyncMock(return_value=[])

        with patch(
            "api.routes.autopilot.get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            client = TestClient(app)
            resp = client.get("/api/autopilot/reports", params={"limit": 0})

        assert resp.status_code == 200
        _, kwargs = mock_db.enginereport.find_many.call_args
        assert kwargs["take"] == 1

# ── Phase 2: broker link / status / resume ──────────────────────────────────

def _admin_app() -> FastAPI:
    """Minimal FastAPI app with only autopilot.router, admin override included."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id="admin1", is_admin=True)
    return app


def _patch_db(db=None):
    """Patch autopilot's get_db. Pass a preconfigured `db` MagicMock when a
    test needs specific attributes/awaitables (e.g. db.sleevesnapshot.find_first);
    otherwise falls back to a bare MagicMock for tests that never touch db."""
    return patch(
        "api.routes.autopilot.get_db",
        new=AsyncMock(return_value=db if db is not None else MagicMock()),
    )


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

    def test_status_linked_with_active_sleeve_and_snapshot(self):
        app = _admin_app()
        snapshot = SimpleNamespace(
            snapshotDate=datetime(2026, 7, 9, tzinfo=timezone.utc),
            sleeve="B",
            equity=31000.0,
            spyClose=605.0,
        )
        db = MagicMock()
        db.sleevesnapshot.find_first = AsyncMock(return_value=snapshot)

        def _sleeve_state(_db, sleeve):
            if sleeve == "A":
                return None
            return SimpleNamespace(status="active", statusReason=None, cashBalance=9000.0)

        with _patch_db(db=db), \
             patch("api.routes.autopilot.get_active_alpaca_account",
                   new=AsyncMock(return_value=SimpleNamespace(provider="alpaca", mode="paper"))), \
             patch("api.routes.autopilot.get_sleeve_state",
                   new=AsyncMock(side_effect=_sleeve_state)):
            resp = TestClient(app).get("/api/autopilot/broker/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["linked"] is True
        assert data["provider"] == "alpaca"
        assert data["mode"] == "paper"
        assert data["sleeves"] == [
            {"sleeve": "B", "status": "active", "status_reason": None, "cash_balance": 9000.0}
        ]
        assert data["latest_snapshot"] == {
            "date": "2026-07-09T00:00:00+00:00",
            "sleeve": "B",
            "equity": 31000.0,
            "spy_close": 605.0,
        }


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

    def test_resume_uninitialized_sleeve_404(self):
        app = _admin_app()
        with _patch_db(), \
             patch("api.routes.autopilot.get_sleeve_state",
                   new=AsyncMock(return_value=None)), \
             patch("api.routes.autopilot.set_sleeve_status", new=AsyncMock()) as setter:
            resp = TestClient(app).post("/api/autopilot/sleeve/B/resume")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Sleeve not initialized"
        setter.assert_not_awaited()


# ── Monday batch audit trail ────────────────────────────────────────────────

BATCH_RUN_DATE = datetime(2026, 7, 13, tzinfo=timezone.utc)


def _make_batch_run_row(**overrides) -> SimpleNamespace:
    defaults = dict(
        id="run1",
        runDate=BATCH_RUN_DATE,
        status="completed",
        abortReason=None,
        universeSize=191,
        advancedCount=23,
        watchlistExtras=3,
        quantStored=22,
        quantFailed=1,
        escalationSwarm=3,
        escalationReuse=2,
        escalationHold=17,
        swarmCap=5,
        outcomes={"AAPL": "full"},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_signal_row(**overrides) -> SimpleNamespace:
    defaults = dict(
        ticker="AAPL",
        tier="full",
        verdict="buy",
        screenerScore=8.2,
        escalationScore=3.1,
        escalationReasons=["prior_buy", "post_earnings"],
        quantSignals={"has_insider_buying": True},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestBatchRunRowToSummary:
    def test_maps_camel_to_snake(self):
        row = _make_batch_run_row()
        result = batch_run_row_to_summary(row)
        assert isinstance(result, WeeklyBatchRunSummary)
        assert result.id == "run1"
        assert result.run_date == BATCH_RUN_DATE
        assert result.status == "completed"
        assert result.universe_size == 191
        assert result.advanced_count == 23
        assert result.watchlist_extras == 3
        assert result.quant_stored == 22
        assert result.quant_failed == 1
        assert result.escalation_swarm == 3
        assert result.escalation_reuse == 2
        assert result.escalation_hold == 17
        assert result.swarm_cap == 5

    def test_aborted_row(self):
        row = _make_batch_run_row(
            status="aborted", abortReason="empty_candidates",
            advancedCount=0, quantStored=None, escalationSwarm=None,
        )
        result = batch_run_row_to_summary(row)
        assert result.status == "aborted"
        assert result.abort_reason == "empty_candidates"
        assert result.quant_stored is None


class TestBatchRunRowToDetail:
    def test_includes_outcomes_and_signals(self):
        row = _make_batch_run_row()
        signal_rows = [_make_signal_row(), _make_signal_row(ticker="MSFT", tier="quant", verdict=None)]
        result = batch_run_row_to_detail(row, signal_rows)
        assert isinstance(result, WeeklyBatchRunDetail)
        assert result.outcomes == {"AAPL": "full"}
        assert len(result.signals) == 2
        assert result.signals[0].ticker == "AAPL"
        assert result.signals[0].escalation_reasons == ["prior_buy", "post_earnings"]
        assert result.signals[1].tier == "quant"
        assert result.signals[1].verdict is None


class TestGetBatchRunsEndpoint:
    def test_returns_summaries_newest_first(self):
        newer = _make_batch_run_row(id="run2", runDate=datetime(2026, 7, 13, tzinfo=timezone.utc))
        older = _make_batch_run_row(id="run1", runDate=datetime(2026, 7, 6, tzinfo=timezone.utc))
        app = _admin_app()
        mock_db = MagicMock()
        mock_db.weeklybatchrun.find_many = AsyncMock(return_value=[newer, older])
        with _patch_db(db=mock_db):
            resp = TestClient(app).get("/api/autopilot/batch-runs")
        assert resp.status_code == 200
        data = resp.json()
        assert [row["id"] for row in data] == ["run2", "run1"]

    def test_passes_limit_through(self):
        app = _admin_app()
        mock_db = MagicMock()
        mock_db.weeklybatchrun.find_many = AsyncMock(return_value=[])
        with _patch_db(db=mock_db):
            resp = TestClient(app).get("/api/autopilot/batch-runs", params={"limit": 4})
        assert resp.status_code == 200
        _, kwargs = mock_db.weeklybatchrun.find_many.call_args
        assert kwargs["take"] == 4


class TestGetBatchRunDetailEndpoint:
    def test_defaults_to_latest_when_no_run_date(self):
        row = _make_batch_run_row()
        app = _admin_app()
        mock_db = MagicMock()
        mock_db.weeklybatchrun.find_first = AsyncMock(return_value=row)
        mock_db.weeklysignal.find_many = AsyncMock(return_value=[_make_signal_row()])
        with _patch_db(db=mock_db):
            resp = TestClient(app).get("/api/autopilot/batch-runs/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "run1"
        assert data["signals"][0]["ticker"] == "AAPL"
        _, kwargs = mock_db.weeklybatchrun.find_first.call_args
        assert kwargs["order"] == {"runDate": "desc"}

    def test_looks_up_specific_run_date(self):
        row = _make_batch_run_row()
        app = _admin_app()
        mock_db = MagicMock()
        mock_db.weeklybatchrun.find_first = AsyncMock(return_value=row)
        mock_db.weeklysignal.find_many = AsyncMock(return_value=[])
        with _patch_db(db=mock_db):
            resp = TestClient(app).get(
                "/api/autopilot/batch-runs/detail",
                params={"run_date": "2026-07-13T00:00:00+00:00"},
            )
        assert resp.status_code == 200
        _, kwargs = mock_db.weeklybatchrun.find_first.call_args
        assert kwargs["where"] == {"runDate": BATCH_RUN_DATE}

    def test_returns_404_when_no_runs(self):
        app = _admin_app()
        mock_db = MagicMock()
        mock_db.weeklybatchrun.find_first = AsyncMock(return_value=None)
        with _patch_db(db=mock_db):
            resp = TestClient(app).get("/api/autopilot/batch-runs/detail")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "No batch run available yet"
