"""
Tests for the Inngest Connect worker (inngest_app/worker.py).

These must pass in BOTH environments:
- SDK / [connect] extra absent (local py3.9 unit-test env): the module still
  imports, start_worker() degrades to None loudly instead of raising.
- SDK present (Railway py3.12): same public contract.

The behaviour under test is mostly about FAILURE being visible. The bug this
worker replaced (2026-08-03) was invisible for 11 minutes and cost two paid
memo calls, so "worker is down" must never be a silent state — and equally,
a normal deploy must never look like an outage.
"""
import asyncio
import importlib
import sys

import pytest


def _run(coro):
    """Run a coroutine on a throwaway loop (no pytest-asyncio in this env)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def worker():
    """Fresh module state per test — worker.py holds process-wide globals."""
    mod = importlib.import_module("inngest_app.worker")
    for name, value in (("_connection", None), ("_task", None),
                        ("_last_error", None), ("_stopping", False)):
        setattr(mod, name, value)
    yield mod
    for name, value in (("_connection", None), ("_task", None),
                        ("_last_error", None), ("_stopping", False)):
        setattr(mod, name, value)


@pytest.fixture
def no_journal(worker, monkeypatch):
    """Capture outage journals instead of hitting the DB."""
    calls = []

    async def _fake():
        calls.append(worker._last_error)

    monkeypatch.setattr(worker, "_journal_worker_down", _fake)
    return calls


def test_module_imports_without_connect_extra(worker):
    """Import safety: Vercel and the py3.9 test env have no [connect] extra."""
    assert callable(worker.start_worker)
    assert callable(worker.stop_worker)
    assert callable(worker.worker_status)


def test_instance_id_prefers_explicit_env(worker, monkeypatch):
    monkeypatch.setenv("INNGEST_INSTANCE_ID", "explicit-id")
    monkeypatch.setenv("RAILWAY_SERVICE_NAME", "web")
    assert worker.resolve_instance_id() == "explicit-id"


def test_instance_id_falls_back_to_railway_service(worker, monkeypatch):
    """Stable across deploys — the SDK's hostname default is not."""
    monkeypatch.delenv("INNGEST_INSTANCE_ID", raising=False)
    monkeypatch.setenv("RAILWAY_SERVICE_NAME", "web")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    assert worker.resolve_instance_id() == "web-production"


def test_instance_id_falls_back_to_hostname(worker, monkeypatch):
    monkeypatch.delenv("INNGEST_INSTANCE_ID", raising=False)
    monkeypatch.delenv("RAILWAY_SERVICE_NAME", raising=False)
    assert worker.resolve_instance_id()


def test_status_reports_not_started(worker):
    """The dangerous state is 'never connected' — it must be labelled, not blank."""
    status = worker.worker_status()
    assert status["running"] is False
    assert status["state"] == "not_started"


def test_status_reports_live_state(worker):
    class _Conn:
        def get_state(self):
            return "ACTIVE"

    worker._connection = _Conn()
    assert worker.worker_status() == {
        "running": True, "state": "ACTIVE", "error": None,
    }


def test_status_never_raises_on_broken_connection(worker):
    class _Conn:
        def get_state(self):
            raise RuntimeError("boom")

    worker._connection = _Conn()
    status = worker.worker_status()
    assert status["running"] is True
    assert status["state"] == "unknown"
    assert "boom" in status["error"]


def test_start_worker_degrades_loudly_when_connect_extra_missing(
    worker, monkeypatch, no_journal
):
    """No [connect] extra must NOT raise — but must journal and record why.

    `from inngest.connect import connect` raises ImportError when the module
    exists but lacks the name, which is how we simulate the extra being absent
    regardless of whether the real SDK is installed.
    """
    monkeypatch.setitem(sys.modules, "inngest.connect", object())

    result = _run(worker.start_worker(object(), [object()]))

    assert result is None
    assert worker._last_error is not None
    assert "connect import failed" in worker._last_error
    assert no_journal, "a dead worker must be journaled, not silently skipped"
    assert worker.worker_status()["running"] is False


def test_start_worker_reports_a_construction_failure(worker, monkeypatch, no_journal):
    """connect() itself blowing up is the same class of outage."""
    class _Mod:
        @staticmethod
        def connect(**_kwargs):
            raise RuntimeError("bad signing key")

    monkeypatch.setitem(sys.modules, "inngest.connect", _Mod)

    assert _run(worker.start_worker(object(), [object()])) is None
    assert "bad signing key" in worker._last_error
    assert no_journal


def test_start_worker_passes_empty_shutdown_signals(worker, monkeypatch, no_journal):
    """uvicorn owns SIGTERM/SIGINT.

    The SDK installs its own handlers when shutdown_signals is None, which
    would clobber uvicorn's graceful shutdown.
    """
    captured = {}

    class _Conn:
        async def start(self):
            await asyncio.sleep(3600)

        def get_state(self):
            return "ACTIVE"

    class _Mod:
        @staticmethod
        def connect(**kwargs):
            captured.update(kwargs)
            return _Conn()

    monkeypatch.setitem(sys.modules, "inngest.connect", _Mod)
    monkeypatch.setenv("INNGEST_INSTANCE_ID", "test-instance")

    async def _scenario():
        await worker.start_worker(object(), [object()])
        await worker.stop_worker()

    _run(_scenario())

    assert captured["shutdown_signals"] == []
    assert captured["instance_id"] == "test-instance"


def test_stop_worker_is_a_noop_when_never_started(worker):
    _run(worker.stop_worker())
    assert worker._connection is None


def test_graceful_stop_does_not_journal_a_false_outage(worker, no_journal):
    """Every deploy closes the worker. That must not look like a crash.

    Regression guard: the first cut of _supervise journaled from a finally
    block, so a clean shutdown wrote a critical 'worker is down' row on each
    redeploy — which is exactly how a real outage row gets ignored.
    """
    closed = {"called": False}

    class _Conn:
        async def start(self):
            # Blocks until close() lets it return, like the real SDK.
            while not closed["called"]:
                await asyncio.sleep(0.01)

        async def close(self, *, wait=False):
            closed["called"] = True

        def get_state(self):
            return "ACTIVE"

    async def _scenario():
        conn = _Conn()
        worker._connection = conn
        worker._task = asyncio.ensure_future(worker._supervise(conn))
        await asyncio.sleep(0.05)
        await worker.stop_worker()
        await asyncio.sleep(0.05)

    _run(_scenario())
    assert no_journal == [], "graceful shutdown must not journal an outage"


def test_unexpected_close_journals_an_outage(worker, no_journal):
    """The inverse: a connection that dies on its own IS an outage."""
    class _Conn:
        async def start(self):
            return  # dies immediately, nobody asked it to

    _run(worker._supervise(_Conn()))

    assert len(no_journal) == 1
    assert "unexpected" in (worker._last_error or "")


def test_crash_journals_an_outage(worker, no_journal):
    class _Conn:
        async def start(self):
            raise ConnectionError("websocket refused")

    _run(worker._supervise(_Conn()))

    assert len(no_journal) == 1
    assert "websocket refused" in worker._last_error
