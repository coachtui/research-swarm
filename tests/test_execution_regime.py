"""Tests for execution/indicators/regime.py (pure functions)."""
import numpy as np
import pandas as pd
import pytest

from execution.indicators.regime import (
    REGIME_ORDER,
    apply_strategist_override,
    classify_regime,
)


def _trend(daily: float, days: int = 260) -> pd.Series:
    return pd.Series(100.0 * (1 + daily) ** np.arange(days))


def test_risk_on_uptrend_low_vix_healthy_breadth():
    result = classify_regime(_trend(0.0008), pd.Series([15.0] * 260), pct_above_200dma=75.0)
    assert result["regime"] == "risk_on"
    assert result["points"] >= 2
    assert result["inputs"]["spy_above_200dma"] is True


def test_risk_off_downtrend_high_vix():
    result = classify_regime(_trend(-0.0008), pd.Series([33.0] * 260), pct_above_200dma=25.0)
    assert result["regime"] == "risk_off"


def test_neutral_mixed_signals():
    # Uptrend but elevated VIX and weak breadth → neutral
    result = classify_regime(_trend(0.0008), pd.Series([24.0] * 260), pct_above_200dma=50.0)
    assert result["regime"] == "neutral"


def test_missing_vix_and_breadth_contribute_zero_points():
    result = classify_regime(_trend(0.0008), None, None)
    assert result["points"] == 1  # only the SPY trend point
    assert result["regime"] == "neutral"
    assert result["inputs"]["vix_last"] is None


def test_override_one_notch_allowed():
    assert apply_strategist_override("neutral", "risk_on") == ("risk_on", True)
    assert apply_strategist_override("risk_on", "neutral") == ("neutral", True)


def test_override_two_notches_clamped_to_one():
    # Never risk_off → risk_on directly; clamp to neutral.
    assert apply_strategist_override("risk_off", "risk_on") == ("neutral", True)
    assert apply_strategist_override("risk_on", "risk_off") == ("neutral", True)


def test_override_same_regime_is_not_an_override():
    assert apply_strategist_override("neutral", "neutral") == ("neutral", False)


def test_override_invalid_proposal_is_ignored():
    assert apply_strategist_override("neutral", "bullish") == ("neutral", False)


def test_regime_order_constant():
    assert REGIME_ORDER == ["risk_off", "neutral", "risk_on"]
