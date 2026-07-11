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


# --- DCA ladder + thesis-break exit (owner conviction-hold philosophy) ---

def _dip_df(n=260, start="2019-01-01", vol=1_000_000):
    """Up 1%/day for 150 days, then -1.2%/day for 60 (max dd ~51%), then
    +1%/day recovery: crosses the 20/30/40 rungs on the way down."""
    idx = pd.bdate_range(start, periods=n)
    r = np.concatenate([np.full(150, 1.01), np.full(60, 0.988),
                        np.full(n - 210, 1.01)])
    close = pd.Series(30.0 * np.cumprod(r), index=idx)
    op = close.shift(1).fillna(close.iloc[0])
    lo = pd.concat([op, close], axis=1).min(axis=1) * 0.999
    hi = pd.concat([op, close], axis=1).max(axis=1) * 1.001
    return pd.DataFrame({"Open": op, "High": hi, "Low": lo,
                         "Close": close, "Volume": float(vol)}, index=idx)


def _dip_fixture():
    return {"DIPR": _dip_df(), "SPY": _mild_df()}


def test_dca_ladder_adds_on_intact_thesis_dips():
    from dataclasses import replace

    from execution.backtest.sensitivity import patched
    cfg = replace(VCFG, dca_ladder=True)
    # the ladder only coheres with stops out of the way (a 2.5-ATR trail
    # sells ~5% below the high — before any rung can arm)
    with patched("inngest_app.functions.execution_daily",
                 "TRAILING_STOP_ATR_MULT", 1e9):
        res = run_backtest(_dip_fixture(), cfg)
    adds = [j for j in res.journal
            if j["side"] == "buy" and j["reason"] == "dca_add"]
    entries = [j for j in res.journal
               if j["side"] == "buy" and j["reason"] == "entry_fill"]
    assert entries, "never entered DIPR"
    assert len(adds) >= 2, f"ladder should fire multiple rungs, got {len(adds)}"
    # adds happen on the way down: each later add at a lower price
    prices = [j["price"] for j in adds if j["symbol"] == "DIPR"]
    assert prices == sorted(prices, reverse=True)
    # at most one tranche per rung: never more than 3 adds per episode
    assert len([j for j in adds if j["symbol"] == "DIPR"]) <= 3


def test_dca_ladder_off_means_no_adds():
    res = run_backtest(_dip_fixture(), VCFG)
    assert not [j for j in res.journal if j["reason"] == "dca_add"]


def test_thesis_break_exits_collapsing_name():
    """CRSH from the base fixture: -3%/day cliff kills its screen score →
    conviction (screen_score×10) sits under the break floor for weeks."""
    import tests.test_backtest_simulator as base
    from dataclasses import replace

    from execution.backtest.sensitivity import patched
    cfg = replace(base.CFG, flat_conviction=None, thesis_break_exit=True)
    with patched("inngest_app.functions.execution_daily",
                 "TRAILING_STOP_ATR_MULT", 1e9):
        res = run_backtest(base._fixture(), cfg)
    breaks = [j for j in res.journal if j["reason"] == "thesis_break"]
    assert any(j["symbol"] == "CRSH" for j in breaks)
