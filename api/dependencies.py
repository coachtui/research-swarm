"""
FastAPI dependencies for authentication, database, and other shared services.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import os
import requests
from jose import jwt, JWTError
from functools import lru_cache
import logging

from api.models.auth import User

logger = logging.getLogger(__name__)

# HTTP Bearer token security (optional in development)
USE_MOCK_AUTH = os.getenv("USE_MOCK_AUTH", "false").lower() == "true"
security = HTTPBearer(auto_error=not USE_MOCK_AUTH)


@lru_cache(maxsize=1)
def get_clerk_jwks():
    """
    Fetch Clerk's JSON Web Key Set (JWKS) for JWT verification.
    Cached to avoid repeated API calls.
    """
    clerk_domain = os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "").split("_")[2]
    if not clerk_domain:
        raise ValueError("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY not configured")

    # Extract the actual domain from the publishable key
    # Format: pk_test_{domain}$
    # Example: pk_test_Y2hvaWNlLWRpbm9zYXVyLTgzLmNsZXJrLmFjY291bnRzLmRldiQ
    import base64
    try:
        # Decode the base64 part after pk_test_
        encoded_domain = os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "").replace("pk_test_", "").replace("pk_live_", "")
        decoded = base64.b64decode(encoded_domain + "==").decode('utf-8').rstrip('$')
        jwks_url = f"https://{decoded}/.well-known/jwks.json"
    except Exception:
        # Fallback: try to construct from environment
        jwks_url = f"https://choice-dinosaur-83.clerk.accounts.dev/.well-known/jwks.json"

    response = requests.get(jwks_url, timeout=5)
    response.raise_for_status()
    return response.json()

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """
    Get the currently authenticated user from Clerk JWT token.

    Verifies the JWT token with Clerk's public keys and fetches user from database.
    Falls back to mock auth if USE_MOCK_AUTH=true (development only).
    """
    from api.lib.db import get_db

    logger.info(f"🔐 get_current_user called, USE_MOCK_AUTH={USE_MOCK_AUTH}, credentials={'present' if credentials else 'missing'}")

    # Skip auth verification in mock mode (development)
    if USE_MOCK_AUTH:
        # Mock user for development
        user_id = "ec2e1e65-e0eb-4aaf-9b1a-6b2b6cb9a817"

        # Try to ensure user exists in database with connection recovery
        for attempt in range(2):
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
                            "tier": "pro",
                            "monthlyBudgetUsd": 200.0,
                            "isActive": True,
                            "isAdmin": True
                        }
                    )
                break  # Success
            except Exception as e:
                error_str = str(e)
                if "Closed" in error_str and attempt == 0:
                    # Force reconnection on first attempt
                    from api.lib.db import _db_client
                    import api.lib.db as db_module
                    if db_module._db_client:
                        try:
                            await db_module._db_client.disconnect()
                        except:
                            pass
                    db_module._db_client = None
                    continue
                else:
                    logger.warning(f"Could not ensure mock user exists: {e}")

        return User(
            id=user_id,
            clerk_id="user_mock_123",
            email="test@example.com",
            full_name="Test User",
            tier="pro",
            monthly_budget_usd=200.0,
            is_active=True,
            is_admin=True
        )

    # Require credentials in production
    if credentials is None:
        logger.error("❌ No credentials provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    # Verify Clerk JWT token
    token = credentials.credentials
    logger.info(f"🎫 Token received (length: {len(token)})")

    try:
        # Get Clerk's public keys
        logger.info("📡 Fetching Clerk JWKS...")
        jwks = get_clerk_jwks()
        logger.info(f"✅ JWKS fetched successfully ({len(jwks.get('keys', []))} keys)")

        # Decode token header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        key_id = unverified_header.get("kid")

        # Find the matching public key
        public_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == key_id:
                public_key = key
                break

        if not public_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: key not found"
            )

        # Verify and decode the JWT
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False}  # Clerk tokens don't use standard aud claim
        )

        logger.info(f"🔑 JWT Payload: {payload}")  # Debug: see full JWT payload

        clerk_user_id = payload.get("sub")
        if not clerk_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject"
            )

        logger.info(f"✅ JWT verified for Clerk user: {clerk_user_id}")

    except JWTError as e:
        logger.error(f"❌ JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    except Exception as e:
        logger.error(f"❌ Auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

    # Fetch user from database with connection recovery
    # Handle stale connections (Neon closes idle connections)
    max_retries = 2
    user = None

    for attempt in range(max_retries):
        try:
            db = await get_db()
            if not db.is_connected():
                await db.connect()

            user = await db.user.find_unique(where={"clerkId": clerk_user_id})
            break  # Success, exit retry loop

        except Exception as e:
            error_str = str(e)
            # Check for connection closed errors
            if "Closed" in error_str or "connection" in error_str.lower():
                logger.warning(f"⚠️  Database connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    # Force fresh connection
                    from api.lib.db import _db_client
                    import api.lib.db as db_module
                    if db_module._db_client:
                        try:
                            await db_module._db_client.disconnect()
                        except:
                            pass
                    db_module._db_client = None
                    continue
                else:
                    # Last attempt failed
                    logger.error(f"❌ Database connection failed after {max_retries} attempts")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Database connection unavailable"
                    )
            else:
                # Non-connection error, re-raise immediately
                raise

    # Auto-create user if they don't exist (webhook fallback)
    if not user:
        logger.warning(f"⚠️  User {clerk_user_id} not found in database, auto-creating...")

        # Get email from JWT payload - try multiple fields
        # Clerk doesn't include email by default - you need to customize the session token template
        email = (
            payload.get("email") or
            payload.get("email_address") or
            payload.get("primary_email_address") or
            f"user_{clerk_user_id[:8]}@example.com"  # Valid domain for fallback
        )
        logger.info(f"📧 Extracted email from JWT: {email}")
        if email.endswith("@example.com"):
            logger.warning(f"⚠️  Email not in JWT - using fallback. Configure Clerk session token to include email!")

        # Check if this is the admin user
        is_admin = email == "tui@aigaai.com"

        # Create user with retry on connection errors
        for create_attempt in range(2):
            try:
                user = await db.user.create(
                    data={
                        "clerkId": clerk_user_id,
                        "email": email,
                        "fullName": email.split("@")[0],
                        "tier": "pro",  # Default to pro tier (requires subscription to activate)
                        "monthlyBudgetUsd": 200.0,
                        "isActive": True,
                        "isAdmin": is_admin
                    }
                )
                logger.info(f"✅ Auto-created user: {user.email} (admin={is_admin})")
                break
            except Exception as create_err:
                if "Closed" in str(create_err) and create_attempt == 0:
                    # Reconnect and retry
                    from api.lib.db import _db_client
                    import api.lib.db as db_module
                    if db_module._db_client:
                        try:
                            await db_module._db_client.disconnect()
                        except:
                            pass
                    db_module._db_client = None
                    db = await get_db()
                    continue
                else:
                    raise
    else:
        logger.info(f"✅ Found existing user: {user.email} (admin={user.isAdmin})")

    if not user.isActive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Return user model
    return User(
        id=user.id,
        clerk_id=user.clerkId,
        email=user.email,
        full_name=user.fullName,
        tier=user.tier,
        monthly_budget_usd=user.monthlyBudgetUsd,
        is_active=user.isActive,
        is_admin=user.isAdmin
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


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """
    Require that the current user has admin privileges.

    Raises HTTPException 403 if user is not an admin.
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user
