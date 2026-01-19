"""Cost monitoring from existing cost_log table."""

from datetime import datetime
from typing import List, Optional

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

    def get_cost_trend(self, months: int = 3) -> List[CostReport]:
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
