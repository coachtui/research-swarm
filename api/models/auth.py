"""
Authentication and user models.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum

class UserTier(str, Enum):
    """User subscription tier."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class User(BaseModel):
    """
    User model for authenticated requests.
    """
    id: str = Field(..., description="User UUID")
    clerk_id: str = Field(..., description="Clerk user ID")
    email: EmailStr = Field(..., description="User email address")
    full_name: Optional[str] = Field(None, description="User's full name")

    tier: UserTier = Field(default=UserTier.FREE, description="Subscription tier")
    monthly_budget_usd: float = Field(default=200.0, description="Monthly API budget in USD")

    is_active: bool = Field(default=True, description="Account active status")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "clerk_id": "user_2abc123def456",
                "email": "investor@example.com",
                "full_name": "Jane Investor",
                "tier": "pro",
                "monthly_budget_usd": 200.0,
                "is_active": True,
                "created_at": "2026-01-01T00:00:00Z"
            }
        }

class TokenResponse(BaseModel):
    """
    JWT token response.
    """
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(default=3600, description="Token expiration in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        }

class UserQuota(BaseModel):
    """
    User's current usage and quota information.
    """
    user_id: str
    tier: UserTier

    # Monthly limits
    monthly_budget_usd: float
    monthly_stock_limit: int

    # Current usage (this month)
    current_month_cost_usd: float
    current_month_stocks: int
    current_month_runs: int

    # Remaining quota
    budget_remaining_usd: float
    stocks_remaining: int

    # Rate limits
    runs_per_hour_limit: int
    runs_this_hour: int

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "tier": "pro",
                "monthly_budget_usd": 200.0,
                "monthly_stock_limit": 50,
                "current_month_cost_usd": 45.30,
                "current_month_stocks": 15,
                "current_month_runs": 3,
                "budget_remaining_usd": 154.70,
                "stocks_remaining": 35,
                "runs_per_hour_limit": 10,
                "runs_this_hour": 2
            }
        }
