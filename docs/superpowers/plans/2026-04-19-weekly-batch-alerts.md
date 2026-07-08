# Weekly Batch Alerts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing weekly batch into an alert trigger — when the Sunday-night pipeline completes, diff each ticker against its prior week and email users whose watchlists include a ticker that materially changed.

**Architecture:** A new Inngest function listens for the `batch/completed` event (already emitted by `weekly_batch`), walks every `WeeklySignal` row for the run_date (which already carries `priorVerdict`/`priorEvProbability`), evaluates alert conditions, and for each matching `(user, ticker)` in the active watchlist population sends an email via Resend and writes an `AlertHistory` row. Pure evaluator logic is unit-tested; Inngest + Resend calls are runtime-only.

**Tech Stack:** Prisma (asyncio), Inngest Python SDK, Resend, pytest/pytest-asyncio. Pattern mirrors `inngest/functions/send_teaser_digest.py`.

---

## Pre-Flight Context (read before starting)

1. The weekly batch is already built and running on main:
   - `inngest/functions/weekly_batch.py` — fires Mondays 03:00 UTC, emits `batch/completed` with `{run_date, ticker_count}`.
   - `api/services/weekly_signal_service.py` — already populates `priorVerdict` and `priorEvProbability` on each new `WeeklySignal` row.
2. Alert plumbing already exists:
   - `api/services/email_service.py` — Resend wrapper with `send_score_change_alert` (single-ticker, watchlist-refresh flow).
   - `Watchlist.enableAlerts` (bool, default true), `UserPreferences.emailAlerts` (bool, default true), `AlertHistory` (log table).
   - The existing `_trigger_score_change_alert` in `api/routes/watchlist.py` is the reference for delivery + logging.
3. Alert-eligible tiers per spec: `starter`, `investor`, `trader`. `free` users do **not** receive alerts.
4. Alert conditions for v1 (from `docs/superpowers/specs/2026-04-17-monetization-leverage-design.md`):
   - Verdict flip (e.g. `hold → buy`, `buy → avoid`)
   - EV probability change ≥ 0.10 (10 percentage points)
   Insider spike / dark pool spike / fair value gap crossing 15% are deferred to v2.
5. Follow `send_teaser_digest.py`'s pattern: pure helpers at module top (importable and unit-testable with no Inngest runtime), runtime registration in `_register_inngest_function()` guarded by `try/except`.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `api/services/alert_evaluator.py` | Pure functions: given prior + current signal, return list of triggered events |
| Create | `tests/test_alert_evaluator.py` | Unit tests for evaluator |
| Modify | `api/services/email_service.py` | Add `send_signal_alert` for verdict/EV-change emails |
| Create | `tests/test_email_service_signal_alert.py` | Unit tests for the new email function (Resend mocked) |
| Create | `api/services/alert_delivery_service.py` | Orchestrates: load signals → find watchers → evaluate → send → log |
| Create | `tests/test_alert_delivery_service.py` | Unit tests (DB mocked) |
| Create | `inngest/functions/send_watchlist_alerts.py` | Inngest listener for `batch/completed` |
| Modify | `inngest/index.py` | Register new function in `serve(...)` |

---

## Task 1: Alert Evaluator (pure TDD)

**Files:**
- Create: `api/services/alert_evaluator.py`
- Create: `tests/test_alert_evaluator.py`

The evaluator is a pure function over a `WeeklySignal`-shaped dict (or model) — no DB, no network. This keeps the logic trivially testable and keeps Inngest/Prisma out of the unit tests.

- [ ] **Step 1: Write failing tests**

Create `tests/test_alert_evaluator.py`:

```python
"""Unit tests for weekly alert evaluator."""
import pytest

from api.services.alert_evaluator import (
    AlertEvent,
    evaluate_signal_change,
    EV_PROB_THRESHOLD,
)


def _sig(verdict=None, ev=None, prior_verdict=None, prior_ev=None):
    """Build a minimal signal-shaped dict for tests."""
    return {
        "ticker": "AAPL",
        "verdict": verdict,
        "evProbability": ev,
        "priorVerdict": prior_verdict,
        "priorEvProbability": prior_ev,
    }


class TestVerdictFlip:
    def test_hold_to_buy_triggers(self):
        events = evaluate_signal_change(_sig(verdict="buy", prior_verdict="hold"))
        assert any(e.kind == "verdict_flip" for e in events)

    def test_buy_to_avoid_triggers(self):
        events = evaluate_signal_change(_sig(verdict="avoid", prior_verdict="buy"))
        assert any(e.kind == "verdict_flip" for e in events)

    def test_same_verdict_no_event(self):
        events = evaluate_signal_change(_sig(verdict="buy", prior_verdict="buy"))
        assert not any(e.kind == "verdict_flip" for e in events)

    def test_missing_prior_verdict_no_event(self):
        events = evaluate_signal_change(_sig(verdict="buy", prior_verdict=None))
        assert not any(e.kind == "verdict_flip" for e in events)

    def test_missing_current_verdict_no_event(self):
        events = evaluate_signal_change(_sig(verdict=None, prior_verdict="buy"))
        assert not any(e.kind == "verdict_flip" for e in events)

    def test_case_insensitive_match(self):
        """'BUY' and 'buy' should not trigger a flip."""
        events = evaluate_signal_change(_sig(verdict="BUY", prior_verdict="buy"))
        assert not any(e.kind == "verdict_flip" for e in events)


class TestEvProbabilityChange:
    def test_large_jump_triggers(self):
        events = evaluate_signal_change(_sig(ev=0.80, prior_ev=0.60))
        assert any(e.kind == "ev_change" for e in events)

    def test_large_drop_triggers(self):
        events = evaluate_signal_change(_sig(ev=0.40, prior_ev=0.60))
        assert any(e.kind == "ev_change" for e in events)

    def test_small_change_no_event(self):
        events = evaluate_signal_change(_sig(ev=0.65, prior_ev=0.60))
        assert not any(e.kind == "ev_change" for e in events)

    def test_exactly_at_threshold_triggers(self):
        events = evaluate_signal_change(
            _sig(ev=0.60 + EV_PROB_THRESHOLD, prior_ev=0.60)
        )
        assert any(e.kind == "ev_change" for e in events)

    def test_missing_ev_no_event(self):
        events = evaluate_signal_change(_sig(ev=None, prior_ev=0.60))
        assert not any(e.kind == "ev_change" for e in events)

    def test_missing_prior_no_event(self):
        events = evaluate_signal_change(_sig(ev=0.80, prior_ev=None))
        assert not any(e.kind == "ev_change" for e in events)


class TestCombinedEvents:
    def test_both_events_emitted_together(self):
        events = evaluate_signal_change(
            _sig(verdict="buy", prior_verdict="hold", ev=0.80, prior_ev=0.55)
        )
        kinds = {e.kind for e in events}
        assert kinds == {"verdict_flip", "ev_change"}

    def test_no_events_when_nothing_changed(self):
        events = evaluate_signal_change(
            _sig(verdict="hold", prior_verdict="hold", ev=0.60, prior_ev=0.60)
        )
        assert events == []


class TestAlertEventPayload:
    def test_verdict_flip_event_payload(self):
        [event] = [
            e for e in evaluate_signal_change(
                _sig(verdict="buy", prior_verdict="hold")
            )
            if e.kind == "verdict_flip"
        ]
        assert event.ticker == "AAPL"
        assert event.prior_value == "hold"
        assert event.current_value == "buy"

    def test_ev_change_event_payload(self):
        [event] = [
            e for e in evaluate_signal_change(_sig(ev=0.80, prior_ev=0.55))
            if e.kind == "ev_change"
        ]
        assert event.ticker == "AAPL"
        assert event.prior_value == 0.55
        assert event.current_value == 0.80
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
cd /Users/tui/research-swarm
python -m pytest tests/test_alert_evaluator.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'api.services.alert_evaluator'`

- [ ] **Step 3: Implement the evaluator**

Create `api/services/alert_evaluator.py`:

```python
"""Pure alert-event evaluator over a WeeklySignal row's current + prior fields."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Union

EV_PROB_THRESHOLD: float = 0.10  # 10 percentage points


@dataclass(frozen=True)
class AlertEvent:
    kind: str                          # "verdict_flip" | "ev_change"
    ticker: str
    prior_value: Union[str, float, None]
    current_value: Union[str, float, None]


def _get(sig: Mapping[str, Any], key: str) -> Any:
    """Read a field that may live on a dict or a Prisma model object."""
    if isinstance(sig, Mapping):
        return sig.get(key)
    return getattr(sig, key, None)


def _norm_verdict(v: Optional[str]) -> Optional[str]:
    return v.lower().strip() if isinstance(v, str) and v.strip() else None


def evaluate_signal_change(signal: Any) -> List[AlertEvent]:
    """
    Return the list of AlertEvents triggered by the transition from
    prior to current values on a single WeeklySignal row.

    Accepts a dict or a Prisma model — any object exposing the expected
    attributes/keys (ticker, verdict, evProbability, priorVerdict,
    priorEvProbability).
    """
    ticker = _get(signal, "ticker")
    if not ticker:
        return []

    events: List[AlertEvent] = []

    # Verdict flip
    current_verdict = _norm_verdict(_get(signal, "verdict"))
    prior_verdict = _norm_verdict(_get(signal, "priorVerdict"))
    if current_verdict and prior_verdict and current_verdict != prior_verdict:
        events.append(AlertEvent(
            kind="verdict_flip",
            ticker=ticker,
            prior_value=prior_verdict,
            current_value=current_verdict,
        ))

    # EV probability change
    current_ev = _get(signal, "evProbability")
    prior_ev = _get(signal, "priorEvProbability")
    if (
        isinstance(current_ev, (int, float))
        and isinstance(prior_ev, (int, float))
        and abs(float(current_ev) - float(prior_ev)) >= EV_PROB_THRESHOLD
    ):
        events.append(AlertEvent(
            kind="ev_change",
            ticker=ticker,
            prior_value=float(prior_ev),
            current_value=float(current_ev),
        ))

    return events
```

- [ ] **Step 4: Run tests and confirm pass**

```bash
python -m pytest tests/test_alert_evaluator.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/services/alert_evaluator.py tests/test_alert_evaluator.py
git commit -m "feat: add weekly alert evaluator for verdict and EV changes"
```

---

## Task 2: Email Template for Signal Alerts (TDD)

**Files:**
- Modify: `api/services/email_service.py` (append new function — do not touch existing `send_score_change_alert`)
- Create: `tests/test_email_service_signal_alert.py`

Add a new function `send_signal_alert(user_email, ticker, events, run_id=None)` that renders a single email covering one or more `AlertEvent`s for a given ticker.

- [ ] **Step 1: Write failing tests**

Create `tests/test_email_service_signal_alert.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
python -m pytest tests/test_email_service_signal_alert.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'send_signal_alert'`

- [ ] **Step 3: Add send_signal_alert to email_service.py**

Open `api/services/email_service.py` and append this function at the end of the file (after `send_weekly_digest`):

```python
async def send_signal_alert(
    user_email: str,
    ticker: str,
    events: list,  # list[AlertEvent] from alert_evaluator
    run_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Send a single email summarising all weekly-batch alert events for one ticker.

    Args:
        user_email: Recipient.
        ticker: Stock ticker the events apply to.
        events: List of AlertEvent from alert_evaluator.evaluate_signal_change.
        run_id: Optional analysis run ID for the "View Full Analysis" link.

    Returns:
        (success, error_message)
    """
    if not resend.api_key:
        return False, "RESEND_API_KEY not configured"
    if not events:
        return False, "no events supplied"

    base_url = os.getenv("FRONTEND_URL", "https://dvrg.co")
    cta_path = f"/results/{run_id}" if run_id else f"/preview/{ticker.lower()}"

    def _render_event(e) -> str:
        if e.kind == "verdict_flip":
            return (
                f"<li><strong>Verdict flipped</strong>: "
                f"{str(e.prior_value).capitalize()} → "
                f"<span style='color:#00B396'>"
                f"{str(e.current_value).capitalize()}</span></li>"
            )
        if e.kind == "ev_change":
            prior_pct = int(round(float(e.prior_value) * 100))
            current_pct = int(round(float(e.current_value) * 100))
            direction = "↑" if current_pct > prior_pct else "↓"
            return (
                f"<li><strong>EV probability {direction}</strong>: "
                f"{prior_pct}% → {current_pct}%</li>"
            )
        # Unknown kind — render defensively rather than crash
        return f"<li>{e.kind}: {e.prior_value} → {e.current_value}</li>"

    event_list_html = "".join(_render_event(e) for e in events)
    kinds = {e.kind for e in events}
    if "verdict_flip" in kinds and "ev_change" in kinds:
        subject = f"🔔 {ticker}: Verdict flipped & EV probability moved"
    elif "verdict_flip" in kinds:
        subject = f"🔔 {ticker}: Verdict flipped"
    elif "ev_change" in kinds:
        subject = f"🔔 {ticker}: EV probability moved"
    else:
        subject = f"🔔 {ticker}: Weekly alert"

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;
             max-width:600px;margin:0 auto;padding:24px;color:#333">
  <div style="background:linear-gradient(135deg,#00D9B5,#00B396);
              color:white;padding:24px;border-radius:8px 8px 0 0">
    <h1 style="margin:0;font-size:22px">Weekly Alert — {ticker}</h1>
    <p style="margin:6px 0 0;opacity:0.9">This week's batch moved a ticker on your watchlist.</p>
  </div>
  <div style="background:white;padding:24px;border:1px solid #e0e0e0;
              border-top:none;border-radius:0 0 8px 8px">
    <ul style="padding-left:20px;line-height:1.6">
      {event_list_html}
    </ul>
    <p style="margin-top:24px">
      <a href="{base_url}{cta_path}"
         style="display:inline-block;background:#00D9B5;color:white;
                padding:12px 22px;text-decoration:none;border-radius:6px;
                font-weight:600">View Full Analysis →</a>
    </p>
    <p style="margin-top:24px;font-size:12px;color:#999">
      You're receiving this because {ticker} is on your DVRG watchlist with
      alerts enabled.
      <a href="{base_url}/dashboard" style="color:#00D9B5">Manage alerts</a>
    </p>
  </div>
</body>
</html>
"""

    try:
        resend.Emails.send({
            "from": "DVRG Alerts <alerts@dvrg.co>",
            "to": [user_email],
            "subject": subject,
            "html": html,
        })
        return True, ""
    except Exception as e:
        return False, str(e)
```

Also add the missing import at the top of the file (only if not already present):

```python
# At top of email_service.py — check imports and add Optional if missing
from typing import Tuple, Optional
```

- [ ] **Step 4: Run tests and confirm pass**

```bash
python -m pytest tests/test_email_service_signal_alert.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/services/email_service.py tests/test_email_service_signal_alert.py
git commit -m "feat: add send_signal_alert email template for weekly batch alerts"
```

---

## Task 3: Alert Delivery Service (TDD)

**Files:**
- Create: `api/services/alert_delivery_service.py`
- Create: `tests/test_alert_delivery_service.py`

Orchestrates the full delivery flow for one batch run: load signals → find watchers → evaluate → send → log.

- [ ] **Step 1: Write failing tests**

Create `tests/test_alert_delivery_service.py`:

```python
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_alert_delivery_service.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'api.services.alert_delivery_service'`

- [ ] **Step 3: Implement the delivery service**

Create `api/services/alert_delivery_service.py`:

```python
"""Deliver weekly alerts for one batch run_date.

Flow:
  1. Load all WeeklySignal rows for run_date.
  2. Evaluate each row; keep only tickers with >=1 triggered event.
  3. Find watchlist rows (including user + user.preferences) whose ticker is
     in that set and whose alert gating is on.
  4. For each qualifying (user, ticker), send one consolidated email via
     send_signal_alert and log to AlertHistory.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from api.services.alert_evaluator import AlertEvent, evaluate_signal_change
from api.services.email_service import send_signal_alert

logger = logging.getLogger(__name__)

ELIGIBLE_TIERS = frozenset({"starter", "investor", "trader"})


def _history_message(events: List[AlertEvent]) -> str:
    parts: List[str] = []
    for e in events:
        if e.kind == "verdict_flip":
            parts.append(f"verdict {e.prior_value}→{e.current_value}")
        elif e.kind == "ev_change":
            parts.append(
                f"EV {int(round(e.prior_value * 100))}%"
                f"→{int(round(e.current_value * 100))}%"
            )
        else:
            parts.append(e.kind)
    return "; ".join(parts)


async def deliver_weekly_alerts(
    db: Any,
    run_date: datetime,
) -> Dict[str, int]:
    """
    Deliver all alerts for the batch that ran on run_date.

    Returns a summary dict with counters.
    """
    signals = await db.weeklysignal.find_many(
        where={"runDate": run_date},
    )
    logger.info("Alert delivery: %d signals for run_date=%s",
                len(signals), run_date.isoformat())

    # Build {ticker -> events} for tickers with >=1 event
    events_by_ticker: Dict[str, List[AlertEvent]] = {}
    for sig in signals:
        evs = evaluate_signal_change(sig)
        if evs:
            events_by_ticker[sig.ticker] = evs

    if not events_by_ticker:
        return {"emails_sent": 0, "emails_failed": 0,
                "skipped_ineligible_tier": 0, "skipped_disabled": 0}

    # Fetch all watchlist rows matching these tickers, joining user + prefs
    watchlist_rows = await db.watchlist.find_many(
        where={"ticker": {"in": list(events_by_ticker.keys())}},
        include={"user": {"include": {"preferences": True}}},
    )

    emails_sent = 0
    emails_failed = 0
    skipped_ineligible_tier = 0
    skipped_disabled = 0

    for row in watchlist_rows:
        ticker = row.ticker
        events = events_by_ticker.get(ticker)
        if not events:
            continue

        # Watchlist-level alert flag
        if not getattr(row, "enableAlerts", True):
            skipped_disabled += 1
            continue

        user = getattr(row, "user", None)
        if user is None:
            skipped_disabled += 1
            continue

        # User-level email preference (default True if row missing)
        prefs = getattr(user, "preferences", None)
        if prefs is not None and prefs.emailAlerts is False:
            skipped_disabled += 1
            continue

        # Tier gate
        tier = (getattr(user, "tier", "") or "").lower()
        if tier not in ELIGIBLE_TIERS:
            skipped_ineligible_tier += 1
            continue

        # Send
        success, error = await send_signal_alert(
            user_email=user.email,
            ticker=ticker,
            events=events,
        )

        if success:
            emails_sent += 1
        else:
            emails_failed += 1

        # Log — never raise from logging
        try:
            await db.alerthistory.create(data={
                "userId": row.userId,
                "ticker": ticker,
                "alertType": "weekly_batch",
                "message": _history_message(events),
                "runId": None,
                "emailSent": success,
                "emailError": error if not success else None,
            })
        except Exception as e:
            logger.warning("Failed to write AlertHistory for %s/%s: %s",
                           row.userId, ticker, e)

    summary = {
        "emails_sent": emails_sent,
        "emails_failed": emails_failed,
        "skipped_ineligible_tier": skipped_ineligible_tier,
        "skipped_disabled": skipped_disabled,
    }
    logger.info("Alert delivery complete: %s", summary)
    return summary
```

- [ ] **Step 4: Run tests and confirm pass**

```bash
python -m pytest tests/test_alert_delivery_service.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/services/alert_delivery_service.py tests/test_alert_delivery_service.py
git commit -m "feat: add alert_delivery_service for weekly batch watchlist alerts"
```

---

## Task 4: Inngest Listener for batch/completed

**Files:**
- Create: `inngest/functions/send_watchlist_alerts.py`

Follows the exact pattern of `inngest/functions/send_teaser_digest.py` — pure helpers at top (none needed here), lazy registration, event trigger.

- [ ] **Step 1: Inspect the teaser-digest pattern**

```bash
sed -n '117,199p' /Users/tui/research-swarm/inngest/functions/send_teaser_digest.py
```

Note the `_register_inngest_function()` wrapper and the `try/except` at the end. Match this structure.

- [ ] **Step 2: Create the listener**

Create `inngest/functions/send_watchlist_alerts.py`:

```python
"""
Weekly watchlist alert dispatcher — fires after each weekly batch.

Listens for the `batch/completed` event emitted by `weekly_batch`. Loads the
run's signals, evaluates each for alertable changes (verdict flip, EV shift),
and emails users whose watchlist includes an affected ticker.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _register_inngest_function():
    """Register the Inngest function. Called at module load only when the
    inngest client is importable (i.e. not during unit-test collection)."""
    from inngest.functions.analyze_stock import inngest  # noqa: PLC0415

    @inngest.create_function(
        fn_id="send-watchlist-alerts",
        trigger=inngest.trigger.event(event="batch/completed"),
        name="Send Watchlist Alerts",
        retries=2,
    )
    async def send_watchlist_alerts(ctx: Any, step: Any) -> Dict[str, Any]:
        run_date_str: str = ctx.event.data["run_date"]

        async def deliver() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from api.services.alert_delivery_service import (  # noqa: PLC0415
                deliver_weekly_alerts,
            )

            run_date = datetime.fromisoformat(run_date_str)
            db = await get_db()
            summary = await deliver_weekly_alerts(db=db, run_date=run_date)
            return {"run_date": run_date_str, **summary}

        return await step.run("deliver-weekly-alerts", deliver)

    return send_watchlist_alerts


try:
    send_watchlist_alerts = _register_inngest_function()
except Exception:
    # inngest pip package not available (e.g. during unit tests) — no-op.
    send_watchlist_alerts = None  # type: ignore[assignment]
```

- [ ] **Step 3: Commit**

```bash
git add inngest/functions/send_watchlist_alerts.py
git commit -m "feat: add Inngest listener send_watchlist_alerts for batch/completed"
```

---

## Task 5: Register in Inngest serve()

**Files:**
- Modify: `inngest/index.py`

- [ ] **Step 1: Read the current file**

```bash
cat /Users/tui/research-swarm/inngest/index.py
```

- [ ] **Step 2: Add the import and the function to serve()**

Edit `inngest/index.py`. Add this import alongside the existing ones:

```python
from inngest.functions.send_watchlist_alerts import send_watchlist_alerts
```

Then extend the list passed to `serve(...)`:

```python
serve(
    app,
    inngest,
    [analyze_stock, weekly_batch, send_teaser_digest, send_watchlist_alerts],
    signing_key=os.getenv("INNGEST_SIGNING_KEY")
)
```

- [ ] **Step 3: Verify the Flask app starts cleanly**

```bash
cd /Users/tui/research-swarm
python -c "from inngest.index import app; print('OK:', app.name)"
```

Expected: `OK: inngest.index` (or similar, no traceback).

- [ ] **Step 4: Commit**

```bash
git add inngest/index.py
git commit -m "feat: register send_watchlist_alerts in Inngest serve()"
```

---

## Task 6: End-to-End Smoke Test

Non-code task, verifies the whole pipeline is wired.

- [ ] **Step 1: Seed a qualifying scenario in the DB (one-off script)**

Use a throwaway Python snippet (do not commit). In a psql or Prisma Studio session:

1. Pick a real user with `tier='starter'` (or promote a test user: `UPDATE "users" SET tier='starter' WHERE email='you+test@example.com'`).
2. Ensure they have a `UserPreferences` row with `emailAlerts=true`.
3. Add a Watchlist row with `enableAlerts=true` for ticker `AAPL` (or whichever ticker the latest batch covered).
4. In the `WeeklySignal` row for the most recent `runDate` and that ticker, set `verdict='buy'` and `priorVerdict='hold'` (or similar flip).

- [ ] **Step 2: Trigger the listener via the Inngest dev server**

In one terminal:
```bash
cd /Users/tui/research-swarm
python -m inngest.index  # or however the Flask app is run locally
```

In another:
```bash
npx inngest-cli@latest dev -u http://localhost:8001/api/inngest
```

In the Inngest UI (http://localhost:8288), send a test `batch/completed` event with:
```json
{
  "name": "batch/completed",
  "data": {
    "run_date": "<ISO string of the WeeklySignal runDate you seeded>",
    "ticker_count": 1
  }
}
```

- [ ] **Step 3: Verify the outcome**

Check three things:

1. Inngest UI shows `send-watchlist-alerts` completed successfully with a summary like `{"emails_sent": 1, ...}`.
2. Your inbox received the email with the verdict-flip content.
3. `AlertHistory` has a new row:
   ```bash
   python -c "
   import asyncio
   from prisma import Prisma
   async def main():
       db = Prisma(); await db.connect()
       rows = await db.alerthistory.find_many(take=3, order={'triggeredAt': 'desc'})
       for r in rows:
           print(r.ticker, r.alertType, r.emailSent, r.message)
       await db.disconnect()
   asyncio.run(main())
   "
   ```

- [ ] **Step 4: Run the full test suite to confirm no regressions**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 5: Final commit**

```bash
git commit --allow-empty -m "chore: weekly batch alerts verified end-to-end"
```

---

## Out of Scope (explicit — track for v2)

- **Insider / dark pool spike alerts** — add as new `AlertEvent.kind` values in the evaluator; no schema changes needed.
- **Fair value gap 15% threshold crossing** — `WeeklySignal.fairValueGapPct` is already stored, but prior-week gap is not. Requires schema addition (`priorFairValueGapPct`) before evaluator work.
- **New-to-universe signal** — requires tracking ticker first-seen date.
- **SMS via Twilio** — Trader-tier feature, separate delivery channel.
- **Weekly digest for Starter+ (non-alerting summary)** — `UserPreferences.weeklyDigest` flag exists but `send_weekly_digest` in `email_service.py` is a stub. Build separately.
- **AlertRule threshold honoring for weekly batch** — current design bypasses `AlertRule` for weekly signals (it was designed for per-user moat-score thresholds on manual refresh). If users want to customise thresholds per ticker, extend `AlertRule.alertType` to include `verdict_flip` / `ev_change` and read thresholds in `alert_delivery_service`.
