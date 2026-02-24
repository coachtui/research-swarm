"""
FastAPI entitlement middleware — composable dependency functions.

Three guards, each a FastAPI Depends()-compatible callable:

    load_entitlements
        Resolves the current user's EntitlementContext from billing state.
        Base dependency — all other guards build on top of this.

    require_features(["flag.one", "flag.two"])
        Hard 403 (FEATURE_NOT_ALLOWED) if any flag is missing.
        Use for endpoints that must be entirely denied to lower tiers.

    require_limit("limits.runs.daily")
        Hard 429 (LIMIT_EXCEEDED) if the user's daily counter is at or above
        the tier limit. Atomically increments the counter on success.
        Use for metered endpoints (analysis runs).

Usage example:

    from api.lib.entitlement_middleware import require_features, require_limit

    @router.post("/allocation/size")
    async def size_position(
        ctx: EntitlementContext = Depends(require_features(["allocation.sizing.write"])),
    ):
        ...

    @router.post("/analyze")
    async def analyze(
        ctx: EntitlementContext = Depends(require_limit("limits.runs.daily")),
        user: User = Depends(get_current_user),
    ):
        ...

Security contract:
  - Backend is the sole authority. Frontend flags are cosmetic only.
  - Every denied access attempt is logged with user_id, tier, and missing flag.
  - Admins bypass all feature and limit guards.
"""

import logging
from datetime import datetime, timezone
from typing import List

from fastapi import Depends, HTTPException
from prisma import Prisma

from api.dependencies import get_current_user
from api.lib.db import get_db
from api.lib.entitlement_resolver import EntitlementContext, load_for_request
from api.models.auth import User

logger = logging.getLogger(__name__)


# ── Base dependency ───────────────────────────────────────────────────────────

async def load_entitlements(
    user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db),
) -> EntitlementContext:
    """
    Resolve the current user's entitlements.

    Runs the subscription state machine inline — no extra DB round-trip.
    Attach to any route that needs to inspect flags or limits.
    """
    return await load_for_request(user, db)


# ── Feature gate ──────────────────────────────────────────────────────────────

def require_features(features: List[str]):
    """
    Returns a FastAPI dependency that hard-denies (HTTP 403) if any of the
    listed feature flags are not granted to the current user.

    Structured error body:
        {
            "error": "FEATURE_NOT_ALLOWED",
            "required_feature": "allocation.sizing.write",
            "user_tier": "investor",
            "message": "..."
        }

    Admins bypass all feature checks.
    """
    async def _guard(
        ctx: EntitlementContext = Depends(load_entitlements),
    ) -> EntitlementContext:
        if ctx.is_admin:
            return ctx

        for flag in features:
            if not ctx.flags.get(flag, False):
                logger.warning(
                    "FEATURE_NOT_ALLOWED | user=%s tier=%s flag=%s",
                    ctx.user_id, ctx.tier, flag,
                )
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error":            "FEATURE_NOT_ALLOWED",
                        "required_feature": flag,
                        "user_tier":        ctx.tier,
                        "message": (
                            f"Your {ctx.tier} plan does not include '{flag}'. "
                            f"Upgrade to unlock this feature."
                        ),
                    },
                )
        return ctx

    return _guard


# ── Limit gate ────────────────────────────────────────────────────────────────

def require_limit(limit_key: str):
    """
    Returns a FastAPI dependency that:
      1. Checks the user's current daily counter for `limit_key`.
      2. Raises HTTP 429 (LIMIT_EXCEEDED) if at or above the tier limit.
      3. Atomically increments the counter on success.

    Counter granularity: UTC calendar day (resets at midnight UTC).

    Structured error body:
        {
            "error": "LIMIT_EXCEEDED",
            "limit_key": "limits.runs.daily",
            "limit": 50,
            "current": 50,
            "reset_at": "2026-02-25T00:00:00+00:00",
            "message": "..."
        }

    Admins bypass all limit checks.
    """
    async def _guard(
        ctx: EntitlementContext = Depends(load_entitlements),
        db: Prisma = Depends(get_db),
    ) -> EntitlementContext:
        if ctx.is_admin:
            return ctx

        tier_limit = ctx.limits.get(limit_key, 0)

        # UTC day start (counter key)
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Fetch current counter
        counter = await db.usagecounter.find_unique(
            where={
                "userId_key_periodStart": {
                    "userId":      ctx.user_id,
                    "key":         limit_key,
                    "periodStart": day_start,
                }
            }
        )
        current = counter.count if counter else 0

        if current >= tier_limit:
            next_reset = day_start.replace(
                day=day_start.day + 1
            ) if day_start.day < 28 else datetime(
                day_start.year + (day_start.month // 12),
                (day_start.month % 12) + 1,
                1,
                tzinfo=timezone.utc,
            )
            logger.warning(
                "LIMIT_EXCEEDED | user=%s key=%s current=%d limit=%d",
                ctx.user_id, limit_key, current, tier_limit,
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error":     "LIMIT_EXCEEDED",
                    "limit_key": limit_key,
                    "limit":     tier_limit,
                    "current":   current,
                    "reset_at":  next_reset.isoformat(),
                    "message": (
                        f"Daily limit of {tier_limit} reached for '{limit_key}'. "
                        f"Resets at UTC midnight."
                    ),
                },
            )

        # Atomically increment
        if counter:
            await db.usagecounter.update(
                where={
                    "userId_key_periodStart": {
                        "userId":      ctx.user_id,
                        "key":         limit_key,
                        "periodStart": day_start,
                    }
                },
                data={"count": current + 1},
            )
        else:
            await db.usagecounter.create(
                data={
                    "userId":      ctx.user_id,
                    "key":         limit_key,
                    "periodStart": day_start,
                    "count":       1,
                }
            )

        logger.info(
            "LIMIT_INCREMENTED | user=%s key=%s count=%d/%d",
            ctx.user_id, limit_key, current + 1, tier_limit,
        )
        return ctx

    return _guard
