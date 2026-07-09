"""Tests for execution/indicators/size_style.py (pure functions)."""
import numpy as np
import pandas as pd
import pytest

from execution.indicators.size_style import compute_size_style


def _series(daily_return: float, days: int = 260, start: float = 100.0) -> pd.Series:
    return pd.Series(start * (1 + daily_return) ** np.arange(days))


def test_small_caps_leading_when_iwm_outperforms():
    closes = {"SPY": _series(0.0002), "IWM": _series(0.0010), "MDY": _series(0.0005)}
    result = compute_size_style(closes)
    assert result["tag"] == "small_caps_leading"
    assert result["iwm"]["label"] == "small_cap"
    assert result["iwm"]["composite"] > 0.01
    assert result["mdy"]["label"] == "mid_cap"
    assert set(result["iwm"]) == {"label", "rs_1m", "rs_3m", "rs_6m", "composite"}


def test_large_caps_leading_when_iwm_lags():
    closes = {"SPY": _series(0.0010), "IWM": _series(0.0001), "MDY": _series(0.0005)}
    result = compute_size_style(closes)
    assert result["tag"] == "large_caps_leading"
    assert result["iwm"]["composite"] < -0.01


def test_mixed_when_iwm_tracks_spy():
    closes = {"SPY": _series(0.0004), "IWM": _series(0.0004), "MDY": _series(0.0004)}
    result = compute_size_style(closes)
    assert result["tag"] == "mixed"
    assert result["iwm"]["composite"] == 0.0


def test_tag_boundaries_are_strict():
    from execution.indicators.size_style import tag_for_composite

    assert tag_for_composite(0.0101) == "small_caps_leading"
    assert tag_for_composite(0.01) == "mixed"       # exactly at threshold ⇒ mixed
    assert tag_for_composite(-0.01) == "mixed"
    assert tag_for_composite(-0.0101) == "large_caps_leading"


def test_missing_spy_raises_keyerror():
    with pytest.raises(KeyError):
        compute_size_style({"IWM": _series(0.001), "MDY": _series(0.001)})


def test_missing_or_short_leg_raises_valueerror():
    with pytest.raises(ValueError):
        compute_size_style({"SPY": _series(0.0004), "MDY": _series(0.0005)})
    with pytest.raises(ValueError):
        compute_size_style({
            "SPY": _series(0.0004),
            "IWM": _series(0.001, days=30),
            "MDY": _series(0.0005),
        })
