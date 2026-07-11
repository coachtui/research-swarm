import numpy as np
import pandas as pd

from execution.market_data import dist_200wma


def _weekly(n, p0=100.0, rate=1.002):
    idx = pd.date_range("2019-01-04", periods=n, freq="W-FRI")
    return pd.Series(p0 * rate ** np.arange(n), index=idx)


def test_dist_200wma_computes_distance():
    closes = _weekly(260)
    d = dist_200wma(closes)
    sma = closes.rolling(200).mean().iloc[-1]
    assert abs(d - (closes.iloc[-1] / sma - 1.0)) < 1e-9


def test_dist_200wma_none_under_200_weeks():
    assert dist_200wma(_weekly(150)) is None
    assert dist_200wma(None) is None
