"""
Inngest Connect worker (replaces the HTTP `serve` mount).

WHY Connect and not `inngest.fast_api.serve`:

Under HTTP serving, Inngest calls this app once per step and the step's whole
duration is one inbound HTTP request. Railway's edge proxy never sees response
headers until the step returns, so it cuts the connection at ~5 minutes and
answers Inngest with plain-text "upstream error". On 2026-08-03 that killed the
sleeve-a-funnel cron twice: the `thesis-memo` step (Sonnet-5, 32k max_tokens,
15 server-side web searches) streamed for 5m17s and 5m03s, past the ceiling
both times, and billed a full paid memo call for each dead attempt.

Connect inverts the direction: the worker holds a persistent outbound WebSocket
to Inngest and step execution is no longer bounded by any inbound HTTP timeout
(the SDK's own graceful-shutdown budget allows executions up to 2 hours).

Deployment shape: the worker runs INSIDE the FastAPI process as a lifespan
background task. That is deliberately like-for-like with what HTTP serving
already did — cron work has always executed in this same uvicorn process — so
this change moves the transport without moving the workload. Splitting the
worker into its own Railway service is a separate (and still open) decision.

Import safety follows the same guarded pattern as inngest_app/client.py: this
module must import cleanly when the pip SDK (or its `connect` extra) is absent,
so Vercel and the py3.9 unit-test env never break on it.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Set once start_worker() runs; read by worker_status() for /api/ready.
_connection: Optional[Any] = None
_task: Optional[asyncio.Task] = None
_last_error: Optional[str] = None
_stopping: bool = False


def resolve_instance_id() -> str:
    """A stable worker identity across restarts.

    The SDK defaults to the machine hostname, which on Railway changes with
    every deploy — that makes the Inngest dashboard's worker list unreadable
    (a new dead entry per deploy). Prefer an explicit id, then the Railway
    service name, and only then fall back to the SDK-ish hostname default.
    """
    explicit = os.getenv("INNGEST_INSTANCE_ID")
    if explicit:
        return explicit
    service = os.getenv("RAILWAY_SERVICE_NAME")
    if service:
        env = os.getenv("RAILWAY_ENVIRONMENT_NAME") or "production"
        return f"{service}-{env}"
    import socket  # noqa: PLC0415

    return socket.gethostname()


def worker_status() -> dict:
    """Connection state for readiness/observability.

    Deliberately explicit about the not-running case: a worker that silently
    never connected means every cron is dead with no other visible symptom
    until a Monday passes with no funnel_summary row.
    """
    if _connection is None:
        return {"running": False, "state": "not_started", "error": _last_error}
    try:
        state = _connection.get_state()
        return {
            "running": True,
            "state": getattr(state, "value", str(state)),
            "error": _last_error,
        }
    except Exception as exc:  # noqa: BLE001 — status must never raise
        return {"running": True, "state": "unknown", "error": str(exc)}


async def _supervise(conn: Any) -> None:
    """Run the connection and make its UNEXPECTED death LOUD.

    `WorkerConnection.start()` blocks until the connection is closed and
    handles its own reconnect backoff, so a return or raise here is terminal:
    the crons are gone until the process restarts. Journal it at critical so it
    surfaces in the same place the engine's other failures do.

    Deliberately silent when `stop_worker()` asked for it — otherwise every
    deploy would write a false "worker is down" row and train the owner to
    ignore the one row that matters.
    """
    global _last_error
    try:
        await conn.start()
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        if _stopping:
            return
        _last_error = f"{type(exc).__name__}: {exc}"
        logger.exception("Inngest Connect worker crashed — crons are NOT running")
        await _journal_worker_down()
        return
    if _stopping:
        return
    _last_error = "worker connection closed unexpectedly"
    logger.error("Inngest Connect worker stopped — crons are NOT running")
    await _journal_worker_down()


async def _journal_worker_down() -> None:
    """Best-effort engine_failure row. Never raises into the supervisor."""
    try:
        from api.lib.db import get_db  # noqa: PLC0415
        from execution.reporting import write_report  # noqa: PLC0415

        db = await get_db()
        await write_report(
            "engine_failure", "critical", "inngest_worker",
            "Inngest Connect worker is down — no cron will run until restart",
            {"error": _last_error, "instance_id": resolve_instance_id()}, db=db,
        )
    except Exception:  # noqa: BLE001
        logger.exception("could not journal Inngest worker outage")


async def start_worker(client: Any, functions: List[Any]) -> Optional[Any]:
    """Open the Connect worker as a background task. Returns the connection.

    Never raises: a broken worker must not take down the API process, because
    this host also serves the dashboard the owner would use to notice.
    """
    global _connection, _task, _last_error, _stopping

    _stopping = False
    if _connection is not None:
        logger.warning("Inngest Connect worker already started — ignoring")
        return _connection

    try:
        from inngest.connect import connect  # noqa: PLC0415 — needs [connect] extra
    except Exception as exc:  # noqa: BLE001
        _last_error = f"connect import failed: {exc}"
        logger.error(
            "Inngest Connect unavailable (%s) — install inngest[connect]. "
            "NO cron will run on this host.", exc,
        )
        await _journal_worker_down()
        return None

    try:
        conn = connect(
            apps=[(client, functions)],
            instance_id=resolve_instance_id(),
            # uvicorn owns SIGTERM/SIGINT. The SDK installs its own handlers by
            # default (connection.py: signal.signal(sig, ...)), which would
            # clobber uvicorn's graceful shutdown; we close the worker from the
            # lifespan shutdown path instead.
            shutdown_signals=[],
        )
    except Exception as exc:  # noqa: BLE001
        _last_error = f"connect() failed: {exc}"
        logger.exception("Inngest Connect worker could not be constructed")
        await _journal_worker_down()
        return None

    _connection = conn
    _task = asyncio.create_task(_supervise(conn))
    logger.info(
        "Inngest Connect worker starting (instance_id=%s, %d function(s))",
        resolve_instance_id(), len(functions),
    )
    return conn


async def stop_worker() -> None:
    """Close the connection on app shutdown. Never raises."""
    global _connection, _task, _stopping

    conn, task = _connection, _task
    _stopping = True
    _connection, _task = None, None
    if conn is None:
        return
    try:
        # wait=False: Railway's SIGTERM grace period is far shorter than the
        # SDK's 2-hour in-flight budget, so waiting would just get us killed
        # mid-wait. Inngest re-drives any step left in flight.
        await conn.close(wait=False)
    except Exception:  # noqa: BLE001
        logger.exception("error closing Inngest Connect worker")
    if task is not None:
        task.cancel()
