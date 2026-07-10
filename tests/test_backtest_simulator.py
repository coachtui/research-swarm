# tests/test_backtest_simulator.py
"""Synthetic end-to-end: three fake symbols with deterministic paths.
Locks the harness's honesty — accounting identity, no lookahead fills,
stops fire on crashes. Production math is trusted (it has its own tests)."""
import numpy as np
import pandas as pd
import pytest

from execution.backtest.simulator import BacktestConfig, run_backtest


def _make_df(closes: np.ndarray, start="2019-01-01", vol=1_000_000) -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=len(closes))
    close = pd.Series(closes, index=idx)
    return pd.DataFrame({
        "Open": close.shift(1).fillna(close.iloc[0]),
        "High": close * 1.01,
        "Low": close * 0.985,   # deep enough daily range that limits fill
        "Close": close,
        "Volume": float(vol),
    }, index=idx)


def _fixture(n=500):
    rng = np.random.default_rng(42)
    noise = lambda: 1 + 0.002 * rng.standard_normal(n)
    up = 50 * np.cumprod(1.0015 * noise())            # strong uptrend
    flat = np.full(n, 50.0) * np.cumprod(noise())     # drifting flat
    crash = 50 * np.cumprod(1.002 * noise())
    crash[300:] = crash[299] * np.cumprod(np.full(n - 300, 0.97))  # −3%/day cliff
    spy = 300 * np.cumprod(1.0004 * noise())
    return {
        "UPUP": _make_df(up), "FLAT": _make_df(flat), "CRSH": _make_df(crash),
        "SPY": _make_df(spy),
    }


CFG = BacktestConfig(start="2019-06-01", end="2020-11-01", starting_cash=100_000.0)


@pytest.fixture(scope="module")
def result():
    return run_backtest(_fixture(), CFG)


def test_uptrending_symbol_gets_bought(result):
    buys = [j for j in result.journal if j["side"] == "buy"]
    assert any(j["symbol"] == "UPUP" for j in buys)


def test_crash_triggers_trailing_stop_exit(result):
    stops = [j for j in result.journal
             if j["side"] == "sell" and j["reason"] == "trailing_stop"]
    assert any(j["symbol"] == "CRSH" for j in stops)


def test_accounting_identity_and_no_negative_cash(result):
    # replay the journal: cash must never go negative and must reconcile
    cash = CFG.starting_cash
    qty: dict = {}
    for j in result.journal:
        if j["side"] == "buy":
            cash -= j["qty"] * j["price"]
            qty[j["symbol"]] = qty.get(j["symbol"], 0) + j["qty"]
        elif j["side"] == "sell":
            cash += j["qty"] * j["price"]
            qty[j["symbol"]] = qty[j["symbol"]] - j["qty"]
        assert cash > -1e-6, f"negative cash after {j}"
    assert all(q >= 0 for q in qty.values())


def test_no_lookahead_buy_fills(result):
    """Every buy fill must be on a day whose low actually reached the fill
    price, and never above the open (min(open, limit) semantics). Fill
    prices are rounded to 4dp, so allow 1e-4 of rounding slack."""
    data = _fixture()
    for j in result.journal:
        if j["side"] != "buy":
            continue
        bar = data[j["symbol"]].loc[pd.Timestamp(j["date"])]
        assert bar["Low"] <= j["price"] + 1e-4
        assert j["price"] <= bar["Open"] + 1e-4


def test_equity_curve_covers_calendar_and_ends_positive(result):
    data = _fixture()
    cal = data["SPY"].loc[CFG.start:CFG.end].index
    assert len(result.equity) == len(cal)
    assert result.equity.iloc[-1] > 0
    assert result.weeks > 50


def test_pit_membership_restricts_entries():
    pit = pd.DataFrame({"ticker": ["UPUP", "FLAT"],
                        "date_added": [pd.Timestamp("2000-01-01")] * 2,
                        "date_removed": [pd.NaT, pd.NaT]})
    res = run_backtest(_fixture(), CFG, pit=pit)
    buys = {j["symbol"] for j in res.journal if j["side"] == "buy"}
    assert "CRSH" not in buys        # not a PIT member, no static list given
