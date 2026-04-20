"""Tests for alert_delivery_service — DB and email calls are mocked."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from api.services.alert_delivery_service import (
    deliver_weekly_alerts,
    ELIGIBLE_TIERS,
)


def _signal(ticker="AAPL", verdict="buy", prior_verdict="hold",
            ev=0.80, prior_ev=0.55):
    s = MagicMock()
    s.ticker = ticker
    s.verdict = verdict
    s.priorVerdict = prior_verdict
    s.evProbability = ev
    s.priorEvProbability = prior_ev
    s.id = f"sig-{ticker}"
    return s


def _watchlist_row(user_id, ticker, enable_alerts=True,
                   user_email="u@x.com", tier="starter",
                   email_alerts=True):
    row = MagicMock()
    row.userId = user_id
    row.ticker = ticker
    row.enableAlerts = enable_alerts
    user = MagicMock()
    user.email = user_email
    user.tier = tier
    user.preferences = MagicMock()
    user.preferences.emailAlerts = email_alerts
    row.user = user
    return row


@pytest.fixture
def run_date():
    return datetime(2026, 4, 20, tzinfo=timezone.utc)


@pytest.fixture
def db_with(*_args):
    """Factory — returns a fn that builds a mocked Prisma db."""
    def _make(signals, watchlists):
        db = MagicMock()
        db.weeklysignal = MagicMock()
        db.weeklysignal.find_many = AsyncMock(return_value=signals)
        db.watchlist = MagicMock()
        db.watchlist.find_many = AsyncMock(return_value=watchlists)
        db.alerthistory = MagicMock()
        db.alerthistory.create = AsyncMock()
        return db
    return _make


@pytest.mark.asyncio
async def test_sends_email_when_verdict_flips_for_watcher(run_date, db_with):
    signals = [_signal(ticker="AAPL", verdict="buy", prior_verdict="hold")]
    watchlists = [_watchlist_row("u1", "AAPL")]
    db = db_with(signals, watchlists)

    with patch(
        "api.services.alert_delivery_service.send_signal_alert",
        new=AsyncMock(return_value=(True, "")),
    ) as mock_send:
        summary = await deliver_weekly_alerts(db=db, run_date=run_date)

    assert summary["emails_sent"] == 1
    mock_send.assert_awaited_once()
    kwargs = mock_send.await_args.kwargs
    assert kwargs["user_email"] == "u@x.com"
    assert kwargs["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_free_tier_gets_no_email(run_date, db_with):
    signals = [_signal()]
    watchlists = [_watchlist_row("u1", "AAPL", tier="free")]
    db = db_with(signals, watchlists)

    with patch(
        "api.services.alert_delivery_service.send_signal_alert",
        new=AsyncMock(return_value=(True, "")),
    ) as mock_send:
        summary = await deliver_weekly_alerts(db=db, run_date=run_date)

    mock_send.assert_not_awaited()
    assert summary["emails_sent"] == 0
    assert summary["skipped_ineligible_tier"] == 1


@pytest.mark.asyncio
async def test_watchlist_alerts_disabled_skipped(run_date, db_with):
    signals = [_signal()]
    watchlists = [_watchlist_row("u1", "AAPL", enable_alerts=False)]
    db = db_with(signals, watchlists)

    with patch(
        "api.services.alert_delivery_service.send_signal_alert",
        new=AsyncMock(return_value=(True, "")),
    ) as mock_send:
        summary = await deliver_weekly_alerts(db=db, run_date=run_date)

    mock_send.assert_not_awaited()
    assert summary["emails_sent"] == 0


@pytest.mark.asyncio
async def test_user_preferences_email_disabled_skipped(run_date, db_with):
    signals = [_signal()]
    watchlists = [_watchlist_row("u1", "AAPL", email_alerts=False)]
    db = db_with(signals, watchlists)

    with patch(
        "api.services.alert_delivery_service.send_signal_alert",
        new=AsyncMock(return_value=(True, "")),
    ) as mock_send:
        summary = await deliver_weekly_alerts(db=db, run_date=run_date)

    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_events_no_email(run_date, db_with):
    # current == prior, no change
    signals = [_signal(verdict="hold", prior_verdict="hold",
                       ev=0.55, prior_ev=0.55)]
    watchlists = [_watchlist_row("u1", "AAPL")]
    db = db_with(signals, watchlists)

    with patch(
        "api.services.alert_delivery_service.send_signal_alert",
        new=AsyncMock(return_value=(True, "")),
    ) as mock_send:
        summary = await deliver_weekly_alerts(db=db, run_date=run_date)

    mock_send.assert_not_awaited()
    assert summary["emails_sent"] == 0


@pytest.mark.asyncio
async def test_logs_alert_history_on_success(run_date, db_with):
    signals = [_signal()]
    watchlists = [_watchlist_row("u1", "AAPL")]
    db = db_with(signals, watchlists)

    with patch(
        "api.services.alert_delivery_service.send_signal_alert",
        new=AsyncMock(return_value=(True, "")),
    ):
        await deliver_weekly_alerts(db=db, run_date=run_date)

    db.alerthistory.create.assert_awaited_once()
    data = db.alerthistory.create.await_args.kwargs["data"]
    assert data["userId"] == "u1"
    assert data["ticker"] == "AAPL"
    assert data["emailSent"] is True


@pytest.mark.asyncio
async def test_logs_alert_history_on_failure(run_date, db_with):
    signals = [_signal()]
    watchlists = [_watchlist_row("u1", "AAPL")]
    db = db_with(signals, watchlists)

    with patch(
        "api.services.alert_delivery_service.send_signal_alert",
        new=AsyncMock(return_value=(False, "resend down")),
    ):
        summary = await deliver_weekly_alerts(db=db, run_date=run_date)

    assert summary["emails_failed"] == 1
    data = db.alerthistory.create.await_args.kwargs["data"]
    assert data["emailSent"] is False
    assert "resend down" in data["emailError"]


@pytest.mark.asyncio
async def test_eligible_tiers_is_complete():
    assert "starter" in ELIGIBLE_TIERS
    assert "investor" in ELIGIBLE_TIERS
    assert "trader" in ELIGIBLE_TIERS
    assert "free" not in ELIGIBLE_TIERS


@pytest.mark.asyncio
async def test_multiple_watchers_each_get_email(run_date, db_with):
    signals = [_signal()]
    watchlists = [
        _watchlist_row("u1", "AAPL", user_email="a@x.com"),
        _watchlist_row("u2", "AAPL", user_email="b@x.com"),
    ]
    db = db_with(signals, watchlists)

    with patch(
        "api.services.alert_delivery_service.send_signal_alert",
        new=AsyncMock(return_value=(True, "")),
    ) as mock_send:
        summary = await deliver_weekly_alerts(db=db, run_date=run_date)

    assert summary["emails_sent"] == 2
    assert mock_send.await_count == 2
    sent_to = {call.kwargs["user_email"] for call in mock_send.await_args_list}
    assert sent_to == {"a@x.com", "b@x.com"}
    assert db.alerthistory.create.await_count == 2
    logged_users = {
        c.kwargs["data"]["userId"] for c in db.alerthistory.create.await_args_list
    }
    assert logged_users == {"u1", "u2"}


@pytest.mark.asyncio
async def test_alert_history_write_failure_does_not_break_delivery(run_date, db_with):
    signals = [_signal()]
    watchlists = [_watchlist_row("u1", "AAPL")]
    db = db_with(signals, watchlists)
    db.alerthistory.create = AsyncMock(side_effect=RuntimeError("db down"))

    with patch(
        "api.services.alert_delivery_service.send_signal_alert",
        new=AsyncMock(return_value=(True, "")),
    ):
        summary = await deliver_weekly_alerts(db=db, run_date=run_date)

    assert summary["emails_sent"] == 1
    assert summary["emails_failed"] == 0
