"""Cost tracking for API usage."""

from typing import Dict, Literal, Optional

from ..logger import logger

# Model pricing per 1K tokens (as of 2024)
ModelType = Literal["haiku", "sonnet", "opus"]


class CostTracker:
    """Tracks API costs and token usage."""

    # Per 1K tokens (input/output)
    PRICING = {
        "haiku": {
            "input": 0.00025,  # $0.25/M
            "output": 0.00125,  # $1.25/M
        },
        "sonnet": {
            "input": 0.003,  # $3/M
            "output": 0.015,  # $15/M
        },
        "opus": {
            "input": 0.015,  # $15/M
            "output": 0.075,  # $75/M
        },
    }

    def __init__(self):
        """Initialize cost tracker."""
        self.total_tokens = 0
        self.total_cost = 0.0
        self.cost_by_agent: Dict[str, float] = {}
        self.cost_by_ticker: Dict[str, float] = {}

    @classmethod
    def calculate_cost(
        cls,
        tokens_input: int,
        tokens_output: int,
        model: ModelType = "haiku",
    ) -> float:
        """Calculate cost for token usage.

        Args:
            tokens_input: Input tokens
            tokens_output: Output tokens
            model: Model type (haiku, sonnet, opus)

        Returns:
            Cost in USD
        """
        pricing = cls.PRICING[model]
        input_cost = (tokens_input / 1000) * pricing["input"]
        output_cost = (tokens_output / 1000) * pricing["output"]
        return input_cost + output_cost

    def log_usage(
        self,
        run_id: str,
        ticker: str,
        agent_name: str,
        tokens_input: int,
        tokens_output: int,
        model: ModelType = "haiku",
        persistence_manager: Optional[object] = None,
    ) -> float:
        """Log token usage and calculate cost.

        Args:
            run_id: Run ID
            ticker: Stock ticker
            agent_name: Agent name (fundamentalist, news_hound, quant, manager)
            tokens_input: Input tokens
            tokens_output: Output tokens
            model: Model type
            persistence_manager: Optional PersistenceManager for logging

        Returns:
            Cost in USD
        """
        cost = self.calculate_cost(tokens_input, tokens_output, model)
        tokens_total = tokens_input + tokens_output

        # Update tracking
        self.total_tokens += tokens_total
        self.total_cost += cost

        # Track by agent
        if agent_name not in self.cost_by_agent:
            self.cost_by_agent[agent_name] = 0.0
        self.cost_by_agent[agent_name] += cost

        # Track by ticker
        if ticker not in self.cost_by_ticker:
            self.cost_by_ticker[ticker] = 0.0
        self.cost_by_ticker[ticker] += cost

        # Log to persistence if provided
        if persistence_manager:
            try:
                persistence_manager.log_cost(
                    run_id=run_id,
                    ticker=ticker,
                    agent_name=agent_name,
                    tokens_total=tokens_total,
                    cost_usd=cost,
                )
            except Exception as e:
                logger.error(f"Failed to log cost to database: {e}")

        logger.debug(
            f"{agent_name} on {ticker}: {tokens_total} tokens = ${cost:.4f}"
        )

        return cost

    @classmethod
    def estimate_run_cost(
        cls,
        ticker_count: int,
        tokens_per_stock: int = 15000,
        model: ModelType = "haiku",
    ) -> float:
        """Estimate cost for a batch run.

        Args:
            ticker_count: Number of stocks to analyze
            tokens_per_stock: Estimated tokens per stock (default 15k)
            model: Model type

        Returns:
            Estimated cost in USD
        """
        # Assume 30% input, 70% output distribution
        tokens_input = int(tokens_per_stock * 0.3)
        tokens_output = int(tokens_per_stock * 0.7)

        cost_per_stock = cls.calculate_cost(tokens_input, tokens_output, model)
        return cost_per_stock * ticker_count

    @classmethod
    def check_budget(
        cls,
        estimated_cost: float,
        monthly_budget: float = 200.0,
        current_month_spending: float = 0.0,
    ) -> Dict[str, any]:
        """Check if estimated cost fits within budget.

        Args:
            estimated_cost: Estimated cost for the run
            monthly_budget: Monthly budget limit
            current_month_spending: Already spent this month

        Returns:
            Dictionary with budget check results
        """
        remaining_budget = monthly_budget - current_month_spending
        within_budget = estimated_cost <= remaining_budget
        runs_remaining = int(remaining_budget / estimated_cost) if estimated_cost > 0 else 999

        return {
            "within_budget": within_budget,
            "estimated_cost": estimated_cost,
            "remaining_budget": remaining_budget,
            "runs_remaining_this_month": max(0, runs_remaining),
            "monthly_budget": monthly_budget,
            "current_month_spending": current_month_spending,
        }

    def get_summary(self) -> Dict[str, any]:
        """Get cost summary.

        Returns:
            Dictionary with cost summary
        """
        return {
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost, 4),
            "cost_by_agent": {
                agent: round(cost, 4)
                for agent, cost in self.cost_by_agent.items()
            },
            "cost_by_ticker": {
                ticker: round(cost, 4)
                for ticker, cost in self.cost_by_ticker.items()
            },
        }
