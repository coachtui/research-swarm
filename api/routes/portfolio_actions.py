"""
Portfolio action execution and cancellation endpoints.

  POST /actions/{action_id}/execute  — execute an immediate-trigger action
  POST /actions/{action_id}/cancel   — cancel an action and all its children
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_current_user
from api.lib.db import get_db
from api.models.auth import User

router = APIRouter()


@router.post("/actions/{action_id}/execute")
async def execute_action(
    action_id: str,
    user: User = Depends(get_current_user),
):
    """Execute an action. Only allowed when triggerCondition is 'immediate'."""
    db = await get_db()

    action = await db.portfolioaction.find_unique(
        where={"id": action_id},
    )
    if not action or action.userId != user.id:
        raise HTTPException(status_code=404, detail="Action not found")

    if action.triggerCondition != "immediate":
        raise HTTPException(
            status_code=400,
            detail="Action can only be executed when trigger condition is 'immediate'",
        )

    if action.status in ("executed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Action is already {action.status}",
        )

    now = datetime.now(timezone.utc)
    await db.portfolioaction.update(
        where={"id": action_id},
        data={"status": "executed", "updatedAt": now},
    )

    return {"success": True, "action_id": action_id, "status": "executed"}


@router.post("/actions/{action_id}/cancel")
async def cancel_action(
    action_id: str,
    user: User = Depends(get_current_user),
):
    """Cancel an action and all of its children (application-layer cascade)."""
    db = await get_db()

    action = await db.portfolioaction.find_unique(
        where={"id": action_id},
        include={"children": True},
    )
    if not action or action.userId != user.id:
        raise HTTPException(status_code=404, detail="Action not found")

    if action.status == "cancelled":
        raise HTTPException(status_code=400, detail="Action is already cancelled")

    now = datetime.now(timezone.utc)

    # Cancel parent
    await db.portfolioaction.update(
        where={"id": action_id},
        data={"status": "cancelled", "updatedAt": now},
    )

    # Cancel all children (application-layer cascade)
    children = action.children or []
    for child in children:
        await db.portfolioaction.update(
            where={"id": child.id},
            data={"status": "cancelled", "updatedAt": now},
        )

    total_cancelled = 1 + len(children)

    return {
        "success": True,
        "action_id": action_id,
        "cancelled_count": total_cancelled,
    }
