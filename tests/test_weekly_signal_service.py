"""Tests for WeeklySignalService — extraction, storage, and alert diffing."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from api.services.weekly_signal_service import WeeklySignalService, extract_signals_from_result


SAMPLE_RESULT = {
    "status": "completed",
    "verdict": "buy",
    "fair_value": 213.50,
    "current_price": 175.20,
    "ev_probability": 0.72,
    "stop_probability": 0.15,
    "insider_score": 7.2,
    "dark_pool_score": 5.8,
    "sentiment_score": 6.5,
    "investment_thesis": "Apple's services segment is accelerating revenue per device. "
                         "Management buyback program reduces float aggressively. "
                         "Key risk: China sales represent 19% of revenue.",
    "catalyst_summary": "Services growth, buyback acceleration",
    "position_size": "2.5% initial",
    "moat_score": 7.8,
}


class TestExtractSignalsFromResult:
    def test_extracts_verdict(self):
        signals = extract_signals_from_result(SAMPLE_RESULT, ticker="AAPL")
        assert signals["verdict"] == "buy"

    def test_extracts_fair_value_gap(self):
        signals = extract_signals_from_result(SAMPLE_RESULT, ticker="AAPL")
        # (213.50 - 175.20) / 175.20 * 100 = ~21.8%
        assert signals["fair_value_gap_pct"] is not None
        assert abs(signals["fair_value_gap_pct"] - 21.8) < 0.5

    def test_extracts_ev_probability(self):
        signals = extract_signals_from_result(SAMPLE_RESULT, ticker="AAPL")
        assert signals["ev_probability"] == 0.72

    def test_extracts_stop_loss_probability(self):
        signals = extract_signals_from_result(SAMPLE_RESULT, ticker="AAPL")
        assert signals["stop_loss_probability"] == 0.15

    def test_extracts_synthesis_as_first_two_sentences(self):
        signals = extract_signals_from_result(SAMPLE_RESULT, ticker="AAPL")
        summary = signals["synthesis_summary"]
        assert summary is not None
        assert len(summary) < len(SAMPLE_RESULT["investment_thesis"])
        assert "services segment" in summary

    def test_handles_missing_fields_gracefully(self):
        minimal = {"status": "completed", "verdict": "hold"}
        signals = extract_signals_from_result(minimal, ticker="AAPL")
        assert signals["verdict"] == "hold"
        assert signals["fair_value_gap_pct"] is None
        assert signals["ev_probability"] is None

    def test_handles_failed_result(self):
        failed = {"status": "failed", "error_message": "timeout"}
        signals = extract_signals_from_result(failed, ticker="AAPL")
        assert signals is None


class TestWeeklySignalService:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.weeklysignal = MagicMock()
        db.weeklysignal.create = AsyncMock()
        db.weeklysignal.find_first = AsyncMock(return_value=None)
        return db

    @pytest.fixture
    def market_context(self):
        from api.services.market_context_service import MarketContext
        return MarketContext(es_change_pct=1.2, nq_change_pct=2.3, dow_change_pct=0.8)

    @pytest.mark.asyncio
    async def test_store_signal_creates_db_record(self, mock_db, market_context):
        service = WeeklySignalService(db=mock_db)
        await service.store_signal(
            ticker="AAPL",
            result=SAMPLE_RESULT,
            run_date=datetime(2026, 4, 13, tzinfo=timezone.utc),
            screener_score=4.5,
            market_context=market_context,
        )
        mock_db.weeklysignal.create.assert_called_once()
        call_data = mock_db.weeklysignal.create.call_args[1]["data"]
        assert call_data["ticker"] == "AAPL"
        assert call_data["verdict"] == "buy"

    @pytest.mark.asyncio
    async def test_store_signal_includes_market_context(self, mock_db, market_context):
        service = WeeklySignalService(db=mock_db)
        await service.store_signal(
            ticker="AAPL",
            result=SAMPLE_RESULT,
            run_date=datetime(2026, 4, 13, tzinfo=timezone.utc),
            screener_score=4.5,
            market_context=market_context,
        )
        call_data = mock_db.weeklysignal.create.call_args[1]["data"]
        assert call_data["esChangePct"] == 1.2
        assert call_data["nqChangePct"] == 2.3

    @pytest.mark.asyncio
    async def test_prior_week_verdict_is_attached_when_present(self, mock_db, market_context):
        prior = MagicMock()
        prior.verdict = "hold"
        prior.evProbability = 0.55
        mock_db.weeklysignal.find_first = AsyncMock(return_value=prior)

        service = WeeklySignalService(db=mock_db)
        await service.store_signal(
            ticker="AAPL",
            result=SAMPLE_RESULT,
            run_date=datetime(2026, 4, 13, tzinfo=timezone.utc),
            screener_score=4.5,
            market_context=market_context,
        )
        call_data = mock_db.weeklysignal.create.call_args[1]["data"]
        assert call_data["priorVerdict"] == "hold"
        assert call_data["priorEvProbability"] == 0.55

    @pytest.mark.asyncio
    async def test_skips_failed_result(self, mock_db, market_context):
        service = WeeklySignalService(db=mock_db)
        await service.store_signal(
            ticker="AAPL",
            result={"status": "failed"},
            run_date=datetime(2026, 4, 13, tzinfo=timezone.utc),
            screener_score=2.0,
            market_context=market_context,
        )
        mock_db.weeklysignal.create.assert_not_called()
