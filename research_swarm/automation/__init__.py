"""Automation module for scheduling and notifications."""

from research_swarm.automation.cost_monitor import CostMonitor
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
from research_swarm.automation.notifier import Notifier, SendGridSender, SMTPSender
from research_swarm.automation.runner import AutomationRunner, run_automation
from research_swarm.automation.scheduler import LaunchdScheduler

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
