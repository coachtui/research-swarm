"""Performance metrics on daily equity curves. Sharpe uses rf=0 and √252
annualization; MAR = CAGR / |maxDD|. yearly_log_outperformance feeds gate
criterion 3 (no single year > 50% of total edge)."""
import math
from typing import Dict, List, Optional

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


def trade_stats(journal: List[dict], equity: pd.Series,
                starting_cash: float) -> Dict[str, Optional[float]]:
    """Win rate over realized sells, annualized turnover (sell notional /
    mean equity / years), and average invested exposure reconstructed from
    the cash flows in the journal."""
    cost_basis: Dict[str, Dict[str, float]] = {}
    sells = 0
    wins = 0
    sell_notional = 0.0
    flows: Dict[pd.Timestamp, float] = {}

    for row in journal:
        side = row.get("side")
        if side not in ("buy", "sell"):
            continue
        symbol = row["symbol"]
        qty = float(row["qty"])
        price = float(row["price"])
        ts = pd.Timestamp(row["date"])
        if side == "buy":
            pos = cost_basis.setdefault(symbol, {"qty": 0.0, "cost": 0.0})
            total_qty = pos["qty"] + qty
            pos["cost"] = ((pos["cost"] * pos["qty"] + price * qty) / total_qty
                          if total_qty else 0.0)
            pos["qty"] = total_qty
            flows[ts] = flows.get(ts, 0.0) - qty * price
        else:  # sell
            pos = cost_basis.setdefault(symbol, {"qty": 0.0, "cost": price})
            realized = (price - pos["cost"]) * qty
            pos["qty"] -= qty
            sells += 1
            if realized > 0:
                wins += 1
            sell_notional += qty * price
            flows[ts] = flows.get(ts, 0.0) + qty * price

    win_rate = round(wins / sells, 4) if sells else None

    eq = equity.dropna()
    years = (eq.index[-1] - eq.index[0]).days / 365.25 if len(eq) >= 2 else 0.0
    mean_equity = float(eq.mean()) if len(eq) else 0.0
    turnover_annual = (round(sell_notional / mean_equity / years, 4)
                       if years > 0 and mean_equity else None)

    if flows:
        flow_series = pd.Series(flows).sort_index()
        cum_flow = flow_series.groupby(level=0).sum().cumsum()
        cash = starting_cash + cum_flow.reindex(eq.index, method="ffill").fillna(0.0)
    else:
        cash = pd.Series(starting_cash, index=eq.index)
    exposure = (eq - cash) / eq
    avg_exposure = round(float(exposure.mean()), 4) if len(eq) else None

    return {"win_rate": win_rate, "turnover_annual": turnover_annual,
            "avg_exposure": avg_exposure}
