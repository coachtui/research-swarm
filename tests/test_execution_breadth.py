"""Tests for execution/indicators/breadth.py (pure functions)."""
import numpy as np
import pandas as pd

from execution.indicators.breadth import compute_breadth


def _trend(daily: float, days: int = 260) -> pd.Series:
    return pd.Series(100.0 * (1 + daily) ** np.arange(days))


def test_pct_above_200dma_counts_only_uptrending_etfs():
    closes = {
        "SPY": _trend(0.0004), "RSP": _trend(0.0004),
        "XLK": _trend(0.0008), "XLE": _trend(0.0008),   # above
        "XLF": _trend(-0.0008), "XLU": _trend(-0.0008),  # below
    }
    result = compute_breadth(closes)
    assert result["pct_above_200dma"] == 50.0


def test_equal_weight_trend_positive_when_rsp_outperforms():
    closes = {"SPY": _trend(0.0002), "RSP": _trend(0.0008), "XLK": _trend(0.0004)}
    result = compute_breadth(closes)
    assert result["equal_weight_trend_3m"] > 0


def test_missing_inputs_return_none():
    result = compute_breadth({"XLK": _trend(0.0004)})
    assert result["equal_weight_trend_3m"] is None
    result_empty = compute_breadth({"SPY": _trend(0.0004), "RSP": _trend(0.0004)})
    assert result_empty["pct_above_200dma"] is None
