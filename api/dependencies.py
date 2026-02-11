"""
FastAPI dependencies for authentication, database, and other shared services.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import os

from api.models.auth import User

# HTTP Bearer token security
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Get the currently authenticated user from JWT token.

    For MVP, this returns a mock user. In production, this will:
    1. Verify Clerk JWT token
    2. Extract user_id from token
    3. Query database for user record
    4. Return User model

    **Phase 1**: Mock implementation
    **Phase 2**: Full Clerk integration
    """

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

    # Mock user for MVP testing
    return User(
        id="550e8400-e29b-41d4-a716-446655440000",
        clerk_id="user_mock_123",
        email="test@example.com",
        full_name="Test User",
        tier="free",
        monthly_budget_usd=200.0,
        is_active=True
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

# Database session dependency (Prisma)
# async def get_db():
#     """
#     Get database session.
#     TODO: Implement Prisma client initialization
#     """
#     from api.lib.db import prisma
#     await prisma.connect()
#     try:
#         yield prisma
#     finally:
#         await prisma.disconnect()

# Inngest client dependency
# async def get_inngest_client():
#     """
#     Get Inngest client for triggering background jobs.
#     TODO: Implement Inngest client initialization
#     """
#     from api.lib.inngest import inngest_client
#     return inngest_client

# R2 storage client dependency
# async def get_storage_client():
#     """
#     Get R2 (S3-compatible) storage client.
#     TODO: Implement R2 client initialization
#     """
#     from api.lib.storage import storage_client
#     return storage_client
