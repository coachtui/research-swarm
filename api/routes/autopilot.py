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
