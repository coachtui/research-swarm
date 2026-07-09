"""Tests for execution/market_data.py with MarketDataClient mocked."""
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from execution.constants import SECTOR_ETFS
from execution.market_data import OutlookDataError, fetch_market_history


def _df(days: int = 260) -> pd.DataFrame:
    return pd.DataFrame({"Close": 100.0 * (1.0005) ** np.arange(days)})


def test_fetch_returns_close_series_for_all_tickers():
    with patch("execution.market_data.MarketDataClient") as MockClient:
        MockClient.return_value.get_historical_data.return_value = _df()
        closes = fetch_market_history()
    for ticker in list(SECTOR_ETFS) + ["SPY", "RSP", "^VIX"]:
        assert ticker in closes
        assert isinstance(closes[ticker], pd.Series)


def test_missing_spy_raises():
    def fake(ticker, period="1y"):
        return None if ticker == "SPY" else _df()
    with patch("execution.market_data.MarketDataClient") as MockClient:
        MockClient.return_value.get_historical_data.side_effect = fake
        with pytest.raises(OutlookDataError):
            fetch_market_history()


def test_too_many_missing_etfs_raises():
    missing = {"XLK", "XLE", "XLF", "XLV"}  # 4 > 3 allowed
    def fake(ticker, period="1y"):
        return None if ticker in missing else _df()
    with patch("execution.market_data.MarketDataClient") as MockClient:
        MockClient.return_value.get_historical_data.side_effect = fake
        with pytest.raises(OutlookDataError):
            fetch_market_history()


def test_missing_vix_and_rsp_tolerated():
    def fake(ticker, period="1y"):
        return None if ticker in {"^VIX", "RSP"} else _df()
    with patch("execution.market_data.MarketDataClient") as MockClient:
        MockClient.return_value.get_historical_data.side_effect = fake
        closes = fetch_market_history()
    assert "^VIX" not in closes and "RSP" not in closes
    assert "SPY" in closes


def test_fetch_history_for_returns_only_available_tickers():
    from execution.market_data import fetch_history_for

    def fake(ticker, period="1y"):
        return None if ticker == "XBI" else _df()

    with patch("execution.market_data.MarketDataClient") as MockClient:
        MockClient.return_value.get_historical_data.side_effect = fake
        closes = fetch_history_for(["XBI", "SMH", "IWM"])

    assert set(closes) == {"SMH", "IWM"}
    assert isinstance(closes["SMH"], pd.Series)


def test_fetch_history_for_never_raises_on_all_missing():
    from execution.market_data import fetch_history_for

    with patch("execution.market_data.MarketDataClient") as MockClient:
        MockClient.return_value.get_historical_data.return_value = None
        assert fetch_history_for(["XBI", "SMH"]) == {}
