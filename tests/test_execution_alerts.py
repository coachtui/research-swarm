"""Tests for execution/alerts.py — dormant-email failure alerts."""
import sys
import types
from unittest.mock import MagicMock

from execution.alerts import send_failure_alert


def test_skips_when_email_unconfigured(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("OWNER_EMAIL", raising=False)
    assert send_failure_alert("subj", "body") == {"status": "skipped"}


def test_sends_when_configured(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_123")
    monkeypatch.setenv("OWNER_EMAIL", "tui@example.com")
    fake_resend = types.ModuleType("resend")
    fake_resend.Emails = MagicMock()
    monkeypatch.setitem(sys.modules, "resend", fake_resend)

    assert send_failure_alert("daily cron failed", "trace") == {"status": "sent"}
    payload = fake_resend.Emails.send.call_args.args[0]
    assert payload["to"] == ["tui@example.com"]
    assert "[Autopilot alert]" in payload["subject"]


def test_never_raises_on_send_error(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_123")
    monkeypatch.setenv("OWNER_EMAIL", "tui@example.com")
    fake_resend = types.ModuleType("resend")
    fake_resend.Emails = MagicMock()
    fake_resend.Emails.send.side_effect = RuntimeError("api down")
    monkeypatch.setitem(sys.modules, "resend", fake_resend)

    assert send_failure_alert("subj", "body") == {"status": "error"}
