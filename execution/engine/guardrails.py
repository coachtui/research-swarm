"""Hard-coded guardrails the engine cannot override (pure).

Sells always pass (they only reduce exposure). Buys are capped by:
- the sleeve/sector concentration limit (35% of account equity per sector —
  each sector ETF is one sector), then
- available cash including estimated sell proceeds (no leverage, ever), then
- dropped when a halted sleeve forbids new buys (circuit breaker) or when
  less than $1 of cash remains (Alpaca's notional minimum).
"""
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from execution.constants import MAX_SECTOR_PCT_OF_ACCOUNT, MAX_THEME_PCT_OF_SLEEVE

_ALPACA_MIN_NOTIONAL = 1.0


def enforce_guardrails(
    orders: List[Dict[str, Any]],
    account_equity: float,
    cash_available: float,
    allow_buys: bool = True,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    notes: List[str] = []
    adjusted: List[Dict[str, Any]] = []
    sector_cap = MAX_SECTOR_PCT_OF_ACCOUNT * account_equity
    cash = cash_available + sum(
        o.get("est_notional", 0.0) for o in orders if o["side"] == "sell"
    )

    for order in orders:
        if order["side"] == "sell":
            adjusted.append(order)
            continue
        if not allow_buys:
            notes.append(f"{order['symbol']}: buy dropped — sleeve halted (circuit breaker)")
            continue
        notional = order["notional"]
        if notional > sector_cap:
            notes.append(
                f"{order['symbol']}: buy capped at 35% sector limit "
                f"({notional:.2f} -> {sector_cap:.2f})"
            )
            notional = sector_cap
        if cash < _ALPACA_MIN_NOTIONAL:
            notes.append(f"{order['symbol']}: buy dropped — no cash available")
            continue
        if notional > cash:
            notes.append(
                f"{order['symbol']}: buy capped by available cash "
                f"({notional:.2f} -> {cash:.2f})"
            )
            notional = cash
        adjusted.append({**order, "notional": round(notional, 2)})
        cash -= notional
    return adjusted, notes


def enforce_funnel_guardrails(
    orders: List[Dict[str, Any]], sleeve_equity: float, account_equity: float,
    cash_available: float, holdings: List[Dict[str, Any]],
    other_sleeve_sector_notional: Dict[str, float], allow_buys: bool = True,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Sleeve A (funnel) guardrails. Sells always pass. Buys shrink through:
    theme overlap cap → cross-sleeve sector cap → cash (incl. sell proceeds)."""
    notes: List[str] = []
    adjusted: List[Dict[str, Any]] = []

    theme_used: Dict[str, float] = defaultdict(float)
    sector_used: Dict[str, float] = defaultdict(float)
    for h in holdings:
        for slug in (h.get("tags") or {}).get("themes", []):
            theme_used[slug] += h["market_value"]
        if h.get("sector"):
            sector_used[h["sector"]] += h["market_value"]
    for sector, notional in (other_sleeve_sector_notional or {}).items():
        sector_used[sector] += notional

    theme_cap = MAX_THEME_PCT_OF_SLEEVE * sleeve_equity
    sector_cap = MAX_SECTOR_PCT_OF_ACCOUNT * account_equity
    cash = cash_available + sum(
        o.get("est_notional", 0.0) for o in orders if o["side"] == "sell"
    )

    for order in orders:
        if order["side"] == "sell":
            adjusted.append(order)
            continue
        if not allow_buys:
            notes.append(f"{order['symbol']}: buy dropped — sleeve halted (circuit breaker)")
            continue
        notional = float(order["notional"])
        for slug in (order.get("tags") or {}).get("themes", []):
            room = theme_cap - theme_used[slug]
            if notional > room:
                notes.append(
                    f"{order['symbol']}: capped by theme '{slug}' aggregate "
                    f"({notional:.2f} -> {max(room, 0.0):.2f})"
                )
                notional = max(room, 0.0)
        sector = order.get("sector")
        if sector:
            room = sector_cap - sector_used[sector]
            if notional > room:
                notes.append(
                    f"{order['symbol']}: capped by cross-sleeve sector cap '{sector}' "
                    f"({notional:.2f} -> {max(room, 0.0):.2f})"
                )
                notional = max(room, 0.0)
        if notional > cash:
            notes.append(
                f"{order['symbol']}: buy capped by available cash "
                f"({notional:.2f} -> {cash:.2f})"
            )
            notional = cash
        if notional < _ALPACA_MIN_NOTIONAL:
            notes.append(f"{order['symbol']}: buy dropped — below minimum notional")
            continue
        cash -= notional
        for slug in (order.get("tags") or {}).get("themes", []):
            theme_used[slug] += notional
        if sector:
            sector_used[sector] += notional
        adjusted.append({**order, "notional": round(notional, 2)})
    return adjusted, notes
