"""Guarded-registration checks for the tiered weekly batch."""
import pytest

import execution.alerts as alerts_mod


def test_module_imports_cleanly_without_optional_deps():
    """Must never raise at import time — even without inngest/prisma installed."""
    import inngest_app.functions.weekly_batch as wb  # noqa: F401


def test_registers_when_deps_available():
    pytest.importorskip("inngest")
    pytest.importorskip("prisma")
    from inngest_app.functions.weekly_batch import weekly_batch
    assert weekly_batch is not None


@pytest.mark.asyncio
async def test_on_failure_alerts_after_retries_are_exhausted(monkeypatch):
    """The 2026-07-27 failure was found by chance — this cron had no alert path,
    unlike theme_delta_weekly. Inngest calls on_failure once retries run out."""
    calls = []

    async def fake_send_failure_alert(subject, body, source="engine"):
        calls.append((subject, body, source))
        return {"status": "journaled"}

    monkeypatch.setattr(alerts_mod, "send_failure_alert", fake_send_failure_alert)

    from inngest_app.functions.weekly_batch import _on_failure

    class _Event:
        data = {"error": "invalid character 'N' looking for beginning of value"}

    class _Ctx:
        event = _Event()

    await _on_failure(_Ctx())

    assert len(calls) == 1
    subject, body, source = calls[0]
    assert source == "weekly_batch"
    assert "invalid character" in body


def test_active_functions_includes_weekly_batch_when_registered():
    from inngest_app.functions.weekly_batch import weekly_batch
    from inngest_app.index import ACTIVE_FUNCTIONS
    if weekly_batch is not None:
        assert weekly_batch in ACTIVE_FUNCTIONS
    else:
        assert weekly_batch not in ACTIVE_FUNCTIONS
