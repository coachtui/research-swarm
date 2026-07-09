"""
Inngest function for analyzing a single stock.

This is the core background job that wraps the existing
manager agent orchestration logic.

DORMANT — not part of ACTIVE_FUNCTIONS (see inngest_app/index.py). Left
registered here for the tiered-batch redesign to pick up later.
"""
from __future__ import annotations

from typing import Dict, Any

# Guarded registration so this module is always importable, even when the
# inngest pip package is not installed (same pattern as send_teaser_digest.py).


def _register_inngest_function():
    from inngest_app.client import inngest_client  # noqa: PLC0415

    @inngest_client.create_function(
        fn_id="analyze-stock",
        trigger=inngest_client.trigger.event(event="analyze_stock"),
        retries=3,
        name="Analyze Single Stock"
    )
    async def analyze_stock(ctx, step):
        """
        Long-running function to analyze a single stock.

        Steps:
        1. Update run status to "running"
        2. Run manager agent (calls fundamentalist, news_hound, quant)
        3. Save results to database
        4. Upload charts to R2
        5. Send webhook notification to user
        6. Update cost logs

        Max duration: 15 minutes (Inngest limit)
        Typical duration: 5-8 minutes per stock
        """

        data: Dict[str, Any] = ctx.event.data

        user_id = data["user_id"]
        run_id = data["run_id"]
        ticker = data["ticker"]
        quarters = data["quarters"]
        news_days_back = data.get("news_days_back", 30)

        # Step 1: Update status to running
        await step.run("update-status-running", lambda:
            update_run_status(run_id, ticker, "running")
        )

        try:
            # Step 2: Run the actual analysis (existing research_swarm code!)
            result = await step.run("run-manager-agent", lambda:
                run_manager_analysis(
                    ticker=ticker,
                    quarters=quarters,
                    news_days_back=news_days_back,
                    user_id=user_id
                )
            )

            # Step 3: Save results to database
            await step.run("save-to-database", lambda:
                save_stock_result(
                    run_id=run_id,
                    ticker=ticker,
                    result=result
                )
            )

            # Step 4: Generate and upload charts to R2
            chart_urls = await step.run("upload-charts", lambda:
                generate_and_upload_charts(
                    run_id=run_id,
                    ticker=ticker,
                    result=result
                )
            )

            # Step 5: Log costs
            await step.run("log-costs", lambda:
                log_analysis_costs(
                    user_id=user_id,
                    run_id=run_id,
                    ticker=ticker,
                    tokens_used=result.get("tokens_used", 0),
                    cost_usd=result.get("cost_usd", 0)
                )
            )

            # Step 6: Update status to completed
            await step.run("update-status-completed", lambda:
                update_run_status(run_id, ticker, "completed")
            )

            # Step 7: Send webhook notification
            await step.run("send-notification", lambda:
                send_completion_webhook(
                    user_id=user_id,
                    run_id=run_id,
                    ticker=ticker,
                    moat_score=result.get("moat_score"),
                    is_watchlist_candidate=result.get("is_watchlist_candidate", False)
                )
            )

            return {
                "status": "success",
                "ticker": ticker,
                "moat_score": result.get("moat_score"),
                "cost_usd": result.get("cost_usd"),
                "chart_urls": chart_urls
            }

        except Exception as e:
            # Step: Handle error
            await step.run("handle-error", lambda:
                handle_analysis_error(
                    run_id=run_id,
                    ticker=ticker,
                    error=str(e)
                )
            )

            # Update status to failed
            await step.run("update-status-failed", lambda:
                update_run_status(run_id, ticker, "failed", error=str(e))
            )

            # Re-raise to trigger Inngest retry
            raise

    return analyze_stock


try:
    analyze_stock = _register_inngest_function()
except Exception:
    # inngest pip package not available (e.g. during unit tests) — no-op.
    analyze_stock = None  # type: ignore[assignment]


# Helper functions (to be implemented)

def update_run_status(run_id: str, ticker: str, status: str, error: str = None):
    """Update run and stock result status in database."""
    # TODO: Implement database update via Prisma
    print(f"[Inngest] {ticker} status: {status}")
    pass

async def run_manager_analysis(ticker: str, quarters: list, news_days_back: int, user_id: str):
    """
    Run the manager agent analysis (wraps existing code).

    This uses the analysis_service which wraps the existing
    research_swarm.agents.manager code.
    """
    from api.services.analysis_service import run_stock_analysis

    # Call the analysis service
    result = await run_stock_analysis(
        ticker=ticker,
        quarters=quarters,
        news_days_back=news_days_back,
        user_id=user_id
    )

    return result

def save_stock_result(run_id: str, ticker: str, result: dict):
    """Save stock result to database."""
    # TODO: Implement Prisma save
    print(f"[Inngest] Saving {ticker} result to database")
    pass

def generate_and_upload_charts(run_id: str, ticker: str, result: dict):
    """Generate charts and upload to R2."""
    # TODO: Implement chart generation + R2 upload
    # from research_swarm.reports.visualizations import create_moat_chart, create_supply_chain_graph
    # from api.services.storage_service import upload_to_r2
    print(f"[Inngest] Generating charts for {ticker}")
    return {
        "moat_chart": f"https://r2.example.com/{run_id}/{ticker}_moat.png",
        "supply_chain_chart": f"https://r2.example.com/{run_id}/{ticker}_supply_chain.png"
    }

def log_analysis_costs(user_id: str, run_id: str, ticker: str, tokens_used: int, cost_usd: float):
    """Log costs to database."""
    # TODO: Implement cost logging
    print(f"[Inngest] Logging costs: {ticker} = ${cost_usd}")
    pass

def send_completion_webhook(user_id: str, run_id: str, ticker: str, moat_score: float, is_watchlist_candidate: bool):
    """Send webhook notification to user."""
    # TODO: Implement webhook or email notification
    print(f"[Inngest] Sending notification for {ticker}")
    pass

def handle_analysis_error(run_id: str, ticker: str, error: str):
    """Handle and log analysis errors."""
    # TODO: Implement error logging
    print(f"[Inngest] Error analyzing {ticker}: {error}")
    pass
