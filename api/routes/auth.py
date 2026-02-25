"""
Authentication endpoints.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
import logging

from api.models.auth import User
from api.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


class UserResponse(BaseModel):
    """Current user information."""
    id: str
    email: str
    full_name: str | None
    tier: str
    is_active: bool
    is_admin: bool


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the currently authenticated user's information.

    This endpoint is used by the frontend to:
    - Check if the user is authenticated
    - Get the user's admin status
    - Redirect admin users to the admin dashboard
    """
    response = UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        tier=current_user.tier,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin
    )
    logger.info("📤 /auth/me returning: user_id=%s is_admin=%s", current_user.id, response.is_admin)
    return response
