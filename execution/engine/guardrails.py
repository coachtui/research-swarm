"""Hard-coded guardrails the engine cannot override (pure).

Sells always pass (they only reduce exposure). Buys are capped by:
- the sleeve/sector concentration limit (35% of account equity per sector —
  each sector ETF is one sector), then
- available cash including estimated sell proceeds (no leverage, ever), then
- dropped when a halted sleeve forbids new buys (circuit breaker) or when
  less than $1 of cash remains (Alpaca's notional minimum).
"""
from typing import Any, Dict, List, Tuple

from execution.constants import MAX_SECTOR_PCT_OF_ACCOUNT

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
