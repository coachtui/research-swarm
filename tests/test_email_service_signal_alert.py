"""Tests for send_signal_alert — the weekly batch alert email."""
import pytest
from unittest.mock import patch, MagicMock

from api.services.alert_evaluator import AlertEvent
from api.services.email_service import send_signal_alert


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setattr("api.services.email_service.resend.api_key", "test-key")


@pytest.mark.asyncio
async def test_returns_false_without_api_key(monkeypatch):
    monkeypatch.setattr("api.services.email_service.resend.api_key", "")
    ok, err = await send_signal_alert(
        "u@x.com", "AAPL",
        [AlertEvent(kind="verdict_flip", ticker="AAPL",
                    prior_value="hold", current_value="buy")],
        run_id="r1",
    )
    assert not ok
    assert "RESEND_API_KEY" in err


@pytest.mark.asyncio
async def test_skips_when_no_events():
    ok, err = await send_signal_alert("u@x.com", "AAPL", [], run_id="r1")
    assert not ok
    assert "no events" in err.lower()


@pytest.mark.asyncio
async def test_verdict_flip_email_renders():
    events = [AlertEvent(kind="verdict_flip", ticker="AAPL",
                         prior_value="hold", current_value="buy")]
    with patch("api.services.email_service.resend.Emails.send") as mock_send:
        mock_send.return_value = {"id": "abc"}
        ok, err = await send_signal_alert("u@x.com", "AAPL", events, run_id="r1")
    assert ok, err
    args, kwargs = mock_send.call_args
    payload = args[0] if args else kwargs
    assert "AAPL" in payload["subject"]
    html = payload["html"]
    assert "hold" in html.lower()
    assert "buy" in html.lower()


@pytest.mark.asyncio
async def test_ev_change_email_renders():
    events = [AlertEvent(kind="ev_change", ticker="AAPL",
                         prior_value=0.55, current_value=0.80)]
    with patch("api.services.email_service.resend.Emails.send") as mock_send:
        mock_send.return_value = {"id": "abc"}
        ok, err = await send_signal_alert("u@x.com", "AAPL", events, run_id="r1")
    assert ok
    payload = mock_send.call_args[0][0]
    # Values should render as percentages
    assert "55" in payload["html"]
    assert "80" in payload["html"]


@pytest.mark.asyncio
async def test_combined_events_single_email():
    events = [
        AlertEvent(kind="verdict_flip", ticker="AAPL",
                   prior_value="hold", current_value="buy"),
        AlertEvent(kind="ev_change", ticker="AAPL",
                   prior_value=0.55, current_value=0.80),
    ]
    with patch("api.services.email_service.resend.Emails.send") as mock_send:
        mock_send.return_value = {"id": "abc"}
        ok, _ = await send_signal_alert("u@x.com", "AAPL", events, run_id="r1")
    assert ok
    mock_send.assert_called_once()
    payload = mock_send.call_args[0][0]
    assert payload["to"] == ["u@x.com"]


@pytest.mark.asyncio
async def test_returns_false_on_resend_exception():
    events = [AlertEvent(kind="verdict_flip", ticker="AAPL",
                         prior_value="hold", current_value="buy")]
    with patch("api.services.email_service.resend.Emails.send",
               side_effect=RuntimeError("boom")):
        ok, err = await send_signal_alert("u@x.com", "AAPL", events)
    assert not ok
    assert "boom" in err
