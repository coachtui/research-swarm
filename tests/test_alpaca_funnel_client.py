# tests/test_alpaca_funnel_client.py
"""AlpacaFunnelBroker: the live paper-account broker for Sleeve A. Mirrors
ShadowBrokerClient's surface (submit_limit_buy / submit_sell / get_open_orders
/ settle_open_order) but every fill/cancel is a real Alpaca order. alpaca-py is
NOT installed here, so the Alpaca client is a MagicMock returning BrokerOrderResult
shapes; the DB is mocked. Nothing here talks to a live account."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from execution.broker.alpaca_funnel_client import AlpacaFunnelBroker
from execution.broker.base import BrokerOrderResult

NOW = datetime(2026, 7, 14, 21, 15, tzinfo=timezone.utc)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _db(find_first=None):
    db = MagicMock()
    db.enginetrade.find_first = AsyncMock(return_value=find_first)
    db.enginetrade.find_many = AsyncMock(return_value=[])
    db.enginetrade.create = AsyncMock(return_value=MagicMock(id="t1"))
    db.enginetrade.update = AsyncMock()
    db.engineposition.find_unique = AsyncMock(return_value=None)
    db.engineposition.upsert = AsyncMock()
    db.engineposition.update = AsyncMock()
    db.engineposition.delete = AsyncMock()
    return db


def _alpaca():
    return MagicMock()


def _order(status, filled_qty=0.0, filled_avg_price=None, order_id="alp-1", symbol="AEHR"):
    return BrokerOrderResult(
        order_id=order_id, symbol=symbol, side="buy", status=status,
        filled_qty=filled_qty, filled_avg_price=filled_avg_price,
    )


# ── submit_limit_buy ────────────────────────────────────────────────────────

def test_submit_limit_buy_places_gtc_and_books_alpaca_id():
    db = _db()
    alpaca = _alpaca()
    alpaca.submit_gtc_limit_buy = MagicMock(return_value=_order("accepted", order_id="alp-99"))
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")

    res = _run(broker.submit_limit_buy(
        "AEHR", 100.0, 20.0, NOW + timedelta(days=7),
        {"why": "test"}, "shadow-A-AEHR-20260713",
    ))

    # GTC limit request goes to Alpaca with our client_order_id.
    alpaca.submit_gtc_limit_buy.assert_called_once_with(
        "AEHR", 100.0, 20.0, "shadow-A-AEHR-20260713"
    )
    # ONE EngineTrade row, brokerOrderId = the ALPACA id, status "open".
    create_data = db.enginetrade.create.call_args.kwargs["data"]
    assert create_data["brokerOrderId"] == "alp-99"
    assert create_data["status"] == "open"
    assert create_data["limitPrice"] == 20.0
    assert create_data["expiresAt"] == NOW + timedelta(days=7)
    assert res.order_id == "alp-99" and res.status == "open"


def test_submit_limit_buy_idempotent_on_existing_row():
    # A prior attempt already booked this client_order_id (journal lookup hit).
    existing = MagicMock(brokerOrderId="alp-77", status="open")
    db = _db(find_first=existing)
    alpaca = _alpaca()
    alpaca.submit_gtc_limit_buy = MagicMock()
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")

    res = _run(broker.submit_limit_buy(
        "AEHR", 100.0, 20.0, NOW + timedelta(days=7), {}, "coid-1",
    ))

    alpaca.submit_gtc_limit_buy.assert_not_called()   # no duplicate order
    db.enginetrade.create.assert_not_called()         # no duplicate row
    assert res.order_id == "alp-77"


def test_submit_limit_buy_lookup_uses_client_order_id_journal_path():
    db = _db()
    alpaca = _alpaca()
    alpaca.submit_gtc_limit_buy = MagicMock(return_value=_order("accepted"))
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")
    _run(broker.submit_limit_buy("AEHR", 1.0, 20.0, NOW, {}, "coid-xyz"))

    where = db.enginetrade.find_first.call_args.kwargs["where"]
    assert where["journal"] == {"path": ["client_order_id"], "equals": "coid-xyz"}
    # client_order_id is persisted in the journal so the lookup can find it.
    assert db.enginetrade.create.call_args.kwargs["data"]["journal"] is not None


# ── submit_sell (market) ────────────────────────────────────────────────────

def test_submit_sell_market_records_actual_fill_and_reduces_position():
    db = _db()
    existing_pos = MagicMock(qty=100.0, avgEntryPrice=20.0)
    db.engineposition.find_unique = AsyncMock(return_value=existing_pos)
    alpaca = _alpaca()
    alpaca.submit_market_sell_qty = MagicMock(return_value=BrokerOrderResult(
        order_id="alp-sell", symbol="AEHR", side="sell", status="filled",
        filled_qty=100.0, filled_avg_price=23.75,   # real market price, not the hint
    ))
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")

    res = _run(broker.submit_sell("AEHR", 100.0, price_hint=21.0,
                                  journal={"reason": "exit"}, client_order_id="c-sell"))

    alpaca.submit_market_sell_qty.assert_called_once_with("AEHR", 100.0)
    create_data = db.enginetrade.create.call_args.kwargs["data"]
    assert create_data["side"] == "sell"
    assert create_data["fillPrice"] == 23.75      # ACTUAL fill, price_hint ignored
    assert create_data["status"] == "filled"
    # position fully reduced -> row deleted
    db.engineposition.delete.assert_called_once()
    assert res.filled_avg_price == 23.75


# ── get_open_orders ─────────────────────────────────────────────────────────

def test_get_open_orders_queries_open_status():
    db = _db()
    broker = AlpacaFunnelBroker(db, _alpaca(), sleeve="A")
    _run(broker.get_open_orders())
    where = db.enginetrade.find_many.call_args.kwargs["where"]
    assert where == {"sleeve": "A", "status": "open"}


# ── settle_open_order ───────────────────────────────────────────────────────

def _open_buy(expires_at, order_id="alp-1"):
    return MagicMock(id="row1", symbol="AEHR", side="buy", qty=100.0,
                     limitPrice=20.0, brokerOrderId=order_id,
                     expiresAt=expires_at, journal={"client_order_id": "c1"})


def test_settle_filled_books_actual_price():
    db = _db()
    alpaca = _alpaca()
    alpaca.get_order = MagicMock(return_value=_order("filled", filled_qty=100.0,
                                                     filled_avg_price=19.87))
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")
    order = _open_buy(NOW + timedelta(days=3))

    out = _run(broker.settle_open_order(order, day_high=999.0, day_low=0.0, now=NOW))

    assert out["status"] == "filled"
    assert out["cash_delta"] == -round(100.0 * 19.87, 2)   # ACTUAL fill price
    upd = db.enginetrade.update.call_args.kwargs["data"]
    assert upd["status"] == "filled" and upd["fillPrice"] == 19.87
    db.engineposition.upsert.assert_called_once()


def test_settle_still_open_before_expiry():
    db = _db()
    alpaca = _alpaca()
    alpaca.get_order = MagicMock(return_value=_order("accepted"))
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")
    order = _open_buy(NOW + timedelta(days=3))

    out = _run(broker.settle_open_order(order, 0.0, 0.0, NOW))
    assert out == {"status": "open", "cash_delta": 0.0}
    db.enginetrade.update.assert_not_called()


def test_settle_expiry_cancels_and_marks_expired():
    db = _db()
    alpaca = _alpaca()
    # first poll: still open; after cancel re-check: canceled/unfilled
    alpaca.get_order = MagicMock(side_effect=[
        _order("accepted"),
        _order("canceled", filled_qty=0.0),
    ])
    alpaca.cancel_order = MagicMock()
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")
    order = _open_buy(NOW - timedelta(days=1))

    out = _run(broker.settle_open_order(order, 0.0, 0.0, NOW))

    alpaca.cancel_order.assert_called_once_with(order.brokerOrderId)
    assert out == {"status": "expired", "cash_delta": 0.0}
    assert db.enginetrade.update.call_args.kwargs["data"]["status"] == "expired"


def test_settle_fill_beats_cancel_race():
    # Order expired; cancel races a fill and the fill wins on re-check.
    db = _db()
    alpaca = _alpaca()
    alpaca.get_order = MagicMock(side_effect=[
        _order("accepted"),                                      # pre-cancel poll
        _order("filled", filled_qty=100.0, filled_avg_price=20.0),  # fill won the race
    ])
    alpaca.cancel_order = MagicMock()
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")
    order = _open_buy(NOW - timedelta(days=1))

    out = _run(broker.settle_open_order(order, 0.0, 0.0, NOW))

    assert out["status"] == "filled"
    assert out["cash_delta"] == -2000.0
    assert db.enginetrade.update.call_args.kwargs["data"]["status"] == "filled"


def test_settle_partial_fill_at_expiry_books_filled_portion():
    db = _db()
    alpaca = _alpaca()
    alpaca.get_order = MagicMock(side_effect=[
        _order("accepted"),
        _order("partially_filled", filled_qty=40.0, filled_avg_price=20.0),
    ])
    alpaca.cancel_order = MagicMock()
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")
    order = _open_buy(NOW - timedelta(days=1))

    out = _run(broker.settle_open_order(order, 0.0, 0.0, NOW))

    assert out["status"] == "filled"
    assert out["cash_delta"] == -round(40.0 * 20.0, 2)     # only the filled 40 shares
    upd = db.enginetrade.update.call_args.kwargs["data"]
    assert upd["status"] == "filled" and upd["qty"] == 40.0   # qty trimmed to fill
    db.engineposition.upsert.assert_called_once()


def test_settle_never_raises():
    db = _db()
    alpaca = _alpaca()
    alpaca.get_order = MagicMock(side_effect=RuntimeError("alpaca 500"))
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")
    order = _open_buy(NOW + timedelta(days=1))

    out = _run(broker.settle_open_order(order, 0.0, 0.0, NOW))
    assert out == {"status": "error", "cash_delta": 0.0}
