"""Theme basket synthetic index + relative strength ranking (Phase 3B).

Equal weight is the point: a $400M photonics mover counts as much as RMBS —
this surfaces broad small-cap theme moves a cap-weighted proxy would hide.
Pure functions; same parameterized RS math as sectors/industries.

history is computed from CURRENT membership over trailing weeks — sparkline
context only. It answers "how did today's basket perform", NOT "when would
the engine have flagged this". The 3D backtest must only use live-recorded
MarketOutlook rows (spec-bound).
"""
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from execution.constants import (
    BENCHMARK,
    MIN_THEME_CONSTITUENTS,
    THEME_HISTORY_WEEKS,
    THEME_ROTATION_MIN_RANK_GAIN,
    WINDOWS,
)
from execution.indicators.sector_strength import (
    compute_relative_strength,
    detect_rotations,
    rank_sectors,
)

_MIN_LEN = max(WINDOWS.values()) + 1
_TRADING_DAYS_PER_WEEK = 5


def build_theme_index(
    constituent_closes: Dict[str, pd.Series],
) -> Tuple[Optional[pd.Series], List[str]]:
    """Equal-weight index: mean of normalized (first=1.0) close series over the
    common tail. Constituents shorter than the longest RS window are excluded."""
    eligible = {
        t: s.dropna().reset_index(drop=True)
        for t, s in constituent_closes.items()
        if s is not None and len(s.dropna()) >= _MIN_LEN
    }
    if not eligible:
        return None, []
    common = min(len(s) for s in eligible.values())
    normed = []
    for t in sorted(eligible):
        tail = eligible[t].iloc[-common:].reset_index(drop=True)
        normed.append(tail / tail.iloc[0])
    index = pd.concat(normed, axis=1).mean(axis=1)
    return index, sorted(eligible)


def _score_history(
    idx_closes: Dict[str, pd.Series], label_map: Dict[str, str],
) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {slug: [] for slug in label_map}
    for weeks_ago in range(THEME_HISTORY_WEEKS - 1, -1, -1):
        offset = weeks_ago * _TRADING_DAYS_PER_WEEK
        truncated = {}
        for key, s in idx_closes.items():
            if offset == 0:
                truncated[key] = s
            elif len(s) > offset:
                truncated[key] = s.iloc[:-offset]
        # Unreachable today (SPY must be >=127 points for label_map to be
        # non-empty and the max offset is 55), but keep the invariant local
        # instead of depending on that distant precondition.
        if BENCHMARK not in truncated:
            continue
        rel = compute_relative_strength(truncated, etf_map=label_map)
        if not rel:
            continue
        ranked = rank_sectors(rel, etf_map=label_map, label_key="theme")
        for position, r in enumerate(ranked, start=1):
            out[r["etf"]].append(
                {"weeks_ago": weeks_ago, "score": r["score"], "rank": position})
    return out


def rank_themes(
    themes: List[Dict[str, Any]],
    closes: Dict[str, pd.Series],
    spy: pd.Series,
) -> Dict[str, Any]:
    idx_closes: Dict[str, pd.Series] = {BENCHMARK: spy}
    label_map: Dict[str, str] = {}
    meta: Dict[str, Dict[str, Any]] = {}
    missing: List[Dict[str, str]] = []

    for theme in themes:
        series = {t: closes.get(t) for t in theme["tickers"]}
        index, eligible = build_theme_index(
            {t: s for t, s in series.items() if s is not None})
        if index is None or len(eligible) < MIN_THEME_CONSTITUENTS:
            missing.append({
                "slug": theme["slug"],
                "reason": f"only {len(eligible)} index-eligible constituents "
                          f"(need {MIN_THEME_CONSTITUENTS})"})
            continue
        idx_closes[theme["slug"]] = index
        label_map[theme["slug"]] = theme["name"]
        meta[theme["slug"]] = {"confidence": theme.get("confidence"),
                               "constituent_count": len(eligible)}

    rel = compute_relative_strength(idx_closes, etf_map=label_map)
    for slug in list(label_map):
        if slug not in rel:  # truncated common tail fell below the RS window
            missing.append({"slug": slug, "reason": "insufficient index history"})
            label_map.pop(slug)
            meta.pop(slug)

    rankings = rank_sectors(rel, etf_map=label_map, label_key="theme")
    for r in rankings:
        r["slug"] = r["etf"]
        r.update(meta[r["etf"]])
    rotations = detect_rotations(
        rankings, min_rank_gain=THEME_ROTATION_MIN_RANK_GAIN, label_key="theme")
    history = _score_history(idx_closes, label_map) if label_map else {}
    return {"rankings": rankings, "rotations": rotations,
            "missing": missing, "history": history}
