"""Tests for compute_extended_signals in inngest_app/functions/weekly_outlook.py."""
import numpy as np
import pandas as pd

from execution.constants import INDUSTRY_ETFS
from inngest_app.functions.weekly_outlook import compute_extended_signals


def _series(daily_return: float, days: int = 260, start: float = 100.0) -> pd.Series:
    return pd.Series(start * (1 + daily_return) ** np.arange(days))


def _full_closes():
    closes = {"SPY": _series(0.0004), "IWM": _series(0.0008), "MDY": _series(0.0005)}
    for i, t in enumerate(INDUSTRY_ETFS):
        closes[t] = _series(0.0001 * (i + 1))
    return closes


def test_both_passes_succeed():
    result, failures = compute_extended_signals(_full_closes())
    assert result["industry"] is not None
    assert len(result["industry"]["rankings"]) == 19
    assert result["size_style"] is not None
    assert result["size_style"]["tag"] in {
        "small_caps_leading", "large_caps_leading", "mixed",
    }
    assert failures == []


def test_industry_failure_degrades_but_size_style_survives():
    closes = _full_closes()
    for t in list(INDUSTRY_ETFS)[:6]:  # only 13 industries left < 15
        del closes[t]
    result, failures = compute_extended_signals(closes)
    assert result["industry"] is None
    assert result["size_style"] is not None
    assert len(failures) == 1
    assert "industry" in failures[0][0].lower()


def test_size_style_failure_degrades_but_industry_survives():
    closes = _full_closes()
    del closes["IWM"]
    result, failures = compute_extended_signals(closes)
    assert result["industry"] is not None
    assert result["size_style"] is None
    assert len(failures) == 1
    assert "size/style" in failures[0][0].lower()


def test_total_failure_degrades_both_and_never_raises():
    result, failures = compute_extended_signals({})
    assert result == {"industry": None, "size_style": None}
    assert len(failures) == 2
