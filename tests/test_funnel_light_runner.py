"""Light runner: numbers only, every source guarded, never raises."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from execution.funnel import light_runner as lr

RUN_DATE = datetime(2026, 7, 13, tzinfo=timezone.utc)
SCREEN = {"price": 20.0, "atr_pct": 0.04, "screen_score": 6.5,
          "liquidity_adv_usd": 5e6, "tags": {"themes": ["photonics"]}}


def test_sentiment_parses_score_line():
    assert lr.sentiment_from_headlines(["Up"], lambda p: "SCORE: 7.5") == 7.5
    assert lr.sentiment_from_headlines(["Up"], lambda p: "garbage") is None
    assert lr.sentiment_from_headlines([], lambda p: "SCORE: 9") is None  # no news → None, no LLM call


def test_light_run_survives_every_source_failing():
    with patch.object(lr, "_gather_market_numbers", side_effect=RuntimeError("boom")), \
         patch.object(lr, "_gather_flow_numbers", side_effect=RuntimeError("boom")), \
         patch.object(lr, "_gather_headlines", side_effect=RuntimeError("boom")):
        out = asyncio.get_event_loop().run_until_complete(
            lr.light_run_one("AEHR", SCREEN, llm_call=lambda p: "SCORE: 5")
        )
    assert out["ticker"] == "AEHR"
    assert out["current_price"] == 20.0          # screen price survives
    assert out["fair_value"] is None and out["insider_score"] is None
    assert out["sentiment_score"] is None


def test_light_run_survives_malformed_screen_row():
    """Self-review hardening: missing/invalid 'price' must not raise, matching the
    'always returns a dict, never raises' contract."""
    out = asyncio.get_event_loop().run_until_complete(
        lr.light_run_one("BADTICK", {"atr_pct": 0.04}, llm_call=lambda p: "SCORE: 5")
    )
    assert out["ticker"] == "BADTICK"
    assert out["current_price"] is None
    assert out["fair_value"] is None and out["sentiment_score"] is None


def test_persist_never_downgrades_full_row():
    db = MagicMock()
    db.weeklysignal.find_unique = AsyncMock(return_value=MagicMock(tier="full"))
    db.weeklysignal.upsert = AsyncMock()
    out = asyncio.get_event_loop().run_until_complete(
        lr.persist_light_signal(db, RUN_DATE, {"ticker": "NVDA"}, 6.5)
    )
    assert out == "kept_full"
    db.weeklysignal.upsert.assert_not_called()


def test_persist_upserts_engine_light():
    db = MagicMock()
    db.weeklysignal.find_unique = AsyncMock(return_value=None)
    db.weeklysignal.upsert = AsyncMock()
    light = {"ticker": "AEHR", "current_price": 20.0, "fair_value": 26.0,
             "fair_value_gap_pct": 30.0, "insider_score": 7.0, "dark_pool_score": None,
             "sentiment_score": 6.0, "market_cap": 4.2e8, "rsi14": 55.0,
             "short_pct_float": 0.03, "valuation_score": 6.0}
    out = asyncio.get_event_loop().run_until_complete(
        lr.persist_light_signal(db, RUN_DATE, light, 6.5)
    )
    assert out == "stored"
    kwargs = db.weeklysignal.upsert.call_args.kwargs
    assert kwargs["where"] == {"ticker_runDate": {"ticker": "AEHR", "runDate": RUN_DATE}}
    created = kwargs["data"]["create"]
    assert created["tier"] == "engine_light"
    assert created["verdict"] is None or "verdict" not in created  # verdicts belong to the manager
    assert created["currentPrice"] == 20.0 and created["fairValueGapPct"] == 30.0
