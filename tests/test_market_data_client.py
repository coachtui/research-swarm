"""calculate_return must never hand a non-finite float across a JSON boundary.

Inngest's Go executor rejects bare NaN/Infinity with "invalid character 'N'
looking for beginning of value", which killed the 2026-07-27 weekly batch.
Nothing in Python catches it: numpy.float64 is a float SUBCLASS, so json.dumps
serializes it silently, and `x is not None` passes for NaN.
"""
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
