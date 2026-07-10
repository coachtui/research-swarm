import math

import numpy as np
import pandas as pd
import pytest

from execution.backtest.metrics import compute_metrics, yearly_log_outperformance


def _series(values, start="2020-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)))


def test_metrics_on_two_year_doubling():
    idx = pd.DatetimeIndex([pd.Timestamp("2020-01-01"), pd.Timestamp("2022-01-01")])
    m = compute_metrics(pd.Series([100.0, 200.0], index=idx))
    # 731 calendar days (2020 is a leap year), CAGR ≈ √2 − 1
    assert m["cagr"] == pytest.approx(2 ** (365.25 / 731) - 1, rel=1e-3)
    assert m["max_drawdown"] == 0.0


def test_max_drawdown_and_yearly_returns():
    idx = pd.DatetimeIndex(["2020-06-01", "2020-09-01", "2020-12-01", "2021-06-01"])
    m = compute_metrics(pd.Series([100.0, 150.0, 90.0, 120.0], index=idx))
    assert m["max_drawdown"] == pytest.approx(-0.4)          # 150 → 90
    assert m["yearly_returns"]["2020"] == pytest.approx(-0.10)  # 100 → 90
    assert m["yearly_returns"]["2021"] == pytest.approx(120.0 / 90.0 - 1)
    assert m["mar"] == pytest.approx(m["cagr"] / 0.4)


def test_sharpe_zero_vol_is_zero_and_positive_drift_positive():
    flat = compute_metrics(_series([100.0] * 50))
    assert flat["sharpe"] == 0.0
    # deterministic +0.2%/day drift with alternating +/-0.5% noise
    rets = [0.002 + (0.005 if i % 2 == 0 else -0.005) for i in range(500)]
    drift = 100 * np.cumprod(1 + np.array(rets))
    assert compute_metrics(_series(list(drift)))["sharpe"] > 0


def test_yearly_log_outperformance():
    a = _series([100, 110, 121], start="2020-12-30")   # spans year boundary
    b = _series([100, 100, 100], start="2020-12-30")
    out = yearly_log_outperformance(a, b)
    total = sum(out.values())
    assert total == pytest.approx(math.log(1.21), rel=1e-9)
    assert set(out) == {"2020", "2021"}
