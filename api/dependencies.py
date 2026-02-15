"""
FastAPI dependencies for authentication, database, and other shared services.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import os

from api.models.auth import User

# HTTP Bearer token security (optional in development)
USE_MOCK_AUTH = os.getenv("USE_MOCK_AUTH", "true").lower() == "true"
security = HTTPBearer(auto_error=not USE_MOCK_AUTH)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """
    Get the currently authenticated user from JWT token.

    For MVP, this returns a mock user when USE_MOCK_AUTH=true.
    In production, this will verify Clerk JWT tokens.

    **Phase 1**: Mock implementation (development)
    **Phase 2**: Full Clerk integration (production)
    """

    # Skip auth verification in mock mode (development)
    if USE_MOCK_AUTH or credentials is None:
        # Mock user for development
        from api.lib.db import get_db

        # Use the actual user ID from database so existing runs are accessible
        user_id = "ec2e1e65-e0eb-4aaf-9b1a-6b2b6cb9a817"

        try:
            db = await get_db()
            if not db.is_connected():
                await db.connect()

            existing_user = await db.user.find_unique(where={"id": user_id})
            if not existing_user:
                await db.user.create(
                    data={
                        "id": user_id,
                        "clerkId": "user_mock_123",
                        "email": "test@example.com",
                        "fullName": "Test User",
                        "tier": "free",
                        "monthlyBudgetUsd": 200.0,
                        "isActive": True
                    }
                )
        except Exception as e:
            print(f"Warning: Could not ensure user exists: {e}")

        return User(
            id=user_id,
            clerk_id="user_mock_123",
            email="test@example.com",
            full_name="Test User",
            tier="free",
            monthly_budget_usd=200.0,
            is_active=True
        )

    # TODO: Implement Clerk JWT verification
    # from jose import JWTError, jwt
    #
    # token = credentials.credentials
    # clerk_secret = os.getenv("CLERK_SECRET_KEY")
    #
    # try:
    #     payload = jwt.decode(token, clerk_secret, algorithms=["RS256"])
    #     clerk_user_id = payload.get("sub")
    # except JWTError:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Invalid authentication token"
    #     )
    #
    # # Query database for user
    # user = await db.user.find_unique(where={"clerk_id": clerk_user_id})
    # if not user or not user.is_active:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="User not found or inactive"
    #     )
    #
    # return User(**user.dict())

    # If we get here, real auth is enabled but not implemented
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Full authentication not yet implemented. Set USE_MOCK_AUTH=true for development."
    )

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    )
) -> Optional[User]:
    """
    Get the current user if authenticated, otherwise None.
    Useful for endpoints that work with or without authentication.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
