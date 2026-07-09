"""Tests for the sleeve DB edge. All prisma calls mocked (AsyncMock)."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from execution.sleeve_service import (
    apply_fill, get_engine_positions, get_sleeve_state, init_sleeve_state,
    set_sleeve_status, store_snapshot, update_sleeve_cash,
)

RUN_DATE = datetime(2026, 7, 13, tzinfo=timezone.utc)


def _db():
    db = MagicMock()
    for model in ("sleevestate", "sleevesnapshot", "enginetrade", "engineposition"):
        table = MagicMock()
        for op in ("create", "update", "upsert", "delete", "find_unique", "find_many", "find_first"):
            setattr(table, op, AsyncMock(return_value=SimpleNamespace(id="row1")))
        setattr(db, model, table)
    # First-attempt path by default: no prior EngineTrade row for this brokerOrderId.
    db.enginetrade.find_first = AsyncMock(return_value=None)
    return db


@pytest.mark.asyncio
async def test_init_sleeve_state_sets_inception_baseline():
    db = _db()
    await init_sleeve_state(db, "B", cash=30000.0, spy_close=600.0, inception_date=RUN_DATE)
    data = db.sleevestate.create.await_args.kwargs["data"]
    assert data["sleeve"] == "B"
    assert data["cashBalance"] == 30000.0
    assert data["inceptionEquity"] == 30000.0
    assert data["inceptionSpyClose"] == 600.0
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_store_snapshot_upserts_on_date_and_sleeve():
    db = _db()
    await store_snapshot(db, "B", RUN_DATE, equity=31000.0, cash=9000.0,
                         positions_value=22000.0, spy_close=605.0)
    kwargs = db.sleevesnapshot.upsert.await_args.kwargs
    assert kwargs["where"] == {
        "snapshotDate_sleeve": {"snapshotDate": RUN_DATE, "sleeve": "B"}
    }
    assert kwargs["data"]["create"]["equity"] == 31000.0


@pytest.mark.asyncio
async def test_apply_fill_buy_creates_position_and_returns_negative_cash_delta():
    db = _db()
    db.engineposition.find_unique = AsyncMock(return_value=None)
    fill = {"order_id": "o1", "symbol": "XLK", "side": "buy", "status": "filled",
            "filled_qty": 10.0, "filled_avg_price": 100.0}
    delta = await apply_fill(db, "B", fill, requested_notional=1000.0, journal={"regime": "risk_on"})

    assert delta == -1000.0
    trade = db.enginetrade.create.await_args.kwargs["data"]
    assert trade["symbol"] == "XLK" and trade["side"] == "buy" and trade["qty"] == 10.0
    upsert = db.engineposition.upsert.await_args.kwargs
    assert upsert["data"]["create"]["qty"] == 10.0
    assert upsert["data"]["create"]["avgEntryPrice"] == 100.0


@pytest.mark.asyncio
async def test_apply_fill_buy_averages_into_existing_position():
    db = _db()
    db.engineposition.find_unique = AsyncMock(
        return_value=SimpleNamespace(qty=10.0, avgEntryPrice=90.0)
    )
    fill = {"order_id": "o2", "symbol": "XLK", "side": "buy", "status": "filled",
            "filled_qty": 10.0, "filled_avg_price": 110.0}
    await apply_fill(db, "B", fill, requested_notional=1100.0, journal={})
    update = db.engineposition.upsert.await_args.kwargs["data"]["update"]
    assert update["qty"] == 20.0
    assert update["avgEntryPrice"] == 100.0  # (10*90 + 10*110) / 20


@pytest.mark.asyncio
async def test_apply_fill_full_sell_deletes_position():
    db = _db()
    db.engineposition.find_unique = AsyncMock(
        return_value=SimpleNamespace(qty=10.0, avgEntryPrice=90.0)
    )
    fill = {"order_id": "o3", "symbol": "XLE", "side": "sell", "status": "filled",
            "filled_qty": 10.0, "filled_avg_price": 95.0}
    delta = await apply_fill(db, "B", fill, requested_notional=None, journal={})
    assert delta == 950.0
    db.engineposition.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_fill_unfilled_order_records_trade_but_touches_nothing():
    db = _db()
    fill = {"order_id": "o4", "symbol": "XLK", "side": "buy", "status": "timeout",
            "filled_qty": 0.0, "filled_avg_price": None}
    delta = await apply_fill(db, "B", fill, requested_notional=500.0, journal={})
    assert delta == 0.0
    db.enginetrade.create.assert_awaited_once()  # journaled for the audit trail
    db.engineposition.upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_fill_replayed_fill_skips_writes_but_returns_delta():
    db = _db()
    db.enginetrade.find_first = AsyncMock(return_value=SimpleNamespace(id="t1"))
    fill = {"order_id": "o1", "symbol": "XLK", "side": "buy", "status": "filled",
            "filled_qty": 10.0, "filled_avg_price": 100.0}
    delta = await apply_fill(db, "B", fill, requested_notional=1000.0, journal={})
    assert delta == -1000.0
    db.enginetrade.create.assert_not_awaited()
    db.engineposition.upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_sleeve_state_queries_unique_sleeve():
    db = _db()
    await get_sleeve_state(db, "B")
    db.sleevestate.find_unique.assert_awaited_once_with(where={"sleeve": "B"})


@pytest.mark.asyncio
async def test_set_sleeve_status_writes_status_and_reason():
    db = _db()
    await set_sleeve_status(db, "B", "halted", reason="circuit breaker")
    db.sleevestate.update.assert_awaited_once_with(
        where={"sleeve": "B"},
        data={"status": "halted", "statusReason": "circuit breaker"},
    )


@pytest.mark.asyncio
async def test_update_sleeve_cash_rounds_to_cents():
    db = _db()
    await update_sleeve_cash(db, "B", 12345.6789)
    db.sleevestate.update.assert_awaited_once_with(
        where={"sleeve": "B"},
        data={"cashBalance": 12345.68},
    )


@pytest.mark.asyncio
async def test_get_engine_positions_filters_by_sleeve():
    db = _db()
    await get_engine_positions(db, "B")
    db.engineposition.find_many.assert_awaited_once_with(where={"sleeve": "B"})
