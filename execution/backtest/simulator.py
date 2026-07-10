# execution/backtest/simulator.py
"""Event-loop simulator: weekly decisions via the production funnel
functions, daily fills/stops between. Only harness concerns live here —
calendars, order queues, the ledger. Decision math is always imported."""
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from execution.constants import (
    BENCHMARK, EQUAL_WEIGHT, MIN_TRADE_NOTIONAL, REGIME_INVESTED_FRACTION,
    SECTOR_ETFS, SLEEVE_A_MAX_POSITIONS, VIX,
)
from execution.funnel.decisions import plan_decisions
from execution.funnel.entries import (
    entry_limit_price, entry_ttl_days, extension_state, size_entry,
)
from execution.funnel.screen import rank_candidates, screen_row
from execution.indicators.breadth import compute_breadth
from execution.indicators.regime import classify_regime

from execution.backtest.fills import (
    LimitOrder, buy_fill_price, check_stop, sell_fill_price, try_fill_buy,
)
from execution.backtest.ledger import Ledger
from execution.backtest.universe import eligible_asof, members_asof

logger = logging.getLogger(__name__)

CANDIDATE_POOL = 25
DELIST_AFTER_MISSING_DAYS = 10
ENTRY_TAGS: Dict[str, Any] = {"themes": [], "industries": [], "watchlist": False}
_NON_STOCK = {BENCHMARK, EQUAL_WEIGHT, VIX, *SECTOR_ETFS}


@dataclass
class BacktestConfig:
    start: str = "2015-01-01"
    end: str = "2026-06-30"
    starting_cash: float = 100_000.0
    flat_conviction: Optional[float] = None   # None → screen_score × 10
    slippage_bps: float = 10.0
    requote_weekly: bool = False        # experiment A: weekly fresh limits
    capitulation_valve: bool = False    # experiment B: market entry after 2 misses


@dataclass
class BacktestResult:
    equity: pd.Series
    journal: List[dict]
    weeks: int


def _conviction(row: Dict[str, Any], cfg: BacktestConfig) -> float:
    if cfg.flat_conviction is not None:
        return float(cfg.flat_conviction)
    return max(0.0, min(100.0, float(row["screen_score"]) * 10.0))


def valve_armed(miss: Optional[dict], conviction: float) -> bool:
    """Two consecutive missed quotes and conviction not lower than the last one."""
    return miss is not None and miss["count"] >= 2 and conviction >= miss["conviction"]


def _record_miss(missed: Dict[str, dict], order: LimitOrder) -> None:
    m = missed.setdefault(order.symbol, {"count": 0, "conviction": 0.0})
    m["count"] += 1
    m["conviction"] = order.conviction


def _week_starts(cal: pd.DatetimeIndex) -> set:
    firsts: Dict[tuple, pd.Timestamp] = {}
    for ts in cal:
        iso = ts.isocalendar()
        firsts.setdefault((iso.year, iso.week), ts)
    return set(firsts.values())


def run_backtest(ohlcv: Dict[str, pd.DataFrame], cfg: BacktestConfig,
                 pit: Optional[pd.DataFrame] = None,
                 static_universe: Optional[List[str]] = None) -> BacktestResult:
    spy = ohlcv[BENCHMARK]
    cal = spy.loc[cfg.start:cfg.end].index
    weeks = _week_starts(cal)
    stocks = {s: df for s, df in ohlcv.items() if s not in _NON_STOCK}
    static = set(static_universe or ())

    ledger = Ledger(cfg.starting_cash)
    open_orders: List[LimitOrder] = []
    pending_sells: List[dict] = []      # {"symbol","qty","reason"}; qty None → full
    pending_market_buys: List[dict] = []   # {"symbol","qty","ref_price","atr","conviction"}
    missed: Dict[str, dict] = {}           # symbol → {"count", "conviction"}
    last_close: Dict[str, float] = {}
    missing_days: Dict[str, int] = {}
    n_weeks = 0

    for today in cal:
        # (a) queued sells at the open
        still_pending: List[dict] = []
        for s in pending_sells:
            sym = s["symbol"]
            pos = ledger.positions.get(sym)
            if pos is None:
                continue
            df = stocks[sym]
            if today not in df.index:
                still_pending.append(s)
                continue
            qty = min(pos.qty, s["qty"] or pos.qty)
            px = sell_fill_price(float(df.at[today, "Open"]), cfg.slippage_bps)
            ledger.sell(sym, qty, px, today.date(), s["reason"])
        pending_sells = still_pending

        # (a2) capitulation market buys at the open (+ adverse slippage)
        still_buys: List[dict] = []
        for b in pending_market_buys:
            df = stocks[b["symbol"]]
            if today not in df.index:
                still_buys.append(b)
                continue
            px = buy_fill_price(float(df.at[today, "Open"]), cfg.slippage_bps)
            if b["qty"] * px <= ledger.cash:
                ledger.buy(b["symbol"], b["qty"], px, today.date(),
                           "capitulation_entry", atr=b["atr"])
                last_close[b["symbol"]] = float(df.at[today, "Close"])
            else:
                ledger.journal.append({"date": today.date(), "side": "cancel",
                                       "symbol": b["symbol"], "qty": b["qty"],
                                       "price": px, "reason": "fill_skipped_cash"})
        pending_market_buys = still_buys

        # (b) limit buys: expiry then fills
        remaining: List[LimitOrder] = []
        for o in open_orders:
            if today.date() > o.expires:
                ledger.journal.append({"date": today.date(), "side": "cancel",
                                       "symbol": o.symbol, "qty": o.qty,
                                       "price": o.limit, "reason": "missed_fill"})
                if cfg.capitulation_valve:
                    _record_miss(missed, o)
                continue
            df = stocks[o.symbol]
            if today in df.index:
                fill = try_fill_buy(o, float(df.at[today, "Open"]),
                                    float(df.at[today, "Low"]))
                if fill is not None:
                    if o.qty * fill <= ledger.cash:
                        ledger.buy(o.symbol, o.qty, fill, today.date(),
                                   "entry_fill", atr=o.atr)
                        last_close[o.symbol] = float(df.at[today, "Close"])
                        missed.pop(o.symbol, None)
                        continue
                    ledger.journal.append({"date": today.date(), "side": "cancel",
                                           "symbol": o.symbol, "qty": o.qty,
                                           "price": fill, "reason": "fill_skipped_cash"})
                    continue
            remaining.append(o)
        open_orders = remaining

        # (c) weekly decisions
        if today in weeks:
            n_weeks += 1
            allowed = (members_asof(pit, today) | static) if pit is not None else None
            _weekly(today, ohlcv, stocks, spy, ledger, open_orders,
                    pending_sells, pending_market_buys, missed,
                    last_close, cfg, allowed)

        # (d) close: stops, delist sweep
        for pos in list(ledger.positions.values()):
            df = stocks[pos.symbol]
            if today in df.index:
                missing_days[pos.symbol] = 0
                close = float(df.at[today, "Close"])
                last_close[pos.symbol] = close
                hw, hit = check_stop(pos.high_water, close, pos.atr)
                pos.high_water = hw
                if hit and not any(s["symbol"] == pos.symbol for s in pending_sells):
                    pending_sells.append({"symbol": pos.symbol, "qty": None,
                                          "reason": "trailing_stop"})
            else:
                missing_days[pos.symbol] = missing_days.get(pos.symbol, 0) + 1
                if missing_days[pos.symbol] >= DELIST_AFTER_MISSING_DAYS:
                    px = sell_fill_price(last_close[pos.symbol], cfg.slippage_bps)
                    ledger.sell(pos.symbol, pos.qty, px, today.date(), "delisted")
                    pending_sells = [s for s in pending_sells
                                     if s["symbol"] != pos.symbol]

        # (e) mark
        ledger.mark(today.date(), last_close)

    return BacktestResult(ledger.equity_series, ledger.journal, n_weeks)


def _weekly(today, ohlcv, stocks, spy, ledger, open_orders, pending_sells,
            market_buys, missed, last_close, cfg, allowed=None) -> None:
    spy_closes = spy.loc[:today]["Close"]

    etf_closes = {sym: ohlcv[sym].loc[:today]["Close"]
                  for sym in (*SECTOR_ETFS, BENCHMARK, EQUAL_WEIGHT) if sym in ohlcv}
    breadth = compute_breadth(etf_closes)
    vix_closes = ohlcv[VIX].loc[:today]["Close"] if VIX in ohlcv else None
    regime = classify_regime(spy_closes, vix_closes,
                             breadth["pct_above_200dma"])["regime"]

    rows = []
    for sym in eligible_asof(stocks, today, allowed=allowed):
        row = screen_row(sym, stocks[sym].loc[:today], spy_closes,
                         ENTRY_TAGS, [], [], None)
        if row is not None:
            rows.append(row)
    ranked = rank_candidates(rows)
    by_symbol = {r["symbol"]: r for r in ranked}

    holdings = []
    for pos in ledger.positions.values():
        row = by_symbol.get(pos.symbol)
        if row is not None:
            pos.atr = float(row["atr"])
        conv = _conviction(row, cfg) if row is not None else 50.0
        price = float(row["price"]) if row is not None else last_close.get(
            pos.symbol, pos.cost_basis)
        holdings.append({"symbol": pos.symbol, "conviction": conv,
                         "market_value": pos.qty * price})
    position_mv = sum(h["market_value"] for h in holdings)
    sleeve_equity = ledger.cash + position_mv

    held = set(ledger.positions)
    candidates = [{"symbol": r["symbol"], "conviction": _conviction(r, cfg)}
                  for r in ranked[:CANDIDATE_POOL] if r["symbol"] not in held]
    plan = plan_decisions(holdings, candidates, sleeve_equity,
                          SLEEVE_A_MAX_POSITIONS)

    queued = {s["symbol"] for s in pending_sells}
    for e in plan["exits"]:
        open_orders[:] = [o for o in open_orders if o.symbol != e["symbol"]]
        if e["symbol"] not in queued:
            pending_sells.append({"symbol": e["symbol"], "qty": None,
                                  "reason": e["reason"]})
            queued.add(e["symbol"])
    for t in plan["trims"]:
        if t["symbol"] in queued:
            continue
        ref = last_close.get(t["symbol"])
        if not ref:
            continue
        qty = int(t["sell_notional"] // ref)
        if qty > 0:
            pending_sells.append({"symbol": t["symbol"], "qty": qty,
                                  "reason": "risk_trim"})
            queued.add(t["symbol"])

    wanted = set(plan["entry_queue"])
    if cfg.requote_weekly:
        # a still-queued name gets a fresh quote off the new week's screen —
        # cancel the stale order here; the entry loop below re-quotes it
        for o in [o for o in open_orders if o.symbol in wanted]:
            open_orders.remove(o)
            ledger.journal.append({"date": today.date(), "side": "cancel",
                                   "symbol": o.symbol, "qty": o.qty,
                                   "price": o.limit, "reason": "requote"})
            if cfg.capitulation_valve:
                _record_miss(missed, o)
    if cfg.capitulation_valve:
        # a streak is *consecutive* misses: break it when the symbol has no
        # standing quote, no pending valve entry, and no place in the queue
        standing = {o.symbol for o in open_orders} | wanted | {
            b["symbol"] for b in market_buys}
        for sym in [s for s in missed if s not in standing]:
            del missed[sym]

    committed = (sum(o.qty * o.limit for o in open_orders)
                 + sum(b["qty"] * b["ref_price"] for b in market_buys))
    invested = REGIME_INVESTED_FRACTION.get(regime, 0.7)
    deployable = max(0.0, invested * sleeve_equity - position_mv - committed)
    cash_remaining = max(0.0, ledger.cash - committed)
    ordered = {o.symbol for o in open_orders} | {b["symbol"] for b in market_buys}

    for sym in plan["entry_queue"]:
        if sym in ordered or sym in queued:
            continue
        row = by_symbol[sym]
        state = extension_state(float(row["ext_atr"]))
        limit = entry_limit_price(state, float(row["price"]),
                                  float(row["sma20"]), float(row["atr"]))
        if limit <= 0:
            continue
        conv = _conviction(row, cfg)
        notional = size_entry(conv, sleeve_equity,
                              float(row["liquidity_adv_usd"] or 0.0),
                              float(row["atr_pct"]), deployable, cash_remaining)
        if cfg.capitulation_valve and valve_armed(missed.get(sym), conv):
            price = float(row["price"])
            qty = int((notional / 2.0) // price)
            if qty > 0 and qty * price >= MIN_TRADE_NOTIONAL:
                market_buys.append({"symbol": sym, "qty": qty, "ref_price": price,
                                    "atr": float(row["atr"]), "conviction": conv})
                missed.pop(sym, None)
                spent = qty * price
                deployable = max(0.0, deployable - spent)
                cash_remaining = max(0.0, cash_remaining - spent)
                continue
            # half-notional under the trade floor: no valve entry, streak stands
        qty = int(notional // limit)
        if qty <= 0 or qty * limit < MIN_TRADE_NOTIONAL:
            continue
        ttl = entry_ttl_days(state)
        open_orders.append(LimitOrder(
            symbol=sym, qty=qty, limit=limit, atr=float(row["atr"]),
            placed=today.date(), expires=today.date() + timedelta(days=ttl),
            conviction=conv))
        spent = qty * limit
        deployable = max(0.0, deployable - spent)
        cash_remaining = max(0.0, cash_remaining - spent)
