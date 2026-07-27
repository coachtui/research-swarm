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
    client._GetAssetsRequest = lambda **kw: SimpleNamespace(**kw)
    client._OrderSide = SimpleNamespace(BUY="buy", SELL="sell")
    client._TimeInForce = SimpleNamespace(DAY="day")
    client._AssetClass = SimpleNamespace(US_EQUITY="us_equity")
    client._AssetStatus = SimpleNamespace(ACTIVE="active")
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

    def test_list_tradable_us_equities_filters_untradable_and_requests_active_us_equity(self):
        # Regression: the funnel's universe feed (ETF top-holdings, theme
        # membership) can carry a foreign listing (e.g. Air Canada as
        # "AC.TO") or a name delisted post-acquisition that the data vendor
        # hasn't dropped. Alpaca's asset list is the ground truth for what's
        # actually orderable — only tradable=True symbols should survive.
        fake = MagicMock()
        fake.get_all_assets.return_value = [
            SimpleNamespace(symbol="AEHR", tradable=True),
            SimpleNamespace(symbol="JNPR", tradable=False),  # delisted
        ]
        result = _bare_client(fake).list_tradable_us_equities()
        assert result == {"AEHR"}
        request = fake.get_all_assets.call_args.args[0]
        assert request.asset_class == "us_equity"
        assert request.status == "active"


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
        # Default (no client_order_id) keeps the request byte-identical to the
        # pre-Sleeve-A shape — Sleeve B's behavior is pinned unchanged.
        assert not hasattr(request, "client_order_id")

    def test_sell_qty_threads_client_order_id(self):
        # C1: an explicit client_order_id reaches the MarketOrderRequest so
        # Alpaca's duplicate rejection backs the engine's DB idempotency guard.
        fake = MagicMock()
        fake.submit_order.return_value = _fake_order()
        fake.get_order_by_id.return_value = _fake_order(status="filled")
        _bare_client(fake).submit_market_sell_qty("AEHR", 3.25, "coid-sell-1")
        request = fake.submit_order.call_args.kwargs["order_data"]
        assert request.client_order_id == "coid-sell-1"
        assert request.qty == 3.25 and request.side == "sell"

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
        fake.cancel_order_by_id.assert_called_once()

    def test_timeout_cancel_races_late_fill(self, monkeypatch):
        fake = MagicMock()
        fake.submit_order.return_value = _fake_order(status="accepted")
        fake.get_order_by_id.side_effect = [
            _fake_order(status="accepted", filled_qty="0", filled_avg_price=None),
            _fake_order(status="filled", filled_qty="2", filled_avg_price="101.5"),
        ]
        monkeypatch.setattr("execution.broker.alpaca_client._FILL_TIMEOUT_S", 0)
        result = _bare_client(fake).submit_market_buy_notional("XLK", 100)
        assert result.status == "filled"
        assert result.filled_qty == 2.0
        assert result.filled_avg_price == 101.5
        fake.cancel_order_by_id.assert_called_once()
        assert fake.get_order_by_id.call_count == 2


class TestTradableFromEnv:
    """Local CLI escape hatch — production crons still go through the encrypted
    LinkedBrokerAccount row. Requiring BROKER_KEY_ENCRYPTION_KEY just to read a
    public asset list is friction with no security benefit off-Inngest."""

    @pytest.mark.asyncio
    async def test_returns_none_when_env_credentials_absent(self, monkeypatch):
        from execution.broker.tradable import alpaca_tradable_symbols_from_env

        monkeypatch.delenv("ALPACA_PAPER_API_KEY", raising=False)
        monkeypatch.delenv("ALPACA_PAPER_API_SECRET", raising=False)
        assert await alpaca_tradable_symbols_from_env() is None

    @pytest.mark.asyncio
    async def test_returns_symbol_set_from_env_credentials(self, monkeypatch):
        import execution.broker.alpaca_client as ac
        from execution.broker.tradable import alpaca_tradable_symbols_from_env

        monkeypatch.setenv("ALPACA_PAPER_API_KEY", "k")
        monkeypatch.setenv("ALPACA_PAPER_API_SECRET", "s")
        seen = {}

        class _Fake:
            def __init__(self, key, secret):
                seen["creds"] = (key, secret)

            def list_tradable_us_equities(self):
                return {"AAOI", "NVDA"}

        monkeypatch.setattr(ac, "AlpacaPaperClient", _Fake)
        assert await alpaca_tradable_symbols_from_env() == {"AAOI", "NVDA"}
        assert seen["creds"] == ("k", "s")

    @pytest.mark.asyncio
    async def test_degrades_to_none_when_broker_call_raises(self, monkeypatch):
        import execution.broker.alpaca_client as ac
        from execution.broker.tradable import alpaca_tradable_symbols_from_env

        monkeypatch.setenv("ALPACA_PAPER_API_KEY", "k")
        monkeypatch.setenv("ALPACA_PAPER_API_SECRET", "s")

        class _Boom:
            def __init__(self, *a):
                raise RuntimeError("alpaca down")

        monkeypatch.setattr(ac, "AlpacaPaperClient", _Boom)
        # None means "don't gate" — never reject the world on an outage.
        assert await alpaca_tradable_symbols_from_env() is None
