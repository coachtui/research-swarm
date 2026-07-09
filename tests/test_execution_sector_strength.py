"""Tests for execution/indicators/sector_strength.py (pure functions)."""
import numpy as np
import pandas as pd
import pytest

from execution.constants import SCORE_WEIGHTS, SECTOR_ETFS, WINDOWS
from execution.indicators.sector_strength import (
    compute_relative_strength,
    detect_rotations,
    rank_sectors,
)


def _series(daily_return: float, days: int = 260, start: float = 100.0) -> pd.Series:
    """Price series compounding at a constant daily return."""
    return pd.Series(start * (1 + daily_return) ** np.arange(days))


def test_constants_shape():
    assert len(SECTOR_ETFS) == 11
    assert "XLK" in SECTOR_ETFS and SECTOR_ETFS["XLK"] == "Technology"
    assert WINDOWS == {"1m": 21, "3m": 63, "6m": 126}


def test_relative_strength_positive_for_outperformer():
    closes = {"SPY": _series(0.0004), "XLE": _series(0.0010), "XLK": _series(0.0001)}
    rs = compute_relative_strength(closes)
    assert rs["XLE"]["1m"] > 0 and rs["XLE"]["3m"] > 0 and rs["XLE"]["6m"] > 0
    assert rs["XLK"]["1m"] < 0


def test_relative_strength_skips_short_history():
    closes = {"SPY": _series(0.0004), "XLE": _series(0.0010, days=30)}
    rs = compute_relative_strength(closes)
    assert "XLE" not in rs  # needs 126+1 days for the 6m window


def test_relative_strength_requires_spy():
    with pytest.raises(KeyError):
        compute_relative_strength({"XLE": _series(0.001)})


def test_rank_sectors_orders_by_score_and_ranks_all_windows():
    closes = {
        "SPY": _series(0.0004),
        "XLE": _series(0.0010),
        "XLK": _series(0.0006),
        "XLU": _series(0.0001),
    }
    rankings = rank_sectors(compute_relative_strength(closes))
    assert [r["etf"] for r in rankings] == ["XLE", "XLK", "XLU"]
    assert rankings[0]["rank_1m"] == 1 and rankings[-1]["rank_1m"] == 3
    assert rankings[0]["sector"] == "Energy"
    # constant-return series ⇒ same rank in every window ⇒ no rank change
    assert all(r["rank_change"] == 0 for r in rankings)


def test_rank_change_detects_improvement():
    """XLE declines for months then surges in the last month ⇒ 1m rank better than 3m rank.

    The decline must be steep enough that XLE's 3m/6m cumulative return still
    trails the laggards despite the recent surge — otherwise one strong month
    dominates every lookback window and no rank divergence appears.
    """
    laggards = {t: _series(0.0006) for t in ["XLK", "XLF", "XLV", "XLI"]}
    daily = np.array([-0.003] * 239 + [0.005] * 21)
    surge = pd.Series(100.0 * np.cumprod(1 + daily))
    closes = {"SPY": _series(0.0004), "XLE": surge, **laggards}
    rankings = rank_sectors(compute_relative_strength(closes))
    xle = next(r for r in rankings if r["etf"] == "XLE")
    assert xle["rank_1m"] < xle["rank_3m"]      # better (lower) rank recently
    assert xle["rank_change"] > 0                # positive = improving


def test_detect_rotations_flags_direction():
    rankings = [
        {"etf": "XLE", "sector": "Energy", "rank_change": 4},
        {"etf": "XLK", "sector": "Technology", "rank_change": -5},
        {"etf": "XLF", "sector": "Financials", "rank_change": 1},
    ]
    flags = detect_rotations(rankings, min_rank_gain=3)
    assert {f["etf"]: f["direction"] for f in flags} == {"XLE": "into", "XLK": "out_of"}


def test_industry_and_size_style_constants_shape():
    from execution.constants import (
        INDUSTRY_ETFS,
        INDUSTRY_ROTATION_MIN_RANK_GAIN,
        MIN_INDUSTRIES_REQUIRED,
        SCORE_WEIGHTS,
        SIZE_STYLE_ETFS,
        SIZE_STYLE_RS_THRESHOLD,
    )

    assert len(INDUSTRY_ETFS) == 19
    assert INDUSTRY_ETFS["XBI"] == "Biotech"
    assert INDUSTRY_ETFS["SMH"] == "Semiconductors"
    assert not set(INDUSTRY_ETFS) & set(SECTOR_ETFS)  # no overlap with sectors
    assert SIZE_STYLE_ETFS == {"IWM": "small_cap", "MDY": "mid_cap"}
    assert SCORE_WEIGHTS == {"1m": 0.5, "3m": 0.3, "6m": 0.2}
    assert INDUSTRY_ROTATION_MIN_RANK_GAIN == 5
    assert MIN_INDUSTRIES_REQUIRED == 15
    assert SIZE_STYLE_RS_THRESHOLD == 0.01


def test_parameterized_output_is_identical_to_default_for_sectors():
    """Control-group contract: explicit SECTOR_ETFS args == default args, exactly."""
    closes = {
        "SPY": _series(0.0004),
        "XLE": _series(0.0010),
        "XLK": _series(0.0006),
        "XLU": _series(0.0001),
    }
    rs_default = compute_relative_strength(closes)
    rs_explicit = compute_relative_strength(closes, etf_map=SECTOR_ETFS)
    assert rs_default == rs_explicit

    rankings_default = rank_sectors(rs_default)
    rankings_explicit = rank_sectors(rs_explicit, etf_map=SECTOR_ETFS, label_key="sector")
    assert rankings_default == rankings_explicit

    flags_default = detect_rotations(rankings_default)
    flags_explicit = detect_rotations(rankings_explicit, min_rank_gain=3, label_key="sector")
    assert flags_default == flags_explicit


def test_custom_etf_map_and_label_key():
    etf_map = {"XBI": "Biotech", "SMH": "Semiconductors"}
    closes = {"SPY": _series(0.0004), "XBI": _series(0.0010), "SMH": _series(0.0001)}
    rs = compute_relative_strength(closes, etf_map=etf_map)
    assert set(rs) == {"XBI", "SMH"}
    rankings = rank_sectors(rs, etf_map=etf_map, label_key="industry")
    assert rankings[0]["etf"] == "XBI"
    assert rankings[0]["industry"] == "Biotech"
    assert "sector" not in rankings[0]
    flags = detect_rotations(
        [{"etf": "XBI", "industry": "Biotech", "rank_change": 6}],
        min_rank_gain=5,
        label_key="industry",
    )
    assert flags == [{"etf": "XBI", "industry": "Biotech",
                      "direction": "into", "rank_change": 6}]
