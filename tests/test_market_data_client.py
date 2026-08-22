"""calculate_return must never hand a non-finite float across a JSON boundary.

Inngest's Go executor rejects bare NaN/Infinity with "invalid character 'N'
looking for beginning of value", which killed the 2026-07-27 weekly batch.
Nothing in Python catches it: numpy.float64 is a float SUBCLASS, so json.dumps
serializes it silently, and `x is not None` passes for NaN.
"""
import importlib
import json
from unittest.mock import patch

import pandas as pd
import pytest

from research_swarm.data.market_data_client import MarketDataClient


def _return_for(closes):
    df = pd.DataFrame({"Close": closes})
    with patch.object(MarketDataClient, "get_historical_data", return_value=df):
        return MarketDataClient().calculate_return("TEST", days=7)


def test_normal_history_returns_percent_change():
    assert _return_for([100.0] * 7 + [110.0]) == pytest.approx(10.0)


def test_zero_start_price_returns_none_not_infinity():
    # numpy division by zero yields inf and raises NOTHING, so the existing
    # try/except never fires — this is the halted/illiquid-ticker path.
    assert _return_for([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]) is None


def test_nan_in_window_returns_none():
    assert _return_for([float("nan")] + [100.0] * 7) is None


def test_result_is_always_strict_json_serializable():
    for closes in ([0.0] + [1.0] * 7, [float("nan")] + [100.0] * 7, [100.0] * 8):
        json.dumps(_return_for(closes), allow_nan=False)


# ── Historical-data cache key ───────────────────────────────────────────────
#
# The daily bar frame for a ticker is only valid for the day it was fetched.
# A plain "{ticker}_hist_{period}" key with a 1-day TTL expires on a ROLLING
# 24h boundary, so a caller that runs a few seconds earlier than it did
# yesterday still gets a hit and reads yesterday's frame. The 21:15 UTC
# execution cron hit exactly that on 8 of 31 days in Jul-Aug 2026, storing the
# prior session's SPY close as the day's benchmark. Scoping the key to the UTC
# date makes the first fetch of each day a guaranteed miss.

def test_historical_cache_key_is_scoped_to_the_utc_date():
    from datetime import datetime, timezone

    # `import ... as mdc` would bind the SINGLETON instance, not the module:
    # research_swarm.data.__init__ does `from .market_data_client import
    # market_data_client`, and that name shadows the submodule in the package
    # namespace. importlib reads sys.modules and is immune to it.
    mdc = importlib.import_module("research_swarm.data.market_data_client")

    seen = []

    class _Cache:
        def get(self, namespace, key):
            seen.append((namespace, key))
            return None

        def set(self, *a, **k):
            pass

    class _Ticker:
        def __init__(self, symbol):
            pass

        def history(self, period):
            return pd.DataFrame(
                {"Close": [1.0]}, index=pd.to_datetime(["2026-08-21"])
            ).rename_axis("Date")

    with patch.object(mdc, "cache", _Cache()), \
         patch.object(mdc.yf, "Ticker", _Ticker), \
         patch.object(mdc.rate_limiter, "wait_if_needed", lambda api: None):
        MarketDataClient().get_historical_data("SPY", period="5d")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert seen == [("market_hist", f"SPY_hist_5d_{today}")]


def test_historical_cache_key_changes_with_the_day():
    """Yesterday's key and today's key are different strings — the property
    that makes a new session a guaranteed cache miss."""
    from datetime import datetime, timedelta, timezone

    # `import ... as mdc` would bind the SINGLETON instance, not the module:
    # research_swarm.data.__init__ does `from .market_data_client import
    # market_data_client`, and that name shadows the submodule in the package
    # namespace. importlib reads sys.modules and is immune to it.
    mdc = importlib.import_module("research_swarm.data.market_data_client")

    seen = []

    class _Cache:
        def get(self, namespace, key):
            seen.append(key)
            return None

        def set(self, *a, **k):
            pass

    class _Ticker:
        def __init__(self, symbol):
            pass

        def history(self, period):
            return pd.DataFrame({"Close": [1.0]}, index=pd.to_datetime(["2026-08-21"]))

    real_datetime = mdc.datetime

    class _FrozenDatetime(real_datetime):
        _now = real_datetime(2026, 8, 21, 21, 15, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls._now

    with patch.object(mdc, "cache", _Cache()), \
         patch.object(mdc.yf, "Ticker", _Ticker), \
         patch.object(mdc.rate_limiter, "wait_if_needed", lambda api: None), \
         patch.object(mdc, "datetime", _FrozenDatetime):
        MarketDataClient().get_historical_data("SPY", period="5d")
        _FrozenDatetime._now += timedelta(days=1)
        MarketDataClient().get_historical_data("SPY", period="5d")

    assert seen == ["SPY_hist_5d_2026-08-21", "SPY_hist_5d_2026-08-22"]
