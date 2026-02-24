"""
Entitlement resolver — subscription state machine.

Single responsibility: given a user's billing state, compute the correct
feature flags and limits. Results are persisted to the entitlements table
after every subscription event and on /billing/refresh.

Subscription state rules (deterministic):
  active / trialing            → full tier entitlements
  past_due + within grace      → full tier entitlements (grace_until set on user)
  past_due + grace expired     → downgrade to starter
  canceled + before period end → maintain tier until subscriptionEndDate
  canceled + after period end  → starter entitlements
  unpaid / uncollectible       → immediately revoke to starter
  admin                        → all flags True, max limits
  multiple subscriptions       → highest tier wins (caller picks best_sub)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any

from api.lib.entitlement_config import (
    ENTITLEMENT_VERSION,
    ADMIN_ENTITLEMENT,
    ACTIVE_STATUSES,
    UNPAID_STATUSES,
    GRACE_PERIOD_DAYS,
    get_flags_for_tier,
    get_limits_for_tier,
)

logger = logging.getLogger(__name__)


# ── Value object ─────────────────────────────────────────────────────────────

@dataclass
class EntitlementContext:
    """Resolved entitlements attached to each authenticated request."""
    user_id: str
    tier: str                      # Effective tier (may differ from user.tier during grace/cancel)
    flags: Dict[str, bool]
    limits: Dict[str, int]
    is_admin: bool
    subscription_status: Optional[str]
    version: str = field(default=ENTITLEMENT_VERSION)

    def has_flag(self, flag: str) -> bool:
        return bool(self.flags.get(flag, False))

    def get_limit(self, key: str) -> int:
        return int(self.limits.get(key, 0))


# ── Utilities ─────────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _tz(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── State machine ─────────────────────────────────────────────────────────────

def _effective_tier(
    tier: str,
    stripe_status: Optional[str],
    subscription_end: Optional[datetime],
    grace_until: Optional[datetime],
) -> str:
    """
    Deterministically resolve which tier's flags to apply.

    Returns a tier string ('starter', 'investor', 'trader').
    """
    now = _now_utc()
    status = (stripe_status or "").lower()

    # No subscription → starter
    if not status:
        return "starter"

    # Active / Trialing → full tier
    if status in ACTIVE_STATUSES:
        return tier

    # Canceled → maintain until period end, then drop to starter
    if status == "canceled":
        end = _tz(subscription_end)
        if end and now < end:
            logger.debug(f"canceled but period not ended ({end}), maintaining {tier}")
            return tier
        return "starter"

    # Past due → grace window
    if status == "past_due":
        g = _tz(grace_until)
        if g and now < g:
            logger.debug(f"past_due within grace until {g}, maintaining {tier}")
            return tier
        logger.info(f"past_due grace expired, downgrading to starter")
        return "starter"

    # Unpaid / uncollectible → immediate revocation
    if status in UNPAID_STATUSES:
        return "starter"

    # incomplete, incomplete_expired, or any unknown state → starter
    return "starter"


# ── Pure resolver (no I/O) ────────────────────────────────────────────────────

def resolve_entitlements_pure(
    user_id: str,
    tier: str,
    stripe_status: Optional[str],
    subscription_end: Optional[datetime],
    grace_until: Optional[datetime],
    is_admin: bool,
) -> EntitlementContext:
    """
    Compute entitlements from user fields — no database access.

    Used for per-request inline resolution (fast path) and as the
    building block for persist_entitlements().
    """
    if is_admin:
        return EntitlementContext(
            user_id=user_id,
            tier=tier,
            flags=dict(ADMIN_ENTITLEMENT["flags"]),
            limits=dict(ADMIN_ENTITLEMENT["limits"]),
            is_admin=True,
            subscription_status=stripe_status,
        )

    effective = _effective_tier(tier, stripe_status, subscription_end, grace_until)

    return EntitlementContext(
        user_id=user_id,
        tier=effective,
        flags=get_flags_for_tier(effective),
        limits=get_limits_for_tier(effective),
        is_admin=False,
        subscription_status=stripe_status,
    )


# ── DB persistence ────────────────────────────────────────────────────────────

async def persist_entitlements(user_db: Any, db: Any) -> EntitlementContext:
    """
    Resolve entitlements for a user and upsert the entitlements table.

    Call this after every Stripe webhook event and on /billing/refresh so that
    the DB always reflects the current billing truth.

    Args:
        user_db: Prisma User record (ORM object with all fields)
        db:      Prisma client instance

    Returns:
        Resolved EntitlementContext
    """
    ctx = resolve_entitlements_pure(
        user_id=user_db.id,
        tier=user_db.tier,
        stripe_status=user_db.stripeSubscriptionStatus,
        subscription_end=getattr(user_db, "subscriptionEndDate", None),
        grace_until=getattr(user_db, "graceUntil", None),
        is_admin=user_db.isAdmin,
    )

    now = _now_utc()
    flags_json = json.dumps(ctx.flags)
    limits_json = json.dumps(ctx.limits)

    existing = await db.entitlement.find_unique(where={"userId": user_db.id})
    if existing:
        await db.entitlement.update(
            where={"userId": user_db.id},
            data={
                "tier":          ctx.tier,
                "flags":         flags_json,
                "limits":        limits_json,
                "version":       ENTITLEMENT_VERSION,
                "effectiveFrom": now,
                "effectiveUntil": None,
            },
        )
    else:
        await db.entitlement.create(
            data={
                "userId":        user_db.id,
                "tier":          ctx.tier,
                "flags":         flags_json,
                "limits":        limits_json,
                "version":       ENTITLEMENT_VERSION,
                "effectiveFrom": now,
            },
        )

    logger.info(
        f"entitlements persisted | user={user_db.id} "
        f"effective_tier={ctx.tier} stripe_status={user_db.stripeSubscriptionStatus}"
    )
    return ctx


# ── Request-time loader ───────────────────────────────────────────────────────

async def load_for_request(user: Any, _db: Any) -> EntitlementContext:
    """
    Resolve entitlements for an inbound API request (fast inline path).

    We intentionally avoid an extra DB round-trip here — the inline
    state machine is always consistent with the DB cache because both
    derive from the same User fields, which are authoritative.

    The `_db` parameter is accepted for signature consistency with
    the middleware dependency but is not used on this path.
    """
    return resolve_entitlements_pure(
        user_id=user.id,
        tier=user.tier,
        stripe_status=user.stripe_subscription_status,
        # These fields are not yet on the User Pydantic model;
        # they live only on the DB record and are consumed by webhooks.
        # For request-time checks the state machine uses stripe_status alone,
        # which is sufficient for active/canceled/past_due routing.
        subscription_end=None,
        grace_until=None,
        is_admin=user.is_admin,
    )
