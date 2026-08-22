# tests/test_sleeve_a_daily.py
"""Daily Sleeve A duties: honest fills, ATR trailing stops, snapshot math."""
import importlib
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from inngest_app.functions.execution_daily import stop_levels


def test_stop_ratchets_up_never_down():
    """stop_levels itself is unchanged — the backtest (execution/backtest/
    fills.py) still imports it for its own simulated sell logic. Only the
    live daily cron retired ITS use of the derived stop (see stopPrice=None
    assertions below); the ratchet math is still exercised here."""
    hw, stop = stop_levels(high_water=100.0, today_close=110.0, atr=4.0)
    assert (hw, stop) == (110.0, 100.0)            # 110 − 2.5×4
    hw2, stop2 = stop_levels(high_water=110.0, today_close=105.0, atr=4.0)
    assert (hw2, stop2) == (110.0, 100.0)          # close dipped: anchor holds


def test_daily_module_still_imports_without_sdk():
    import inngest_app.functions.execution_daily as mod
    assert hasattr(mod, "execution_daily")


# ── Step-function harness (mirrors tests/test_execution_daily.py) ───────────
#
# Same rationale as test_execution_daily.py's own harness: the pip `inngest`
# SDK isn't installed here, so the guarded registration is exercised through
# a minimal fake of the SDK surface `_register_inngest_function` touches.

class _FakeStep:
    def __init__(self):
        self.calls = []

    async def run(self, name, fn):
        self.calls.append(name)
        return await fn()


class _FakeCtx:
    def __init__(self):
        self.step = _FakeStep()
        self.event = types.SimpleNamespace(data={})


class _SleeveState:
    def __init__(self, status, cash=10000.0, inception_equity=10000.0,
                 inception_spy=400.0, mode="shadow", sleeve="A"):
        self.status = status
        self.cashBalance = cash
        self.inceptionEquity = inception_equity
        self.inceptionSpyClose = inception_spy
        self.statusReason = None
        self.mode = mode
        self.sleeve = sleeve


class _EnginePos:
    def __init__(self, symbol, qty):
        self.symbol = symbol
        self.qty = qty


class _BrokerPos:
    def __init__(self, d):
        self._d = d

    def to_dict(self):
        return self._d


@pytest.fixture
def execution_daily_fn():
    """Reload inngest_app.functions.execution_daily under a fake `inngest`
    module so its guarded registration actually runs, and hand back the raw
    (undecorated) coroutine function for direct invocation. Restores the
    real (SDK-absent) module state on teardown."""
    saved_inngest = sys.modules.get("inngest")
    saved_client = sys.modules.get("inngest_app.client")

    fake_inngest = types.ModuleType("inngest")

    class Inngest:
        def __init__(self, **kwargs):
            pass

        def create_function(self, **kwargs):
            def decorator(fn):
                return fn
            return decorator

    class TriggerCron:
        def __init__(self, cron):
            self.cron = cron

    fake_inngest.Inngest = Inngest
    fake_inngest.TriggerCron = TriggerCron
    sys.modules["inngest"] = fake_inngest
    sys.modules.pop("inngest_app.client", None)

    import inngest_app.functions.execution_daily as mod
    importlib.reload(mod)
    assert mod.execution_daily is not None, "fake inngest SDK injection failed"

    yield mod.execution_daily

    if saved_inngest is not None:
        sys.modules["inngest"] = saved_inngest
    else:
        sys.modules.pop("inngest", None)
    if saved_client is not None:
        sys.modules["inngest_app.client"] = saved_client
    else:
        sys.modules.pop("inngest_app.client", None)
    importlib.reload(mod)


def _healthy_sleeve_b_mocks(monkeypatch, pd):
    """Wire up everything the existing Sleeve B path needs to reach 'ok'
    with a clean reconciliation and no breaker trip, so execution reaches
    the appended Sleeve A section. Sleeve B specifics aren't under test
    here — only that Sleeve A stays fully inert when its SleeveState is
    absent."""
    import importlib as _importlib

    import execution.broker.alpaca_client as alpaca_mod
    import execution.broker.credentials as creds_mod
    import execution.engine.circuit_breaker as breaker_mod
    import execution.engine.reconcile as reconcile_mod
    import execution.sleeve_service as sleeve_mod
    import api.lib.db as db_mod

    mdc_mod = _importlib.import_module("research_swarm.data.market_data_client")

    async def fake_get_db():
        return object()

    async def fake_get_active_alpaca_account(db):
        return object()

    async def fake_get_engine_positions(db, sleeve):
        return []

    async def fake_get_sleeve_state(db, sleeve):
        if sleeve == "B":
            return _SleeveState(status="active", cash=10000.0,
                                 inception_equity=50000.0, inception_spy=400.0)
        return None  # Sleeve A never bootstrapped — the case under test

    def fake_client_from_account(account):
        class _Client:
            def get_positions(self):
                return []

            def get_account_summary(self):
                return {"equity": 11000.0, "cash": 10000.0}
        return _Client()

    def fake_find_mismatches(broker_qty, engine_qty):
        return []

    async def fake_store_snapshot(db, sleeve, snapshot_date, equity, cash,
                                   positions_value, spy_close):
        return None

    class _FakeMarketDataClient:
        def get_historical_data(self, symbol, period="5d"):
            return pd.DataFrame({"Close": [300.0, 310.0]})

    def fake_circuit_breaker_tripped(equity, inception_equity, spy_close, inception_spy):
        return False

    monkeypatch.setattr(db_mod, "get_db", fake_get_db)
    monkeypatch.setattr(creds_mod, "get_active_alpaca_account", fake_get_active_alpaca_account)
    monkeypatch.setattr(sleeve_mod, "get_engine_positions", fake_get_engine_positions)
    monkeypatch.setattr(sleeve_mod, "get_sleeve_state", fake_get_sleeve_state)
    monkeypatch.setattr(alpaca_mod, "client_from_account", fake_client_from_account)
    monkeypatch.setattr(reconcile_mod, "find_mismatches", fake_find_mismatches)
    monkeypatch.setattr(sleeve_mod, "store_snapshot", fake_store_snapshot)
    monkeypatch.setattr(mdc_mod, "MarketDataClient", _FakeMarketDataClient)
    monkeypatch.setattr(breaker_mod, "circuit_breaker_tripped", fake_circuit_breaker_tripped)


@pytest.mark.asyncio
async def test_sleeve_a_absent_is_a_full_noop(monkeypatch, execution_daily_fn):
    """No SleeveState A row (funnel not yet bootstrapped) -> none of the
    four new Sleeve A steps ever touch the DB. The shadow-order query
    (ShadowBrokerClient.get_open_orders) must never fire, and Sleeve B's
    own path still completes normally."""
    import pandas as pd
    import execution.broker.shadow_client as shadow_mod

    _healthy_sleeve_b_mocks(monkeypatch, pd)

    open_orders_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(shadow_mod.ShadowBrokerClient, "get_open_orders", open_orders_mock)

    result = await execution_daily_fn(_FakeCtx())

    assert result["status"] == "ok"
    open_orders_mock.assert_not_called()


@pytest.mark.asyncio
async def test_sleeve_a_fill_then_snapshot_runs_in_order(monkeypatch, execution_daily_fn):
    """SleeveState A present, one open buy order that trades through today:
    the fill sweep settles it (real ShadowBrokerClient + position math, not
    mocked), journals entry_filled, and moves cash by exactly the fill
    notional; the stops step then correctly finds zero positions (the fake
    get_engine_positions stub isn't wired to reflect the just-created
    EnginePosition row, so this exercises stops' *own* "no positions" no-op,
    not the SleeveState-absent gate); snapshot values the (empty, per the
    stub) book and reads cash off SleeveState A; breaker evaluates cleanly.
    All four Sleeve A steps must run strictly after Sleeve B's."""
    import pandas as pd

    import execution.broker.shadow_client as shadow_mod
    import execution.market_data as market_data_mod
    import execution.sleeve_service as sleeve_mod

    _healthy_sleeve_b_mocks(monkeypatch, pd)

    sleeve_a_cash = {"value": 10000.0}
    cash_updates = []

    async def fake_get_sleeve_state(db, sleeve):
        if sleeve == "B":
            return _SleeveState(status="active", cash=10000.0,
                                 inception_equity=50000.0, inception_spy=400.0)
        return _SleeveState(status="active", cash=sleeve_a_cash["value"],
                             inception_equity=5000.0, inception_spy=300.0)

    async def fake_update_sleeve_cash(db, sleeve, cash_balance):
        cash_updates.append((sleeve, cash_balance))
        if sleeve == "A":
            sleeve_a_cash["value"] = cash_balance

    async def fake_get_engine_positions(db, sleeve):
        return []  # neither sleeve holds anything in this scenario

    monkeypatch.setattr(sleeve_mod, "get_sleeve_state", fake_get_sleeve_state)
    monkeypatch.setattr(sleeve_mod, "update_sleeve_cash", fake_update_sleeve_cash)
    monkeypatch.setattr(sleeve_mod, "get_engine_positions", fake_get_engine_positions)

    order = MagicMock(id="o1", symbol="AEHR", side="buy", qty=100.0,
                      limitPrice=20.0, expiresAt=datetime(2026, 12, 1, tzinfo=timezone.utc))

    shadow_db = MagicMock()
    shadow_db.enginetrade.find_many = AsyncMock(return_value=[order])
    shadow_db.enginetrade.update = AsyncMock()
    shadow_db.engineposition.find_unique = AsyncMock(return_value=None)
    shadow_db.engineposition.upsert = AsyncMock()

    import api.lib.db as db_mod

    async def fake_get_db():
        return shadow_db
    monkeypatch.setattr(db_mod, "get_db", fake_get_db)

    def fake_fetch_ohlcv_batch(symbols, period="1y"):
        assert period == "5d"  # fills sweep only needs today's bar
        return {"AEHR": pd.DataFrame({
            "Open": [20.0], "High": [22.0], "Low": [19.0],
            "Close": [21.0], "Volume": [1000],
        })}
    monkeypatch.setattr(market_data_mod, "fetch_ohlcv_batch", fake_fetch_ohlcv_batch)

    reports = []

    async def fake_write_report(report_type, severity, source, title, body, db=None):
        reports.append(report_type)
        return "rep-id"

    import execution.reporting as reporting_mod
    monkeypatch.setattr(reporting_mod, "write_report", fake_write_report)

    ctx = _FakeCtx()
    result = await execution_daily_fn(ctx)

    assert result["status"] == "ok"
    a = result["sleeve_a"]
    assert a["active"] is True
    assert a["fills"] == {"active": True, "filled": 1, "missed": 0}
    assert a["stops"] == {"active": True, "exits": 0}
    assert a["snapshot"]["active"] is True
    assert a["breaker"]["active"] is True

    # Honesty-rule fill at the limit price (day_low 19 <= limit 20): the
    # order fills AT 20.0, not at a friendlier price. Cash moves by exactly
    # -100 * 20.0, applied once (not per-order, per the "accumulate then one
    # update_sleeve_cash call" contract).
    assert cash_updates == [("A", 8000.0)]
    assert reports == ["entry_filled"]

    step_names = ctx.step.calls
    fills_i = step_names.index("sleeve-a-fills")
    stops_i = step_names.index("sleeve-a-stops")
    snap_i = step_names.index("sleeve-a-snapshot")
    breaker_i = step_names.index("sleeve-a-breaker")
    assert fills_i < stops_i < snap_i < breaker_i
    # Sleeve B's own steps all precede every Sleeve A step.
    assert step_names.index("circuit-breaker") < fills_i


def _sleeve_a_state_mocks(monkeypatch, positions_a=None):
    """Sleeve-aware overrides on top of _healthy_sleeve_b_mocks: SleeveState A
    exists, optional Sleeve A positions, and a recording update_sleeve_cash."""
    import execution.sleeve_service as sleeve_mod

    cash_updates = []

    async def fake_get_sleeve_state(db, sleeve):
        if sleeve == "B":
            return _SleeveState(status="active", cash=10000.0,
                                 inception_equity=50000.0, inception_spy=400.0)
        return _SleeveState(status="active", cash=10000.0,
                             inception_equity=5000.0, inception_spy=300.0)

    async def fake_update_sleeve_cash(db, sleeve, cash_balance):
        cash_updates.append((sleeve, cash_balance))

    async def fake_get_engine_positions(db, sleeve):
        if sleeve == "A":
            return list(positions_a or [])
        return []

    monkeypatch.setattr(sleeve_mod, "get_sleeve_state", fake_get_sleeve_state)
    monkeypatch.setattr(sleeve_mod, "update_sleeve_cash", fake_update_sleeve_cash)
    monkeypatch.setattr(sleeve_mod, "get_engine_positions", fake_get_engine_positions)
    return cash_updates


def _capture_reports(monkeypatch):
    """Capture the engine journal — BOTH channels.

    An alert is not a separate transport: send_failure_alert is write_report at
    "critical" severity. It still needs its own patch, because execution.alerts
    binds write_report at module import, so patching execution.reporting never
    reaches it — and an unpatched alert would hit the real DB.

    Returns (reports, alerts): every row lands in `reports` as
    (type, title); the alert subset also lands in `alerts` so a test can assert
    that something alerted rather than merely journaled.
    """
    import execution.alerts as alerts_mod
    import execution.reporting as reporting_mod

    reports = []
    alerts = []

    async def fake_write_report(report_type, severity, source, title, body, db=None):
        reports.append((report_type, title))
        return "rep-id"

    async def fake_send_failure_alert(subject, body, source="engine", detail=None):
        alerts.append(subject)
        reports.append(("engine_failure", subject))
        return {"status": "journaled"}

    monkeypatch.setattr(reporting_mod, "write_report", fake_write_report)
    monkeypatch.setattr(alerts_mod, "send_failure_alert", fake_send_failure_alert)
    return reports, alerts


@pytest.mark.asyncio
async def test_expiry_leaves_cash_untouched(monkeypatch, execution_daily_fn):
    """Single cash mover contract, expiry half: an open shadow buy that
    expires unfilled journals entry_missed and moves NO cash — the funnel
    reserved nothing at submit, so there is nothing to refund."""
    import pandas as pd

    import api.lib.db as db_mod
    import execution.market_data as market_data_mod

    _healthy_sleeve_b_mocks(monkeypatch, pd)
    cash_updates = _sleeve_a_state_mocks(monkeypatch)
    reports, _alerts = _capture_reports(monkeypatch)

    # Expired yesterday; today's bar never traded through the 20.0 limit.
    order = MagicMock(id="o1", symbol="AEHR", side="buy", qty=100.0,
                      limitPrice=20.0, expiresAt=datetime(2020, 1, 1, tzinfo=timezone.utc))
    shadow_db = MagicMock()
    shadow_db.enginetrade.find_many = AsyncMock(return_value=[order])
    shadow_db.enginetrade.update = AsyncMock()

    async def fake_get_db():
        return shadow_db
    monkeypatch.setattr(db_mod, "get_db", fake_get_db)

    def fake_fetch_ohlcv_batch(symbols, period="1y"):
        return {"AEHR": pd.DataFrame({
            "Open": [22.0], "High": [23.0], "Low": [21.0],
            "Close": [22.5], "Volume": [1000],
        })}
    monkeypatch.setattr(market_data_mod, "fetch_ohlcv_batch", fake_fetch_ohlcv_batch)

    result = await execution_daily_fn(_FakeCtx())

    assert result["status"] == "ok"
    assert result["sleeve_a"]["fills"] == {"active": True, "filled": 0, "missed": 1}
    assert cash_updates == []                      # no deduction, no refund
    assert [r[0] for r in reports] == ["entry_missed"]


@pytest.mark.asyncio
async def test_fills_error_does_not_cascade_to_stops(monkeypatch, execution_daily_fn):
    """A transient fills-step failure journals engine_failure but must NOT
    skip the later Sleeve A steps: stops still evaluates positions (persists
    the ratcheted stop), snapshot still writes, breaker still runs. Only
    SleeveState-A-absent skips them."""
    import pandas as pd

    import api.lib.db as db_mod
    import execution.broker.shadow_client as shadow_mod
    import execution.market_data as market_data_mod

    _healthy_sleeve_b_mocks(monkeypatch, pd)
    pos = types.SimpleNamespace(symbol="AEHR", qty=100.0,
                                highWaterClose=None, avgEntryPrice=100.0)
    _sleeve_a_state_mocks(monkeypatch, positions_a=[pos])
    reports, _alerts = _capture_reports(monkeypatch)

    async def broken_get_open_orders(self):
        raise RuntimeError("transient DB blip")
    monkeypatch.setattr(shadow_mod.ShadowBrokerClient, "get_open_orders",
                        broken_get_open_orders)

    shadow_db = MagicMock()
    shadow_db.engineposition.update = AsyncMock()

    async def fake_get_db():
        return shadow_db
    monkeypatch.setattr(db_mod, "get_db", fake_get_db)

    # 16 flat bars — thesis-hold means stops never fire regardless of ATR.
    def fake_fetch_ohlcv_batch(symbols, period="1y"):
        n = 16
        return {"AEHR": pd.DataFrame({
            "Open": [100.0] * n, "High": [101.0] * n, "Low": [99.0] * n,
            "Close": [100.0] * n, "Volume": [1000] * n,
        })}
    monkeypatch.setattr(market_data_mod, "fetch_ohlcv_batch", fake_fetch_ohlcv_batch)

    result = await execution_daily_fn(_FakeCtx())

    assert result["status"] == "ok"
    a = result["sleeve_a"]
    assert a["fills"] == {"active": True, "error": True}
    assert a["stops"] == {"active": True, "exits": 0}   # stops still ran
    assert a["snapshot"]["active"] is True               # snapshot still ran
    assert a["breaker"] == {"active": True, "tripped": False}
    # The stop anchor was actually persisted — proof stops did real work.
    # Thesis-hold (spec 2026-07-10): the ratchet lands, but stopPrice is
    # always retired to None — price never sells.
    upd = shadow_db.engineposition.update.call_args.kwargs
    assert upd["data"] == {"highWaterClose": 100.0, "stopPrice": None}
    assert ("engine_failure", "Sleeve A fills sweep failed") in reports


@pytest.mark.asyncio
async def test_missing_bar_skips_snapshot_and_breaker(monkeypatch, execution_daily_fn):
    """A held position with no OHLCV bar must SKIP the day's Sleeve A
    snapshot (raising an alert) rather than value the holding at 0
    — a zeroed holding understates equity and could falsely trip the -15pp
    breaker. The breaker step then no-ops (it gates on the snapshot)."""
    import pandas as pd

    import api.lib.db as db_mod
    import execution.broker.shadow_client as shadow_mod
    import execution.market_data as market_data_mod
    import execution.sleeve_service as sleeve_mod

    _healthy_sleeve_b_mocks(monkeypatch, pd)
    pos = types.SimpleNamespace(symbol="AEHR", qty=100.0,
                                highWaterClose=105.0, avgEntryPrice=100.0)
    _sleeve_a_state_mocks(monkeypatch, positions_a=[pos])
    reports, _alerts = _capture_reports(monkeypatch)

    monkeypatch.setattr(shadow_mod.ShadowBrokerClient, "get_open_orders",
                        AsyncMock(return_value=[]))

    snapshot_calls = []

    async def fake_store_snapshot(db, sleeve, snapshot_date, equity, cash,
                                   positions_value, spy_close):
        snapshot_calls.append(sleeve)
    monkeypatch.setattr(sleeve_mod, "store_snapshot", fake_store_snapshot)

    async def fake_get_db():
        return MagicMock()
    monkeypatch.setattr(db_mod, "get_db", fake_get_db)

    def fake_fetch_ohlcv_batch(symbols, period="1y"):
        return {}  # AEHR's bar is missing today
    monkeypatch.setattr(market_data_mod, "fetch_ohlcv_batch", fake_fetch_ohlcv_batch)

    result = await execution_daily_fn(_FakeCtx())

    assert result["status"] == "ok"
    a = result["sleeve_a"]
    assert a["snapshot"] == {"active": False, "skipped": True, "missing": ["AEHR"]}
    assert a["breaker"] == {"active": False}             # gated on the snapshot
    assert snapshot_calls == ["B"]                       # Sleeve B's snapshot only
    # Alerts, not just journals: a skipped snapshot takes the sleeve's circuit
    # breaker offline for the day, which nobody notices in a warning row.
    assert _alerts == ["Sleeve A snapshot skipped — missing bars"]


def _reconcile_scenario_mocks(monkeypatch, pd, *, a_engine, broker_positions):
    """Shared wiring for the shared-account reconcile tests: real
    reconcile_sleeve (find_mismatches un-patched), Sleeve B with an EMPTY book,
    Sleeve A holding `a_engine`, and the broker reporting `broker_positions`."""
    import execution.broker.alpaca_client as alpaca_mod
    import execution.broker.shadow_client as shadow_mod
    import execution.engine.reconcile as reconcile_mod
    import execution.market_data as market_data_mod
    import execution.sleeve_service as sleeve_mod
    import api.lib.db as db_mod
    from execution.engine.reconcile import find_mismatches as real_fm

    _healthy_sleeve_b_mocks(monkeypatch, pd)
    monkeypatch.setattr(reconcile_mod, "find_mismatches", real_fm)  # exercise real scoping

    status_calls = []

    async def fake_set_sleeve_status(db, sleeve, status, reason=None):
        status_calls.append((sleeve, status))
    monkeypatch.setattr(sleeve_mod, "set_sleeve_status", fake_set_sleeve_status)

    async def fake_get_engine_positions(db, sleeve):
        if sleeve == "A":
            return [_EnginePos(s, q) for s, q in a_engine.items()]
        return []  # Sleeve B holds nothing in these scenarios
    monkeypatch.setattr(sleeve_mod, "get_engine_positions", fake_get_engine_positions)

    async def fake_get_sleeve_state(db, sleeve):
        if sleeve == "B":
            return _SleeveState(status="active", cash=10000.0,
                                 inception_equity=50000.0, inception_spy=400.0)
        return _SleeveState(status="active", cash=5000.0,
                             inception_equity=5000.0, inception_spy=300.0, mode="shadow")
    monkeypatch.setattr(sleeve_mod, "get_sleeve_state", fake_get_sleeve_state)

    def fake_client_from_account(account):
        class _Client:
            def get_positions(self):
                return [_BrokerPos({"symbol": s, "qty": q, "market_value": q * 20.0,
                                    "current_price": 20.0, "avg_entry_price": 20.0})
                        for s, q in broker_positions.items()]

            def get_account_summary(self):
                return {"equity": 11000.0, "cash": 10000.0}
        return _Client()
    monkeypatch.setattr(alpaca_mod, "client_from_account", fake_client_from_account)

    monkeypatch.setattr(shadow_mod.ShadowBrokerClient, "get_open_orders",
                        AsyncMock(return_value=[]))

    def fake_fetch_ohlcv_batch(symbols, period="1y"):
        return {s: pd.DataFrame({"Open": [20.0], "High": [21.0], "Low": [19.0],
                                 "Close": [20.0], "Volume": [1000]}) for s in symbols}
    monkeypatch.setattr(market_data_mod, "fetch_ohlcv_batch", fake_fetch_ohlcv_batch)

    async def fake_get_db():
        return MagicMock()
    monkeypatch.setattr(db_mod, "get_db", fake_get_db)
    return status_calls


@pytest.mark.asyncio
async def test_sleeve_a_stock_in_broker_never_freezes_sleeve_b(monkeypatch, execution_daily_fn):
    """THE LANDMINE regression: the shared paper account's broker position list
    carries Sleeve A's real stocks. Sleeve B reconciles only its own scope
    (empty book ∪ sector ETFs), so an A stock (AAPL) can never freeze B — and
    when A's book matches the broker, A stays clean too."""
    import pandas as pd

    status_calls = _reconcile_scenario_mocks(
        monkeypatch, pd, a_engine={"AAPL": 5.0}, broker_positions={"AAPL": 5.0},
    )
    reports, _alerts = _capture_reports(monkeypatch)

    result = await execution_daily_fn(_FakeCtx())

    assert result["status"] == "ok"                       # Sleeve B NOT frozen
    assert result["sleeve_a"]["reconcile"] == {"active": True, "frozen": False}
    assert status_calls == []                             # nobody frozen
    assert not any(t == "breaker_event" for t, _ in reports)


@pytest.mark.asyncio
async def test_sleeve_a_mismatch_freezes_only_a(monkeypatch, execution_daily_fn):
    """A qty drift inside Sleeve A's own book (engine 10 vs broker 5) freezes
    ONLY Sleeve A — B is untouched (the AAPL drift isn't in B's scope) — and A's
    fills/stops halt for the day while the whole run still returns ok."""
    import pandas as pd

    status_calls = _reconcile_scenario_mocks(
        monkeypatch, pd, a_engine={"AAPL": 10.0}, broker_positions={"AAPL": 5.0},
    )
    reports, _alerts = _capture_reports(monkeypatch)

    result = await execution_daily_fn(_FakeCtx())

    assert result["status"] == "ok"                       # B path completes
    assert result["sleeve_a"]["reconcile"]["frozen"] is True
    assert status_calls == [("A", "frozen")]              # ONLY A frozen, never B
    assert result["sleeve_a"]["fills"] == {"active": True, "filled": 0, "missed": 0}
    assert result["sleeve_a"]["stops"] == {"active": True, "exits": 0}
    assert ("breaker_event", "Sleeve A frozen: reconciliation mismatch") in reports


def test_c1_position_provenance_persisted_on_fill():
    """C1a: a filled buy copies sourceTags / convictionScore / reportRef from
    its order journal onto the EnginePosition row (dead columns revived)."""
    import asyncio as _asyncio
    from unittest.mock import AsyncMock as _AsyncMock, MagicMock as _MagicMock
    from inngest_app.functions.execution_daily import _persist_position_provenance

    order = _MagicMock(symbol="AEHR",
                       journal={"sourceTags": {"themes": ["photonics"]},
                                "convictionScore": 80.0, "reportRef": "ws-123"})
    db = _MagicMock()
    db.engineposition.update = _AsyncMock()

    loop = _asyncio.new_event_loop()
    try:
        loop.run_until_complete(_persist_position_provenance(db, order))
    finally:
        loop.close()

    db.engineposition.update.assert_awaited_once()
    kw = db.engineposition.update.call_args.kwargs
    assert kw["where"]["sleeve_symbol"]["symbol"] == "AEHR"
    data = kw["data"]
    assert data["convictionScore"] == 80.0 and data["reportRef"] == "ws-123"
    assert "sourceTags" in data


def _capture_report_bodies(monkeypatch):
    import execution.reporting as reporting_mod

    reports = []

    async def fake_write_report(report_type, severity, source, title, body, db=None):
        reports.append((report_type, title, body))
        return "rep-id"

    monkeypatch.setattr(reporting_mod, "write_report", fake_write_report)
    return reports


def _live_stops_scenario(monkeypatch, pd):
    """Sleeve A live-mode stops scenario: a position whose price move would
    have fired the now-retired ATR trailing stop hard. Wires a mocked live
    broker so the test can assert broker.submit_sell is never reached."""
    import execution.broker as broker_pkg
    import api.lib.db as db_mod
    import execution.market_data as market_data_mod

    _healthy_sleeve_b_mocks(monkeypatch, pd)
    pos = types.SimpleNamespace(symbol="AEHR", qty=100.0,
                                highWaterClose=100.0, avgEntryPrice=100.0)
    cash_updates = _sleeve_a_state_mocks(monkeypatch, positions_a=[pos])

    mock_broker = MagicMock()
    mock_broker.get_open_orders = AsyncMock(return_value=[])
    mock_broker.submit_sell = AsyncMock()

    async def fake_sleeve_a_broker(db, state):
        return mock_broker
    monkeypatch.setattr(broker_pkg, "sleeve_a_broker", fake_sleeve_a_broker)

    shadow_db = MagicMock()
    shadow_db.engineposition.update = AsyncMock()

    async def fake_get_db():
        return shadow_db
    monkeypatch.setattr(db_mod, "get_db", fake_get_db)

    # 16 bars: flat 100 except today's low 90 — would have fired any ATR
    # trailing stop hard under the retired price-selling rule.
    def fake_fetch_ohlcv_batch(symbols, period="1y"):
        n = 16
        return {"AEHR": pd.DataFrame({
            "Open": [100.0] * n, "High": [101.0] * n,
            "Low": [99.0] * (n - 1) + [90.0], "Close": [100.0] * n,
            "Volume": [1000] * n,
        })}
    monkeypatch.setattr(market_data_mod, "fetch_ohlcv_batch", fake_fetch_ohlcv_batch)
    return cash_updates, mock_broker, shadow_db


@pytest.mark.asyncio
async def test_live_mode_stops_never_calls_broker_sell(monkeypatch, execution_daily_fn):
    """Thesis-hold (spec 2026-07-10): converts the former I1 fill-crediting
    coverage (previously two tests distinguishing a successful vs. a
    zero-fill live sell) into one no-sell assertion set — with the firing
    branch retired, both scenarios collapse to the identical observable
    outcome: submit_sell is never invoked. Engineer a today-low that would
    have fired the old ATR trailing stop hard, and assert: broker.submit_sell
    is never called, no cash moves, no exit_stop/engine_failure report, and
    the ratchet + stopPrice=None still land."""
    import pandas as pd

    cash_updates, mock_broker, shadow_db = _live_stops_scenario(monkeypatch, pd)
    reports = _capture_report_bodies(monkeypatch)

    result = await execution_daily_fn(_FakeCtx())

    assert result["status"] == "ok"
    assert result["sleeve_a"]["stops"] == {"active": True, "exits": 0}
    mock_broker.submit_sell.assert_not_called()
    assert not any(s == "A" for s, _ in cash_updates)    # no cash moved
    assert not any(t == "exit_stop" for t, _, _ in reports)
    assert not any(t == "engine_failure" for t, _, _ in reports)
    upd = shadow_db.engineposition.update.call_args.kwargs
    assert upd["data"] == {"highWaterClose": 100.0, "stopPrice": None}


@pytest.mark.asyncio
async def test_unclaimed_broker_symbol_journals_without_freezing(monkeypatch, execution_daily_fn):
    """I2: a broker symbol claimed by NEITHER sleeve (not in either engine
    book, not a sector ETF) must be journaled as an engine_failure warning —
    visible — but must NOT freeze anyone."""
    import pandas as pd

    status_calls = _reconcile_scenario_mocks(
        monkeypatch, pd,
        a_engine={"AAPL": 5.0},
        broker_positions={"AAPL": 5.0, "ZZZZ": 3.0},   # ZZZZ: nobody's
    )
    reports, _alerts = _capture_reports(monkeypatch)

    result = await execution_daily_fn(_FakeCtx())

    assert result["status"] == "ok"                     # B not frozen
    assert status_calls == []                           # nobody frozen
    recon = result["sleeve_a"]["reconcile"]
    assert recon["frozen"] is False
    assert recon.get("unclaimed") == ["ZZZZ"]
    assert ("engine_failure", "unclaimed broker positions: ['ZZZZ']") in reports


@pytest.mark.asyncio
async def test_sleeve_a_stops_step_ratchets_but_never_sells(monkeypatch, execution_daily_fn):
    """Thesis-hold (spec 2026-07-10): Sleeve A never sells on price. Engineer
    a today-close far below the position's existing high-water mark — the
    now-retired ATR trailing stop would have fired hard here — and assert
    the step still: never calls broker.submit_sell, persists the high-water
    ratchet (unchanged here, since a lower close never ratchets it down),
    persists stopPrice=None, and reports zero exits."""
    import pandas as pd

    import api.lib.db as db_mod
    import execution.broker.shadow_client as shadow_mod
    import execution.market_data as market_data_mod

    _healthy_sleeve_b_mocks(monkeypatch, pd)
    pos = types.SimpleNamespace(symbol="NVDA", qty=10.0,
                                highWaterClose=200.0, avgEntryPrice=100.0)
    _sleeve_a_state_mocks(monkeypatch, positions_a=[pos])
    reports, _alerts = _capture_reports(monkeypatch)

    submit_sell_mock = AsyncMock()
    monkeypatch.setattr(shadow_mod.ShadowBrokerClient, "submit_sell", submit_sell_mock)
    monkeypatch.setattr(shadow_mod.ShadowBrokerClient, "get_open_orders",
                        AsyncMock(return_value=[]))

    shadow_db = MagicMock()
    shadow_db.engineposition.update = AsyncMock()

    async def fake_get_db():
        return shadow_db
    monkeypatch.setattr(db_mod, "get_db", fake_get_db)

    # 16 bars, today's close/low far below the 200 high-water mark — the
    # retired ATR trailing stop would have fired hard on this bar.
    def fake_fetch_ohlcv_batch(symbols, period="1y"):
        n = 16
        return {"NVDA": pd.DataFrame({
            "Open": [100.0] * n, "High": [101.0] * (n - 1) + [100.0],
            "Low": [99.0] * (n - 1) + [95.0], "Close": [100.0] * (n - 1) + [96.0],
            "Volume": [1000] * n,
        })}
    monkeypatch.setattr(market_data_mod, "fetch_ohlcv_batch", fake_fetch_ohlcv_batch)

    result = await execution_daily_fn(_FakeCtx())

    assert result["status"] == "ok"
    assert result["sleeve_a"]["stops"] == {"active": True, "exits": 0}
    submit_sell_mock.assert_not_called()                 # never sells on price
    upd = shadow_db.engineposition.update.call_args.kwargs
    assert upd["data"] == {"highWaterClose": 200.0, "stopPrice": None}
    assert not any(t == "exit_stop" for t, _ in reports)


# ── Benchmark guards on the shared SPY close ────────────────────────────────
#
# spyClose is stored on every snapshot and feeds the -15pp circuit breaker for
# BOTH sleeves, so a benchmark the cron cannot trust must skip the snapshot
# rather than store a guess. Two distinct failures, two distinct postures.

def _benchmark_returns(monkeypatch, df):
    """Point MarketDataClient at `df` (or None) AFTER _healthy_sleeve_b_mocks
    has installed its own healthy fake."""
    import importlib as _importlib

    mdc_mod = _importlib.import_module("research_swarm.data.market_data_client")

    class _Client:
        def get_historical_data(self, symbol, period="5d"):
            return df

    monkeypatch.setattr(mdc_mod, "MarketDataClient", _Client)


@pytest.mark.asyncio
async def test_unavailable_benchmark_skips_snapshot_and_alerts(monkeypatch,
                                                               execution_daily_fn):
    """2026-08-19 regression. yfinance rate-limited SPY, MarketDataClient
    swallowed it and returned None, and `float(df["Close"]...)` raised
    TypeError inside step 4 of 11 — killing the whole cron, so the breaker,
    the Sleeve A fills sweep, its reconcile, its stops and its snapshot never
    ran at all. The fetch failure must now cost exactly the snapshot it broke:
    no row stored, an alert raised, and every later step still executed."""
    import pandas as pd

    import api.lib.db as db_mod
    import execution.broker.shadow_client as shadow_mod
    import execution.sleeve_service as sleeve_mod

    _healthy_sleeve_b_mocks(monkeypatch, pd)
    _sleeve_a_state_mocks(monkeypatch)
    reports, alerts = _capture_reports(monkeypatch)
    _benchmark_returns(monkeypatch, None)

    monkeypatch.setattr(shadow_mod.ShadowBrokerClient, "get_open_orders",
                        AsyncMock(return_value=[]))

    snapshot_calls = []

    async def fake_store_snapshot(db, sleeve, snapshot_date, equity, cash,
                                   positions_value, spy_close):
        snapshot_calls.append(sleeve)
    monkeypatch.setattr(sleeve_mod, "store_snapshot", fake_store_snapshot)

    async def fake_get_db():
        return MagicMock()
    monkeypatch.setattr(db_mod, "get_db", fake_get_db)

    result = await execution_daily_fn(_FakeCtx())

    # The cron completed instead of dying at step 4.
    assert result["status"] == "snapshot_skipped"
    assert result["snapshot_skip_reason"] == "benchmark_unavailable"
    assert snapshot_calls == []                       # neither sleeve valued
    assert result["breaker_tripped"] is False         # no verdict from a missing leg
    assert alerts == ["Sleeve B snapshot skipped — benchmark unavailable"]
    # Sleeve A's own steps still ran; only its snapshot deferred to the
    # benchmark, and it does not double-alert for the same missing number.
    assert result["sleeve_a"]["snapshot"] == {
        "active": False, "skipped": True, "reason": "benchmark_unavailable",
    }


@pytest.mark.asyncio
async def test_stale_benchmark_skips_snapshot_without_alerting(monkeypatch,
                                                               execution_daily_fn):
    """A frame whose last bar predates this run is the 1-day-TTL cache hit that
    stored the prior session's close on 8 of 31 days. Skip the snapshot — but
    journal only: a weekday market holiday produces exactly this shape and is
    not a failure anyone needs paging about."""
    import pandas as pd

    import api.lib.db as db_mod
    import execution.broker.shadow_client as shadow_mod
    import execution.sleeve_service as sleeve_mod

    _healthy_sleeve_b_mocks(monkeypatch, pd)
    _sleeve_a_state_mocks(monkeypatch)
    reports, alerts = _capture_reports(monkeypatch)
    _benchmark_returns(monkeypatch, pd.DataFrame(
        {"Close": [300.0, 310.0]},
        index=pd.to_datetime(["2020-01-06", "2020-01-07"]),
    ))

    monkeypatch.setattr(shadow_mod.ShadowBrokerClient, "get_open_orders",
                        AsyncMock(return_value=[]))

    snapshot_calls = []

    async def fake_store_snapshot(db, sleeve, snapshot_date, equity, cash,
                                   positions_value, spy_close):
        snapshot_calls.append(sleeve)
    monkeypatch.setattr(sleeve_mod, "store_snapshot", fake_store_snapshot)

    async def fake_get_db():
        return MagicMock()
    monkeypatch.setattr(db_mod, "get_db", fake_get_db)

    result = await execution_daily_fn(_FakeCtx())

    assert result["snapshot_skip_reason"] == "benchmark_stale"
    assert snapshot_calls == []
    assert alerts == []                               # journalled, never paged
    assert any(t == "engine_failure" and "is stale" in title for t, title in reports)


@pytest.mark.asyncio
async def test_dateless_benchmark_frame_is_accepted(monkeypatch, execution_daily_fn):
    """"Cannot tell which day this is" is not "not today". A frame carrying no
    date at all must still be stored — refusing it would skip every snapshot
    over a shape we simply failed to read."""
    import pandas as pd

    import api.lib.db as db_mod
    import execution.broker.shadow_client as shadow_mod
    import execution.sleeve_service as sleeve_mod

    _healthy_sleeve_b_mocks(monkeypatch, pd)
    _sleeve_a_state_mocks(monkeypatch)
    reports, alerts = _capture_reports(monkeypatch)
    _benchmark_returns(monkeypatch, pd.DataFrame({"Close": [300.0, 310.0]}))

    monkeypatch.setattr(shadow_mod.ShadowBrokerClient, "get_open_orders",
                        AsyncMock(return_value=[]))

    snapshot_calls = []

    async def fake_store_snapshot(db, sleeve, snapshot_date, equity, cash,
                                   positions_value, spy_close):
        snapshot_calls.append((sleeve, spy_close))
    monkeypatch.setattr(sleeve_mod, "store_snapshot", fake_store_snapshot)

    async def fake_get_db():
        return MagicMock()
    monkeypatch.setattr(db_mod, "get_db", fake_get_db)

    result = await execution_daily_fn(_FakeCtx())

    assert result["status"] == "ok"
    assert ("B", 310.0) in snapshot_calls
    assert alerts == []


@pytest.mark.asyncio
async def test_legacy_memoized_snapshot_shape_still_completes(monkeypatch,
                                                              execution_daily_fn):
    """Inngest memoizes step results. A run that started before the benchmark
    guards shipped can replay into this code holding the previous `snapshot`
    shape — {"equity", "spy_close"}, no "stored" key. That must not KeyError
    the cron; the old shape only ever existed when the snapshot HAD been
    stored, so it replays as a normal day."""
    import pandas as pd

    import api.lib.db as db_mod
    import execution.broker.shadow_client as shadow_mod
    import execution.sleeve_service as sleeve_mod

    _healthy_sleeve_b_mocks(monkeypatch, pd)
    _sleeve_a_state_mocks(monkeypatch)
    reports, alerts = _capture_reports(monkeypatch)

    monkeypatch.setattr(shadow_mod.ShadowBrokerClient, "get_open_orders",
                        AsyncMock(return_value=[]))

    async def fake_store_snapshot(db, sleeve, snapshot_date, equity, cash,
                                   positions_value, spy_close):
        return None
    monkeypatch.setattr(sleeve_mod, "store_snapshot", fake_store_snapshot)

    async def fake_get_db():
        return MagicMock()
    monkeypatch.setattr(db_mod, "get_db", fake_get_db)

    class _ReplayStep(_FakeStep):
        """Serve the pre-guard return value for the memoized `snapshot` step."""

        async def run(self, name, fn):
            if name == "snapshot":
                self.calls.append(name)
                return {"equity": 11000.0, "spy_close": 310.0}
            return await super().run(name, fn)

    ctx = _FakeCtx()
    ctx.step = _ReplayStep()

    result = await execution_daily_fn(ctx)

    assert result["status"] == "ok"
    assert result["equity"] == 11000.0
    assert alerts == []
