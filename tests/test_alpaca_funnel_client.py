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


def _db(find_first=None, rows=None):
    # `rows` feeds the bounded find_many window the idempotency guards scan
    # (prisma 0.15 has no Json path filter — the match happens Python-side).
    db = MagicMock()
    db.enginetrade.find_first = AsyncMock(return_value=find_first)
    db.enginetrade.find_many = AsyncMock(return_value=list(rows or []))
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
    # A prior attempt already booked this client_order_id: the Python-side
    # match over the bounded window finds it among unrelated rows.
    other = MagicMock(brokerOrderId="alp-11", status="filled",
                      journal={"client_order_id": "some-other-coid"})
    existing = MagicMock(brokerOrderId="alp-77", status="open",
                         journal={"client_order_id": "coid-1"})
    db = _db(rows=[other, existing])
    alpaca = _alpaca()
    alpaca.submit_gtc_limit_buy = MagicMock()
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")

    res = _run(broker.submit_limit_buy(
        "AEHR", 100.0, 20.0, NOW + timedelta(days=7), {}, "coid-1",
    ))

    alpaca.submit_gtc_limit_buy.assert_not_called()   # no duplicate order
    db.enginetrade.create.assert_not_called()         # no duplicate row
    assert res.order_id == "alp-77"


def test_submit_limit_buy_lookup_is_bounded_and_matches_python_side():
    """prisma 0.15 has NO Json path filter (FieldNotFoundError at
    where.journal.equals) — the guard must issue a bounded sleeve/symbol/side
    query and match client_order_id in Python. Rows with a DIFFERENT coid must
    NOT short-circuit the submit."""
    other = MagicMock(brokerOrderId="alp-11", status="open",
                      journal={"client_order_id": "some-other-coid"})
    no_journal = MagicMock(brokerOrderId="alp-12", status="filled", journal=None)
    db = _db(rows=[other, no_journal])
    alpaca = _alpaca()
    alpaca.submit_gtc_limit_buy = MagicMock(return_value=_order("accepted"))
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")
    _run(broker.submit_limit_buy("AEHR", 1.0, 20.0, NOW, {}, "coid-xyz"))

    alpaca.submit_gtc_limit_buy.assert_called_once()  # wrong coids don't block
    kwargs = db.enginetrade.find_many.call_args.kwargs
    assert kwargs["where"] == {"sleeve": "A", "symbol": "AEHR", "side": "buy"}
    assert kwargs["take"] == 25                       # bounded window
    assert kwargs["order"] == {"createdAt": "desc"}
    # NO Json path filter anywhere in the query (raises on prisma 0.15).
    assert "journal" not in kwargs["where"]
    # client_order_id is persisted in the journal so the lookup can find it.
    assert db.enginetrade.create.call_args.kwargs["data"]["journal"] is not None


def test_submit_limit_buy_floors_fractional_qty_to_whole_shares():
    """Alpaca rejects fractional GTC orders (code 42210000: 'fractional orders
    must be DAY orders'). The sized fractional qty must floor to whole shares
    in BOTH the request and the EngineTrade row (notional recomputed) so
    settle/position math stays consistent."""
    db = _db()
    alpaca = _alpaca()
    alpaca.submit_gtc_limit_buy = MagicMock(return_value=_order("accepted", order_id="alp-31"))
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")

    res = _run(broker.submit_limit_buy(
        "AEHR", 26.619, 20.0, NOW + timedelta(days=7), {}, "coid-frac",
    ))

    alpaca.submit_gtc_limit_buy.assert_called_once_with(
        "AEHR", 26.0, 20.0, "coid-frac"        # request qty EXACTLY whole
    )
    create_data = db.enginetrade.create.call_args.kwargs["data"]
    assert create_data["qty"] == 26.0          # row records the FLOORED qty
    assert create_data["notional"] == 520.0    # 26 * 20, recomputed
    assert res.status == "open"


def test_submit_limit_buy_sub_one_share_rejected_without_submit():
    """A floored qty of 0 (input < 1 share) must NOT reach Alpaca and must NOT
    create an EngineTrade row — return a rejected result so the call site's
    existing handling reports it."""
    db = _db()
    alpaca = _alpaca()
    alpaca.submit_gtc_limit_buy = MagicMock()
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")

    res = _run(broker.submit_limit_buy(
        "AEHR", 0.8, 20.0, NOW + timedelta(days=7), {}, "coid-tiny",
    ))

    alpaca.submit_gtc_limit_buy.assert_not_called()
    db.enginetrade.create.assert_not_called()
    assert res.status == "rejected"
    assert res.filled_qty == 0.0 and res.filled_avg_price is None


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

    # client_order_id threads through to Alpaca so its duplicate rejection
    # backs the DB idempotency guard.
    alpaca.submit_market_sell_qty.assert_called_once_with("AEHR", 100.0, "c-sell")
    create_data = db.enginetrade.create.call_args.kwargs["data"]
    assert create_data["side"] == "sell"
    assert create_data["fillPrice"] == 23.75      # ACTUAL fill, price_hint ignored
    assert create_data["status"] == "filled"
    # position fully reduced -> row deleted
    db.engineposition.delete.assert_called_once()
    assert res.filled_avg_price == 23.75


def test_submit_sell_idempotent_second_call_returns_recorded_fill():
    """C1: the funnel's decide/execute stage replays outside step.run — a
    second submit_sell with the SAME client_order_id must NOT fire a second
    real market sell (oversold position, double cash credit). It short-circuits
    on the recorded EngineTrade row and returns the recorded fill."""
    other = MagicMock(brokerOrderId="alp-old", status="filled", qty=5.0,
                      fillPrice=19.0, journal={"client_order_id": "different"})
    existing = MagicMock(brokerOrderId="alp-sell-1", status="filled",
                         qty=100.0, fillPrice=23.75,
                         journal={"client_order_id": "c-sell"})
    db = _db(rows=[other, existing])
    alpaca = _alpaca()
    alpaca.submit_market_sell_qty = MagicMock()
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")

    res = _run(broker.submit_sell("AEHR", 100.0, price_hint=21.0,
                                  journal={"reason": "exit"}, client_order_id="c-sell"))

    alpaca.submit_market_sell_qty.assert_not_called()   # NO second real sell
    db.enginetrade.create.assert_not_called()           # no duplicate row
    db.engineposition.delete.assert_not_called()        # no second reduce
    db.engineposition.update.assert_not_called()
    assert res.status == "filled"
    assert res.filled_qty == 100.0 and res.filled_avg_price == 23.75
    # dedup: bounded sleeve/symbol/side query + Python-side coid match —
    # NO Json path filter (prisma 0.15 raises FieldNotFoundError on it).
    kwargs = db.enginetrade.find_many.call_args.kwargs
    assert kwargs["where"] == {"sleeve": "A", "symbol": "AEHR", "side": "sell"}
    assert kwargs["take"] == 25
    assert "journal" not in kwargs["where"]


# ── submit_market_buy (DCA ADD tranches) ────────────────────────────────────

def test_submit_market_buy_records_actual_fill_and_creates_position():
    db = _db()
    alpaca = _alpaca()
    alpaca.submit_market_buy_notional = MagicMock(return_value=BrokerOrderResult(
        order_id="alp-buy", symbol="AEHR", side="buy", status="filled",
        filled_qty=5.0, filled_avg_price=101.0,   # real fill price, not the hint
    ))
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")

    res = _run(broker.submit_market_buy(
        "AEHR", qty=5.0, price_hint=100.0,
        journal={"reason": "dca_add", "rung": 0.2}, client_order_id="c-buy",
    ))

    # notional = qty * price_hint sent to Alpaca; real fill diverges from hint
    alpaca.submit_market_buy_notional.assert_called_once_with("AEHR", 500.0)
    create_data = db.enginetrade.create.call_args.kwargs["data"]
    assert create_data["side"] == "buy"
    assert create_data["fillPrice"] == 101.0
    assert create_data["status"] == "filled"
    assert create_data["journal"].data["reason"] == "dca_add"
    assert create_data["journal"].data["client_order_id"] == "c-buy"
    # NEW position -> highWaterClose seeded at the fill price
    upsert_data = db.engineposition.upsert.call_args.kwargs["data"]
    assert upsert_data["create"]["highWaterClose"] == 101.0
    assert res.status == "filled" and res.filled_avg_price == 101.0


def test_submit_market_buy_add_to_existing_position_preserves_high_water():
    """CRITICAL: a DCA ADD to an EXISTING position must NOT reset
    highWaterClose — it anchors the DCA ladder. _increase_position's update
    branch only touches qty/avgEntryPrice."""
    db = _db()
    db.engineposition.find_unique = AsyncMock(
        return_value=MagicMock(qty=10.0, avgEntryPrice=90.0, highWaterClose=150.0)
    )
    alpaca = _alpaca()
    alpaca.submit_market_buy_notional = MagicMock(return_value=BrokerOrderResult(
        order_id="alp-buy2", symbol="AEHR", side="buy", status="filled",
        filled_qty=5.0, filled_avg_price=101.0,
    ))
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")

    _run(broker.submit_market_buy(
        "AEHR", qty=5.0, price_hint=100.0,
        journal={"reason": "dca_add"}, client_order_id="c-buy-2",
    ))

    upsert_data = db.engineposition.upsert.call_args.kwargs["data"]
    assert "highWaterClose" not in upsert_data["update"]   # ratchet untouched
    assert upsert_data["update"]["qty"] == 15.0


def test_submit_market_buy_is_idempotent_on_client_order_id():
    """C1-shaped: a repeated client_order_id must NOT fire a second real
    market buy (double position size, double cash debit)."""
    other = MagicMock(brokerOrderId="alp-old", status="filled", qty=5.0,
                      fillPrice=95.0, journal={"client_order_id": "different"})
    existing = MagicMock(brokerOrderId="alp-buy-1", status="filled",
                         qty=5.0, fillPrice=101.0,
                         journal={"client_order_id": "c-buy"})
    db = _db(rows=[other, existing])
    alpaca = _alpaca()
    alpaca.submit_market_buy_notional = MagicMock()
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")

    res = _run(broker.submit_market_buy(
        "AEHR", qty=5.0, price_hint=100.0,
        journal={"reason": "dca_add"}, client_order_id="c-buy",
    ))

    alpaca.submit_market_buy_notional.assert_not_called()   # NO second real buy
    db.enginetrade.create.assert_not_called()                # no duplicate row
    db.engineposition.upsert.assert_not_called()              # no second increase
    assert res.status == "filled"
    assert res.filled_qty == 5.0 and res.filled_avg_price == 101.0
    kwargs = db.enginetrade.find_many.call_args.kwargs
    assert kwargs["where"] == {"sleeve": "A", "symbol": "AEHR", "side": "buy"}
    assert kwargs["take"] == 25


def test_submit_market_buy_floors_fractional_qty_to_whole_shares():
    db = _db()
    alpaca = _alpaca()
    alpaca.submit_market_buy_notional = MagicMock(return_value=BrokerOrderResult(
        order_id="alp-buy3", symbol="AEHR", side="buy", status="filled",
        filled_qty=26.0, filled_avg_price=20.0,
    ))
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")

    _run(broker.submit_market_buy(
        "AEHR", qty=26.619, price_hint=20.0,
        journal={}, client_order_id="coid-frac",
    ))

    # request notional built from the FLOORED qty (26, not 26.619)
    alpaca.submit_market_buy_notional.assert_called_once_with("AEHR", 520.0)


def test_submit_market_buy_sub_one_share_rejected_without_submit():
    db = _db()
    alpaca = _alpaca()
    alpaca.submit_market_buy_notional = MagicMock()
    broker = AlpacaFunnelBroker(db, alpaca, sleeve="A")

    res = _run(broker.submit_market_buy(
        "AEHR", qty=0.8, price_hint=20.0,
        journal={}, client_order_id="coid-tiny",
    ))

    alpaca.submit_market_buy_notional.assert_not_called()
    db.enginetrade.create.assert_not_called()
    assert res.status == "rejected"
    assert res.filled_qty == 0.0 and res.filled_avg_price is None


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
