"""Tests for execution/indicators/industry_strength.py (pure functions)."""
import numpy as np
import pandas as pd
import pytest

from execution.constants import INDUSTRY_ETFS
from execution.indicators.industry_strength import (
    InsufficientIndustryData,
    rank_industries,
)


def _series(daily_return: float, days: int = 260, start: float = 100.0) -> pd.Series:
    return pd.Series(start * (1 + daily_return) ** np.arange(days))


def _closes_for(tickers, spy_return: float = 0.0004):
    """SPY plus a distinct constant-return series per ticker."""
    closes = {"SPY": _series(spy_return)}
    for i, t in enumerate(tickers):
        closes[t] = _series(0.0001 * (i + 1))
    return closes


def test_ranks_all_industries_with_industry_label():
    closes = _closes_for(list(INDUSTRY_ETFS))
    result = rank_industries(closes)
    assert set(result) == {"rankings", "rotations", "missing"}
    assert len(result["rankings"]) == 19
    assert result["missing"] == []
    top = result["rankings"][0]
    assert top["industry"] == INDUSTRY_ETFS[top["etf"]]
    assert "sector" not in top
    # constant-return series ⇒ no rank divergence ⇒ no rotation flags
    assert result["rotations"] == []


def test_missing_tickers_listed_but_still_ranks():
    present = list(INDUSTRY_ETFS)[:16]  # 16 >= MIN_INDUSTRIES_REQUIRED
    closes = _closes_for(present)
    result = rank_industries(closes)
    assert len(result["rankings"]) == 16
    assert result["missing"] == sorted(set(INDUSTRY_ETFS) - set(present))


def test_too_few_industries_raises():
    present = list(INDUSTRY_ETFS)[:14]  # 14 < 15
    closes = _closes_for(present)
    with pytest.raises(InsufficientIndustryData):
        rank_industries(closes)


def test_missing_spy_raises_keyerror():
    closes = {t: _series(0.001) for t in INDUSTRY_ETFS}
    with pytest.raises(KeyError):
        rank_industries(closes)


def test_rotation_uses_industry_threshold():
    """A surge industry must move ≥5 ranks to flag (sectors flag at 3)."""
    laggards = {t: _series(0.0006) for t in list(INDUSTRY_ETFS) if t != "XBI"}
    daily = np.array([-0.003] * 239 + [0.006] * 21)
    surge = pd.Series(100.0 * np.cumprod(1 + daily))
    closes = {"SPY": _series(0.0004), "XBI": surge, **laggards}
    result = rank_industries(closes)
    xbi = next(r for r in result["rankings"] if r["etf"] == "XBI")
    flagged = [f["etf"] for f in result["rotations"]]
    if xbi["rank_change"] >= 5:
        assert "XBI" in flagged
        flag = next(f for f in result["rotations"] if f["etf"] == "XBI")
        assert flag["direction"] == "into"
        assert flag["industry"] == "Biotech"
    else:
        assert "XBI" not in flagged
