"""Performance metrics on daily equity curves. Sharpe uses rf=0 and √252
annualization; MAR = CAGR / |maxDD|. yearly_log_outperformance feeds gate
criterion 3 (no single year > 50% of total edge)."""
import math
from typing import Dict

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def compute_metrics(equity: pd.Series) -> dict:
    eq = equity.dropna()
    if len(eq) < 2:
        raise ValueError("equity series too short")
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    dd = eq / eq.cummax() - 1.0
    max_dd = float(dd.min())
    rets = eq.pct_change().dropna()
    std = float(rets.std())
    sharpe = float(rets.mean() / std * math.sqrt(TRADING_DAYS)) if std > 0 else 0.0
    mar = float(cagr / abs(max_dd)) if max_dd < 0 else float("inf")
    # yearly return = year-end value vs prior year-end (first year: vs start)
    yearly: Dict[str, float] = {}
    prev = None
    for year, grp in eq.groupby(eq.index.year):
        start = prev if prev is not None else grp.iloc[0]
        yearly[str(year)] = float(grp.iloc[-1] / start - 1.0)
        prev = grp.iloc[-1]
    return {"cagr": float(cagr), "max_drawdown": max_dd, "sharpe": sharpe,
            "mar": mar, "yearly_returns": yearly}


def yearly_log_outperformance(a: pd.Series, b: pd.Series) -> Dict[str, float]:
    a, b = a.align(b, join="inner")
    diff = np.log(a / a.shift(1)) - np.log(b / b.shift(1))
    diff = diff.dropna()
    return {str(y): float(g.sum()) for y, g in diff.groupby(diff.index.year)}
