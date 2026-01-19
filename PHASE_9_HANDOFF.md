# Phase 9 Handoff: Scheduling & Automation

**From**: CTO Architect Agent
**To**: Builder Agent
**Date**: 2026-01-17
**Status**: Ready for Implementation

---

## Mission

Build an automation layer that enables unattended bi-weekly research runs with email notifications, cost monitoring, and macOS launchd scheduling.

**No LLM calls required** - this is pure infrastructure. Cost = $0.

---

## What You're Building

```
research_swarm/automation/
├── __init__.py              # Public API exports
├── models.py                # Pydantic models
├── scheduler.py             # Launchd plist generation & management
├── notifier.py              # SMTP + SendGrid email abstraction
├── cost_monitor.py          # Monthly cost aggregation
├── runner.py                # Main AutomationRunner orchestrator
└── templates/
    └── email_report.html.j2 # Email HTML template
```

---

## Dependencies to Install

**Python packages** (add to requirements.txt):
```
sendgrid>=6.9.0
```

Note: SMTP uses Python's built-in `smtplib` - no additional dependency needed.

---

## Implementation Guide

### Step 1: Models (`models.py`)

Create these Pydantic models:

```python
"""Pydantic models for automation layer."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, EmailStr


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
    HIGH = "high"       # Moat score >= 9
    ALERT = "alert"     # Budget or error alerts


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
```

---

### Step 2: Update Config (`config.py`)

Add to the `Settings` class:

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Phase 9: Automation & Scheduling
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    sendgrid_api_key: str = ""

    notification_recipients: str = ""  # Comma-separated emails
    notification_from_email: str = "research-swarm@localhost"

    monthly_budget_usd: float = 200.0
    budget_alert_threshold_usd: float = 180.0
```

---

### Step 3: Cost Monitor (`cost_monitor.py`)

```python
"""Cost monitoring from existing cost_log table."""

from datetime import datetime
from typing import Optional

from research_swarm.automation.models import BudgetConfig, CostReport
from research_swarm.orchestration import PersistenceManager


class CostMonitor:
    """Monitors API costs from existing cost_log table."""

    def __init__(
        self,
        persistence: Optional[PersistenceManager] = None,
        budget_config: Optional[BudgetConfig] = None,
    ):
        self.persistence = persistence or PersistenceManager()
        self.budget_config = budget_config or BudgetConfig()

    def get_monthly_cost(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> CostReport:
        """Aggregate costs for a specific month from cost_log table."""
        now = datetime.now()
        year = year or now.year
        month = month or now.month

        data = self.persistence.get_monthly_costs(year, month)

        total = data.get("total_cost", 0.0)
        budget = self.budget_config.monthly_budget_usd

        return CostReport(
            month=f"{year:04d}-{month:02d}",
            total_cost_usd=total,
            run_count=data.get("run_count", 0),
            stock_count=data.get("stock_count", 0),
            cost_by_day=data.get("cost_by_day", {}),
            cost_by_ticker=data.get("cost_by_ticker", {}),
            within_budget=total <= budget,
            budget_remaining_usd=max(0, budget - total),
        )

    def get_current_month_cost(self) -> CostReport:
        """Get cost report for current month."""
        return self.get_monthly_cost()

    def should_alert(self) -> bool:
        """Check if budget alert should be sent."""
        if not self.budget_config.send_budget_alerts:
            return False

        report = self.get_current_month_cost()
        return report.total_cost_usd >= self.budget_config.alert_threshold_usd

    def get_cost_trend(self, months: int = 3) -> list[CostReport]:
        """Get cost trend over multiple months."""
        reports = []
        now = datetime.now()

        for i in range(months):
            year = now.year
            month = now.month - i

            if month <= 0:
                month += 12
                year -= 1

            reports.append(self.get_monthly_cost(year, month))

        return reports
```

**Add to `persistence.py`** (new method):

```python
def get_monthly_costs(self, year: int, month: int) -> dict:
    """Aggregate costs for a specific month.

    Returns:
        Dictionary with total_cost, run_count, stock_count,
        cost_by_day, cost_by_ticker
    """
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row

        # Date range for the month
        start_date = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1:04d}-01-01"
        else:
            end_date = f"{year:04d}-{month + 1:02d}-01"

        # Aggregate from cost_log table
        cursor = conn.execute(
            """
            SELECT
                SUM(cost_usd) as total_cost,
                COUNT(DISTINCT run_id) as run_count,
                COUNT(*) as entry_count
            FROM cost_log
            WHERE timestamp >= ? AND timestamp < ?
            """,
            (start_date, end_date),
        )

        row = cursor.fetchone()
        total_cost = row["total_cost"] or 0.0
        run_count = row["run_count"] or 0

        # Cost by day
        cursor = conn.execute(
            """
            SELECT DATE(timestamp) as date, SUM(cost_usd) as cost
            FROM cost_log
            WHERE timestamp >= ? AND timestamp < ?
            GROUP BY DATE(timestamp)
            """,
            (start_date, end_date),
        )
        cost_by_day = {row["date"]: row["cost"] for row in cursor.fetchall()}

        # Cost by ticker
        cursor = conn.execute(
            """
            SELECT ticker, SUM(cost_usd) as cost
            FROM cost_log
            WHERE timestamp >= ? AND timestamp < ?
            GROUP BY ticker
            """,
            (start_date, end_date),
        )
        cost_by_ticker = {row["ticker"]: row["cost"] for row in cursor.fetchall()}

        # Stock count
        cursor = conn.execute(
            """
            SELECT COUNT(DISTINCT ticker) as stock_count
            FROM cost_log
            WHERE timestamp >= ? AND timestamp < ?
            """,
            (start_date, end_date),
        )
        stock_count = cursor.fetchone()["stock_count"] or 0

        return {
            "total_cost": total_cost,
            "run_count": run_count,
            "stock_count": stock_count,
            "cost_by_day": cost_by_day,
            "cost_by_ticker": cost_by_ticker,
        }
```

---

### Step 4: Notifier (`notifier.py`)

```python
"""Email notification system with SMTP and SendGrid support."""

import smtplib
from abc import ABC, abstractmethod
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, PackageLoader

from research_swarm.automation.models import (
    AutomationResult,
    EmailConfig,
    EmailProvider,
    NotificationConfig,
    NotificationResult,
    CostReport,
)
from research_swarm.logger import logger


class EmailSender(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    def send(
        self,
        to: List[str],
        subject: str,
        body_html: str,
        body_text: str,
        attachments: Optional[List[Path]] = None,
    ) -> NotificationResult:
        """Send an email."""
        pass


class SMTPSender(EmailSender):
    """SMTP email sender."""

    def __init__(self, config: EmailConfig):
        self.config = config

    def send(
        self,
        to: List[str],
        subject: str,
        body_html: str,
        body_text: str,
        attachments: Optional[List[Path]] = None,
    ) -> NotificationResult:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
            msg["To"] = ", ".join(to)

            msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))

            # Add attachments
            if attachments:
                for file_path in attachments:
                    if file_path.exists():
                        with open(file_path, "rb") as f:
                            part = MIMEApplication(f.read(), Name=file_path.name)
                            part["Content-Disposition"] = f'attachment; filename="{file_path.name}"'
                            msg.attach(part)

            # Send via SMTP
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.smtp_use_tls:
                    server.starttls()
                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(self.config.from_email, to, msg.as_string())

            return NotificationResult(success=True, recipients_sent=to)

        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            return NotificationResult(
                success=False,
                recipients_failed=to,
                error_message=str(e),
            )


class SendGridSender(EmailSender):
    """SendGrid email sender."""

    def __init__(self, config: EmailConfig):
        self.config = config

    def send(
        self,
        to: List[str],
        subject: str,
        body_html: str,
        body_text: str,
        attachments: Optional[List[Path]] = None,
    ) -> NotificationResult:
        try:
            import sendgrid
            from sendgrid.helpers.mail import (
                Attachment,
                Content,
                Email,
                FileContent,
                FileName,
                FileType,
                Mail,
                To,
            )
            import base64

            sg = sendgrid.SendGridAPIClient(api_key=self.config.sendgrid_api_key)

            message = Mail(
                from_email=Email(self.config.from_email, self.config.from_name),
                to_emails=[To(email) for email in to],
                subject=subject,
            )
            message.add_content(Content("text/plain", body_text))
            message.add_content(Content("text/html", body_html))

            # Add attachments
            if attachments:
                for file_path in attachments:
                    if file_path.exists():
                        with open(file_path, "rb") as f:
                            data = base64.b64encode(f.read()).decode()

                        attachment = Attachment()
                        attachment.file_content = FileContent(data)
                        attachment.file_name = FileName(file_path.name)
                        attachment.file_type = FileType("application/pdf")
                        message.add_attachment(attachment)

            response = sg.send(message)

            if response.status_code in (200, 201, 202):
                return NotificationResult(success=True, recipients_sent=to)
            else:
                return NotificationResult(
                    success=False,
                    recipients_failed=to,
                    error_message=f"SendGrid returned {response.status_code}",
                )

        except Exception as e:
            logger.error(f"SendGrid send failed: {e}")
            return NotificationResult(
                success=False,
                recipients_failed=to,
                error_message=str(e),
            )


class Notifier:
    """Email notification manager."""

    def __init__(
        self,
        email_config: EmailConfig,
        notification_config: NotificationConfig,
    ):
        self.email_config = email_config
        self.notification_config = notification_config
        self.sender = self._create_sender()
        self.templates = Environment(
            loader=PackageLoader("research_swarm.automation", "templates"),
            autoescape=True,
        )

    def _create_sender(self) -> EmailSender:
        """Factory method to create appropriate email sender."""
        if self.email_config.provider == EmailProvider.SENDGRID:
            return SendGridSender(self.email_config)
        return SMTPSender(self.email_config)

    def send_run_completion(
        self,
        result: AutomationResult,
        pdf_path: Optional[Path] = None,
    ) -> NotificationResult:
        """Send run completion notification with optional PDF attachment."""
        if not self.notification_config.send_on_completion:
            return NotificationResult(success=True, recipients_sent=[])

        template = self.templates.get_template("email_report.html.j2")
        body_html = template.render(result=result)

        body_text = f"""
Research Swarm Analysis Complete

Run ID: {result.run_id}
Stocks Analyzed: {result.tickers_analyzed}
Completed: {result.completed_count}
Failed: {result.failed_count}
Cost: ${result.cost_usd:.2f}

Watchlist Candidates: {', '.join(result.watchlist_candidates) or 'None'}
High Priority (>=9): {', '.join(result.high_priority_stocks) or 'None'}
        """.strip()

        subject = f"[Research Swarm] Analysis Complete - {result.completed_count}/{result.tickers_analyzed} stocks"

        if result.high_priority_stocks:
            subject = f"[HIGH PRIORITY] {subject}"

        attachments = []
        if pdf_path and pdf_path.exists() and self.notification_config.attach_pdf_report:
            attachments.append(pdf_path)

        return self.sender.send(
            to=self.email_config.recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            attachments=attachments,
        )

    def send_error_notification(
        self,
        error_message: str,
        run_id: Optional[str] = None,
    ) -> NotificationResult:
        """Send error notification."""
        if not self.notification_config.send_on_error:
            return NotificationResult(success=True, recipients_sent=[])

        subject = f"[Research Swarm ERROR] Run failed"
        if run_id:
            subject += f" - {run_id}"

        body_text = f"""
Research Swarm encountered an error.

Run ID: {run_id or 'N/A'}
Error: {error_message}

Please check the logs for more details.
        """.strip()

        body_html = f"<h2>Research Swarm Error</h2><p><strong>Error:</strong> {error_message}</p>"

        return self.sender.send(
            to=self.email_config.recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )

    def send_budget_alert(self, cost_report: CostReport) -> NotificationResult:
        """Send budget warning notification."""
        subject = f"[Research Swarm ALERT] Budget threshold exceeded - ${cost_report.total_cost_usd:.2f}"

        body_text = f"""
Budget Alert!

Month: {cost_report.month}
Current Spend: ${cost_report.total_cost_usd:.2f}
Budget Remaining: ${cost_report.budget_remaining_usd:.2f}

Consider reducing analysis frequency or stock count.
        """.strip()

        body_html = f"""
<h2>Budget Alert</h2>
<p><strong>Month:</strong> {cost_report.month}</p>
<p><strong>Current Spend:</strong> ${cost_report.total_cost_usd:.2f}</p>
<p><strong>Budget Remaining:</strong> ${cost_report.budget_remaining_usd:.2f}</p>
        """

        return self.sender.send(
            to=self.email_config.recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )

    def send_test(self) -> NotificationResult:
        """Send a test notification."""
        return self.sender.send(
            to=self.email_config.recipients,
            subject="[Research Swarm] Test Notification",
            body_html="<h2>Test Email</h2><p>This is a test email from Research Swarm.</p>",
            body_text="Test email from Research Swarm.",
        )
```

---

### Step 5: Email Template (`templates/email_report.html.j2`)

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background: #4361ee; color: white; padding: 20px; }
        .content { padding: 20px; }
        .summary { background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0; }
        .metric { display: inline-block; margin-right: 30px; }
        .metric-value { font-size: 24px; font-weight: bold; color: #4361ee; }
        .metric-label { font-size: 12px; color: #666; }
        .watchlist { margin: 20px 0; }
        .stock { padding: 10px; border-left: 4px solid #4361ee; margin: 10px 0; background: #f9f9f9; }
        .stock.high-priority { border-left-color: #e74c3c; background: #fff5f5; }
        .footer { font-size: 12px; color: #666; padding: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Research Swarm Analysis Report</h1>
    </div>

    <div class="content">
        <div class="summary">
            <div class="metric">
                <div class="metric-value">{{ result.completed_count }}/{{ result.tickers_analyzed }}</div>
                <div class="metric-label">Stocks Analyzed</div>
            </div>
            <div class="metric">
                <div class="metric-value">${{ "%.2f"|format(result.cost_usd) }}</div>
                <div class="metric-label">Cost</div>
            </div>
            <div class="metric">
                <div class="metric-value">{{ result.duration_seconds|int }}s</div>
                <div class="metric-label">Duration</div>
            </div>
        </div>

        {% if result.high_priority_stocks %}
        <div class="watchlist">
            <h2>High Priority Stocks (Moat >= 9)</h2>
            {% for ticker in result.high_priority_stocks %}
            <div class="stock high-priority">
                <strong>{{ ticker }}</strong>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if result.watchlist_candidates %}
        <div class="watchlist">
            <h2>Watchlist Candidates</h2>
            {% for ticker in result.watchlist_candidates %}
            <div class="stock">
                <strong>{{ ticker }}</strong>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <p>Run ID: {{ result.run_id }}</p>
        {% if result.pdf_path %}
        <p>Full report attached as PDF.</p>
        {% endif %}
    </div>

    <div class="footer">
        <p>Generated by Research Swarm | {{ result.completed_at.strftime('%Y-%m-%d %H:%M:%S') }}</p>
    </div>
</body>
</html>
```

---

### Step 6: Scheduler (`scheduler.py`)

```python
"""macOS launchd scheduler for automated runs."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
import sys

from research_swarm.automation.models import LaunchdStatus, ScheduleConfig, ScheduleFrequency
from research_swarm.logger import logger


class LaunchdScheduler:
    """Manages macOS launchd plist for scheduling."""

    PLIST_NAME = "com.research-swarm.automation"
    PLIST_DIR = Path.home() / "Library" / "LaunchAgents"

    def __init__(self, config: ScheduleConfig):
        self.config = config
        self.plist_path = self.PLIST_DIR / f"{self.PLIST_NAME}.plist"
        self.state_file = Path("./data/state/scheduler_state.json")

    def generate_plist(self) -> str:
        """Generate launchd plist XML content."""
        # Get paths
        python_path = sys.executable
        working_dir = Path.cwd()
        tickers_file = self.config.tickers_file.absolute()
        log_dir = working_dir / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Map day_of_week (0=Mon) to launchd weekday (1=Mon, 7=Sun)
        launchd_weekday = self.config.day_of_week + 1
        if launchd_weekday == 7:
            launchd_weekday = 0  # Sunday in launchd is 0

        plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{self.PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>-m</string>
        <string>research_swarm</string>
        <string>auto</string>
        <string>--tickers-file</string>
        <string>{tickers_file}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{working_dir}</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>{launchd_weekday}</integer>
        <key>Hour</key>
        <integer>{self.config.hour}</integer>
        <key>Minute</key>
        <integer>{self.config.minute}</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>{log_dir}/launchd_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>{log_dir}/launchd_stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:{Path(python_path).parent}</string>
    </dict>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>'''
        return plist

    def install(self) -> bool:
        """Install and load the launchd job."""
        try:
            # Ensure directory exists
            self.PLIST_DIR.mkdir(parents=True, exist_ok=True)

            # Unload if already loaded
            if self.plist_path.exists():
                subprocess.run(
                    ["launchctl", "unload", str(self.plist_path)],
                    capture_output=True,
                )

            # Write plist
            plist_content = self.generate_plist()
            self.plist_path.write_text(plist_content)

            # Load job
            result = subprocess.run(
                ["launchctl", "load", str(self.plist_path)],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.error(f"Failed to load launchd job: {result.stderr}")
                return False

            # Initialize state
            self._init_state()

            logger.info(f"Installed launchd job: {self.plist_path}")
            return True

        except Exception as e:
            logger.error(f"Install failed: {e}")
            return False

    def uninstall(self) -> bool:
        """Unload and remove the launchd job."""
        try:
            if self.plist_path.exists():
                subprocess.run(
                    ["launchctl", "unload", str(self.plist_path)],
                    capture_output=True,
                )
                self.plist_path.unlink()
                logger.info("Uninstalled launchd job")

            return True

        except Exception as e:
            logger.error(f"Uninstall failed: {e}")
            return False

    def get_status(self) -> LaunchdStatus:
        """Get current status of the scheduled job."""
        installed = self.plist_path.exists()

        if not installed:
            return LaunchdStatus(
                installed=False,
                enabled=False,
                status="not_installed",
            )

        # Check if loaded
        result = subprocess.run(
            ["launchctl", "list", self.PLIST_NAME],
            capture_output=True,
            text=True,
        )

        enabled = result.returncode == 0

        # Get last run from state
        state = self._load_state()
        last_run = None
        if state.get("last_run_timestamp"):
            last_run = datetime.fromisoformat(state["last_run_timestamp"])

        return LaunchdStatus(
            installed=True,
            enabled=enabled,
            plist_path=self.plist_path,
            last_run=last_run,
            status="waiting" if enabled else "disabled",
        )

    def should_run_today(self) -> bool:
        """Check if bi-weekly run should execute today.

        Since launchd doesn't support "every other week", we run weekly
        and check state to skip alternate weeks.
        """
        if self.config.frequency != ScheduleFrequency.BI_WEEKLY:
            return True  # Weekly/monthly always run

        state = self._load_state()

        if state.get("last_run_iso_week") is None:
            # First run - always execute
            return True

        now = datetime.now()
        current_week = now.isocalendar()[1]
        current_year = now.year

        last_week = state["last_run_iso_week"]
        last_year = state.get("last_run_year", current_year)

        # Handle year boundary
        if current_year != last_year:
            weeks_elapsed = (52 - last_week) + current_week
        else:
            weeks_elapsed = current_week - last_week

        return weeks_elapsed >= 2

    def update_last_run(self) -> None:
        """Update state file with current run info."""
        now = datetime.now()
        state = self._load_state()

        state["last_run_iso_week"] = now.isocalendar()[1]
        state["last_run_year"] = now.year
        state["last_run_timestamp"] = now.isoformat()
        state["run_count"] = state.get("run_count", 0) + 1

        self._save_state(state)

    def _init_state(self) -> None:
        """Initialize state file."""
        if not self.state_file.exists():
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_state({
                "frequency": self.config.frequency.value,
                "initial_week": datetime.now().isocalendar()[1],
                "run_count": 0,
            })

    def _load_state(self) -> dict:
        """Load state from file."""
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {}

    def _save_state(self, state: dict) -> None:
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2))
```

---

### Step 7: Runner (`runner.py`)

```python
"""Main automation runner that orchestrates run → report → notify."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from research_swarm.automation.models import (
    AutomationConfig,
    AutomationResult,
    NotificationResult,
)
from research_swarm.automation.scheduler import LaunchdScheduler
from research_swarm.automation.notifier import Notifier
from research_swarm.automation.cost_monitor import CostMonitor
from research_swarm.orchestration import PersistenceManager, run_batch
from research_swarm.reports import generate_report
from research_swarm.logger import logger


class AutomationRunner:
    """Main orchestrator for automated runs."""

    def __init__(self, config: Optional[AutomationConfig] = None):
        self.config = config or AutomationConfig()
        self.persistence = PersistenceManager()
        self.notifier = Notifier(self.config.email, self.config.notification)
        self.cost_monitor = CostMonitor(self.persistence, self.config.budget)
        self.scheduler = LaunchdScheduler(self.config.schedule)

    def run(self, tickers: Optional[List[str]] = None) -> AutomationResult:
        """Execute full automation workflow: run → report → notify."""
        started_at = datetime.now()
        run_id = None

        try:
            # Check bi-weekly schedule
            if not self.scheduler.should_run_today():
                logger.info("Skipping run - bi-weekly schedule not due")
                return AutomationResult(
                    run_id="skipped",
                    success=True,
                    tickers_analyzed=0,
                    completed_count=0,
                    failed_count=0,
                    cost_usd=0.0,
                    notification_sent=False,
                    started_at=started_at,
                    completed_at=datetime.now(),
                    duration_seconds=0.0,
                )

            # Load tickers
            if tickers is None:
                tickers = self._load_tickers()

            if not tickers:
                raise ValueError("No tickers to analyze")

            logger.info(f"Starting automated run for {len(tickers)} stocks")

            # Run batch analysis
            swarm_run = run_batch(
                tickers=tickers,
                fiscal_year=self.config.fiscal_year,
                news_days_back=self.config.news_days_back,
                max_retries=self.config.max_retries,
                run_name=f"auto_{datetime.now().strftime('%Y%m%d_%H%M')}",
            )

            run_id = swarm_run.run_id

            # Generate report
            pdf_path = None
            report_path = None

            if swarm_run.completed_count > 0:
                report_result = generate_report(
                    run_id=run_id,
                    output_dir=str(self.config.reports_dir),
                    report_type="both",
                    include_charts=True,
                )

                if report_result.success:
                    report_path = report_result.markdown_path
                    pdf_path = report_result.pdf_path

            # Identify high-priority stocks
            high_priority = [
                ticker for ticker, result in swarm_run.stock_results.items()
                if result.moat_score and result.moat_score >= self.config.notification.high_moat_threshold
            ]

            watchlist = [r.ticker for r in swarm_run.watchlist_candidates]

            completed_at = datetime.now()

            result = AutomationResult(
                run_id=run_id,
                success=True,
                tickers_analyzed=len(tickers),
                completed_count=swarm_run.completed_count,
                failed_count=swarm_run.failed_count,
                watchlist_candidates=watchlist,
                high_priority_stocks=high_priority,
                report_path=report_path,
                pdf_path=pdf_path,
                cost_usd=swarm_run.cost_summary.total_cost_usd,
                notification_sent=False,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds(),
            )

            # Send notifications
            notification_result = self._send_notifications(result, pdf_path)
            result.notification_sent = notification_result.success
            result.notification_result = notification_result

            # Check budget alerts
            self._check_and_alert_budget()

            # Update scheduler state
            self.scheduler.update_last_run()

            logger.success(f"Automation complete: {result.completed_count}/{result.tickers_analyzed}")
            return result

        except Exception as e:
            logger.error(f"Automation failed: {e}")

            # Send error notification
            self.notifier.send_error_notification(str(e), run_id)

            return AutomationResult(
                run_id=run_id or "failed",
                success=False,
                tickers_analyzed=len(tickers) if tickers else 0,
                completed_count=0,
                failed_count=len(tickers) if tickers else 0,
                cost_usd=0.0,
                notification_sent=True,
                error_message=str(e),
                started_at=started_at,
                completed_at=datetime.now(),
                duration_seconds=(datetime.now() - started_at).total_seconds(),
            )

    def _load_tickers(self) -> List[str]:
        """Load tickers from configured file."""
        file_path = self.config.schedule.tickers_file

        if not file_path.exists():
            raise FileNotFoundError(f"Tickers file not found: {file_path}")

        with open(file_path) as f:
            tickers = [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]

        return tickers

    def _send_notifications(
        self,
        result: AutomationResult,
        pdf_path: Optional[Path] = None,
    ) -> NotificationResult:
        """Send all applicable notifications."""
        return self.notifier.send_run_completion(result, pdf_path)

    def _check_and_alert_budget(self) -> None:
        """Check budget and send alert if needed."""
        if self.cost_monitor.should_alert():
            report = self.cost_monitor.get_current_month_cost()
            self.notifier.send_budget_alert(report)
            logger.warning(f"Budget alert sent: ${report.total_cost_usd:.2f} / ${self.config.budget.monthly_budget_usd:.2f}")


def run_automation(
    tickers: Optional[List[str]] = None,
    config: Optional[AutomationConfig] = None,
) -> AutomationResult:
    """Convenience function to run automation."""
    runner = AutomationRunner(config)
    return runner.run(tickers)
```

---

### Step 8: Public API (`__init__.py`)

```python
"""Automation module for scheduling and notifications."""

from research_swarm.automation.models import (
    AutomationConfig,
    AutomationResult,
    BudgetConfig,
    CostReport,
    EmailConfig,
    EmailProvider,
    LaunchdStatus,
    NotificationConfig,
    NotificationPriority,
    NotificationResult,
    ScheduleConfig,
    ScheduleFrequency,
)
from research_swarm.automation.scheduler import LaunchdScheduler
from research_swarm.automation.notifier import Notifier, SMTPSender, SendGridSender
from research_swarm.automation.cost_monitor import CostMonitor
from research_swarm.automation.runner import AutomationRunner, run_automation

__all__ = [
    # Models
    "AutomationConfig",
    "AutomationResult",
    "BudgetConfig",
    "CostReport",
    "EmailConfig",
    "EmailProvider",
    "LaunchdStatus",
    "NotificationConfig",
    "NotificationPriority",
    "NotificationResult",
    "ScheduleConfig",
    "ScheduleFrequency",
    # Scheduler
    "LaunchdScheduler",
    # Notifier
    "Notifier",
    "SMTPSender",
    "SendGridSender",
    # Cost Monitor
    "CostMonitor",
    # Runner
    "AutomationRunner",
    "run_automation",
]
```

---

### Step 9: CLI Integration (`__main__.py`)

Add these imports at the top:

```python
from research_swarm.automation import (
    AutomationConfig,
    CostMonitor,
    EmailConfig,
    LaunchdScheduler,
    Notifier,
    NotificationConfig,
    ScheduleConfig,
    ScheduleFrequency,
    run_automation,
)
```

Add these command handlers:

```python
def cmd_schedule_install(args):
    """Install the launchd scheduled job."""
    config = ScheduleConfig(
        frequency=ScheduleFrequency(args.frequency),
        day_of_week=args.day,
        hour=args.hour,
        tickers_file=Path(args.tickers_file),
    )
    scheduler = LaunchdScheduler(config)

    if scheduler.install():
        logger.success("Scheduled job installed successfully")
        status = scheduler.get_status()
        logger.info(f"Plist: {status.plist_path}")
        logger.info(f"Frequency: {args.frequency}")
        logger.info(f"Day: {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][args.day]}")
        logger.info(f"Time: {args.hour:02d}:00")
        return 0
    else:
        logger.error("Failed to install scheduled job")
        return 1


def cmd_schedule_uninstall(args):
    """Uninstall the launchd scheduled job."""
    scheduler = LaunchdScheduler(ScheduleConfig())

    if scheduler.uninstall():
        logger.success("Scheduled job removed successfully")
        return 0
    else:
        logger.error("Failed to remove scheduled job")
        return 1


def cmd_schedule_status(args):
    """Show status of scheduled job."""
    scheduler = LaunchdScheduler(ScheduleConfig())
    status = scheduler.get_status()

    logger.info(f"\n=== Schedule Status ===")
    logger.info(f"Installed: {'YES' if status.installed else 'NO'}")
    logger.info(f"Enabled: {'YES' if status.enabled else 'NO'}")
    logger.info(f"Status: {status.status}")

    if status.plist_path:
        logger.info(f"Plist: {status.plist_path}")
    if status.last_run:
        logger.info(f"Last Run: {status.last_run.strftime('%Y-%m-%d %H:%M:%S')}")

    return 0


def cmd_auto_run(args):
    """Run automated analysis."""
    config = AutomationConfig()
    config.schedule.tickers_file = Path(args.tickers_file)

    if args.skip_notify:
        config.notification.send_on_completion = False
        config.notification.send_on_error = False
        config.notification.send_high_priority_alerts = False

    if args.dry_run:
        logger.info("DRY RUN - would execute:")
        try:
            with open(config.schedule.tickers_file) as f:
                tickers = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            logger.info(f"  Tickers: {', '.join(tickers)}")
        except FileNotFoundError:
            logger.error(f"  Tickers file not found: {config.schedule.tickers_file}")
        logger.info(f"  Reports dir: {config.reports_dir}")
        logger.info(f"  Notifications: {'NO' if args.skip_notify else 'YES'}")
        return 0

    result = run_automation(config=config)

    if result.success:
        if result.run_id == "skipped":
            logger.info("Run skipped - bi-weekly schedule not due")
            return 0

        logger.success(f"\nAutomation complete: {result.completed_count}/{result.tickers_analyzed} stocks")

        if result.watchlist_candidates:
            logger.info(f"Watchlist: {', '.join(result.watchlist_candidates)}")
        if result.high_priority_stocks:
            logger.info(f"High Priority: {', '.join(result.high_priority_stocks)}")
        if result.report_path:
            logger.info(f"Report: {result.report_path}")
        if result.pdf_path:
            logger.info(f"PDF: {result.pdf_path}")

        logger.info(f"Cost: ${result.cost_usd:.2f}")
        logger.info(f"Duration: {result.duration_seconds:.0f}s")

        return 0
    else:
        logger.error(f"Automation failed: {result.error_message}")
        return 1


def cmd_cost(args):
    """View cost reports."""
    monitor = CostMonitor()

    if args.trend > 0:
        reports = monitor.get_cost_trend(args.trend)
        logger.info(f"\n=== Cost Trend ({args.trend} months) ===")
        for report in reports:
            status = "OK" if report.within_budget else "OVER"
            logger.info(f"  {report.month}: ${report.total_cost_usd:.2f} ({report.run_count} runs) [{status}]")
    else:
        if args.month:
            year, month = map(int, args.month.split("-"))
            report = monitor.get_monthly_cost(year, month)
        else:
            report = monitor.get_current_month_cost()

        logger.info(f"\n=== Cost Report: {report.month} ===")
        logger.info(f"Total Cost: ${report.total_cost_usd:.2f}")
        logger.info(f"Runs: {report.run_count}")
        logger.info(f"Stocks Analyzed: {report.stock_count}")
        logger.info(f"Budget Remaining: ${report.budget_remaining_usd:.2f}")
        logger.info(f"Within Budget: {'YES' if report.within_budget else 'NO'}")

    return 0


def cmd_notify_test(args):
    """Send test notification."""
    from research_swarm.config import settings

    recipients = [args.to] if args.to else settings.notification_recipients.split(",")
    recipients = [r.strip() for r in recipients if r.strip()]

    if not recipients:
        logger.error("No recipients configured. Set NOTIFICATION_RECIPIENTS or use --to")
        return 1

    config = EmailConfig(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_password=settings.smtp_password,
        recipients=recipients,
        from_email=settings.notification_from_email,
    )

    notifier = Notifier(config, NotificationConfig())
    result = notifier.send_test()

    if result.success:
        logger.success(f"Test email sent to: {', '.join(result.recipients_sent)}")
        return 0
    else:
        logger.error(f"Failed to send test email: {result.error_message}")
        return 1
```

Add subparsers in `main()`:

```python
# Schedule command with subcommands
parser_schedule = subparsers.add_parser("schedule", help="Manage scheduled automation")
schedule_subparsers = parser_schedule.add_subparsers(dest="schedule_command")

# schedule install
parser_schedule_install = schedule_subparsers.add_parser("install", help="Install scheduled job")
parser_schedule_install.add_argument(
    "--frequency", choices=["weekly", "bi_weekly", "monthly"],
    default="bi_weekly", help="Run frequency (default: bi_weekly)"
)
parser_schedule_install.add_argument(
    "--day", type=int, default=0,
    help="Day of week (0=Monday, 6=Sunday, default: 0)"
)
parser_schedule_install.add_argument(
    "--hour", type=int, default=6,
    help="Hour to run in 24h format (default: 6)"
)
parser_schedule_install.add_argument(
    "--tickers-file", default="./data/watchlist.txt",
    help="Path to tickers file (default: ./data/watchlist.txt)"
)
parser_schedule_install.set_defaults(func=cmd_schedule_install)

# schedule uninstall
parser_schedule_uninstall = schedule_subparsers.add_parser("uninstall", help="Remove scheduled job")
parser_schedule_uninstall.set_defaults(func=cmd_schedule_uninstall)

# schedule status
parser_schedule_status = schedule_subparsers.add_parser("status", help="Show schedule status")
parser_schedule_status.set_defaults(func=cmd_schedule_status)

# Auto command
parser_auto = subparsers.add_parser("auto", help="Run automated analysis")
parser_auto.add_argument(
    "--tickers-file", default="./data/watchlist.txt",
    help="File with tickers (one per line)"
)
parser_auto.add_argument(
    "--skip-notify", action="store_true",
    help="Skip email notifications"
)
parser_auto.add_argument(
    "--dry-run", action="store_true",
    help="Show what would be done without executing"
)
parser_auto.set_defaults(func=cmd_auto_run)

# Cost command
parser_cost = subparsers.add_parser("cost", help="View cost reports")
parser_cost.add_argument(
    "--month", help="Month in YYYY-MM format (default: current)"
)
parser_cost.add_argument(
    "--trend", type=int, default=0,
    help="Show trend for N months"
)
parser_cost.set_defaults(func=cmd_cost)

# Notify command
parser_notify = subparsers.add_parser("notify", help="Test email notifications")
parser_notify.add_argument(
    "--test", action="store_true", required=True,
    help="Send test email"
)
parser_notify.add_argument(
    "--to", help="Override recipient for test"
)
parser_notify.set_defaults(func=cmd_notify_test)
```

Handle schedule subcommands:

```python
# In main(), update the command handler section:
if not args.command:
    parser.print_help()
    return 0

# Handle schedule subcommand
if args.command == "schedule":
    if not args.schedule_command:
        parser_schedule.print_help()
        return 0

return args.func(args)
```

---

## Testing

Create `tests/test_automation.py`:

```python
"""Tests for automation module (Phase 9)."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from research_swarm.automation import (
    AutomationConfig,
    AutomationRunner,
    BudgetConfig,
    CostMonitor,
    CostReport,
    EmailConfig,
    EmailProvider,
    LaunchdScheduler,
    Notifier,
    NotificationConfig,
    ScheduleConfig,
    ScheduleFrequency,
    SMTPSender,
)


class TestModels:
    """Test Pydantic models."""

    def test_schedule_config_defaults(self):
        config = ScheduleConfig()
        assert config.frequency == ScheduleFrequency.BI_WEEKLY
        assert config.day_of_week == 0
        assert config.hour == 6

    def test_email_config_defaults(self):
        config = EmailConfig()
        assert config.provider == EmailProvider.SMTP
        assert config.smtp_port == 587

    def test_budget_config_defaults(self):
        config = BudgetConfig()
        assert config.monthly_budget_usd == 200.0
        assert config.alert_threshold_usd == 180.0


class TestScheduler:
    """Test LaunchdScheduler."""

    def test_generate_plist(self):
        config = ScheduleConfig(day_of_week=1, hour=8)
        scheduler = LaunchdScheduler(config)
        plist = scheduler.generate_plist()

        assert "com.research-swarm.automation" in plist
        assert "<integer>2</integer>" in plist  # Tuesday
        assert "<integer>8</integer>" in plist

    def test_should_run_biweekly_first_run(self):
        config = ScheduleConfig(frequency=ScheduleFrequency.BI_WEEKLY)
        scheduler = LaunchdScheduler(config)

        with patch.object(scheduler, '_load_state', return_value={}):
            assert scheduler.should_run_today() is True

    def test_should_run_weekly_always(self):
        config = ScheduleConfig(frequency=ScheduleFrequency.WEEKLY)
        scheduler = LaunchdScheduler(config)

        assert scheduler.should_run_today() is True


class TestCostMonitor:
    """Test cost monitoring."""

    def test_get_current_month_cost(self):
        mock_pm = Mock()
        mock_pm.get_monthly_costs.return_value = {
            "total_cost": 45.50,
            "run_count": 3,
            "stock_count": 15,
            "cost_by_day": {},
            "cost_by_ticker": {},
        }

        monitor = CostMonitor(persistence=mock_pm)
        report = monitor.get_current_month_cost()

        assert report.total_cost_usd == 45.50
        assert report.within_budget is True

    def test_should_alert_over_threshold(self):
        mock_pm = Mock()
        mock_pm.get_monthly_costs.return_value = {
            "total_cost": 185.0,
            "run_count": 10,
            "stock_count": 50,
            "cost_by_day": {},
            "cost_by_ticker": {},
        }

        monitor = CostMonitor(persistence=mock_pm)
        assert monitor.should_alert() is True


class TestNotifier:
    """Test email notification."""

    @patch('smtplib.SMTP')
    def test_smtp_send_success(self, mock_smtp):
        mock_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_instance

        config = EmailConfig(
            smtp_host="smtp.test.com",
            smtp_user="user",
            smtp_password="pass",
            recipients=["test@example.com"],
        )
        sender = SMTPSender(config)

        result = sender.send(
            to=["test@example.com"],
            subject="Test",
            body_html="<p>Test</p>",
            body_text="Test",
        )

        assert result.success is True


class TestRunner:
    """Test AutomationRunner."""

    def test_load_tickers(self, tmp_path):
        tickers_file = tmp_path / "watchlist.txt"
        tickers_file.write_text("NVDA\nMSFT\n# Comment\nAAPL\n")

        config = AutomationConfig()
        config.schedule.tickers_file = tickers_file

        runner = AutomationRunner(config)
        tickers = runner._load_tickers()

        assert tickers == ["NVDA", "MSFT", "AAPL"]
```

---

## Success Criteria

- [ ] `pip install sendgrid` succeeds (optional)
- [ ] `pytest tests/test_automation.py -v` passes
- [ ] `python -m research_swarm schedule install` creates plist
- [ ] `python -m research_swarm schedule status` shows status
- [ ] `python -m research_swarm schedule uninstall` removes plist
- [ ] `python -m research_swarm auto --dry-run` shows plan
- [ ] `python -m research_swarm cost` shows monthly costs
- [ ] `python -m research_swarm notify --test` sends email (with SMTP configured)
- [ ] Bi-weekly logic correctly skips alternate weeks

---

## CLI Usage

```bash
# Install bi-weekly schedule (every other Monday at 6am)
python -m research_swarm schedule install

# Install weekly on Fridays at 8am
python -m research_swarm schedule install --frequency weekly --day 4 --hour 8

# Check status
python -m research_swarm schedule status

# Remove schedule
python -m research_swarm schedule uninstall

# Manual run with notifications
python -m research_swarm auto

# Manual run without notifications
python -m research_swarm auto --skip-notify

# Dry run
python -m research_swarm auto --dry-run

# View current month costs
python -m research_swarm cost

# View 3-month trend
python -m research_swarm cost --trend 3

# Test email
python -m research_swarm notify --test --to your@email.com
```

---

## Environment Variables

Add to `.env.example`:

```bash
# Phase 9: Automation
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true

# Or use SendGrid
SENDGRID_API_KEY=SG.xxxxx

# Notifications
NOTIFICATION_RECIPIENTS=recipient@example.com
NOTIFICATION_FROM_EMAIL=research-swarm@localhost

# Budget
MONTHLY_BUDGET_USD=200.0
BUDGET_ALERT_THRESHOLD_USD=180.0
```

---

## Files Summary

### Create (9 files)
1. `research_swarm/automation/__init__.py`
2. `research_swarm/automation/models.py`
3. `research_swarm/automation/scheduler.py`
4. `research_swarm/automation/notifier.py`
5. `research_swarm/automation/cost_monitor.py`
6. `research_swarm/automation/runner.py`
7. `research_swarm/automation/templates/email_report.html.j2`
8. `tests/test_automation.py`
9. `data/watchlist.txt` (sample)

### Modify (4 files)
1. `research_swarm/config.py` - Add SMTP/notification settings
2. `research_swarm/__main__.py` - Add CLI commands
3. `research_swarm/orchestration/persistence.py` - Add `get_monthly_costs()`
4. `requirements.txt` - Add sendgrid

---

Good luck, Builder!
