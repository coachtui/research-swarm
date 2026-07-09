"""Breadth proxies from sector ETFs and the RSP/SPY ratio.

Phase 1 uses the 11 sector ETFs (not the 191-stock universe) as the breadth
sample — cheap and adequate for a weekly regime input.
"""
from typing import Dict, Optional

import pandas as pd

from execution.constants import BENCHMARK, EQUAL_WEIGHT, SECTOR_ETFS


def compute_breadth(closes: Dict[str, pd.Series]) -> Dict[str, Optional[float]]:
    above = 0
    total = 0
    for etf in SECTOR_ETFS:
        series = closes.get(etf)
        if series is None or len(series) < 60:
            continue
        sma200 = series.rolling(200, min_periods=60).mean().iloc[-1]
        total += 1
        if series.iloc[-1] > sma200:
            above += 1
    pct_above = round(100.0 * above / total, 1) if total else None

    trend: Optional[float] = None
    spy, rsp = closes.get(BENCHMARK), closes.get(EQUAL_WEIGHT)
    if spy is not None and rsp is not None and len(spy) > 63 and len(rsp) > 63:
        n = min(len(spy), len(rsp))
        ratio = rsp.iloc[-n:].reset_index(drop=True) / spy.iloc[-n:].reset_index(drop=True)
        trend = round(float(ratio.iloc[-1] / ratio.iloc[-64] - 1.0) * 100, 2)

    return {"pct_above_200dma": pct_above, "equal_weight_trend_3m": trend}
