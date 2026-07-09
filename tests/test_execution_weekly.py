"""Tests for execution_weekly — pure plan builder + guarded registration."""
import importlib
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest


def _sdk_available() -> bool:
    try:
        from inngest import Inngest  # noqa: F401
        return True
    except Exception:
        return False


def _rankings(order):
    return [{"etf": etf, "sector": etf, "rank_1m": i + 1, "rank_change": 0, "score": 1.0 - i * 0.1}
            for i, etf in enumerate(order)]


RANKINGS = _rankings(["XLK", "XLE", "XLF", "XLI", "XLV", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"])


def test_module_imports_without_sdk():
    mod = importlib.import_module("inngest_app.functions.execution_weekly")
    if not _sdk_available():
        assert mod.execution_weekly is None


def test_outlook_is_stale():
    from inngest_app.functions.execution_weekly import outlook_is_stale

    assert outlook_is_stale("2026-07-05T20:00:00+00:00", "2026-07-14T15:00:00+00:00") is True
    assert outlook_is_stale("2026-07-12T20:00:00+00:00", "2026-07-13T15:00:00+00:00") is False


def test_build_rebalance_plan_fresh_book_buys_top3():
    from inngest_app.functions.execution_weekly import build_rebalance_plan

    outlook = {"id": "o1", "regime": "risk_on", "conviction": 1.0, "sectorRankings": RANKINGS}
    plan = build_rebalance_plan(
        outlook,
        engine_positions={},
        broker_positions=[],
        state={"cashBalance": 30000.0, "status": "active", "accountEquity": 100000.0},
    )
    assert [o["symbol"] for o in plan["orders"]] == ["XLE", "XLF", "XLK"]
    assert all(o["side"] == "buy" for o in plan["orders"])
    assert sum(o["notional"] for o in plan["orders"]) == 30000.0
    assert plan["journal"]["regime"] == "risk_on"


def test_build_rebalance_plan_halted_sleeve_only_sells():
    from inngest_app.functions.execution_weekly import build_rebalance_plan

    outlook = {"id": "o1", "regime": "risk_on", "conviction": 1.0, "sectorRankings": RANKINGS}
    plan = build_rebalance_plan(
        outlook,
        engine_positions={"XLB": 100.0},  # rank 9 — will be rotated out
        broker_positions=[{"symbol": "XLB", "qty": 100.0, "market_value": 8000.0,
                           "current_price": 80.0}],
        state={"cashBalance": 22000.0, "status": "halted", "accountEquity": 100000.0},
    )
    assert all(o["side"] == "sell" for o in plan["orders"])
    assert any("halted" in n for n in plan["notes"])


# ── Step-function harness ────────────────────────────────────────────────────
#
# See tests/test_execution_daily.py for the rationale: the pip `inngest` SDK
# isn't installed in this environment, so a minimal fake of its surface lets
# `_register_inngest_function` actually run and hands back the raw coroutine
# to drive directly. `step.run` executes immediately — no memoization needed.

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
    def __init__(self, status, cash_balance=30000.0):
        self.status = status
        self.cashBalance = cash_balance
        self.statusReason = None


class _OutlookRow:
    def __init__(self, run_date):
        self.id = "o1"
        self.regime = "risk_on"
        self.conviction = 1.0
        self.sectorRankings = RANKINGS
        self.runDate = run_date


class _OrderResult:
    def __init__(self, d):
        self._d = d

    def to_dict(self):
        return self._d


@pytest.fixture
def execution_weekly_fn():
    """Reload inngest_app.functions.execution_weekly under a fake `inngest`
    module so its guarded registration actually runs, and hand back the raw
    (undecorated) coroutine function. Restores the real (SDK-absent) module
    state on teardown."""
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

    import inngest_app.functions.execution_weekly as mod
    importlib.reload(mod)
    assert mod.execution_weekly is not None, "fake inngest SDK injection failed"

    yield mod.execution_weekly

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
async def test_weekly_run_writes_rebalance_summary(monkeypatch, execution_weekly_fn):
    """A completed rebalance writes one rebalance_summary EngineReport whose
    body contains the orders/fills/regime the run returned."""
    import api.lib.db as db_mod
    import execution.broker.alpaca_client as alpaca_mod
    import execution.broker.credentials as creds_mod
    import execution.engine.reconcile as reconcile_mod
    import execution.outlook_service as outlook_mod
    import execution.reporting as reporting_mod
    import execution.sleeve_service as sleeve_mod

    write_calls = []

    async def fake_get_db():
        return object()

    async def fake_get_active_alpaca_account(db):
        return object()

    async def fake_get_latest_outlook(db):
        return _OutlookRow(run_date=datetime.now(timezone.utc) - timedelta(days=1))

    async def fake_get_sleeve_state(db, sleeve):
        return _SleeveState(status="active", cash_balance=30000.0)

    async def fake_get_engine_positions(db, sleeve):
        return []

    def fake_find_mismatches(broker_qty, engine_qty):
        return []

    def fake_client_from_account(account):
        class _Client:
            def is_market_open(self):
                return True

            def get_positions(self):
                return []

            def get_account_summary(self):
                return {"equity": 100000.0, "cash": 30000.0}

            def submit_market_buy_notional(self, symbol, notional):
                return _OrderResult({
                    "side": "buy", "symbol": symbol, "status": "filled",
                    "brokerOrderId": f"ord-{symbol}", "qty": notional / 100.0,
                    "notional": notional,
                })

            def submit_market_sell_qty(self, symbol, qty):
                raise AssertionError("no sells expected in this fixture")
        return _Client()

    fill_deltas = {}

    async def fake_apply_fill(db, sleeve, fill, requested_notional=None, journal=None):
        delta = -fill.get("requested_notional", 0.0)
        fill_deltas[fill["symbol"]] = delta
        return delta

    async def fake_update_sleeve_cash(db, sleeve, cash_balance):
        return None

    async def fake_write_report(report_type, severity, source, title, body, db=None):
        write_calls.append((report_type, severity, source, title, body))
        return "rep-id"

    monkeypatch.setattr(db_mod, "get_db", fake_get_db)
    monkeypatch.setattr(creds_mod, "get_active_alpaca_account", fake_get_active_alpaca_account)
    monkeypatch.setattr(outlook_mod, "get_latest_outlook", fake_get_latest_outlook)
    monkeypatch.setattr(sleeve_mod, "get_sleeve_state", fake_get_sleeve_state)
    monkeypatch.setattr(sleeve_mod, "get_engine_positions", fake_get_engine_positions)
    monkeypatch.setattr(reconcile_mod, "find_mismatches", fake_find_mismatches)
    monkeypatch.setattr(alpaca_mod, "client_from_account", fake_client_from_account)
    monkeypatch.setattr(sleeve_mod, "apply_fill", fake_apply_fill)
    monkeypatch.setattr(sleeve_mod, "update_sleeve_cash", fake_update_sleeve_cash)
    monkeypatch.setattr(reporting_mod, "write_report", fake_write_report)

    result = await execution_weekly_fn(_FakeCtx())

    assert result["status"] == "rebalanced"
    assert result["orders"] == 3
    assert result["unfilled"] == []
    assert result["regime"] == "risk_on"

    assert len(write_calls) == 1
    report_type, severity, source, title, body = write_calls[0]
    assert (report_type, severity, source) == ("rebalance_summary", "info", "execution_weekly")
    assert "rebalanced" in title
    assert body == result
