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
        where={"runDate": run_date, "tier": "full"},
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
