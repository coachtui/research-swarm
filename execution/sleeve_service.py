"""DB touchpoints for sleeve state, positions, trades, and snapshots.

Same edge-layer role outlook_service.py plays for MarketOutlook: all prisma
access for the execution engine funnels through here; everything above it
is pure. JSON columns are wrapped in prisma.Json at this edge only.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

_QTY_EPSILON = 1e-6


async def get_sleeve_state(db, sleeve: str) -> Optional[Any]:
    return await db.sleevestate.find_unique(where={"sleeve": sleeve})


async def init_sleeve_state(
    db, sleeve: str, cash: float, spy_close: float, inception_date: datetime
) -> Any:
    return await db.sleevestate.create(data={
        "sleeve": sleeve,
        "status": "active",
        "cashBalance": round(cash, 2),
        "inceptionDate": inception_date,
        "inceptionEquity": round(cash, 2),
        "inceptionSpyClose": spy_close,
    })


async def set_sleeve_status(db, sleeve: str, status: str, reason: Optional[str] = None) -> Any:
    return await db.sleevestate.update(
        where={"sleeve": sleeve},
        data={"status": status, "statusReason": reason},
    )


async def update_sleeve_cash(db, sleeve: str, cash_balance: float) -> Any:
    return await db.sleevestate.update(
        where={"sleeve": sleeve},
        data={"cashBalance": round(cash_balance, 2)},
    )


async def get_engine_positions(db, sleeve: str) -> List[Any]:
    return await db.engineposition.find_many(where={"sleeve": sleeve})


async def store_snapshot(
    db, sleeve: str, snapshot_date: datetime, equity: float,
    cash: float, positions_value: float, spy_close: float,
) -> Any:
    payload = {
        "equity": round(equity, 2),
        "cash": round(cash, 2),
        "positionsValue": round(positions_value, 2),
        "spyClose": spy_close,
    }
    return await db.sleevesnapshot.upsert(
        where={"snapshotDate_sleeve": {"snapshotDate": snapshot_date, "sleeve": sleeve}},
        data={
            "create": {"snapshotDate": snapshot_date, "sleeve": sleeve, **payload},
            "update": payload,
        },
    )


async def apply_fill(
    db, sleeve: str, fill: Dict[str, Any],
    requested_notional: Optional[float], journal: Dict[str, Any],
) -> float:
    """Record one broker fill: EngineTrade row (always — even unfilled
    orders belong in the audit trail) + EnginePosition upsert/delete.
    Returns the signed cash delta (negative for buys)."""
    from prisma import Json  # runtime-only dependency

    symbol = fill["symbol"]
    side = fill["side"]
    filled_qty = float(fill.get("filled_qty") or 0.0)
    fill_price = fill.get("filled_avg_price")

    # Idempotency contract: Inngest's persist-fills step is un-memoized per
    # fill, so a partial-failure retry re-runs this function for fills that
    # already made it to the DB on a prior attempt. Dedupe on brokerOrderId
    # so a retry never re-creates the EngineTrade row or re-applies the
    # position delta (which would double-count qty/avgEntryPrice) — it still
    # returns the same cash delta so the caller's running total stays correct.
    order_id = fill.get("order_id")
    if order_id:
        existing_trade = await db.enginetrade.find_first(
            where={"brokerOrderId": order_id}
        )
        if existing_trade is not None:
            if filled_qty <= 0 or fill_price is None:
                return 0.0
            notional = filled_qty * float(fill_price)
            return -round(notional, 2) if side == "buy" else round(notional, 2)

    await db.enginetrade.create(data={
        "sleeve": sleeve,
        "symbol": symbol,
        "side": side,
        "qty": filled_qty,
        "notional": requested_notional,
        "fillPrice": fill_price,
        "brokerOrderId": fill.get("order_id"),
        "status": fill["status"],
        "journal": Json(journal),
    })

    if filled_qty <= 0 or fill_price is None:
        return 0.0  # nothing actually traded

    notional = filled_qty * float(fill_price)
    existing = await db.engineposition.find_unique(
        where={"sleeve_symbol": {"sleeve": sleeve, "symbol": symbol}}
    )

    if side == "buy":
        if existing is None:
            new_qty, new_avg = filled_qty, float(fill_price)
        else:
            new_qty = existing.qty + filled_qty
            new_avg = (existing.qty * existing.avgEntryPrice + notional) / new_qty
        await db.engineposition.upsert(
            where={"sleeve_symbol": {"sleeve": sleeve, "symbol": symbol}},
            data={
                "create": {
                    "sleeve": sleeve, "symbol": symbol, "qty": new_qty,
                    "avgEntryPrice": round(new_avg, 4), "thesis": Json(journal),
                },
                "update": {"qty": new_qty, "avgEntryPrice": round(new_avg, 4)},
            },
        )
        return -round(notional, 2)

    # sell
    remaining = (existing.qty if existing else 0.0) - filled_qty
    if remaining <= _QTY_EPSILON:
        if existing is not None:
            await db.engineposition.delete(
                where={"sleeve_symbol": {"sleeve": sleeve, "symbol": symbol}}
            )
    else:
        await db.engineposition.update(
            where={"sleeve_symbol": {"sleeve": sleeve, "symbol": symbol}},
            data={"qty": remaining},
        )
    return round(notional, 2)
