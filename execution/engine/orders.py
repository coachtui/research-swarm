"""Turn target notionals into concrete market orders (pure).

Sells first (they free the cash the buys need). Full exits sell the whole
position qty; trims sell qty at current price; buys are notional (Alpaca
notional orders are DAY-only, which is what we use anyway).
"""
from typing import Any, Dict, List

from execution.constants import MIN_TRADE_NOTIONAL


def diff_to_orders(
    targets: Dict[str, float],
    positions: Dict[str, Dict[str, float]],
) -> List[Dict[str, Any]]:
    sells: List[Dict[str, Any]] = []
    buys: List[Dict[str, Any]] = []
    for symbol in sorted(set(targets) | set(positions)):
        target = targets.get(symbol, 0.0)
        pos = positions.get(symbol)
        current = pos["market_value"] if pos else 0.0
        delta = target - current

        if pos and delta < 0 and (target <= 0 or -delta >= MIN_TRADE_NOTIONAL):
            full_exit = target <= 0
            qty = pos["qty"] if full_exit else round(-delta / pos["current_price"], 4)
            qty = min(qty, pos["qty"])  # never short
            if qty > 0:
                sells.append({
                    "symbol": symbol,
                    "side": "sell",
                    "qty": qty,
                    "est_notional": round(qty * pos["current_price"], 2),
                })
        elif delta >= MIN_TRADE_NOTIONAL:
            buys.append({"symbol": symbol, "side": "buy", "notional": round(delta, 2)})
    return sells + buys
