"""Size/style regime inputs — Phase 3A.

IWM (small) and MDY (mid) windowed relative strength vs SPY, plus a simple
leadership tag from IWM's composite. Pure; the weekly-outlook cron handles
degradation (null + alert). Consumed by Sleeve A only — never the shared
regime (control-group contract).
"""
from typing import Any, Dict

import pandas as pd

from execution.constants import (
    BENCHMARK,
    SCORE_WEIGHTS,
    SIZE_STYLE_ETFS,
    SIZE_STYLE_RS_THRESHOLD,
    WINDOWS,
)
from execution.indicators.sector_strength import _window_return


def tag_for_composite(composite: float) -> str:
    """Leadership tag from IWM's composite RS vs SPY (strict thresholds)."""
    if composite > SIZE_STYLE_RS_THRESHOLD:
        return "small_caps_leading"
    if composite < -SIZE_STYLE_RS_THRESHOLD:
        return "large_caps_leading"
    return "mixed"


def compute_size_style(closes: Dict[str, pd.Series]) -> Dict[str, Any]:
    """Windowed RS vs SPY for IWM/MDY + leadership tag.

    Raises KeyError if SPY is missing, ValueError if either leg is missing
    or has fewer than max(WINDOWS)+1 days.
    """
    spy = closes[BENCHMARK]
    min_len = max(WINDOWS.values()) + 1
    if len(spy) < min_len:
        raise ValueError(f"{BENCHMARK} history too short for size/style")

    out: Dict[str, Any] = {}
    for etf, label in SIZE_STYLE_ETFS.items():
        series = closes.get(etf)
        if series is None or len(series) < min_len:
            raise ValueError(f"{etf} history unavailable or too short for size/style")
        rs = {
            w: _window_return(series, days) - _window_return(spy, days)
            for w, days in WINDOWS.items()
        }
        out[etf.lower()] = {
            "label": label,
            "rs_1m": round(rs["1m"], 4),
            "rs_3m": round(rs["3m"], 4),
            "rs_6m": round(rs["6m"], 4),
            "composite": round(sum(SCORE_WEIGHTS[w] * rs[w] for w in WINDOWS), 4),
        }

    out["tag"] = tag_for_composite(out["iwm"]["composite"])
    return out
