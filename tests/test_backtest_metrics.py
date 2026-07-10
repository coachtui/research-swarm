import math

import numpy as np
import pandas as pd
import pytest

from execution.backtest.metrics import (
    compute_metrics, trade_stats, yearly_log_outperformance,
)


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


def test_trade_stats_hand_computed():
    # flat 100k equity over 30 calendar days; buy 10@50 day2, sell 10@60
    # day10 (win, +100 realized), buy 10@50 day12, sell 10@40 day20 (loss,
    # -100 realized). See task write-up for the by-hand cash/exposure trace.
    idx = pd.date_range("2021-01-01", periods=30, freq="D")
    equity = pd.Series([100_000.0] * 30, index=idx)
    journal = [
        {"date": idx[2].date(), "side": "buy", "symbol": "AAA", "qty": 10, "price": 50.0},
        {"date": idx[10].date(), "side": "sell", "symbol": "AAA", "qty": 10, "price": 60.0},
        {"date": idx[12].date(), "side": "buy", "symbol": "AAA", "qty": 10, "price": 50.0},
        {"date": idx[20].date(), "side": "sell", "symbol": "AAA", "qty": 10, "price": 40.0},
        {"date": idx[5].date(), "side": "cancel", "symbol": "BBB", "qty": 5, "price": 10.0},
    ]
    stats = trade_stats(journal, equity, starting_cash=100_000.0)
    assert stats["win_rate"] == pytest.approx(0.5)
    # turnover = (600+400) / 100000 / (29/365.25), rounded to 4dp
    assert stats["turnover_annual"] == pytest.approx(365.25 / 2900, abs=1e-4)
    # avg_exposure = (2*0 + 8*0.005 + 2*(-0.001) + 8*0.004 + 10*0) / 30
    assert stats["avg_exposure"] == pytest.approx(0.0023333333, abs=1e-4)


def test_trade_stats_no_sells_win_rate_none():
    idx = pd.date_range("2021-01-01", periods=10, freq="D")
    equity = pd.Series([100_000.0] * 10, index=idx)
    journal = [{"date": idx[1].date(), "side": "buy", "symbol": "AAA",
                "qty": 10, "price": 50.0}]
    stats = trade_stats(journal, equity, starting_cash=100_000.0)
    assert stats["win_rate"] is None
