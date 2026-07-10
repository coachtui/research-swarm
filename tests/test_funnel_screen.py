"""Free screen: ATR, scores, slot selection. Synthetic frames — no network."""
import numpy as np
import pandas as pd
import pytest

from execution.funnel.screen import (
    compute_atr, rank_candidates, screen_row, select_light_slots,
)


def _frame(days=260, drift=0.0005, vol=0.01, start=50.0, volume=1_000_000, seed=7):
    rng = np.random.default_rng(seed)
    close = start * np.cumprod(1 + drift + vol * rng.standard_normal(days))
    high = close * (1 + np.abs(vol * rng.standard_normal(days)))
    low = close * (1 - np.abs(vol * rng.standard_normal(days)))
    idx = pd.bdate_range(end="2026-07-06", periods=days)
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close,
         "Volume": np.full(days, float(volume))}, index=idx,
    )


def _tags(**over):
    base = {"themes": [], "industries": [], "watchlist": False, "holding": False}
    base.update(over)
    return base


def test_atr_positive_and_none_when_short():
    assert compute_atr(_frame()) > 0
    assert compute_atr(_frame(days=10)) is None


def test_screen_row_shape_and_momentum_ordering():
    spy = _frame(drift=0.0003, seed=1)["Close"]
    hot = screen_row("HOT", _frame(drift=0.004, seed=2), spy, _tags(), [], [], None)
    cold = screen_row("COLD", _frame(drift=-0.002, seed=3), spy, _tags(), [], [], None)
    assert hot["momentum"] > cold["momentum"]
    assert hot["screen_score"] > cold["screen_score"]
    for key in ("price", "atr", "atr_pct", "ext_atr", "sma20", "liquidity_adv_usd"):
        assert hot[key] is not None
    assert screen_row("SHORT", _frame(days=30), spy, _tags(), [], [], None) is None


def test_hunting_ground_bonus_breaks_ties():
    spy = _frame(seed=1)["Close"]
    df = _frame(seed=4)
    themed = screen_row("A", df, spy, _tags(themes=["photonics"]), ["photonics"], [], None)
    plain = screen_row("B", df, spy, _tags(), ["photonics"], [], None)
    assert themed["hunting_bonus"] > plain["hunting_bonus"]
    assert themed["screen_score"] > plain["screen_score"]


def test_quality_neutral_when_missing():
    spy = _frame(seed=1)["Close"]
    df = _frame(seed=5)
    missing = screen_row("A", df, spy, _tags(), [], [], None)
    assert missing["quality"] == 5.0  # neutral — never disqualifying


def test_select_light_slots_stale_holdings_first_and_budget():
    ranked = [{"symbol": s} for s in ["N1", "N2", "N3", "FRESH", "N4"]]
    out = select_light_slots(
        ranked, fresh_symbols={"FRESH"}, stale_holdings=["HOLD1"], budget=3,
    )
    assert out["light"] == ["HOLD1", "N1", "N2"]     # stale holding claims slot 1
    assert out["free_ride"] == ["FRESH"]
    assert out["over_budget"] == ["N3", "N4"]
