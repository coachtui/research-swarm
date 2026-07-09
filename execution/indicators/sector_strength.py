"""Sector relative strength, ranking, and rotation detection.

Pure functions over close-price series. Rank 1 = strongest sector.
`rank_change = rank_3m - rank_1m`: positive means the sector's rank improved
recently — the early-rotation signal.
"""
from typing import Any, Dict, List

import pandas as pd

from execution.constants import BENCHMARK, SECTOR_ETFS, WINDOWS

# Composite weights favor recent momentum (early rotation) over long trend.
_SCORE_WEIGHTS = {"1m": 0.5, "3m": 0.3, "6m": 0.2}


def _window_return(closes: pd.Series, days: int) -> float:
    return float(closes.iloc[-1] / closes.iloc[-(days + 1)] - 1.0)


def compute_relative_strength(closes: Dict[str, pd.Series]) -> Dict[str, Dict[str, float]]:
    """Excess return vs SPY per window, for every sector ETF with enough history.

    Raises KeyError if SPY is missing. ETFs with < max(WINDOWS)+1 days are omitted.
    """
    spy = closes[BENCHMARK]
    min_len = max(WINDOWS.values()) + 1
    out: Dict[str, Dict[str, float]] = {}
    for etf in SECTOR_ETFS:
        series = closes.get(etf)
        if series is None or len(series) < min_len or len(spy) < min_len:
            continue
        out[etf] = {
            label: _window_return(series, days) - _window_return(spy, days)
            for label, days in WINDOWS.items()
        }
    return out


def rank_sectors(rel_strength: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
    """Rank sectors per window and compute a composite score (best first)."""
    if not rel_strength:
        return []
    ranks: Dict[str, Dict[str, int]] = {etf: {} for etf in rel_strength}
    for label in WINDOWS:
        ordered = sorted(rel_strength, key=lambda e: rel_strength[e][label], reverse=True)
        for i, etf in enumerate(ordered):
            ranks[etf][label] = i + 1

    rankings = []
    for etf, rs in rel_strength.items():
        rankings.append({
            "etf": etf,
            "sector": SECTOR_ETFS[etf],
            "rs_1m": round(rs["1m"], 4),
            "rs_3m": round(rs["3m"], 4),
            "rs_6m": round(rs["6m"], 4),
            "rank_1m": ranks[etf]["1m"],
            "rank_3m": ranks[etf]["3m"],
            "rank_6m": ranks[etf]["6m"],
            "rank_change": ranks[etf]["3m"] - ranks[etf]["1m"],
            "score": round(sum(_SCORE_WEIGHTS[w] * rs[w] for w in WINDOWS), 4),
        })
    rankings.sort(key=lambda r: r["score"], reverse=True)
    return rankings


def detect_rotations(rankings: List[Dict[str, Any]], min_rank_gain: int = 3) -> List[Dict[str, Any]]:
    """Flag sectors whose 1m rank improved/deteriorated ≥ min_rank_gain vs 3m."""
    flags = []
    for r in rankings:
        if r["rank_change"] >= min_rank_gain:
            flags.append({"etf": r["etf"], "sector": r["sector"],
                          "direction": "into", "rank_change": r["rank_change"]})
        elif r["rank_change"] <= -min_rank_gain:
            flags.append({"etf": r["etf"], "sector": r["sector"],
                          "direction": "out_of", "rank_change": r["rank_change"]})
    return flags
