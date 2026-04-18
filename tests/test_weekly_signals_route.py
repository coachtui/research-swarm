"""Unit tests for weekly signals route business logic."""
import sys
import types
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

# Stub out prisma before any api.routes import triggers the Prisma client
# (prisma generate hasn't been run in this environment, so the real client
# raises RuntimeError on import).
_prisma_stub = types.ModuleType("prisma")
_prisma_stub.Prisma = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("prisma", _prisma_stub)

from api.models.weekly_signals import WeeklySignalPublic, WeeklySignalFull


# ── Shared fixtures ──────────────────────────────────────────────────────────

RUN_DATE = datetime(2026, 4, 13, tzinfo=timezone.utc)


def _make_signal(ticker: str, verdict: str = "buy", screener_score: float = 5.0) -> MagicMock:
    """Build a mock Prisma WeeklySignal object."""
    s = MagicMock()
    s.ticker = ticker
    s.verdict = verdict
    s.fairValueGapPct = 15.5
    s.synthesisSummary = f"{ticker} thesis"
    s.runDate = RUN_DATE
    s.currentPrice = 100.0
    s.screenerScore = screener_score
    s.esChangePct = 1.2
    s.nqChangePct = 2.3
    s.dowChangePct = 0.8
    s.priorVerdict = "hold"
    s.fairValue = 115.5
    s.evProbability = 0.72
    s.stopLossProbability = 0.12
    s.insiderScore = 7.0
    s.darkPoolScore = 5.5
    s.sentimentScore = 6.0
    s.catalystSummary = "Strong earnings"
    s.positionSizeRec = "2.5% initial"
    s.priorEvProbability = 0.60
    return s


# ── Import helpers under test (written in Task 3) ────────────────────────────

from api.routes.weekly_signals import (
    _shape_public,
    _shape_full,
    _is_starter_plus,
    _compute_track_record_stats,
)


class TestShapePublic:
    def test_maps_camel_to_snake(self):
        signal = _make_signal("AAPL")
        result = _shape_public(signal)
        assert isinstance(result, WeeklySignalPublic)
        assert result.ticker == "AAPL"
        assert result.fair_value_gap_pct == 15.5
        assert result.synthesis_summary == "AAPL thesis"

    def test_does_not_include_ev_probability(self):
        signal = _make_signal("AAPL")
        result = _shape_public(signal)
        assert not hasattr(result, "ev_probability") or result.__class__ is WeeklySignalPublic


class TestShapeFull:
    def test_includes_ev_probability(self):
        signal = _make_signal("NVDA")
        result = _shape_full(signal)
        assert isinstance(result, WeeklySignalFull)
        assert result.ev_probability == 0.72
        assert result.stop_loss_probability == 0.12
        assert result.insider_score == 7.0

    def test_includes_catalyst_summary(self):
        signal = _make_signal("NVDA")
        result = _shape_full(signal)
        assert result.catalyst_summary == "Strong earnings"


class TestIsStarterPlus:
    def test_none_user_is_not_starter_plus(self):
        assert _is_starter_plus(None) is False

    def test_free_tier_is_not_starter_plus(self):
        user = MagicMock()
        user.tier = "free"
        user.is_admin = False
        assert _is_starter_plus(user) is False

    def test_starter_is_starter_plus(self):
        user = MagicMock()
        user.tier = "starter"
        assert _is_starter_plus(user) is True

    def test_investor_is_starter_plus(self):
        user = MagicMock()
        user.tier = "investor"
        assert _is_starter_plus(user) is True

    def test_trader_is_starter_plus(self):
        user = MagicMock()
        user.tier = "trader"
        assert _is_starter_plus(user) is True

    def test_admin_is_starter_plus(self):
        user = MagicMock()
        user.tier = "free"
        user.is_admin = True
        assert _is_starter_plus(user) is True


class TestComputeTrackRecordStats:
    def test_counts_verdicts(self):
        signals = [
            _make_signal("A", verdict="buy"),
            _make_signal("B", verdict="buy"),
            _make_signal("C", verdict="hold"),
            _make_signal("D", verdict="avoid"),
            _make_signal("E", verdict="buy"),
        ]
        stats = _compute_track_record_stats(signals)
        assert stats.analyzed == 5
        assert stats.buy == 3
        assert stats.hold == 1
        assert stats.avoid == 1

    def test_handles_empty(self):
        stats = _compute_track_record_stats([])
        assert stats.analyzed == 0
        assert stats.buy == 0
