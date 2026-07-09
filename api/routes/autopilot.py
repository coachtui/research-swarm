"""
Admin-only endpoints for the autopilot market outlook.

Email delivery is dormant (Resend never configured); the weekly MarketOutlook
row is surfaced in-app instead, admin-only for now, with tier gating to
follow later.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import require_admin
from api.lib.db import get_db
from api.models.auth import User
from execution.outlook_service import get_latest_outlook

router = APIRouter()


# --- Response Models ---

class MarketOutlookResponse(BaseModel):
    """Latest MarketOutlook row, serialized for the admin dashboard."""
    id: str
    run_date: datetime
    regime: str
    regime_mechanical: str
    strategist_override: bool
    strategist_status: str
    conviction: Optional[float]
    sector_rankings: List[dict]
    rotation_flags: List[dict]
    breadth: dict
    reasoning: Optional[str]


# --- Pure helpers (tested directly) ────────────────────────────────────────

def outlook_row_to_response(row) -> MarketOutlookResponse:
    """Map a Prisma MarketOutlook row (camelCase) to MarketOutlookResponse (snake_case)."""
    return MarketOutlookResponse(
        id=row.id,
        run_date=row.runDate,
        regime=row.regime,
        regime_mechanical=row.regimeMechanical,
        strategist_override=row.strategistOverride,
        strategist_status=row.strategistStatus,
        conviction=row.conviction,
        sector_rankings=row.sectorRankings,
        rotation_flags=row.rotationFlags,
        breadth=row.breadth,
        reasoning=row.reasoning,
    )


# --- Endpoints ──────────────────────────────────────────────────────────────

@router.get("/autopilot/outlook", response_model=MarketOutlookResponse)
async def get_outlook(admin: User = Depends(require_admin)):
    """
    Return the most recent MarketOutlook row.

    Admin-only endpoint. Tier gating (flag flip) to follow later.
    """
    db = await get_db()
    row = await get_latest_outlook(db)
    if row is None:
        raise HTTPException(status_code=404, detail="No outlook available yet")

    return outlook_row_to_response(row)


# ── Phase 2: broker linking + sleeve control ────────────────────────────────

import asyncio

from execution.broker.credentials import get_active_alpaca_account, upsert_alpaca_account
from execution.sleeve_service import get_sleeve_state, set_sleeve_status


def _alpaca_client_factory(api_key: str, api_secret: str):
    """Indirection so tests can patch client construction (alpaca-py is a
    runtime-only dep, not installed in the unit-test env)."""
    from execution.broker.alpaca_client import AlpacaPaperClient

    return AlpacaPaperClient(api_key, api_secret)


class BrokerLinkRequest(BaseModel):
    api_key: str
    api_secret: str


class BrokerLinkResponse(BaseModel):
    status: str
    account_equity: float


@router.post("/autopilot/broker/link", response_model=BrokerLinkResponse)
async def link_broker(body: BrokerLinkRequest, admin: User = Depends(require_admin)):
    """Validate Alpaca paper keys against the live API, then store them
    encrypted (Fernet). Bad keys are rejected before anything is stored."""
    try:
        client = _alpaca_client_factory(body.api_key, body.api_secret)
        summary = await asyncio.to_thread(client.get_account_summary)
    except Exception:
        raise HTTPException(status_code=400, detail="Alpaca rejected these keys")

    db = await get_db()
    await upsert_alpaca_account(db, admin.id, body.api_key, body.api_secret)
    return BrokerLinkResponse(status="linked", account_equity=summary["equity"])


@router.get("/autopilot/broker/status")
async def broker_status(admin: User = Depends(require_admin)):
    """Linked-account + sleeve health overview (admin dashboard / curl)."""
    db = await get_db()
    account = await get_active_alpaca_account(db)
    if account is None:
        return {"linked": False, "sleeves": [], "latest_snapshot": None}

    sleeves = []
    for sleeve in ("A", "B"):
        state = await get_sleeve_state(db, sleeve)
        if state is not None:
            sleeves.append({
                "sleeve": sleeve,
                "status": state.status,
                "status_reason": state.statusReason,
                "cash_balance": state.cashBalance,
            })
    latest = await db.sleevesnapshot.find_first(order={"snapshotDate": "desc"})
    snapshot = None
    if latest is not None:
        snapshot = {
            "date": latest.snapshotDate.isoformat(),
            "sleeve": latest.sleeve,
            "equity": latest.equity,
            "spy_close": latest.spyClose,
        }
    return {
        "linked": True,
        "provider": account.provider,
        "mode": account.mode,
        "sleeves": sleeves,
        "latest_snapshot": snapshot,
    }


@router.post("/autopilot/sleeve/{sleeve}/resume")
async def resume_sleeve(sleeve: str, admin: User = Depends(require_admin)):
    """Manual reset after a circuit-breaker halt or reconciliation freeze —
    the engine never un-halts itself (spec requirement)."""
    if sleeve not in ("A", "B"):
        raise HTTPException(status_code=404, detail="Unknown sleeve")
    db = await get_db()
    state = await get_sleeve_state(db, sleeve)
    if state is None:
        raise HTTPException(status_code=404, detail="Sleeve not initialized")
    await set_sleeve_status(db, sleeve, "active", reason=None)
    return {"sleeve": sleeve, "status": "active"}
