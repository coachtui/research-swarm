import numpy as np
import pandas as pd
import pytest

from execution.backtest.baselines import (
    equal_weight_universe, naive_momentum, spy_buy_hold,
)
from execution.backtest.simulator import BacktestConfig


def _make_df(closes, start="2019-01-01", vol=1_000_000):
    idx = pd.bdate_range(start, periods=len(closes))
    close = pd.Series(np.asarray(closes, dtype=float), index=idx)
    return pd.DataFrame({"Open": close.shift(1).fillna(close.iloc[0]),
                         "High": close * 1.01, "Low": close * 0.99,
                         "Close": close, "Volume": float(vol)}, index=idx)


CFG = BacktestConfig(start="2019-06-02", end="2020-06-01", starting_cash=100_000.0)


def _fixture():
    n = 400
    return {
        "AAA": _make_df(50 * 1.001 ** np.arange(n)),     # steady +0.1%/day
        "BBB": _make_df(np.full(n, 50.0)),               # flat
        "SPY": _make_df(300 * 1.0005 ** np.arange(n)),
    }


def test_spy_buy_hold_tracks_spy_exactly():
    data = _fixture()
    eq = spy_buy_hold(data, CFG)
    spy = data["SPY"].loc[CFG.start:CFG.end, "Close"]
    assert eq.iloc[0] == pytest.approx(100_000.0)
    assert eq.iloc[-1] / eq.iloc[0] == pytest.approx(spy.iloc[-1] / spy.iloc[0])


def test_equal_weight_is_mean_of_member_paths():
    # single-calendar-year window: no rebalance boundary, exact arithmetic
    data = _fixture()
    cfg1 = BacktestConfig(start="2019-04-15", end="2019-12-15",
                          starting_cash=100_000.0)
    eq = equal_weight_universe(data, cfg1)
    aaa = data["AAA"].loc[cfg1.start:cfg1.end, "Close"]
    ret_aaa = aaa.iloc[-1] / aaa.iloc[0] - 1.0
    # BBB is flat → portfolio return is exactly half of AAA's
    assert eq.iloc[-1] / eq.iloc[0] - 1.0 == pytest.approx(ret_aaa / 2, rel=1e-6)


def test_naive_momentum_prefers_the_trender():
    data = _fixture()
    eq = naive_momentum(data, CFG, top_n=1)
    ew = equal_weight_universe(data, CFG)
    assert eq.iloc[-1] > ew.iloc[-1]          # holds only AAA, beats the 50/50 mix


def test_baselines_share_the_spy_calendar():
    data = _fixture()
    cal = data["SPY"].loc[CFG.start:CFG.end].index
    for series in (spy_buy_hold(data, CFG), equal_weight_universe(data, CFG),
                   naive_momentum(data, CFG)):
        assert len(series) == len(cal)
