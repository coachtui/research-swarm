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


def _mock_db():
    db = MagicMock()
    db.weeklysignal.find_first = AsyncMock(return_value=None)
    db.weeklysignal.upsert = AsyncMock()
    db.weeklysignal.update = AsyncMock()
    db.stockresult.find_first = AsyncMock(return_value=None)
    return db


RUN_DATE = datetime(2026, 7, 13, tzinfo=timezone.utc)
MC = None  # Will be created per-test


class TestGetPriorContext:
    @pytest.mark.asyncio
    async def test_splits_any_tier_score_from_full_tier_verdict(self):
        from api.services.market_context_service import MarketContext
        db = _mock_db()
        prior_any = MagicMock(screenerScore=4.0)
        prior_full = MagicMock(verdict="buy", evProbability=0.7)
        db.weeklysignal.find_first = AsyncMock(side_effect=[prior_any, prior_full])
        service = WeeklySignalService(db=db)
        ctx = await service.get_prior_context("AAPL", before=RUN_DATE)
        assert ctx == {
            "prior_screener_score": 4.0,
            "prior_verdict": "buy",
            "prior_ev_probability": 0.7,
        }
        # second lookup must exclude verdict-less quant rows
        _, second_call = db.weeklysignal.find_first.call_args_list
        assert second_call.kwargs["where"]["verdict"] == {"not": None}

    @pytest.mark.asyncio
    async def test_no_history_returns_nones(self):
        service = WeeklySignalService(db=_mock_db())
        ctx = await service.get_prior_context("AAPL", before=RUN_DATE)
        assert ctx == {
            "prior_screener_score": None,
            "prior_verdict": None,
            "prior_ev_probability": None,
        }


class TestStoreQuantSnapshot:
    @pytest.mark.asyncio
    async def test_upserts_quant_row_with_continuity(self):
        from api.services.market_context_service import MarketContext
        db = _mock_db()
        MC = MarketContext(es_change_pct=1.0, nq_change_pct=2.0, dow_change_pct=0.5)
        service = WeeklySignalService(db=db)
        await service.store_quant_snapshot(
            ticker="AAPL", run_date=RUN_DATE, screener_score=5.5,
            current_price=175.2,
            quant_signals={"has_insider_buying": True},
            market_context=MC,
            prior_ctx={"prior_screener_score": 2.0, "prior_verdict": "buy",
                       "prior_ev_probability": 0.7},
        )
        kwargs = db.weeklysignal.upsert.call_args.kwargs
        assert kwargs["where"] == {
            "ticker_runDate": {"ticker": "AAPL", "runDate": RUN_DATE}
        }
        create = kwargs["data"]["create"]
        assert create["tier"] == "quant"
        assert create["verdict"] is None
        assert create["screenerScore"] == 5.5
        assert create["currentPrice"] == 175.2
        assert create["priorVerdict"] == "buy"
        assert create["priorEvProbability"] == 0.7
        assert create["esChangePct"] == 1.0


class TestRecordEscalation:
    @pytest.mark.asyncio
    async def test_updates_row_with_score_and_reasons(self):
        db = _mock_db()
        service = WeeklySignalService(db=db)
        await service.record_escalation(
            ticker="AAPL", run_date=RUN_DATE, score=5.5, reasons=["prior_buy"])
        kwargs = db.weeklysignal.update.call_args.kwargs
        assert kwargs["where"] == {
            "ticker_runDate": {"ticker": "AAPL", "runDate": RUN_DATE}
        }
        assert kwargs["data"]["escalationScore"] == 5.5


class TestUpgradeToFull:
    @pytest.mark.asyncio
    async def test_completed_result_updates_row_to_full(self):
        db = _mock_db()
        service = WeeklySignalService(db=db)
        ok = await service.upgrade_to_full(
            ticker="AAPL", run_date=RUN_DATE, result=SAMPLE_RESULT,
            escalation_score=5.5, escalation_reasons=["prior_buy"])
        assert ok is True
        kwargs = db.weeklysignal.update.call_args.kwargs
        data = kwargs["data"]
        assert data["tier"] == "full"
        assert data["verdict"] == "buy"
        assert data["fairValue"] == 213.50
        assert data["escalationScore"] == 5.5

    @pytest.mark.asyncio
    async def test_failed_result_returns_false_without_update(self):
        db = _mock_db()
        service = WeeklySignalService(db=db)
        ok = await service.upgrade_to_full(
            ticker="AAPL", run_date=RUN_DATE, result={"status": "failed"},
            escalation_score=5.5, escalation_reasons=[])
        assert ok is False
        db.weeklysignal.update.assert_not_awaited()


class TestFindFreshResult:
    @pytest.mark.asyncio
    async def test_returns_full_output_with_status_defaulted(self):
        db = _mock_db()
        row = MagicMock(fullOutput={"verdict": "buy"})
        db.stockresult.find_first = AsyncMock(return_value=row)
        service = WeeklySignalService(db=db)
        result = await service.find_fresh_result("AAPL")
        assert result == {"verdict": "buy", "status": "completed"}
        where = db.stockresult.find_first.call_args.kwargs["where"]
        assert where["ticker"] == "AAPL"
        assert where["status"] == "completed"
        assert "gte" in where["createdAt"]

    @pytest.mark.asyncio
    async def test_no_row_or_empty_output_returns_none(self):
        service = WeeklySignalService(db=_mock_db())
        assert await service.find_fresh_result("AAPL") is None
        db = _mock_db()
        db.stockresult.find_first = AsyncMock(return_value=MagicMock(fullOutput=None))
        assert await WeeklySignalService(db=db).find_fresh_result("AAPL") is None


# ── Live manager schema (2026-07, verified against stored NVDA full_output) ──

LIVE_RESULT = {
    "status": "completed",
    "ticker": "NVDA",
    "rating": "BUY",
    "rating_score": 7.2,
    "synthesis_narrative": "NVDA remains the dominant AI compute franchise. "
                           "Sovereign AI partnerships add a new demand leg. "
                           "Valuation is undemanding relative to growth.",
    "investment_thesis": {
        "key_risks": ["Technical breakdown risk"],
        "entry_strategy": "Scale in below $200",
        "company_overview": "NVIDIA designs GPUs.",
        "investment_highlights": ["AI leadership"],
        "recommendation_summary": "Buy on weakness. Thesis intact.",
        "valuation_signal_analysis": "Fair value above spot.",
    },
    "fair_value_calibration": {
        "internal_fair_value": 211.22,
        "consensus_target": 301.62,
    },
    "signal_breakdown": {
        "insider_score": 5.0,
        "dark_pool_score": 3.0,
        "news_score": 7.8,
        "stop_probability": {
            "effective_stop_probability_pct": 24.0,
            "base_stop_risk_pct": 25.0,
        },
        "portfolio_action": {
            "sizing_guidance": "Maintain existing position at 0.90x weight.",
            "allocation_bias": "Hold",
        },
    },
    "strategic_catalysts": [
        {"title": "Sovereign AI Partnership Expansion", "category": "Strategic Investment"},
        {"title": "AWS/Blackwell Hyperscaler Integration", "category": "Competitive Positioning"},
        {"title": "$20B Investment-Grade Bond Offering", "category": "Strategic Investment"},
        {"title": "Fourth Catalyst Beyond The Cap", "category": "Other"},
    ],
}


class TestExtractSignalsFromLiveSchema:
    def test_verdict_from_rating(self):
        signals = extract_signals_from_result(LIVE_RESULT, ticker="NVDA")
        assert signals["verdict"] == "buy"

    def test_sell_and_avoid_ratings_map_to_avoid(self):
        for rating in ("SELL", "AVOID", "Strong Sell"):
            result = dict(LIVE_RESULT, rating=rating)
            assert extract_signals_from_result(result, ticker="X")["verdict"] == "avoid"

    def test_fair_value_from_calibration(self):
        signals = extract_signals_from_result(LIVE_RESULT, ticker="NVDA")
        assert signals["fairValue"] == 211.22

    def test_stop_probability_from_effective_pct(self):
        signals = extract_signals_from_result(LIVE_RESULT, ticker="NVDA")
        assert signals["stop_loss_probability"] == 0.24

    def test_activity_scores_from_signal_breakdown(self):
        signals = extract_signals_from_result(LIVE_RESULT, ticker="NVDA")
        assert signals["insiderScore"] == 5.0
        assert signals["darkPoolScore"] == 3.0
        assert signals["sentimentScore"] == 7.8

    def test_synthesis_from_narrative_first_two_sentences(self):
        signals = extract_signals_from_result(LIVE_RESULT, ticker="NVDA")
        assert signals["synthesis_summary"] == (
            "NVDA remains the dominant AI compute franchise. "
            "Sovereign AI partnerships add a new demand leg."
        )

    def test_synthesis_falls_back_to_recommendation_summary(self):
        result = dict(LIVE_RESULT)
        result.pop("synthesis_narrative")
        signals = extract_signals_from_result(result, ticker="NVDA")
        assert signals["synthesis_summary"] == "Buy on weakness. Thesis intact."

    def test_catalysts_join_first_three_titles(self):
        signals = extract_signals_from_result(LIVE_RESULT, ticker="NVDA")
        assert signals["catalystSummary"] == (
            "Sovereign AI Partnership Expansion; "
            "AWS/Blackwell Hyperscaler Integration; "
            "$20B Investment-Grade Bond Offering"
        )

    def test_position_size_from_portfolio_action(self):
        signals = extract_signals_from_result(LIVE_RESULT, ticker="NVDA")
        assert signals["positionSizeRec"] == "Maintain existing position at 0.90x weight."

    def test_ev_probability_absent_stays_none(self):
        signals = extract_signals_from_result(LIVE_RESULT, ticker="NVDA")
        assert signals["ev_probability"] is None

    def test_current_price_absent_stays_none(self):
        signals = extract_signals_from_result(LIVE_RESULT, ticker="NVDA")
        assert signals["currentPrice"] is None

    def test_dict_fields_never_raise_strip_errors(self):
        # Regression: 2026-07-08 production failure — every field defensively coerced
        hostile = {"status": "completed", "rating": {"nested": "dict"},
                   "investment_thesis": {"unexpected": "shape"},
                   "signal_breakdown": "not-a-dict",
                   "strategic_catalysts": "not-a-list",
                   "fair_value_calibration": None}
        signals = extract_signals_from_result(hostile, ticker="X")
        assert signals is not None
        assert signals["verdict"] is None
        assert signals["synthesis_summary"] is None

    def test_old_schema_keys_still_win(self):
        merged = dict(LIVE_RESULT, verdict="hold", fair_value=99.0)
        signals = extract_signals_from_result(merged, ticker="X")
        assert signals["verdict"] == "hold"
        assert signals["fairValue"] == 99.0


# ── Paid-path wrapper (run_stock_analysis) — first-invoke incident 2026-07-10 ──
# run_stock_analysis returns {ticker, status, scores..., "full_output": {manager blob}}.
# extract_signals_from_result must unwrap full_output so the paid path and the
# reuse path (which feeds the blob directly) extract identically.

WRAPPER_RESULT = {
    "ticker": "LRCX",
    "status": "completed",
    "sentiment_score": 9.9,  # top-level decoy — must NOT be used when full_output present
    "full_output": {
        "rating": "BUY",
        "fair_value_calibration": {"internal_fair_value": 400.0},
        "signal_breakdown": {
            "insider_score": 7.0,
            "news_score": 6.0,
            "dark_pool_score": 5.5,
        },
        "synthesis_narrative": "Long thesis. Second sentence. Third.",
    },
}


class TestExtractSignalsFromWrapper:
    def test_unwraps_full_output_and_ignores_top_level_decoy(self):
        signals = extract_signals_from_result(WRAPPER_RESULT, ticker="LRCX")
        assert signals["verdict"] == "buy"
        assert signals["fairValue"] == 400.0
        assert signals["insiderScore"] == 7.0
        # decoy top-level sentiment_score=9.9 must be ignored in favor of the
        # blob's news_score — proves both paths extract from the same shape
        assert signals["sentimentScore"] == 6.0
        assert signals["synthesis_summary"] == "Long thesis. Second sentence."

    def test_blob_shaped_input_without_full_output_still_works(self):
        # Reuse path (StockResult.fullOutput fed directly) — pin against the
        # existing NVDA-style shape, must be unaffected by the unwrap change.
        signals = extract_signals_from_result(LIVE_RESULT, ticker="NVDA")
        assert signals["verdict"] == "buy"
        assert signals["fairValue"] == 211.22
        assert signals["insiderScore"] == 5.0

    def test_etf_wrapper_without_rating_behaves_as_before(self):
        etf_wrapper = {
            "ticker": "SPY",
            "status": "completed",
            "instrument_type": "ETF",
            "full_output": {
                "instrument_type": "ETF",
                "allocation_recommendation": "overweight",
            },
        }
        signals = extract_signals_from_result(etf_wrapper, ticker="SPY")
        assert signals is not None
        assert signals["verdict"] is None


class TestUpgradePreservesQuantPrice:
    @pytest.mark.asyncio
    async def test_missing_current_price_not_clobbered_and_gap_computed(self):
        db = _mock_db()
        db.weeklysignal.find_unique = AsyncMock(
            return_value=MagicMock(currentPrice=190.0)
        )
        service = WeeklySignalService(db=db)
        ok = await service.upgrade_to_full(
            ticker="NVDA", run_date=RUN_DATE, result=LIVE_RESULT,
            escalation_score=3.5, escalation_reasons=["outlook_sector"])
        assert ok is True
        data = db.weeklysignal.update.call_args.kwargs["data"]
        assert "currentPrice" not in data  # quant row's market price preserved
        # gap computed from quant row's price: (211.22-190)/190*100 ≈ 11.17
        assert abs(data["fairValueGapPct"] - 11.17) < 0.01
