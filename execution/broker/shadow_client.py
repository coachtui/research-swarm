# execution/broker/shadow_client.py
"""Shadow broker for Sleeve A (Phase 3C). Same result shapes as
AlpacaPaperClient, but orders are EngineTrade rows and fills come from real
daily bars under the honesty rule: a shadow order fills ONLY if the market
traded through its limit, always AT the limit — no generous fills, so the
3D backtest comparison stays honest. Phase 3D flips Sleeve A live by
swapping this client for AlpacaPaperClient. Nothing here talks to Alpaca."""
import logging
from datetime import datetime
from typing import Any, Dict, List

from execution.broker.base import BrokerOrderResult
from execution.sleeve_service import position_after_fill

logger = logging.getLogger(__name__)


def evaluate_fill(
    side: str, limit_price: float, day_high: float, day_low: float, expired: bool,
) -> str:
    traded_through = (day_low <= limit_price) if side == "buy" else (day_high >= limit_price)
    if traded_through:
        return "filled"
    return "expired" if expired else "open"


class ShadowBrokerClient:
    def __init__(self, db, sleeve: str = "A"):
        self._db = db
        self._sleeve = sleeve

    async def submit_limit_buy(
        self, symbol: str, qty: float, limit_price: float, expires_at: datetime,
        journal: Dict[str, Any], client_order_id: str,
    ) -> BrokerOrderResult:
        from prisma import Json  # noqa: PLC0415

        existing = await self._db.enginetrade.find_first(
            where={"brokerOrderId": client_order_id}
        )
        if existing is None:
            await self._db.enginetrade.create(data={
                "sleeve": self._sleeve, "symbol": symbol, "side": "buy",
                "qty": qty, "notional": round(qty * limit_price, 2),
                "limitPrice": limit_price, "expiresAt": expires_at,
                "brokerOrderId": client_order_id, "status": "shadow_open",
                "journal": Json(journal or {}),
            })
        return BrokerOrderResult(
            order_id=client_order_id, symbol=symbol, side="buy",
            status="shadow_open", filled_qty=0.0, filled_avg_price=None,
        )

    async def submit_sell(
        self, symbol: str, qty: float, price_hint: float,
        journal: Dict[str, Any], client_order_id: str,
    ) -> BrokerOrderResult:
        """Shadow sell — fills immediately AT price_hint (the caller's last
        close / stop level). Same behavior as the former submit_shadow_sell;
        renamed to share a signature with AlpacaFunnelBroker.submit_sell so the
        crons are broker-agnostic (the live broker ignores the hint)."""
        from prisma import Json  # noqa: PLC0415

        existing = await self._db.enginetrade.find_first(
            where={"brokerOrderId": client_order_id}
        )
        if existing is None:
            await self._db.enginetrade.create(data={
                "sleeve": self._sleeve, "symbol": symbol, "side": "sell",
                "qty": qty, "fillPrice": price_hint, "limitPrice": None,
                "brokerOrderId": client_order_id, "status": "shadow_filled",
                "journal": Json(journal or {}),
            })
            await self._reduce_position(symbol, qty, price_hint)
        return BrokerOrderResult(
            order_id=client_order_id, symbol=symbol, side="sell",
            status="shadow_filled", filled_qty=qty, filled_avg_price=price_hint,
        )

    async def submit_market_buy(
        self, symbol: str, qty: float, price_hint: float,
        journal: Dict[str, Any], client_order_id: str,
    ) -> BrokerOrderResult:
        """Shadow market buy for DCA ADD tranches — fills immediately AT
        price_hint (same convention as submit_sell; there's no real market to
        trade through in the shadow world). Idempotent on client_order_id
        like submit_sell/submit_limit_buy. _increase_position's update branch
        (an ADD to an existing position) leaves highWaterClose untouched — it
        anchors the DCA ladder and only the create branch seeds it."""
        from prisma import Json  # noqa: PLC0415

        existing = await self._db.enginetrade.find_first(
            where={"brokerOrderId": client_order_id}
        )
        if existing is None:
            await self._db.enginetrade.create(data={
                "sleeve": self._sleeve, "symbol": symbol, "side": "buy",
                "qty": qty, "fillPrice": price_hint, "limitPrice": None,
                "brokerOrderId": client_order_id, "status": "shadow_filled",
                "journal": Json(journal or {}),
            })
            await self._increase_position(symbol, qty, price_hint)
        return BrokerOrderResult(
            order_id=client_order_id, symbol=symbol, side="buy",
            status="shadow_filled", filled_qty=qty, filled_avg_price=price_hint,
        )

    async def get_open_orders(self) -> List[Any]:
        return await self._db.enginetrade.find_many(
            where={"sleeve": self._sleeve, "status": "shadow_open"}
        )

    async def settle_open_order(
        self, order: Any, day_high: float, day_low: float, now: datetime,
    ) -> Dict[str, Any]:
        try:
            expires = order.expiresAt
            expired = bool(expires is not None and now > expires)
            verdict = evaluate_fill(order.side, order.limitPrice, day_high, day_low, expired)
            if verdict == "open":
                return {"status": "open", "cash_delta": 0.0}
            if verdict == "expired":
                await self._db.enginetrade.update(
                    where={"id": order.id}, data={"status": "shadow_expired"}
                )
                return {"status": "expired", "cash_delta": 0.0}
            await self._db.enginetrade.update(
                where={"id": order.id},
                data={"status": "shadow_filled", "fillPrice": order.limitPrice},
            )
            # fill_price/filled_qty surfaced (same keys as AlpacaFunnelBroker)
            # so the cron journals actual fill values broker-agnostically.
            fill_keys = {"fill_price": order.limitPrice, "filled_qty": order.qty}
            if order.side == "buy":
                await self._increase_position(order.symbol, order.qty, order.limitPrice)
                return {"status": "filled",
                        "cash_delta": -round(order.qty * order.limitPrice, 2), **fill_keys}
            await self._reduce_position(order.symbol, order.qty, order.limitPrice)
            return {"status": "filled",
                    "cash_delta": round(order.qty * order.limitPrice, 2), **fill_keys}
        except Exception:  # noqa: BLE001 — a broken settle must not sink the sweep
            logger.exception("shadow settle failed for order %s", getattr(order, "id", "?"))
            return {"status": "error", "cash_delta": 0.0}

    async def _increase_position(self, symbol: str, qty: float, price: float) -> None:
        row = await self._db.engineposition.find_unique(
            where={"sleeve_symbol": {"sleeve": self._sleeve, "symbol": symbol}}
        )
        qty0 = float(getattr(row, "qty", 0.0) or 0.0)
        avg0 = float(getattr(row, "avgEntryPrice", 0.0) or 0.0)
        qty1, avg1 = position_after_fill(qty0, avg0, qty, price, "buy")
        from prisma import Json  # noqa: PLC0415

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
            logger.warning("shadow sell with no position: %s", symbol)
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
