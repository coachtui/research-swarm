# execution/broker/alpaca_funnel_client.py
"""Live paper-account broker for Sleeve A.

Owner ruling (2026-07-10): Sleeve A trades DIRECTLY on the Alpaca paper
account — the earlier "shadow" scoping was a mis-scoping. This client mirrors
ShadowBrokerClient's surface (submit_limit_buy / submit_sell / get_open_orders
/ settle_open_order) so the funnel and daily crons switch brokers purely on
SleeveState.mode with near-zero call-site change.

EngineTrade rows stay the book of record; every position move flows through
the shared `position_after_fill` math. Unlike the shadow client, fills come
from REAL Alpaca orders at ACTUAL prices; nothing is imagined from daily bars.
All Alpaca SDK calls are synchronous and wrapped in asyncio.to_thread.

ShadowBrokerClient is retained as the Phase 3D backtest replay engine; 3D's
backtest — not this client — is what gates the move to real money.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from execution.broker.base import BrokerOrderResult
from execution.sleeve_service import position_after_fill

logger = logging.getLogger(__name__)


class AlpacaFunnelBroker:
    def __init__(self, db, alpaca, sleeve: str = "A"):
        self._db = db
        self._alpaca = alpaca
        self._sleeve = sleeve

    async def submit_limit_buy(
        self, symbol: str, qty: float, limit_price: float, expires_at: datetime,
        journal: Dict[str, Any], client_order_id: str,
    ) -> BrokerOrderResult:
        """Idempotent GTC limit buy. Guarded TWO ways:
        1. local — a prior attempt already booked this client_order_id (we
           store it in the journal, since brokerOrderId now holds the Alpaca
           id, and look it up on the JSON path);
        2. authoritative — Alpaca rejects a duplicate client_order_id outright
           (closing the long-deferred Phase 2 idempotency rider).
        Exactly ONE EngineTrade row per order: status "open", brokerOrderId =
        the ALPACA order id."""
        from prisma import Json  # noqa: PLC0415

        existing = await self._db.enginetrade.find_first(
            where={
                "sleeve": self._sleeve,
                "journal": {"path": ["client_order_id"], "equals": client_order_id},
            }
        )
        if existing is not None:
            return BrokerOrderResult(
                order_id=str(existing.brokerOrderId), symbol=symbol, side="buy",
                status=existing.status, filled_qty=0.0, filled_avg_price=None,
            )

        result = await asyncio.to_thread(
            self._alpaca.submit_gtc_limit_buy, symbol, qty, limit_price, client_order_id,
        )
        merged_journal = {**(journal or {}), "client_order_id": client_order_id}
        await self._db.enginetrade.create(data={
            "sleeve": self._sleeve, "symbol": symbol, "side": "buy",
            "qty": qty, "notional": round(qty * limit_price, 2),
            "limitPrice": limit_price, "expiresAt": expires_at,
            "brokerOrderId": result.order_id, "status": "open",
            "journal": Json(merged_journal),
        })
        return BrokerOrderResult(
            order_id=result.order_id, symbol=symbol, side="buy",
            status="open", filled_qty=0.0, filled_avg_price=None,
        )

    async def submit_sell(
        self, symbol: str, qty: float, price_hint: float,
        journal: Dict[str, Any], client_order_id: str,
    ) -> BrokerOrderResult:
        """Market sell (the existing helper already polls to fill). price_hint
        is IGNORED — the real market decides the price. Records the EngineTrade
        at the ACTUAL filled_avg_price and reduces the position accordingly.

        Idempotent like the buy path (C1): the funnel's decide/execute stage
        replays outside step.run, so a repeated client_order_id must NOT fire a
        second real market sell (oversold position, double cash credit). Guarded
        two ways — the journal client_order_id lookup short-circuits to the
        recorded fill, and the coid is passed to Alpaca so its duplicate
        rejection backs the DB guard."""
        from prisma import Json  # noqa: PLC0415

        existing = await self._db.enginetrade.find_first(
            where={
                "sleeve": self._sleeve,
                "journal": {"path": ["client_order_id"], "equals": client_order_id},
            }
        )
        if existing is not None:
            return BrokerOrderResult(
                order_id=str(existing.brokerOrderId), symbol=symbol, side="sell",
                status=existing.status, filled_qty=float(existing.qty or 0.0),
                filled_avg_price=existing.fillPrice,
            )

        result = await asyncio.to_thread(
            self._alpaca.submit_market_sell_qty, symbol, qty, client_order_id,
        )
        fill_price = result.filled_avg_price
        filled_qty = float(result.filled_qty or 0.0)
        await self._db.enginetrade.create(data={
            "sleeve": self._sleeve, "symbol": symbol, "side": "sell",
            "qty": filled_qty if filled_qty > 0 else qty,
            "fillPrice": fill_price, "limitPrice": None,
            "brokerOrderId": result.order_id, "status": result.status,
            "journal": Json({**(journal or {}), "client_order_id": client_order_id}),
        })
        if fill_price is not None and filled_qty > 0:
            await self._reduce_position(symbol, filled_qty, float(fill_price))
        return result

    async def get_open_orders(self) -> List[Any]:
        return await self._db.enginetrade.find_many(
            where={"sleeve": self._sleeve, "status": "open"}
        )

    async def settle_open_order(
        self, order: Any, day_high: float, day_low: float, now: datetime,
    ) -> Dict[str, Any]:
        """Settle one open limit buy against Alpaca (the bars are IGNORED — the
        real order status is authoritative). Filled -> book the actual fill.
        Past expiry and unfilled -> cancel (a fill can race the cancel; re-check
        once, the fill wins). Partial fill at expiry -> cancel the remainder and
        book the filled portion. Never raises."""
        try:
            result = await asyncio.to_thread(self._alpaca.get_order, order.brokerOrderId)
            if result.status == "filled":
                return await self._book_fill(
                    order, float(result.filled_qty or 0.0), float(result.filled_avg_price),
                    full=True,
                )

            expires = order.expiresAt
            expired = bool(expires is not None and now > expires)
            if not expired:
                return {"status": "open", "cash_delta": 0.0}

            # Expired and unfilled -> cancel. The cancel can race a late fill;
            # re-fetch once and let a fill win.
            try:
                await asyncio.to_thread(self._alpaca.cancel_order, order.brokerOrderId)
            except Exception:  # noqa: BLE001 — already filled/canceled; re-check tells us
                pass
            result = await asyncio.to_thread(self._alpaca.get_order, order.brokerOrderId)
            if result.status == "filled":
                return await self._book_fill(
                    order, float(result.filled_qty or 0.0), float(result.filled_avg_price),
                    full=True,
                )
            filled_qty = float(result.filled_qty or 0.0)
            if filled_qty > 0 and result.filled_avg_price is not None:
                # A partial fill locked in before the cancel — book just that part.
                return await self._book_fill(
                    order, filled_qty, float(result.filled_avg_price),
                    full=False, note="partial_fill_at_expiry",
                )
            await self._db.enginetrade.update(
                where={"id": order.id}, data={"status": "expired"}
            )
            return {"status": "expired", "cash_delta": 0.0}
        except Exception:  # noqa: BLE001 — a broken settle must not sink the sweep
            logger.exception("alpaca settle failed for order %s", getattr(order, "id", "?"))
            return {"status": "error", "cash_delta": 0.0}

    async def _book_fill(
        self, order: Any, filled_qty: float, fill_price: float,
        full: bool, note: Optional[str] = None,
    ) -> Dict[str, Any]:
        from prisma import Json  # noqa: PLC0415

        data: Dict[str, Any] = {"status": "filled", "fillPrice": fill_price}
        if not full:
            # Trim the recorded qty to what actually filled and note the partial.
            data["qty"] = filled_qty
            journal = getattr(order, "journal", None)
            if isinstance(journal, dict):
                data["journal"] = Json({**journal, "note": note})
        await self._db.enginetrade.update(where={"id": order.id}, data=data)
        await self._increase_position(order.symbol, filled_qty, fill_price)
        # fill_price/filled_qty surfaced so the cron journals ACTUAL values.
        return {"status": "filled", "cash_delta": -round(filled_qty * fill_price, 2),
                "fill_price": fill_price, "filled_qty": filled_qty}

    async def _increase_position(self, symbol: str, qty: float, price: float) -> None:
        from prisma import Json  # noqa: PLC0415

        row = await self._db.engineposition.find_unique(
            where={"sleeve_symbol": {"sleeve": self._sleeve, "symbol": symbol}}
        )
        qty0 = float(getattr(row, "qty", 0.0) or 0.0)
        avg0 = float(getattr(row, "avgEntryPrice", 0.0) or 0.0)
        qty1, avg1 = position_after_fill(qty0, avg0, qty, price, "buy")
        await self._db.engineposition.upsert(
            where={"sleeve_symbol": {"sleeve": self._sleeve, "symbol": symbol}},
            data={
                "create": {"sleeve": self._sleeve, "symbol": symbol, "qty": qty1,
                           "avgEntryPrice": avg1, "thesis": Json({}),
                           "highWaterClose": price, "stopPrice": None},
                "update": {"qty": qty1, "avgEntryPrice": avg1},
            },
        )

    async def _reduce_position(self, symbol: str, qty: float, price: float) -> None:
        row = await self._db.engineposition.find_unique(
            where={"sleeve_symbol": {"sleeve": self._sleeve, "symbol": symbol}}
        )
        if row is None:
            logger.warning("alpaca sell with no position: %s", symbol)
            return
        qty1, avg1 = position_after_fill(float(row.qty), float(row.avgEntryPrice),
                                         qty, price, "sell")
        if qty1 <= 0:
            await self._db.engineposition.delete(
                where={"sleeve_symbol": {"sleeve": self._sleeve, "symbol": symbol}}
            )
        else:
            await self._db.engineposition.update(
                where={"sleeve_symbol": {"sleeve": self._sleeve, "symbol": symbol}},
                data={"qty": qty1, "avgEntryPrice": avg1},
            )
