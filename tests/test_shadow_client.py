# tests/test_shadow_client.py
"""Shadow broker: honesty rule, idempotent submits, one row per order."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from execution.broker.shadow_client import ShadowBrokerClient, evaluate_fill
from execution.sleeve_service import position_after_fill

NOW = datetime(2026, 7, 14, 21, 15, tzinfo=timezone.utc)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_position_math():
    assert position_after_fill(0.0, 0.0, 10.0, 20.0, "buy") == (10.0, 20.0)
    qty, avg = position_after_fill(10.0, 20.0, 10.0, 30.0, "buy")
    assert (qty, round(avg, 4)) == (20.0, 25.0)
    assert position_after_fill(20.0, 25.0, 5.0, 40.0, "sell") == (15.0, 25.0)


def test_position_math_create_branch_takes_price_directly():
    # Fresh position must return the fill price EXACTLY (direct assignment,
    # not the weighted formula, whose ulp drift can flip round(x, 4) at
    # boundary values — e.g. this pair: formula rounds to 1656.358, price 1656.3581).
    qty, avg = position_after_fill(0.0, 0.0, 84693.486085, 1656.35805, "buy")
    assert avg == 1656.35805
    assert qty == 84693.486085


def test_evaluate_fill_honesty_rule():
    # buy fills only if the day's low traded through the limit
    assert evaluate_fill("buy", 20.0, day_high=25.0, day_low=19.5, expired=False) == "filled"
    assert evaluate_fill("buy", 20.0, day_high=25.0, day_low=20.5, expired=False) == "open"
    assert evaluate_fill("buy", 20.0, day_high=25.0, day_low=20.5, expired=True) == "expired"
    # a fill on the expiry day still wins
    assert evaluate_fill("buy", 20.0, day_high=25.0, day_low=19.9, expired=True) == "filled"
    assert evaluate_fill("sell", 30.0, day_high=30.1, day_low=25.0, expired=False) == "filled"


def _db_with(order_lookup=None):
    db = MagicMock()
    db.enginetrade.find_first = AsyncMock(return_value=order_lookup)
    db.enginetrade.create = AsyncMock(return_value=MagicMock(id="t1"))
    db.enginetrade.update = AsyncMock()
    db.engineposition.find_unique = AsyncMock(return_value=None)
    db.engineposition.upsert = AsyncMock()
    db.engineposition.delete = AsyncMock()
    return db


def test_submit_limit_buy_is_idempotent():
    db = _db_with(order_lookup=MagicMock(id="dup", status="shadow_open"))
    client = ShadowBrokerClient(db, sleeve="A")
    res = _run(
        client.submit_limit_buy("AEHR", 100.0, 20.0, NOW + timedelta(days=7),
                                {"why": "test"}, "shadow-A-AEHR-20260713")
    )
    assert res.status == "shadow_open"
    db.enginetrade.create.assert_not_called()


def test_settle_fills_at_limit_and_reports_cash_delta():
    db = _db_with()
    client = ShadowBrokerClient(db, sleeve="A")
    order = MagicMock(id="o1", symbol="AEHR", side="buy", qty=100.0,
                      limitPrice=20.0, expiresAt=NOW + timedelta(days=5))
    out = _run(
        client.settle_open_order(order, day_high=22.0, day_low=19.0, now=NOW)
    )
    assert out["status"] == "filled" and out["cash_delta"] == -2000.0
    upd = db.enginetrade.update.call_args.kwargs
    assert upd["data"]["status"] == "shadow_filled" and upd["data"]["fillPrice"] == 20.0
    db.engineposition.upsert.assert_called_once()


def test_submit_sell_fills_at_price_hint():
    # Renamed from submit_shadow_sell — fills immediately AT the hint, records
    # one EngineTrade sell row, and reduces the position.
    db = _db_with()
    db.engineposition.find_unique = AsyncMock(
        return_value=MagicMock(qty=100.0, avgEntryPrice=20.0)
    )
    db.engineposition.update = AsyncMock()
    client = ShadowBrokerClient(db, sleeve="A")
    res = _run(
        client.submit_sell("AEHR", 40.0, price_hint=25.0,
                           journal={"reason": "risk_trim"}, client_order_id="shadow-A-AEHR-sell")
    )
    assert res.status == "shadow_filled" and res.filled_avg_price == 25.0
    create = db.enginetrade.create.call_args.kwargs["data"]
    assert create["side"] == "sell" and create["fillPrice"] == 25.0
    db.engineposition.update.assert_called_once()  # 100 -> 60, not deleted


def test_submit_sell_is_idempotent():
    db = _db_with(order_lookup=MagicMock(id="dup", status="shadow_filled"))
    client = ShadowBrokerClient(db, sleeve="A")
    _run(client.submit_sell("AEHR", 40.0, 25.0, {}, "shadow-A-AEHR-sell"))
    db.enginetrade.create.assert_not_called()


def test_submit_market_buy_fills_immediately_at_price_hint():
    # DCA ADD tranches — no real market to trade through, so (like
    # submit_sell) the shadow fill is immediate AT price_hint.
    db = _db_with()
    client = ShadowBrokerClient(db, sleeve="A")
    res = _run(
        client.submit_market_buy("AEHR", 5.0, price_hint=101.0,
                                 journal={"reason": "dca_add"},
                                 client_order_id="shadow-A-AEHR-buy")
    )
    assert res.status == "shadow_filled" and res.filled_avg_price == 101.0
    assert res.filled_qty == 5.0
    create = db.enginetrade.create.call_args.kwargs["data"]
    assert create["side"] == "buy" and create["fillPrice"] == 101.0
    assert create["journal"].data["reason"] == "dca_add"
    db.engineposition.upsert.assert_called_once()   # _increase_position, not _reduce


def test_submit_market_buy_add_to_existing_position_preserves_high_water():
    db = _db_with()
    db.engineposition.find_unique = AsyncMock(
        return_value=MagicMock(qty=10.0, avgEntryPrice=90.0, highWaterClose=150.0)
    )
    client = ShadowBrokerClient(db, sleeve="A")
    _run(
        client.submit_market_buy("AEHR", 5.0, price_hint=101.0,
                                 journal={"reason": "dca_add"},
                                 client_order_id="shadow-A-AEHR-buy-2")
    )
    upsert_data = db.engineposition.upsert.call_args.kwargs["data"]
    assert "highWaterClose" not in upsert_data["update"]
    assert upsert_data["update"]["qty"] == 15.0


def test_submit_market_buy_is_idempotent():
    db = _db_with(order_lookup=MagicMock(id="dup", status="shadow_filled"))
    client = ShadowBrokerClient(db, sleeve="A")
    _run(client.submit_market_buy("AEHR", 5.0, 101.0, {}, "shadow-A-AEHR-buy"))
    db.enginetrade.create.assert_not_called()
    db.engineposition.upsert.assert_not_called()


def test_settle_expires_quietly():
    db = _db_with()
    client = ShadowBrokerClient(db, sleeve="A")
    order = MagicMock(id="o1", symbol="AEHR", side="buy", qty=100.0,
                      limitPrice=20.0, expiresAt=NOW - timedelta(days=1))
    out = _run(
        client.settle_open_order(order, day_high=22.0, day_low=21.0, now=NOW)
    )
    assert out == {"status": "expired", "cash_delta": 0.0}
    db.engineposition.upsert.assert_not_called()
