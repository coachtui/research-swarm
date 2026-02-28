"""
Health check endpoints for monitoring and status verification.

/api/health  — liveness probe: is the process alive?  (no DB, responds in <1ms)
/api/ready   — readiness probe: is the DB reachable?  (2s timeout, returns 503 if not)

Railway healthcheck should point to /api/health (liveness) to avoid boot-loops
when Neon cold-starts.  Use /api/ready for manual readiness checks or separate
readiness gates.
"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Liveness probe — returns 200 immediately with no DB or external calls.
    Railway healthcheck path must stay pointed here.
    """
    return {"status": "ok"}


@router.get("/ready")
async def readiness_check():
    """
    Readiness probe — checks DB connectivity with a 2s timeout.
    Returns 200 if DB is reachable, 503 if not.
    Do NOT use this as the Railway healthcheck path (will cause boot-loops on
    Neon cold-start before the background connect_db() task completes).
    """
    try:
        from api.lib.db import get_db
        db = await asyncio.wait_for(get_db(), timeout=2.0)
        await asyncio.wait_for(db.execute_raw("SELECT 1"), timeout=2.0)
        return {"status": "ready", "db": "connected", "timestamp": datetime.utcnow().isoformat()}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "reason": "db_timeout"})
    except Exception as e:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "reason": str(e)})
