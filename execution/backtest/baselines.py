"""The three comparison baselines, on the identical universe and calendar.
(a) equal-weight universe, yearly rebalance; (b) naive momentum — same
screen top-N, equal weight, weekly rebalance, no stops/sizing/regime;
(c) SPY buy-and-hold, context only. Fractional shares are fine here —
benchmarks, not simulations of a broker."""
from typing import Dict, List

import pandas as pd

from typing import Optional, Set

from execution.constants import BENCHMARK
from execution.funnel.screen import rank_candidates, screen_row

from execution.backtest.simulator import ENTRY_TAGS, _NON_STOCK, BacktestConfig, _week_starts
from execution.backtest.universe import eligible_asof, members_asof


def _calendar(ohlcv: Dict[str, pd.DataFrame], cfg: BacktestConfig) -> pd.DatetimeIndex:
    return ohlcv[BENCHMARK].loc[cfg.start:cfg.end].index


def _allowed(pit, static_universe, asof) -> Optional[Set[str]]:
    if pit is None:
        return None
    return members_asof(pit, asof) | set(static_universe or ())


def spy_buy_hold(ohlcv: Dict[str, pd.DataFrame], cfg: BacktestConfig) -> pd.Series:
    spy = ohlcv[BENCHMARK].loc[cfg.start:cfg.end, "Close"]
    return cfg.starting_cash * spy / spy.iloc[0]


def _segment_curve(stocks: Dict[str, pd.DataFrame], members: List[str],
                   seg: pd.DatetimeIndex, start_value: float) -> pd.Series:
    """Equal-weight buy-and-hold across `members` over `seg` (daily curve).
    Members without a bar on seg[0] are dropped; prices forward-fill."""
    paths = []
    for sym in members:
        px = stocks[sym]["Close"].reindex(seg).ffill()
        if pd.isna(px.iloc[0]) or px.iloc[0] <= 0:
            continue
        paths.append(px / px.iloc[0])
    if not paths:
        return pd.Series(start_value, index=seg)
    return start_value * pd.concat(paths, axis=1).mean(axis=1)


def equal_weight_universe(ohlcv: Dict[str, pd.DataFrame], cfg: BacktestConfig,
                          pit=None, static_universe=None) -> pd.Series:
    cal = _calendar(ohlcv, cfg)
    stocks = {s: df for s, df in ohlcv.items() if s not in _NON_STOCK}
    parts: List[pd.Series] = []
    value = cfg.starting_cash
    for year, seg in cal.groupby(cal.year).items():
        seg = pd.DatetimeIndex(seg)
        members = eligible_asof(stocks, seg[0],
                                allowed=_allowed(pit, static_universe, seg[0]))
        curve = _segment_curve(stocks, members, seg, value)
        value = float(curve.iloc[-1])
        parts.append(curve)
    return pd.concat(parts)


def naive_momentum(ohlcv: Dict[str, pd.DataFrame], cfg: BacktestConfig,
                   top_n: int = 10, pit=None, static_universe=None) -> pd.Series:
    cal = _calendar(ohlcv, cfg)
    stocks = {s: df for s, df in ohlcv.items() if s not in _NON_STOCK}
    spy_all = ohlcv[BENCHMARK]["Close"]
    starts = sorted(_week_starts(cal))
    parts: List[pd.Series] = []
    value = cfg.starting_cash
    for i, ws in enumerate(starts):
        seg_end = starts[i + 1] if i + 1 < len(starts) else cal[-1]
        seg = cal[(cal >= ws) & (cal <= seg_end)] if i + 1 < len(starts) \
            else cal[cal >= ws]
        rows = []
        for sym in eligible_asof(stocks, ws,
                                 allowed=_allowed(pit, static_universe, ws)):
            row = screen_row(sym, stocks[sym].loc[:ws], spy_all.loc[:ws],
                             ENTRY_TAGS, [], [], None)
            if row is not None:
                rows.append(row)
        members = [r["symbol"] for r in rank_candidates(rows)[:top_n]]
        curve = _segment_curve(stocks, members, pd.DatetimeIndex(seg), value)
        value = float(curve.iloc[-1])
        parts.append(curve.iloc[:-1] if i + 1 < len(starts) else curve)
    return pd.concat(parts)
