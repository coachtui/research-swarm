"""Main automation runner that orchestrates run -> report -> notify."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from research_swarm.automation.cost_monitor import CostMonitor
from research_swarm.automation.models import (
    AutomationConfig,
    AutomationResult,
    NotificationResult,
)
from research_swarm.automation.notifier import Notifier
from research_swarm.automation.scheduler import LaunchdScheduler
from research_swarm.logger import logger
from research_swarm.orchestration import PersistenceManager, run_batch
from research_swarm.reports import generate_report


class AutomationRunner:
    """Main orchestrator for automated runs."""

    def __init__(self, config: Optional[AutomationConfig] = None):
        self.config = config or AutomationConfig()
        self.persistence = PersistenceManager()
        self.notifier = Notifier(self.config.email, self.config.notification)
        self.cost_monitor = CostMonitor(self.persistence, self.config.budget)
        self.scheduler = LaunchdScheduler(self.config.schedule)

    def run(self, tickers: Optional[List[str]] = None) -> AutomationResult:
        """Execute full automation workflow: run -> report -> notify."""
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
                ticker
                for ticker, result in swarm_run.stock_results.items()
                if result.moat_score
                and result.moat_score >= self.config.notification.high_moat_threshold
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

            logger.success(
                f"Automation complete: {result.completed_count}/{result.tickers_analyzed}"
            )
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
            tickers = [
                line.strip().upper()
                for line in f
                if line.strip() and not line.startswith("#")
            ]

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
            logger.warning(
                f"Budget alert sent: ${report.total_cost_usd:.2f} / "
                f"${self.config.budget.monthly_budget_usd:.2f}"
            )


def run_automation(
    tickers: Optional[List[str]] = None,
    config: Optional[AutomationConfig] = None,
) -> AutomationResult:
    """Convenience function to run automation."""
    runner = AutomationRunner(config)
    return runner.run(tickers)
