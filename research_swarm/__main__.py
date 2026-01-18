import argparse
import sys
from pathlib import Path

from research_swarm import __version__
from research_swarm.config import settings
from research_swarm.logger import logger
from research_swarm.orchestration import (
    estimate_cost,
    get_resumable_runs,
    get_run_history,
    resume_batch,
    run_batch,
)


def cmd_run(args):
    """Run a batch analysis on multiple stocks."""
    # Load tickers from file or command line
    if args.from_file:
        file_path = Path(args.from_file)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return 1

        with open(file_path, "r") as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
    else:
        tickers = [t.upper() for t in args.tickers]

    if not tickers:
        logger.error("No tickers provided")
        return 1

    logger.info(f"Starting batch analysis for {len(tickers)} stocks: {', '.join(tickers)}")

    # Run batch
    try:
        swarm_run = run_batch(
            tickers=tickers,
            fiscal_year=args.fiscal_year,
            news_days_back=args.news_days_back,
            max_retries=args.max_retries,
            run_name=args.name,
        )

        # Display results
        logger.success(f"\n✓ Batch run {swarm_run.run_id} completed!")
        logger.info(f"Status: {swarm_run.status.value}")
        logger.info(
            f"Completed: {swarm_run.completed_count}/{swarm_run.total_stocks}"
        )
        logger.info(f"Failed: {swarm_run.failed_count}")
        logger.info(
            f"Cost: ${swarm_run.cost_summary.total_cost_usd:.2f}"
        )
        logger.info(f"Time: {swarm_run.elapsed_seconds:.0f}s")

        # Show watchlist candidates
        watchlist = swarm_run.watchlist_candidates
        if watchlist:
            logger.info(
                f"\nWatchlist Candidates ({len(watchlist)}):"
            )
            for result in watchlist:
                logger.info(
                    f"  • {result.ticker}: {result.moat_score:.1f}/10"
                )

        return 0

    except Exception as e:
        logger.error(f"Batch run failed: {e}")
        return 1


def cmd_resume(args):
    """Resume a paused or failed batch run."""
    # List resumable runs
    if args.list:
        resumable = get_resumable_runs()
        if not resumable:
            logger.info("No resumable runs found")
            return 0

        logger.info(f"Resumable runs ({len(resumable)}):")
        for run in resumable:
            logger.info(
                f"  {run.run_id} ({run.run_name or 'Unnamed'}) - "
                f"{run.pending_count} pending stocks"
            )
        return 0

    # Resume specific run
    if not args.run_id:
        logger.error("Run ID required. Use --list to see resumable runs.")
        return 1

    try:
        logger.info(f"Resuming run {args.run_id}...")
        swarm_run = resume_batch(args.run_id)

        logger.success(f"\n✓ Run {swarm_run.run_id} resumed!")
        logger.info(f"Status: {swarm_run.status.value}")
        logger.info(
            f"Completed: {swarm_run.completed_count}/{swarm_run.total_stocks}"
        )
        logger.info(f"Failed: {swarm_run.failed_count}")

        return 0

    except Exception as e:
        logger.error(f"Resume failed: {e}")
        return 1


def cmd_history(args):
    """Show run history."""
    try:
        runs = get_run_history(limit=args.limit)

        if not runs:
            logger.info("No runs found")
            return 0

        logger.info(f"Recent runs ({len(runs)}):")
        for run in runs:
            logger.info(
                f"\n  Run ID: {run.run_id}"
            )
            if run.run_name:
                logger.info(f"  Name: {run.run_name}")
            logger.info(
                f"  Tickers: {', '.join(run.tickers)}"
            )
            logger.info(f"  Status: {run.status.value}")
            logger.info(
                f"  Completed: {run.completed_count}/{run.total_stocks}"
            )
            logger.info(f"  Cost: ${run.cost_summary.total_cost_usd:.2f}")
            logger.info(
                f"  Created: {run.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        # Export if requested
        if args.export:
            export_path = Path(args.export)
            with open(export_path, "w") as f:
                f.write("# Research Swarm Run History\n\n")
                for run in runs:
                    f.write(f"## Run {run.run_id}\n")
                    if run.run_name:
                        f.write(f"**Name**: {run.run_name}\n\n")
                    f.write(f"**Status**: {run.status.value}\n")
                    f.write(f"**Tickers**: {', '.join(run.tickers)}\n")
                    f.write(
                        f"**Completed**: {run.completed_count}/{run.total_stocks}\n"
                    )
                    f.write(f"**Cost**: ${run.cost_summary.total_cost_usd:.2f}\n")
                    f.write(
                        f"**Created**: {run.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    )

                    # Include results
                    f.write("### Results\n\n")
                    for ticker, result in run.stock_results.items():
                        f.write(f"#### {ticker}\n")
                        f.write(f"- Status: {result.status.value}\n")
                        if result.moat_score:
                            f.write(f"- Moat Score: {result.moat_score:.2f}/10\n")
                        if result.is_watchlist_candidate:
                            f.write("- Watchlist: YES ✓\n")
                        if result.investment_thesis:
                            f.write(f"- Thesis: {result.investment_thesis}\n")
                        f.write("\n")

                    f.write("---\n\n")

            logger.success(f"History exported to {export_path}")

        return 0

    except Exception as e:
        logger.error(f"Failed to retrieve history: {e}")
        return 1


def cmd_estimate(args):
    """Estimate cost for a batch run."""
    # Load tickers from file or command line
    if args.from_file:
        file_path = Path(args.from_file)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return 1

        with open(file_path, "r") as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
    else:
        tickers = [t.upper() for t in args.tickers]

    if not tickers:
        logger.error("No tickers provided")
        return 1

    try:
        estimate = estimate_cost(tickers, tokens_per_stock=args.tokens_per_stock)

        logger.info(f"\n=== Cost Estimate ===")
        logger.info(f"Tickers: {', '.join(estimate.tickers)}")
        logger.info(f"Estimated Cost: ${estimate.estimated_cost_usd:.2f}")
        logger.info(f"Estimated Time: {estimate.estimated_total_time_human}")
        logger.info(
            f"Within Budget: {'YES ✓' if estimate.within_budget else 'NO ✗'}"
        )
        logger.info(
            f"Runs Remaining This Month: {estimate.runs_remaining_this_month}"
        )

        return 0

    except Exception as e:
        logger.error(f"Estimate failed: {e}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="research-swarm",
        description="Research Swarm: Multi-agent stock analysis system",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    parser_run = subparsers.add_parser("run", help="Run batch stock analysis")
    parser_run.add_argument("tickers", nargs="*", help="Stock tickers to analyze")
    parser_run.add_argument(
        "--from-file", help="Load tickers from file (one per line)"
    )
    parser_run.add_argument("--name", help="Name for this run")
    parser_run.add_argument(
        "--fiscal-year", type=int, default=2024, help="Fiscal year (default: 2024)"
    )
    parser_run.add_argument(
        "--news-days-back",
        type=int,
        default=30,
        help="Days to look back for news (default: 30)",
    )
    parser_run.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries per stock (default: 3)",
    )
    parser_run.set_defaults(func=cmd_run)

    # Resume command
    parser_resume = subparsers.add_parser("resume", help="Resume a paused run")
    parser_resume.add_argument("run_id", nargs="?", help="Run ID to resume")
    parser_resume.add_argument(
        "--list", action="store_true", help="List resumable runs"
    )
    parser_resume.set_defaults(func=cmd_resume)

    # History command
    parser_history = subparsers.add_parser("history", help="Show run history")
    parser_history.add_argument(
        "--limit", type=int, default=20, help="Number of runs to show (default: 20)"
    )
    parser_history.add_argument(
        "--export", help="Export history to markdown file"
    )
    parser_history.set_defaults(func=cmd_history)

    # Estimate command
    parser_estimate = subparsers.add_parser("estimate", help="Estimate run cost")
    parser_estimate.add_argument("tickers", nargs="*", help="Stock tickers")
    parser_estimate.add_argument(
        "--from-file", help="Load tickers from file (one per line)"
    )
    parser_estimate.add_argument(
        "--tokens-per-stock",
        type=int,
        default=15000,
        help="Estimated tokens per stock (default: 15000)",
    )
    parser_estimate.set_defaults(func=cmd_estimate)

    # Parse arguments
    args = parser.parse_args()

    # Show help if no command
    if not args.command:
        parser.print_help()
        return 0

    # Run command
    return args.func(args)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
