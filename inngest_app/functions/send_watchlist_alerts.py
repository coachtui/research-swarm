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
    from inngest_app.client import inngest_client  # noqa: PLC0415

    @inngest_client.create_function(
        fn_id="send-watchlist-alerts",
        trigger=inngest_client.trigger.event(event="batch/completed"),
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
