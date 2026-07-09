"""Tests for the broker layer. alpaca-py is NOT installed in this env, so
tests build AlpacaPaperClient via __new__ and inject fakes for the SDK
attributes the constructor would normally set."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from execution.broker.alpaca_client import AlpacaPaperClient
from execution.broker.base import BrokerOrderResult, BrokerPosition


def _bare_client(fake_trading_client):
    client = AlpacaPaperClient.__new__(AlpacaPaperClient)
    client._client = fake_trading_client
    client._MarketOrderRequest = lambda **kw: SimpleNamespace(**kw)
    client._OrderSide = SimpleNamespace(BUY="buy", SELL="sell")
    client._TimeInForce = SimpleNamespace(DAY="day")
    return client


def _fake_order(status="filled", filled_qty="2", filled_avg_price="101.5"):
    return SimpleNamespace(
        id="ord-1", symbol="XLK", side="buy", status=status,
        filled_qty=filled_qty, filled_avg_price=filled_avg_price,
    )


class TestAccountAndPositions:
    def test_get_account_summary_floats(self):
        fake = MagicMock()
        fake.get_account.return_value = SimpleNamespace(equity="100000.5", cash="30000.25")
        client = _bare_client(fake)
        assert client.get_account_summary() == {"equity": 100000.5, "cash": 30000.25}

    def test_get_positions_maps_to_dataclass(self):
        fake = MagicMock()
        fake.get_all_positions.return_value = [
            SimpleNamespace(symbol="XLE", qty="10.5", market_value="945.0",
                            current_price="90.0", avg_entry_price="88.0"),
        ]
        positions = _bare_client(fake).get_positions()
        assert positions == [BrokerPosition(
            symbol="XLE", qty=10.5, market_value=945.0,
            current_price=90.0, avg_entry_price=88.0,
        )]

    def test_is_market_open(self):
        fake = MagicMock()
        fake.get_clock.return_value = SimpleNamespace(is_open=True)
        assert _bare_client(fake).is_market_open() is True


class TestOrders:
    def test_buy_notional_submits_and_returns_fill(self):
        fake = MagicMock()
        fake.submit_order.return_value = _fake_order()
        fake.get_order_by_id.return_value = _fake_order()
        result = _bare_client(fake).submit_market_buy_notional("XLK", 500.129)

        request = fake.submit_order.call_args.kwargs["order_data"]
        assert request.symbol == "XLK"
        assert request.notional == 500.13  # rounded to cents
        assert request.side == "buy"
        assert result == BrokerOrderResult(
            order_id="ord-1", symbol="XLK", side="buy", status="filled",
            filled_qty=2.0, filled_avg_price=101.5,
        )

    def test_sell_qty_never_notional(self):
        fake = MagicMock()
        fake.submit_order.return_value = _fake_order()
        fake.get_order_by_id.return_value = _fake_order(status="filled")
        _bare_client(fake).submit_market_sell_qty("XLK", 3.25)
        request = fake.submit_order.call_args.kwargs["order_data"]
        assert request.qty == 3.25
        assert request.side == "sell"
        assert not hasattr(request, "notional")

    def test_wait_for_fill_times_out_to_timeout_status(self, monkeypatch):
        fake = MagicMock()
        fake.submit_order.return_value = _fake_order(status="accepted")
        fake.get_order_by_id.return_value = _fake_order(
            status="accepted", filled_qty="0", filled_avg_price=None
        )
        monkeypatch.setattr("execution.broker.alpaca_client._FILL_TIMEOUT_S", 0)
        result = _bare_client(fake).submit_market_buy_notional("XLK", 100)
        assert result.status == "timeout"
        assert result.filled_qty == 0.0
        assert result.filled_avg_price is None
