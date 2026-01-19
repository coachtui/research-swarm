"""Pydantic models for automation layer."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ScheduleFrequency(str, Enum):
    """Supported schedule frequencies."""

    WEEKLY = "weekly"
    BI_WEEKLY = "bi_weekly"
    MONTHLY = "monthly"


class EmailProvider(str, Enum):
    """Supported email providers."""

    SMTP = "smtp"
    SENDGRID = "sendgrid"


class NotificationPriority(str, Enum):
    """Email notification priority levels."""

    NORMAL = "normal"
    HIGH = "high"  # Moat score >= 9
    ALERT = "alert"  # Budget or error alerts


class ScheduleConfig(BaseModel):
    """Configuration for scheduled runs."""

    frequency: ScheduleFrequency = ScheduleFrequency.BI_WEEKLY
    day_of_week: int = Field(default=0, ge=0, le=6)  # 0=Monday, 6=Sunday
    hour: int = Field(default=6, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    tickers_file: Path = Field(default=Path("./data/watchlist.txt"))
    enabled: bool = True
    last_run_week: Optional[int] = None  # ISO week number


class EmailConfig(BaseModel):
    """Configuration for email notifications."""

    provider: EmailProvider = EmailProvider.SMTP
    recipients: List[str] = Field(default_factory=list)

    # SMTP settings
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # SendGrid settings
    sendgrid_api_key: str = ""

    # Sender settings
    from_email: str = "research-swarm@localhost"
    from_name: str = "Research Swarm"


class NotificationConfig(BaseModel):
    """Configuration for notification behavior."""

    send_on_completion: bool = True
    send_on_error: bool = True
    send_high_priority_alerts: bool = True
    attach_pdf_report: bool = True
    high_moat_threshold: float = Field(default=9.0, ge=0, le=10)


class BudgetConfig(BaseModel):
    """Configuration for budget monitoring."""

    monthly_budget_usd: float = Field(default=200.0, gt=0)
    alert_threshold_usd: float = Field(default=180.0, gt=0)
    send_budget_alerts: bool = True


class AutomationConfig(BaseModel):
    """Complete automation configuration."""

    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)

    # Run parameters
    fiscal_year: int = 2024
    news_days_back: int = 30
    max_retries: int = 3

    # Output settings
    reports_dir: Path = Field(default=Path("./reports"))
    logs_archive_dir: Path = Field(default=Path("./data/logs/archive"))


class CostReport(BaseModel):
    """Monthly cost aggregation report."""

    month: str  # YYYY-MM format
    total_cost_usd: float
    run_count: int
    stock_count: int
    cost_by_day: Dict[str, float] = Field(default_factory=dict)
    cost_by_ticker: Dict[str, float] = Field(default_factory=dict)
    within_budget: bool
    budget_remaining_usd: float


class NotificationResult(BaseModel):
    """Result of sending a notification."""

    success: bool
    recipients_sent: List[str] = Field(default_factory=list)
    recipients_failed: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class AutomationResult(BaseModel):
    """Result of an automated run."""

    run_id: str
    success: bool
    tickers_analyzed: int
    completed_count: int
    failed_count: int
    watchlist_candidates: List[str] = Field(default_factory=list)
    high_priority_stocks: List[str] = Field(default_factory=list)
    report_path: Optional[Path] = None
    pdf_path: Optional[Path] = None
    cost_usd: float
    notification_sent: bool
    notification_result: Optional[NotificationResult] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: datetime
    duration_seconds: float


class LaunchdStatus(BaseModel):
    """Status of launchd job."""

    installed: bool
    enabled: bool
    plist_path: Optional[Path] = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    status: str  # running, waiting, not_installed
