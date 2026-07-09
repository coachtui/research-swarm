"""Failure alerts land in the EngineReport journal (email path deleted)."""
import pytest

import execution.alerts as alerts


@pytest.mark.asyncio
async def test_alert_writes_engine_failure_report(monkeypatch):
    calls = {}

    async def fake_write_report(report_type, severity, source, title, body, db=None):
        calls.update(type=report_type, severity=severity, source=source,
                     title=title, body=body)
        return "rep_1"

    monkeypatch.setattr(alerts, "write_report", fake_write_report)
    result = await alerts.send_failure_alert("subj", "detail", source="unit")
    assert result == {"status": "journaled"}
    assert calls["type"] == "engine_failure"
    assert calls["severity"] == "critical"
    assert calls["source"] == "unit"
    assert calls["title"] == "subj"
    assert calls["body"] == {"detail": "detail"}


@pytest.mark.asyncio
async def test_alert_reports_error_when_journal_fails(monkeypatch):
    async def fake_write_report(*a, **k):
        return None

    monkeypatch.setattr(alerts, "write_report", fake_write_report)
    result = await alerts.send_failure_alert("subj", "detail")
    assert result == {"status": "error"}


def test_resend_is_gone():
    import inspect
    src = inspect.getsource(alerts)
    assert "resend" not in src
    assert "RESEND_API_KEY" not in src
