# tests/test_backtest_simulator_variants.py
"""Entry-mechanics variants (requote / capitulation valve). Synthetic
fixture: one permanently *extended* uptrend whose patient limit never
fills — the exact pathology the 41% missed-fill finding points at."""
import numpy as np
import pandas as pd
import pytest

from execution.backtest.fills import LimitOrder
from execution.backtest.simulator import (
    BacktestConfig, run_backtest, valve_armed, _record_miss,
)


def test_config_flags_default_off():
    cfg = BacktestConfig()
    assert cfg.requote_weekly is False
    assert cfg.capitulation_valve is False


def test_valve_armed_rules():
    assert not valve_armed(None, 60.0)                              # never missed
    assert not valve_armed({"count": 1, "conviction": 60.0}, 60.0)  # one miss only
    assert not valve_armed({"count": 2, "conviction": 61.0}, 60.0)  # conviction dropped
    assert valve_armed({"count": 2, "conviction": 60.0}, 60.0)      # not lower: equal ok
    assert valve_armed({"count": 3, "conviction": 55.0}, 60.0)      # higher ok


def test_record_miss_counts_and_tracks_conviction():
    missed = {}
    order = LimitOrder("XY", 10, 50.0, 1.0,
                       pd.Timestamp("2020-01-06").date(),
                       pd.Timestamp("2020-01-13").date(), conviction=70.0)
    _record_miss(missed, order)
    _record_miss(missed, order)
    assert missed["XY"] == {"count": 2, "conviction": 70.0}


def _steep_df(n=260, start="2019-01-01", rate=1.015, p0=20.0, vol=1_000_000):
    """Tight-range 1.5%/day uptrend: price runs ~9 ATR above SMA20, so the
    entry is always 'extended' and the patient limit (price − ATR) sits
    below every subsequent low — the quote can never fill."""
    idx = pd.bdate_range(start, periods=n)
    close = pd.Series(p0 * rate ** np.arange(n), index=idx)
    op = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame({"Open": op, "High": close * 1.001, "Low": op * 0.999,
                         "Close": close, "Volume": float(vol)}, index=idx)


def _mild_df(n=260, start="2019-01-01", p0=300.0, vol=1_000_000):
    rng = np.random.default_rng(7)
    idx = pd.bdate_range(start, periods=n)
    close = pd.Series(p0 * np.cumprod(1.0004 * (1 + 0.002 * rng.standard_normal(n))),
                      index=idx)
    op = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame({"Open": op, "High": close * 1.005, "Low": op * 0.995,
                         "Close": close, "Volume": float(vol)}, index=idx)


def _ext_fixture():
    return {"EXTD": _steep_df(), "SPY": _mild_df()}


VCFG = BacktestConfig(start="2019-06-01", end="2019-12-15",
                      starting_cash=100_000.0, flat_conviction=60.0)


def test_extended_quote_never_fills_in_base():
    res = run_backtest(_ext_fixture(), VCFG)
    assert not [j for j in res.journal if j["side"] == "buy"]
    assert [j for j in res.journal if j["reason"] == "missed_fill"]
    assert not [j for j in res.journal if j["reason"] == "requote"]


def test_requote_cancels_and_refreshes_weekly():
    from dataclasses import replace

    from execution.backtest.sensitivity import patched
    cfg = replace(VCFG, requote_weekly=True)
    with patched("execution.funnel.entries", "PATIENT_LIMIT_TTL_WEEKS", 1):
        res = run_backtest(_ext_fixture(), cfg)
    requotes = [j for j in res.journal if j["reason"] == "requote"]
    assert len(requotes) >= 3
    assert all(j["side"] == "cancel" for j in requotes)
    # each fresh quote is struck off the *new* week's (higher) SMA20/ATR:
    # the cancelled limits must ratchet upward with the trend
    limits = [j["price"] for j in requotes if j["symbol"] == "EXTD"]
    assert limits == sorted(limits) and limits[-1] > limits[0]


def test_valve_fires_after_two_misses_at_next_open_plus_slippage():
    from dataclasses import replace
    data = _ext_fixture()
    res = run_backtest(data, replace(VCFG, capitulation_valve=True))
    valve = [j for j in res.journal if j["reason"] == "capitulation_entry"]
    assert valve, "valve never fired"
    first = valve[0]
    misses = [j for j in res.journal if j["reason"] == "missed_fill"
              and j["symbol"] == first["symbol"] and j["date"] < first["date"]]
    assert len(misses) >= 2
    bar = data[first["symbol"]].loc[pd.Timestamp(first["date"])]
    assert first["price"] == pytest.approx(float(bar["Open"]) * 1.001, rel=1e-6)
    # half of the flat-60 band (≈8.4% of equity) minus whole-share rounding
    notional = first["qty"] * first["price"]
    assert 0.02 * VCFG.starting_cash <= notional <= 0.045 * VCFG.starting_cash


def test_combined_requote_misses_arm_the_valve_faster():
    from dataclasses import replace

    from execution.backtest.sensitivity import patched
    cfg = replace(VCFG, requote_weekly=True, capitulation_valve=True)
    with patched("execution.funnel.entries", "PATIENT_LIMIT_TTL_WEEKS", 1):
        res = run_backtest(_ext_fixture(), cfg)
    valve = [j for j in res.journal if j["reason"] == "capitulation_entry"]
    assert valve
    # requote cadence: 2 misses accumulate in ~2 weeks, so the first valve
    # entry lands within 5 weeks of the window start (valve-alone needs ~7)
    assert (valve[0]["date"] - pd.Timestamp(VCFG.start).date()).days <= 35
    # once held, no further quotes: at most one valve entry per symbol
    assert len([j for j in valve if j["symbol"] == "EXTD"]) == 1
