"""Alpaca paper-account client (alpaca-py TradingClient wrapper).

All methods are synchronous — async callers must use asyncio.to_thread
(same convention as the yfinance calls in weekly_batch). SDK classes are
imported in __init__ and stored on self so unit tests can inject fakes via
__new__ without alpaca-py installed.
"""
import time
from typing import Dict, List, Optional

from execution.broker.base import BrokerOrderResult, BrokerPosition

_FILL_TIMEOUT_S = 30
_TERMINAL_STATUSES = ("filled", "canceled", "rejected", "expired")


def _enum_str(value) -> str:
    return str(value.value) if hasattr(value, "value") else str(value)


class AlpacaPaperClient:
    def __init__(self, api_key: str, api_secret: str):
        from alpaca.trading.client import TradingClient  # lazy — runtime dep
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

        self._client = TradingClient(api_key, api_secret, paper=True)
        self._MarketOrderRequest = MarketOrderRequest
        self._LimitOrderRequest = LimitOrderRequest
        self._OrderSide = OrderSide
        self._TimeInForce = TimeInForce

    def get_account_summary(self) -> Dict[str, float]:
        account = self._client.get_account()
        return {"equity": float(account.equity), "cash": float(account.cash)}

    def get_positions(self) -> List[BrokerPosition]:
        return [
            BrokerPosition(
                symbol=p.symbol,
                qty=float(p.qty),
                market_value=float(p.market_value),
                current_price=float(p.current_price),
                avg_entry_price=float(p.avg_entry_price),
            )
            for p in self._client.get_all_positions()
        ]

    def is_market_open(self) -> bool:
        return bool(self._client.get_clock().is_open)

    def submit_market_buy_notional(self, symbol: str, notional: float) -> BrokerOrderResult:
        order = self._client.submit_order(
            order_data=self._MarketOrderRequest(
                symbol=symbol,
                notional=round(notional, 2),
                side=self._OrderSide.BUY,
                time_in_force=self._TimeInForce.DAY,
            )
        )
        return self._wait_for_fill(order.id)

    def submit_market_sell_qty(self, symbol: str, qty: float) -> BrokerOrderResult:
        order = self._client.submit_order(
            order_data=self._MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=self._OrderSide.SELL,
                time_in_force=self._TimeInForce.DAY,
            )
        )
        return self._wait_for_fill(order.id)

    def submit_gtc_limit_buy(
        self, symbol: str, qty: float, limit_price: float,
        client_order_id: Optional[str] = None,
    ) -> BrokerOrderResult:
        """Place a good-till-canceled limit buy and return IMMEDIATELY with its
        working status — a GTC limit may sit open for days, so (unlike the
        market helpers) we do NOT poll to fill here; the daily settle sweep
        polls by order id. client_order_id makes the submit idempotent: Alpaca
        rejects a duplicate outright."""
        order = self._client.submit_order(
            order_data=self._LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                limit_price=round(limit_price, 2),
                side=self._OrderSide.BUY,
                time_in_force=self._TimeInForce.GTC,
                client_order_id=client_order_id,
            )
        )
        return self._to_result(order, _enum_str(order.status))

    def get_order(self, order_id) -> BrokerOrderResult:
        """Current normalized state of one order (for the settle sweep)."""
        order = self._client.get_order_by_id(order_id)
        return self._to_result(order, _enum_str(order.status))

    def cancel_order(self, order_id) -> None:
        self._client.cancel_order_by_id(order_id)

    def _to_result(self, order, status: str) -> BrokerOrderResult:
        price = order.filled_avg_price
        return BrokerOrderResult(
            order_id=str(order.id),
            symbol=order.symbol,
            side=_enum_str(order.side),
            status=status,
            filled_qty=float(order.filled_qty or 0),
            filled_avg_price=float(price) if price else None,
        )

    def _wait_for_fill(self, order_id) -> BrokerOrderResult:
        """Poll until terminal status or timeout. Paper market orders fill
        near-instantly in regular hours; timeout is a safety valve, and a
        'timeout' result is journaled, never guessed at."""
        deadline = time.monotonic() + _FILL_TIMEOUT_S
        while True:
            order = self._client.get_order_by_id(order_id)
            status = _enum_str(order.status)
            if status in _TERMINAL_STATUSES:
                return self._to_result(order, status)
            if time.monotonic() >= deadline:
                # Cancel the still-working DAY order so a late fill can't
                # silently drift the cash ledger. The cancel can race a fill —
                # re-fetch once and report whichever won.
                try:
                    self._client.cancel_order_by_id(order_id)
                except Exception:
                    pass  # already filled/canceled — the re-fetch tells us
                order = self._client.get_order_by_id(order_id)
                status = _enum_str(order.status)
                return self._to_result(
                    order, status if status in _TERMINAL_STATUSES else "timeout"
                )
            time.sleep(1.0)


def client_from_account(row) -> AlpacaPaperClient:
    """Build a client from a LinkedBrokerAccount row (decrypts in-process;
    plaintext keys must never cross an Inngest step boundary)."""
    from execution.broker.credentials import decrypt_secret

    return AlpacaPaperClient(
        decrypt_secret(row.apiKeyEncrypted),
        decrypt_secret(row.apiSecretEncrypted),
    )
