"""Tests for execution/market_data.py with MarketDataClient mocked."""
from datetime import date
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


def test_fetch_ohlcv_batch_empty_download_returns_empty():
    """A bare empty frame (e.g. total network failure yfinance swallows)
    must degrade to {} — not KeyError on the OHLCV column slice."""
    from execution.market_data import fetch_ohlcv_batch

    with patch("yfinance.download", return_value=pd.DataFrame()):
        assert fetch_ohlcv_batch(["AAPL"]) == {}


# ── latest_bar_date ─────────────────────────────────────────────────────────
#
# The daily cron uses this to answer "is the benchmark close I just fetched
# actually today's?" — the check that catches a stale cache hit before it is
# stored as a snapshot's spyClose and fed to the circuit breaker.

def test_latest_bar_date_reads_a_fresh_datetime_index():
    """The shape a live yfinance fetch returns."""
    from execution.market_data import latest_bar_date

    df = pd.DataFrame(
        {"Close": [100.0, 101.0]},
        index=pd.to_datetime(["2026-08-20", "2026-08-21"]),
    )
    assert latest_bar_date(df) == date(2026, 8, 21)


def test_latest_bar_date_reads_a_cached_date_column():
    """The shape a cache hit returns: the index was reset and the date
    round-tripped through JSON as a string column."""
    from execution.market_data import latest_bar_date

    df = pd.DataFrame({"Date": ["2026-08-20", "2026-08-21"], "Close": [100.0, 101.0]})
    assert latest_bar_date(df) == date(2026, 8, 21)


def test_latest_bar_date_is_none_when_the_frame_carries_no_date():
    """A bare RangeIndex means "unknown", never a guess — callers must be able
    to tell "not today" apart from "cannot tell", and only skip on the former."""
    from execution.market_data import latest_bar_date

    assert latest_bar_date(pd.DataFrame({"Close": [100.0, 101.0]})) is None


def test_latest_bar_date_handles_empty_and_none():
    from execution.market_data import latest_bar_date

    assert latest_bar_date(None) is None
    assert latest_bar_date(pd.DataFrame({"Close": []})) is None


def test_latest_bar_date_survives_an_unparseable_date_column():
    from execution.market_data import latest_bar_date

    df = pd.DataFrame({"Date": ["not-a-date"], "Close": [100.0]})
    assert latest_bar_date(df) is None
