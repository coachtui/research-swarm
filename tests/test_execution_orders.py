"""Tests for pure order construction and hard guardrails."""
from execution.engine.guardrails import enforce_guardrails
from execution.engine.orders import diff_to_orders


def _pos(qty, price):
    return {"qty": qty, "market_value": qty * price, "current_price": price}


class TestDiffToOrders:
    def test_fresh_start_all_buys(self):
        orders = diff_to_orders({"XLK": 10000.0, "XLE": 6000.0}, positions={})
        assert orders == [
            {"symbol": "XLE", "side": "buy", "notional": 6000.0},
            {"symbol": "XLK", "side": "buy", "notional": 10000.0},
        ]

    def test_sells_come_first_and_full_exit_sells_all_qty(self):
        orders = diff_to_orders(
            {"XLK": 10000.0},
            positions={"XLF": _pos(qty=50.0, price=40.0), "XLK": _pos(qty=80.0, price=100.0)},
        )
        assert orders[0] == {"symbol": "XLF", "side": "sell", "qty": 50.0, "est_notional": 2000.0}
        assert orders[1] == {"symbol": "XLK", "side": "buy", "notional": 2000.0}

    def test_trim_sells_partial_qty_never_short(self):
        orders = diff_to_orders({"XLK": 5000.0}, positions={"XLK": _pos(qty=80.0, price=100.0)})
        assert orders == [{"symbol": "XLK", "side": "sell", "qty": 30.0, "est_notional": 3000.0}]

    def test_dust_deltas_ignored(self):
        # $30 delta < MIN_TRADE_NOTIONAL ($50) in both directions
        assert diff_to_orders({"XLK": 8030.0}, positions={"XLK": _pos(qty=80.0, price=100.0)}) == []
        assert diff_to_orders({"XLK": 7970.0}, positions={"XLK": _pos(qty=80.0, price=100.0)}) == []


class TestGuardrails:
    def test_buys_capped_by_available_cash_including_sell_proceeds(self):
        orders = [
            {"symbol": "XLF", "side": "sell", "qty": 10.0, "est_notional": 1000.0},
            {"symbol": "XLK", "side": "buy", "notional": 2500.0},
        ]
        adjusted, notes = enforce_guardrails(orders, account_equity=100000.0, cash_available=2000.0)
        assert adjusted[1]["notional"] == 2500.0  # 2000 cash + 1000 proceeds covers it
        assert notes == []

        adjusted, notes = enforce_guardrails(orders, account_equity=100000.0, cash_available=1000.0)
        assert adjusted[1]["notional"] == 2000.0  # capped at 1000 + 1000
        assert len(notes) == 1

    def test_sector_cap_35pct_of_account(self):
        orders = [{"symbol": "XLK", "side": "buy", "notional": 40000.0}]
        adjusted, notes = enforce_guardrails(orders, account_equity=100000.0, cash_available=50000.0)
        assert adjusted[0]["notional"] == 35000.0
        assert len(notes) == 1

    def test_halted_sleeve_drops_buys_keeps_sells(self):
        orders = [
            {"symbol": "XLF", "side": "sell", "qty": 10.0, "est_notional": 1000.0},
            {"symbol": "XLK", "side": "buy", "notional": 500.0},
        ]
        adjusted, notes = enforce_guardrails(
            orders, account_equity=100000.0, cash_available=5000.0, allow_buys=False
        )
        assert adjusted == [orders[0]]
        assert any("halted" in n for n in notes)

    def test_penniless_buys_dropped(self):
        orders = [{"symbol": "XLK", "side": "buy", "notional": 100.0}]
        adjusted, notes = enforce_guardrails(orders, account_equity=100000.0, cash_available=0.0)
        assert adjusted == []
        assert len(notes) == 1
