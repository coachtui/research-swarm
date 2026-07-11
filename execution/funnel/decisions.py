"""Weekly decision planner (pure). Priority: sell-verdict → failed theme
review → outcompeted → risk trim → entries. No maintenance rebalancing:
between the entry band and the trim ceiling, winners run untouched."""
from typing import Any, Dict, List, Optional

from execution.constants import (
    OUTCOMPETE_MARGIN, RISK_TRIM_CEILING, RISK_TRIM_TARGET,
)


_TRIM_DEFAULT = object()


def plan_decisions(
    holdings: List[Dict[str, Any]], candidates: List[Dict[str, Any]],
    sleeve_equity: float, max_positions: int,
    evictions: bool = True, trim_ceiling: Any = _TRIM_DEFAULT,
) -> Dict[str, Any]:
    if trim_ceiling is _TRIM_DEFAULT:
        trim_ceiling = RISK_TRIM_CEILING
    exits: List[Dict[str, str]] = []
    notes: List[str] = []

    for h in holdings:
        if h.get("vetoed"):
            exits.append({"symbol": h["symbol"], "reason": "sell_verdict"})
        elif h.get("theme_review_failed"):
            exits.append({"symbol": h["symbol"], "reason": "theme_review_failed"})
    exited = {e["symbol"] for e in exits}
    survivors = [h for h in holdings if h["symbol"] not in exited]

    held = {h["symbol"] for h in holdings}
    challengers = sorted(
        (c for c in candidates if not c.get("vetoed") and c["symbol"] not in held),
        key=lambda c: c["conviction"], reverse=True,
    )

    # Outcompete: while the book is full, the strongest challenger may evict
    # the weakest survivor only by clearing the hysteresis margin.
    entry_queue: List[str] = []
    book = sorted(survivors, key=lambda h: h["conviction"])
    for ch in challengers:
        if len(book) + len(entry_queue) < max_positions:
            entry_queue.append(ch["symbol"])
            continue
        if not book:
            break
        if not evictions:
            break                     # thesis-hold: challengers never evict
        weakest = book[0]
        if ch["conviction"] >= weakest["conviction"] + OUTCOMPETE_MARGIN:
            exits.append({"symbol": weakest["symbol"], "reason": "outcompeted"})
            book.pop(0)
            entry_queue.append(ch["symbol"])
        else:
            notes.append(
                f"{ch['symbol']}: blocked — inside hysteresis margin vs {weakest['symbol']}"
            )
            break  # ordered by conviction: nobody weaker can clear it either

    trims: List[Dict[str, Any]] = []
    if sleeve_equity > 0 and trim_ceiling is not None:
        exited = {e["symbol"] for e in exits}
        for h in holdings:
            if h["symbol"] in exited:
                continue
            weight = h["market_value"] / sleeve_equity
            if weight > trim_ceiling:
                trims.append({
                    "symbol": h["symbol"],
                    "sell_notional": round(
                        h["market_value"] - RISK_TRIM_TARGET * sleeve_equity, 2
                    ),
                    "reason": "risk_trim",
                })
    return {"exits": exits, "trims": trims, "entry_queue": entry_queue, "notes": notes}
