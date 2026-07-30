"""Tests for execution_daily — pure helper + guarded registration."""
import importlib
import sys
import types

import pytest


def _sdk_available() -> bool:
    try:
        from inngest import Inngest  # noqa: F401
        return True
    except Exception:
        return False


def test_module_imports_without_sdk():
    mod = importlib.import_module("inngest_app.functions.execution_daily")
    if not _sdk_available():
        assert mod.execution_daily is None


def test_build_sleeve_snapshot_only_counts_engine_symbols():
    from inngest_app.functions.execution_daily import build_sleeve_snapshot

    broker_positions = [
        {"symbol": "XLK", "qty": 10.0, "market_value": 1000.0, "current_price": 100.0},
        {"symbol": "AAPL", "qty": 5.0, "market_value": 900.0, "current_price": 180.0},
    ]
    snap = build_sleeve_snapshot(
        state_cash=500.0, engine_symbols=["XLK"], broker_positions=broker_positions
    )
    assert snap == {"positions_value": 1000.0, "equity": 1500.0}


def test_build_sleeve_snapshot_empty_book():
    from inngest_app.functions.execution_daily import build_sleeve_snapshot

    assert build_sleeve_snapshot(9000.0, [], []) == {
        "positions_value": 0.0, "equity": 9000.0,
    }


# ── Step-function harness ────────────────────────────────────────────────────
#
# The pip `inngest` SDK isn't installed in this environment (guarded
# registration leaves `execution_daily = None`), so exercising the actual
# step bodies needs a minimal fake of the SDK surface `_register_inngest_function`
# touches: `Inngest`/`TriggerCron` (only ever constructed, never introspected)
# and `create_function`, which just needs to hand back the undecorated
# coroutine so tests can drive it directly. `step.run` runs the given step
# function immediately — no memoization/retries needed for a unit test.

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
    def __init__(self, status, cash=10000.0, inception_equity=10000.0, inception_spy=400.0):
        self.status = status
        self.cashBalance = cash
        self.inceptionEquity = inception_equity
        self.inceptionSpyClose = inception_spy
        self.statusReason = None


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


@pytest.mark.asyncio
async def test_frozen_transition_writes_breaker_event_once(monkeypatch, execution_daily_fn):
    """First mismatch day (sleeve was active): breaker_event written once and
    one alert fires. Second day, already frozen: no new breaker_event, no
    repeat alert — closes the Phase 2 re-alert-while-frozen rider."""
    import execution.alerts as alerts_mod
    import execution.broker.alpaca_client as alpaca_mod
    import execution.broker.credentials as creds_mod
    import execution.engine.reconcile as reconcile_mod
    import execution.reporting as reporting_mod
    import execution.sleeve_service as sleeve_mod
    import api.lib.db as db_mod

    write_calls = []
    alert_calls = []
    status_calls = []

    async def fake_get_db():
        return object()

    async def fake_get_active_alpaca_account(db):
        return object()

    async def fake_get_engine_positions(db, sleeve):
        return [_EnginePos("XLK", 10.0)]

    def fake_client_from_account(account):
        class _Client:
            def get_positions(self):
                return [_BrokerPos({
                    "symbol": "XLK", "qty": 5.0,
                    "market_value": 500.0, "current_price": 100.0,
                })]

            def get_account_summary(self):
                return {"equity": 100000.0, "cash": 20000.0}
        return _Client()

    def fake_find_mismatches(broker_qty, engine_qty):
        return ["XLK: broker=5.0 engine=10.0"]

    async def fake_send_failure_alert(subject, body, source="engine"):
        alert_calls.append(subject)
        return {"status": "journaled"}

    async def fake_set_sleeve_status(db, sleeve, status, reason=None):
        status_calls.append(status)

    async def fake_write_report(report_type, severity, source, title, body, db=None):
        write_calls.append((report_type, severity))
        return "rep-id"

    monkeypatch.setattr(db_mod, "get_db", fake_get_db)
    monkeypatch.setattr(creds_mod, "get_active_alpaca_account", fake_get_active_alpaca_account)
    monkeypatch.setattr(sleeve_mod, "get_engine_positions", fake_get_engine_positions)
    monkeypatch.setattr(alpaca_mod, "client_from_account", fake_client_from_account)
    monkeypatch.setattr(reconcile_mod, "find_mismatches", fake_find_mismatches)
    monkeypatch.setattr(alerts_mod, "send_failure_alert", fake_send_failure_alert)
    monkeypatch.setattr(sleeve_mod, "set_sleeve_status", fake_set_sleeve_status)
    monkeypatch.setattr(reporting_mod, "write_report", fake_write_report)

    # Day 1: sleeve currently active -> mismatch freezes it, alerts + journals once.
    # Sleeve-aware: this scenario only sets up Sleeve B, so SleeveState A
    # correctly reads as absent — the Task 13 Sleeve A steps are no-ops here
    # too (though this path returns "frozen" before ever reaching them).
    async def fake_get_sleeve_state_day1(db, sleeve):
        return _SleeveState(status="active") if sleeve == "B" else None
    monkeypatch.setattr(sleeve_mod, "get_sleeve_state", fake_get_sleeve_state_day1)

    result1 = await execution_daily_fn(_FakeCtx())
    assert result1["status"] == "frozen"
    assert status_calls == ["frozen"]
    assert alert_calls == ["position reconciliation mismatch — Sleeve B frozen"]
    assert write_calls == [("breaker_event", "critical")]

    # Day 2: sleeve already frozen -> no repeat alert, no repeat journal entry.
    async def fake_get_sleeve_state_day2(db, sleeve):
        return _SleeveState(status="frozen") if sleeve == "B" else None
    monkeypatch.setattr(sleeve_mod, "get_sleeve_state", fake_get_sleeve_state_day2)

    result2 = await execution_daily_fn(_FakeCtx())
    assert result2["status"] == "frozen"
    # set_sleeve_status still runs each day (idempotent re-freeze), but the
    # alert and journal write must NOT repeat.
    assert status_calls == ["frozen", "frozen"]
    assert alert_calls == ["position reconciliation mismatch — Sleeve B frozen"]
    assert write_calls == [("breaker_event", "critical")]


@pytest.mark.asyncio
async def test_breaker_trip_writes_breaker_event(monkeypatch, execution_daily_fn):
    """active -> halted transition writes one breaker_event with equity stats."""
    import pandas as pd

    import execution.alerts as alerts_mod
    import execution.broker.alpaca_client as alpaca_mod
    import execution.broker.credentials as creds_mod
    import execution.engine.circuit_breaker as breaker_mod
    import execution.engine.reconcile as reconcile_mod
    import execution.reporting as reporting_mod
    import execution.sleeve_service as sleeve_mod
    import api.lib.db as db_mod

    # `research_swarm.data.__init__` does `from .market_data_client import
    # market_data_client` (the singleton) — since that imported name is the
    # same as the submodule's own basename, it shadows the submodule
    # reference in the parent package's namespace. `import ... as mdc_mod`
    # would silently bind mdc_mod to the singleton *instance*, not the
    # module, so patching a class attribute on it fails. Go through
    # importlib.import_module(), which reads sys.modules directly and is
    # immune to that package-attribute shadowing.
    mdc_mod = importlib.import_module("research_swarm.data.market_data_client")

    write_calls = []
    alert_calls = []
    status_calls = []

    async def fake_get_db():
        return object()

    async def fake_get_active_alpaca_account(db):
        return object()

    async def fake_get_engine_positions(db, sleeve):
        return [_EnginePos("XLK", 10.0)]

    async def fake_get_sleeve_state(db, sleeve):
        # Sleeve-aware: this scenario only sets up Sleeve B. SleeveState A
        # correctly reads as absent, so the Task 13 Sleeve A steps (appended
        # after Sleeve B's breaker check, which this test's flow does reach)
        # are a full no-op and never touch write_report/alerts/status here.
        if sleeve != "B":
            return None
        return _SleeveState(status="active", cash=10000.0,
                             inception_equity=50000.0, inception_spy=400.0)

    def fake_client_from_account(account):
        class _Client:
            def get_positions(self):
                return [_BrokerPos({
                    "symbol": "XLK", "qty": 10.0,
                    "market_value": 1000.0, "current_price": 100.0,
                })]

            def get_account_summary(self):
                return {"equity": 11000.0, "cash": 10000.0}
        return _Client()

    def fake_find_mismatches(broker_qty, engine_qty):
        return []  # reconcile clean -> proceeds to snapshot + breaker check

    async def fake_store_snapshot(db, sleeve, snapshot_date, equity, cash,
                                   positions_value, spy_close):
        return None

    class _FakeMarketDataClient:
        def get_historical_data(self, symbol, period="5d"):
            return pd.DataFrame({"Close": [300.0, 310.0]})

    def fake_circuit_breaker_tripped(equity, inception_equity, spy_close, inception_spy):
        return True  # force the transition regardless of the real math

    async def fake_send_failure_alert(subject, body, source="engine"):
        alert_calls.append(subject)
        return {"status": "journaled"}

    async def fake_set_sleeve_status(db, sleeve, status, reason=None):
        status_calls.append(status)

    async def fake_write_report(report_type, severity, source, title, body, db=None):
        write_calls.append((report_type, severity, body))
        return "rep-id"

    monkeypatch.setattr(db_mod, "get_db", fake_get_db)
    monkeypatch.setattr(creds_mod, "get_active_alpaca_account", fake_get_active_alpaca_account)
    monkeypatch.setattr(sleeve_mod, "get_engine_positions", fake_get_engine_positions)
    monkeypatch.setattr(sleeve_mod, "get_sleeve_state", fake_get_sleeve_state)
    monkeypatch.setattr(alpaca_mod, "client_from_account", fake_client_from_account)
    monkeypatch.setattr(reconcile_mod, "find_mismatches", fake_find_mismatches)
    monkeypatch.setattr(sleeve_mod, "store_snapshot", fake_store_snapshot)
    monkeypatch.setattr(mdc_mod, "MarketDataClient", _FakeMarketDataClient)
    monkeypatch.setattr(breaker_mod, "circuit_breaker_tripped", fake_circuit_breaker_tripped)
    monkeypatch.setattr(alerts_mod, "send_failure_alert", fake_send_failure_alert)
    monkeypatch.setattr(sleeve_mod, "set_sleeve_status", fake_set_sleeve_status)
    monkeypatch.setattr(reporting_mod, "write_report", fake_write_report)

    result = await execution_daily_fn(_FakeCtx())

    assert result["status"] == "ok"
    assert result["breaker_tripped"] is True
    assert status_calls == ["halted"]
    assert alert_calls == ["Sleeve B circuit breaker tripped"]
    assert len(write_calls) == 1
    report_type, severity, body = write_calls[0]
    assert (report_type, severity) == ("breaker_event", "critical")
    assert body["transition"] == "active->halted"
    # the branch already has the equity/SPY numbers in scope — they must
    # land in the journal body, not just the alert text.
    assert body["equity"] == 11000.0
    assert body["inception_equity"] == 50000.0
    assert body["spy_close"] == 310.0
    assert body["inception_spy"] == 400.0


def test_fills_settle_before_reconcile():
    """Reconciling BEFORE settling compares the broker to a stale book.

    2026-07-28: five Sleeve A limit orders filled during the session. Alpaca
    held 8 names, EnginePosition held 3 — and sleeve-a-reconcile ran before
    sleeve-a-fills, so the nightly pass would have seen five unexplained broker
    positions and frozen the sleeve over orders the engine placed itself.

    Settling first is also the SAFER operation: it only touches orders that
    already have an EngineTrade row, so it can never adopt a position it cannot
    explain. Reconcile then catches whatever genuinely remains unexplained.

    Asserted against the registered function's source rather than a simulated
    run: the step names are literals and the ordering is the whole invariant,
    so this fails loudly if anyone swaps them back.
    """
    import inspect

    import inngest_app.functions.execution_daily as ed

    src = inspect.getsource(ed._register_inngest_function)
    fills = src.index('step.run("sleeve-a-fills"')
    recon = src.index('step.run("sleeve-a-reconcile"')
    assert fills < recon, "sleeve-a-fills must run before sleeve-a-reconcile"

    # And fills must no longer gate on the reconcile result it now precedes.
    fills_body = src[src.index("async def sleeve_a_fills_step"):fills]
    assert "a_recon" not in fills_body, (
        "fills cannot read a_recon once it runs first — it would be undefined"
    )


# ── Phase C: the plan lands on the position at fill ──────────────────────────
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import inngest_app.functions.execution_daily as xd

_PLAN = {"ladder": [{"price": 340.0, "size_pct": 0.5, "why": "r"}],
         "thesis_break": "capex cut", "exit_plan": None}


def _order(symbol="AEHR", journal=None):
    return SimpleNamespace(symbol=symbol, journal=journal or {})


def test_provenance_copies_position_plan():
    db = MagicMock()
    db.engineposition.update = AsyncMock()
    order = _order(journal={"sourceTags": {"themes": ["x"]},
                            "position_plan": _PLAN})
    asyncio.run(xd._persist_position_provenance(db, order))
    data = db.engineposition.update.call_args.kwargs["data"]
    assert "positionPlan" in data          # Json-wrapped plan present


def test_provenance_without_plan_leaves_column_untouched():
    """Latest plan wins on adds — but an add with NO plan must not blank the
    plan already on the row. Absent key → no positionPlan in the update."""
    db = MagicMock()
    db.engineposition.update = AsyncMock()
    asyncio.run(xd._persist_position_provenance(
        db, _order(journal={"sourceTags": {"themes": ["x"]},
                            "position_plan": None})))
    data = db.engineposition.update.call_args.kwargs["data"]
    assert "positionPlan" not in data


def test_provenance_is_replay_idempotent():
    """The fills sweep re-runs on Inngest replay (PR #12 lesson). Running the
    provenance copy twice must produce the identical update both times and
    never raise."""
    db = MagicMock()
    db.engineposition.update = AsyncMock()
    order = _order(journal={"position_plan": _PLAN})
    asyncio.run(xd._persist_position_provenance(db, order))
    asyncio.run(xd._persist_position_provenance(db, order))
    first, second = db.engineposition.update.call_args_list
    assert first.kwargs["where"] == second.kwargs["where"]
    assert str(first.kwargs["data"]) == str(second.kwargs["data"])


def test_provenance_still_never_raises():
    db = MagicMock()
    db.engineposition.update = AsyncMock(side_effect=RuntimeError("db down"))
    asyncio.run(xd._persist_position_provenance(
        db, _order(journal={"position_plan": _PLAN})))   # must not raise
