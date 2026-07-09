"""Tests for execution/outlook_service.py (db mocked)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from execution.outlook_service import build_outlook_record, get_latest_outlook, store_outlook

RUN_DATE = datetime(2026, 7, 12, tzinfo=timezone.utc)

INDICATORS = {
    "rankings": [{"etf": "XLE", "sector": "Energy", "rs_1m": 0.03, "rs_3m": 0.02,
                  "rs_6m": 0.01, "rank_1m": 1, "rank_3m": 2, "rank_6m": 3,
                  "rank_change": 1, "score": 0.024}],
    "rotations": [],
    "breadth": {"pct_above_200dma": 63.6, "equal_weight_trend_3m": 0.8},
    "regime_mechanical": "neutral",
    "regime_inputs": {"spy_above_200dma": True, "vix_last": 21.0, "pct_above_200dma": 63.6},
}

STRATEGIST_OK = {"status": "ok", "regime_proposal": "risk_on", "conviction": 0.65,
                 "sector_comments": {"XLE": "leadership"}, "rotation_calls": [],
                 "reasoning": "Breadth improving."}


def test_build_record_applies_one_notch_override():
    record = build_outlook_record(RUN_DATE, INDICATORS, STRATEGIST_OK)
    assert record["regime"] == "risk_on"           # neutral -> risk_on = one notch, allowed
    assert record["regimeMechanical"] == "neutral"
    assert record["strategistOverride"] is True
    assert record["strategistStatus"] == "ok"
    assert record["conviction"] == 0.65
    assert record["sectorRankings"] == INDICATORS["rankings"]


def test_build_record_clamps_two_notch_proposal():
    indicators = {**INDICATORS, "regime_mechanical": "risk_off"}
    record = build_outlook_record(RUN_DATE, indicators, STRATEGIST_OK)  # proposes risk_on
    assert record["regime"] == "neutral"           # clamped to one notch
    assert record["strategistOverride"] is True


def test_build_record_fallback_keeps_mechanical_regime():
    fallback = {"status": "fallback", "regime_proposal": "neutral", "conviction": None,
                "sector_comments": {}, "rotation_calls": [],
                "reasoning": "Strategist unavailable (x); mechanical regime used."}
    record = build_outlook_record(RUN_DATE, INDICATORS, fallback)
    assert record["regime"] == "neutral"
    assert record["strategistOverride"] is False
    assert record["strategistStatus"] == "fallback"


@pytest.mark.asyncio
async def test_store_outlook_creates_row_with_json_fields():
    db = MagicMock()
    db.marketoutlook.create = AsyncMock(return_value="row")
    record = build_outlook_record(RUN_DATE, INDICATORS, STRATEGIST_OK)
    result = await store_outlook(db, record)
    assert result == "row"
    data = db.marketoutlook.create.call_args.kwargs["data"]
    assert data["regime"] == "risk_on"
    assert data["runDate"] == RUN_DATE


@pytest.mark.asyncio
async def test_get_latest_outlook_orders_by_run_date_desc():
    db = MagicMock()
    db.marketoutlook.find_first = AsyncMock(return_value="latest")
    assert await get_latest_outlook(db) == "latest"
    kwargs = db.marketoutlook.find_first.call_args.kwargs
    assert kwargs["order"] == {"runDate": "desc"}


INDUSTRY = {
    "rankings": [{"etf": "XBI", "industry": "Biotech", "rs_1m": 0.05, "rs_3m": 0.02,
                  "rs_6m": 0.01, "rank_1m": 1, "rank_3m": 4, "rank_6m": 5,
                  "rank_change": 3, "score": 0.033}],
    "rotations": [],
    "missing": ["UFO"],
}
SIZE_STYLE = {
    "iwm": {"label": "small_cap", "rs_1m": 0.02, "rs_3m": 0.01, "rs_6m": 0.0,
            "composite": 0.013},
    "mdy": {"label": "mid_cap", "rs_1m": 0.01, "rs_3m": 0.0, "rs_6m": 0.0,
            "composite": 0.005},
    "tag": "small_caps_leading",
}


def test_build_record_includes_extended_signals_when_present():
    indicators = {**INDICATORS, "industry": INDUSTRY, "size_style": SIZE_STYLE}
    record = build_outlook_record(RUN_DATE, indicators, STRATEGIST_OK)
    assert record["industryRankings"] == INDUSTRY
    assert record["sizeStyle"] == SIZE_STYLE


def test_build_record_extended_signals_default_to_none():
    record = build_outlook_record(RUN_DATE, INDICATORS, STRATEGIST_OK)
    assert record["industryRankings"] is None
    assert record["sizeStyle"] is None


@pytest.mark.asyncio
async def test_store_outlook_wraps_extended_json_only_when_present():
    db = MagicMock()
    db.marketoutlook.create = AsyncMock(return_value="row")

    indicators = {**INDICATORS, "industry": INDUSTRY, "size_style": SIZE_STYLE}
    await store_outlook(db, build_outlook_record(RUN_DATE, indicators, STRATEGIST_OK))
    data = db.marketoutlook.create.call_args.kwargs["data"]
    # prisma.Json is stubbed by conftest; assert the fields were wrapped (not raw dicts)
    assert data["industryRankings"] is not INDUSTRY
    assert data["sizeStyle"] is not SIZE_STYLE

    db.marketoutlook.create.reset_mock()
    await store_outlook(db, build_outlook_record(RUN_DATE, INDICATORS, STRATEGIST_OK))
    data = db.marketoutlook.create.call_args.kwargs["data"]
    assert "industryRankings" not in data
    assert "sizeStyle" not in data
