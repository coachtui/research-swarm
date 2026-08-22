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


def _ohlcv_frame(symbols, days=3):
    """The MultiIndex shape yf.download returns for a multi-symbol request."""
    idx = pd.to_datetime([f"2026-08-{18 + i}" for i in range(days)])
    cols = pd.MultiIndex.from_product(
        [symbols, ["Open", "High", "Low", "Close", "Volume"]]
    )
    return pd.DataFrame(1.0, index=idx, columns=cols)


def test_fetch_ohlcv_batch_empty_download_returns_empty():
    """A bare empty frame (e.g. total network failure yfinance swallows)
    must degrade to {} — not KeyError on the OHLCV column slice."""
    from execution.market_data import fetch_ohlcv_batch

    with patch("yfinance.download", return_value=pd.DataFrame()), \
         patch("execution.market_data.time.sleep"):
        assert fetch_ohlcv_batch(["AAPL"]) == {}


# ── Rate-limit retry ────────────────────────────────────────────────────────
#
# yfinance answers a 429 by logging "N Failed downloads" and returning an empty
# frame WITHOUT raising, so the except inside the download never fires and the
# whole batch vanishes silently. That is how every Sleeve A holding lost its bar
# on 2026-08-20 and the day's snapshot was skipped.

def test_fetch_ohlcv_batch_retries_an_empty_batch_and_recovers():
    from execution.market_data import fetch_ohlcv_batch

    good = _ohlcv_frame(["NVDA", "MU"])
    attempts = [pd.DataFrame(), pd.DataFrame(), good]

    with patch("yfinance.download", side_effect=attempts) as dl, \
         patch("execution.market_data.time.sleep") as slept:
        out = fetch_ohlcv_batch(["NVDA", "MU"])

    assert sorted(out) == ["MU", "NVDA"]
    assert dl.call_count == 3
    assert slept.call_count == 2


def test_fetch_ohlcv_batch_gives_up_after_the_ladder():
    from execution.market_data import _OHLCV_RETRY_BACKOFF, fetch_ohlcv_batch

    with patch("yfinance.download", return_value=pd.DataFrame()) as dl, \
         patch("execution.market_data.time.sleep") as slept:
        assert fetch_ohlcv_batch(["NVDA", "MU"]) == {}

    assert dl.call_count == len(_OHLCV_RETRY_BACKOFF) + 1
    assert slept.call_count == len(_OHLCV_RETRY_BACKOFF)


def test_fetch_ohlcv_batch_does_not_retry_a_partial_batch():
    """One dead ticker among several is a data fact, not a rate limit. Paying
    the backoff for it would tax every run that includes a delisted name."""
    from execution.market_data import fetch_ohlcv_batch

    with patch("yfinance.download", return_value=_ohlcv_frame(["NVDA"])) as dl, \
         patch("execution.market_data.time.sleep") as slept:
        out = fetch_ohlcv_batch(["NVDA", "DEADTICKER"])

    assert sorted(out) == ["NVDA"]
    assert dl.call_count == 1
    assert slept.call_count == 0


def test_fetch_ohlcv_batch_retries_a_raising_download():
    from execution.market_data import fetch_ohlcv_batch

    with patch("yfinance.download",
               side_effect=[ConnectionError("boom"), _ohlcv_frame(["NVDA", "MU"])]) as dl, \
         patch("execution.market_data.time.sleep") as slept:
        out = fetch_ohlcv_batch(["NVDA", "MU"])

    assert sorted(out) == ["MU", "NVDA"]
    assert dl.call_count == 2
    assert slept.call_count == 1


def test_fetch_ohlcv_batch_never_sleeps_for_an_empty_symbol_list():
    from execution.market_data import fetch_ohlcv_batch

    with patch("yfinance.download") as dl, patch("execution.market_data.time.sleep") as slept:
        assert fetch_ohlcv_batch([]) == {}

    assert dl.call_count == 0
    assert slept.call_count == 0


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
