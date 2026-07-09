"""Tests for compute_extended_signals / compute_theme_rankings_payload in
inngest_app/functions/weekly_outlook.py."""
import numpy as np
import pandas as pd

from execution.constants import INDUSTRY_ETFS
from inngest_app.functions.weekly_outlook import compute_extended_signals


def _series(daily_return: float, days: int = 260, start: float = 100.0) -> pd.Series:
    return pd.Series(start * (1 + daily_return) ** np.arange(days))


def _full_closes():
    closes = {"SPY": _series(0.0004), "IWM": _series(0.0008), "MDY": _series(0.0005)}
    for i, t in enumerate(INDUSTRY_ETFS):
        closes[t] = _series(0.0001 * (i + 1))
    return closes


def test_both_passes_succeed():
    result, failures = compute_extended_signals(_full_closes())
    assert result["industry"] is not None
    assert len(result["industry"]["rankings"]) == 19
    assert result["size_style"] is not None
    assert result["size_style"]["tag"] in {
        "small_caps_leading", "large_caps_leading", "mixed",
    }
    assert failures == []


def test_industry_failure_degrades_but_size_style_survives():
    closes = _full_closes()
    for t in list(INDUSTRY_ETFS)[:6]:  # only 13 industries left < 15
        del closes[t]
    result, failures = compute_extended_signals(closes)
    assert result["industry"] is None
    assert result["size_style"] is not None
    assert len(failures) == 1
    assert "industry" in failures[0][0].lower()


def test_size_style_failure_degrades_but_industry_survives():
    closes = _full_closes()
    del closes["IWM"]
    result, failures = compute_extended_signals(closes)
    assert result["industry"] is not None
    assert result["size_style"] is None
    assert len(failures) == 1
    assert "size/style" in failures[0][0].lower()


def test_total_failure_degrades_both_and_never_raises():
    result, failures = compute_extended_signals({})
    assert result == {"industry": None, "size_style": None}
    assert len(failures) == 2


# ── compute_theme_rankings_payload (Phase 3B theme pass) ─────────────────────

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from inngest_app.functions.weekly_outlook import compute_theme_rankings_payload


def _theme_row(slug, tickers, active=True):
    return SimpleNamespace(
        slug=slug, name=slug.title(), confidence=0.7,
        constituents=[SimpleNamespace(ticker=t, status="active" if active else "removed")
                      for t in tickers],
    )


def _db_returning(rows):
    db = MagicMock()
    db.themebasket.find_many = AsyncMock(return_value=rows)
    return db


@pytest.mark.asyncio
async def test_theme_payload_success_returns_rank_themes_output(monkeypatch):
    spy = _series(0.0004)
    closes = {"AAA": _series(0.0008), "BBB": _series(0.0006)}
    sentinel = {"rankings": [{"etf": "photonics"}], "rotations": [],
                "missing": [], "history": {}}
    captured = {}

    def fake_rank_themes(themes, closes_arg, spy_arg):
        captured["themes"] = themes
        captured["closes"] = closes_arg
        captured["spy"] = spy_arg
        return sentinel

    monkeypatch.setattr("execution.market_data.fetch_closes_batch",
                        lambda tickers: closes)
    monkeypatch.setattr("execution.market_data.fetch_history_for",
                        lambda tickers: {"SPY": spy})
    monkeypatch.setattr("execution.indicators.theme_strength.rank_themes",
                        fake_rank_themes)

    db = _db_returning([_theme_row("photonics", ["AAA", "BBB"])])
    result = await compute_theme_rankings_payload(db)

    assert result == sentinel
    assert captured["themes"] == [{"slug": "photonics", "name": "Photonics",
                                   "confidence": 0.7, "tickers": ["AAA", "BBB"]}]
    assert captured["closes"] is closes
    assert captured["spy"] is spy
    kwargs = db.themebasket.find_many.call_args.kwargs
    assert kwargs["where"] == {"status": "active"}
    assert kwargs["include"] == {"constituents": True}


@pytest.mark.asyncio
async def test_theme_payload_pre_discovery_returns_none_without_fetching(monkeypatch):
    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("market data must not be fetched pre-discovery")

    monkeypatch.setattr("execution.market_data.fetch_closes_batch", _must_not_be_called)
    monkeypatch.setattr("execution.market_data.fetch_history_for", _must_not_be_called)

    # Seed themes exist but have no ACTIVE constituents yet.
    db = _db_returning([_theme_row("photonics", ["AAA"], active=False),
                        _theme_row("gas-turbines", [])])
    assert await compute_theme_rankings_payload(db) is None


@pytest.mark.asyncio
async def test_theme_payload_raises_when_spy_missing(monkeypatch):
    monkeypatch.setattr("execution.market_data.fetch_closes_batch",
                        lambda tickers: {"AAA": _series(0.0008)})
    monkeypatch.setattr("execution.market_data.fetch_history_for",
                        lambda tickers: {})  # no SPY

    db = _db_returning([_theme_row("photonics", ["AAA", "BBB"])])
    with pytest.raises(RuntimeError, match="SPY history unavailable"):
        await compute_theme_rankings_payload(db)
