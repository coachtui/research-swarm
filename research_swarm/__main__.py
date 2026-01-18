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
from research_swarm.reports import generate_report
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


def cmd_report(args):
    """Generate report from completed run."""
    try:
        logger.info(f"Generating report for run {args.run_id}...")

        result = generate_report(
            run_id=args.run_id,
            output_dir=args.output_dir,
            report_type=args.format,
            include_charts=not args.no_charts,
            top_picks=args.top_picks,
        )

        if result.success:
            logger.success(f"\n✓ Report generated in {result.generation_time_seconds:.1f}s!")

            if result.markdown_path:
                logger.info(f"Markdown: {result.markdown_path}")

            if result.pdf_path:
                logger.info(f"PDF: {result.pdf_path}")

            if result.charts_generated:
                logger.info(f"Charts: {len(result.charts_generated)} generated")

            return 0
        else:
            logger.error(f"Report generation failed: {result.error_message}")
            return 1

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return 1


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
        logger.info(
            f"Day: {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][args.day]}"
        )
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

    logger.info("\n=== Schedule Status ===")
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
                tickers = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.startswith("#")
                ]
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

        logger.success(
            f"\nAutomation complete: {result.completed_count}/{result.tickers_analyzed} stocks"
        )

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
    """View cost reports and dashboard."""
    from research_swarm.automation.cost_monitor import CostMonitor
    from research_swarm.orchestration.persistence import PersistenceManager
    from research_swarm.config import settings

    monitor = CostMonitor()
    persistence = PersistenceManager()

    if args.dashboard:
        # Full dashboard view
        logger.info("\n" + "=" * 50)
        logger.info("       RESEARCH SWARM COST DASHBOARD")
        logger.info("=" * 50)

        # Current month summary
        from datetime import datetime
        now = datetime.now()
        current = monitor.get_monthly_cost(now.year, now.month)
        budget = settings.monthly_budget_usd
        utilization = (current.total_cost_usd / budget) * 100 if budget > 0 else 0

        logger.info(f"\n--- {current.month} Summary ---")
        logger.info(f"Total Spend:     ${current.total_cost_usd:.2f}")
        logger.info(f"Budget:          ${budget:.2f}")
        logger.info(f"Remaining:       ${current.budget_remaining_usd:.2f}")
        logger.info(f"Utilization:     {utilization:.1f}%")
        logger.info(f"Runs:            {current.run_count}")
        logger.info(f"Stocks Analyzed: {current.stock_count}")

        # Cost by agent
        agent_costs = persistence.get_cost_by_agent(now.year, now.month)
        if agent_costs:
            logger.info(f"\n--- Cost by Agent ---")
            for agent, cost in sorted(agent_costs.items(), key=lambda x: -x[1]):
                pct = (cost / current.total_cost_usd * 100) if current.total_cost_usd > 0 else 0
                logger.info(f"  {agent:15} ${cost:.4f} ({pct:.1f}%)")

        # 3-month trend
        logger.info(f"\n--- 3-Month Trend ---")
        trend = monitor.get_cost_trend(3)
        for report in reversed(trend):
            status = "OK" if report.within_budget else "OVER"
            bar_len = int(report.total_cost_usd / budget * 20) if budget > 0 else 0
            bar = "#" * min(bar_len, 20)
            logger.info(f"  {report.month}: ${report.total_cost_usd:6.2f} [{bar:20}] {status}")

        logger.info("")
        return 0

    # Existing trend logic
    if args.trend > 0:
        reports = monitor.get_cost_trend(args.trend)
        logger.info(f"\n=== Cost Trend ({args.trend} months) ===")
        for report in reports:
            status = "OK" if report.within_budget else "OVER"
            logger.info(
                f"  {report.month}: ${report.total_cost_usd:.2f} "
                f"({report.run_count} runs) [{status}]"
            )
    else:
        # Existing monthly report logic
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


def cmd_cache_stats(args):
    """Show cache statistics."""
    import os
    from research_swarm.data.cache import cache

    stats = cache.stats()
    db_path = cache.db_path
    db_size = os.path.getsize(db_path) / 1024 if os.path.exists(db_path) else 0

    logger.info("\n=== Cache Statistics ===")
    logger.info(f"Database:        {db_path}")
    logger.info(f"Size:            {db_size:.1f} KB")
    logger.info(f"Total Entries:   {stats['total_entries']}")
    logger.info(f"Valid Entries:   {stats['valid_entries']}")
    logger.info(f"Expired Entries: {stats['expired_entries']}")

    return 0


def cmd_cache_clear(args):
    """Clear cache entries."""
    from research_swarm.data.cache import cache
    import sqlite3

    if args.all:
        if not args.force:
            confirm = input("Clear ALL cache entries? This cannot be undone. [y/N]: ")
            if confirm.lower() != 'y':
                logger.info("Cancelled")
                return 0
        with sqlite3.connect(cache.db_path) as conn:
            cursor = conn.execute("DELETE FROM cache")
            deleted = cursor.rowcount
        logger.success(f"Cleared {deleted} cache entries (all)")
    else:
        deleted = cache.clear_expired()
        logger.success(f"Cleared {deleted} expired cache entries")

    return 0


def cmd_notify_test(args):
    """Send test notification."""
    recipients = (
        [args.to]
        if args.to
        else settings.notification_recipients.split(",")
    )
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


def main():
    """Main CLI entry point."""
    # Clean up expired cache entries on startup
    try:
        from research_swarm.data.cache import cache
        deleted = cache.clear_expired()
        if deleted > 0:
            logger.debug(f"Cleaned up {deleted} expired cache entries")
    except Exception as e:
        logger.debug(f"Cache cleanup skipped: {e}")

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

    # Report command
    parser_report = subparsers.add_parser("report", help="Generate report from run")
    parser_report.add_argument("run_id", help="Run ID to generate report for")
    parser_report.add_argument(
        "--format",
        choices=["markdown", "pdf", "both"],
        default="both",
        help="Report format (default: both)",
    )
    parser_report.add_argument(
        "--output-dir",
        default="./reports",
        help="Output directory (default: ./reports)",
    )
    parser_report.add_argument(
        "--no-charts",
        action="store_true",
        help="Disable chart generation",
    )
    parser_report.add_argument(
        "--top-picks",
        type=int,
        default=3,
        help="Number of top picks to highlight (default: 3)",
    )
    parser_report.set_defaults(func=cmd_report)

    # Schedule command with subcommands
    parser_schedule = subparsers.add_parser("schedule", help="Manage scheduled automation")
    schedule_subparsers = parser_schedule.add_subparsers(dest="schedule_command")

    # schedule install
    parser_schedule_install = schedule_subparsers.add_parser(
        "install", help="Install scheduled job"
    )
    parser_schedule_install.add_argument(
        "--frequency",
        choices=["weekly", "bi_weekly", "monthly"],
        default="bi_weekly",
        help="Run frequency (default: bi_weekly)",
    )
    parser_schedule_install.add_argument(
        "--day",
        type=int,
        default=0,
        help="Day of week (0=Monday, 6=Sunday, default: 0)",
    )
    parser_schedule_install.add_argument(
        "--hour",
        type=int,
        default=6,
        help="Hour to run in 24h format (default: 6)",
    )
    parser_schedule_install.add_argument(
        "--tickers-file",
        default="./data/watchlist.txt",
        help="Path to tickers file (default: ./data/watchlist.txt)",
    )
    parser_schedule_install.set_defaults(func=cmd_schedule_install)

    # schedule uninstall
    parser_schedule_uninstall = schedule_subparsers.add_parser(
        "uninstall", help="Remove scheduled job"
    )
    parser_schedule_uninstall.set_defaults(func=cmd_schedule_uninstall)

    # schedule status
    parser_schedule_status = schedule_subparsers.add_parser(
        "status", help="Show schedule status"
    )
    parser_schedule_status.set_defaults(func=cmd_schedule_status)

    # Auto command
    parser_auto = subparsers.add_parser("auto", help="Run automated analysis")
    parser_auto.add_argument(
        "--tickers-file",
        default="./data/watchlist.txt",
        help="File with tickers (one per line)",
    )
    parser_auto.add_argument(
        "--skip-notify",
        action="store_true",
        help="Skip email notifications",
    )
    parser_auto.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing",
    )
    parser_auto.set_defaults(func=cmd_auto_run)

    # Cost command
    parser_cost = subparsers.add_parser("cost", help="View cost reports")
    parser_cost.add_argument(
        "--month",
        help="Month in YYYY-MM format (default: current)",
    )
    parser_cost.add_argument(
        "--trend",
        type=int,
        default=0,
        help="Show trend for N months",
    )
    parser_cost.add_argument(
        "--dashboard",
        action="store_true",
        help="Show full cost dashboard with agent breakdown and trends",
    )
    parser_cost.set_defaults(func=cmd_cost)

    # Cache command
    parser_cache = subparsers.add_parser("cache", help="Manage cache")
    cache_subparsers = parser_cache.add_subparsers(dest="cache_command", required=True)

    parser_cache_stats = cache_subparsers.add_parser("stats", help="Show cache statistics")
    parser_cache_stats.set_defaults(func=cmd_cache_stats)

    parser_cache_clear = cache_subparsers.add_parser("clear", help="Clear cache entries")
    parser_cache_clear.add_argument("--all", action="store_true", help="Clear all entries (not just expired)")
    parser_cache_clear.add_argument("--force", "-f", action="store_true", help="Skip confirmation for --all")
    parser_cache_clear.set_defaults(func=cmd_cache_clear)

    # Notify command
    parser_notify = subparsers.add_parser("notify", help="Test email notifications")
    parser_notify.add_argument(
        "--test",
        action="store_true",
        required=True,
        help="Send test email",
    )
    parser_notify.add_argument(
        "--to",
        help="Override recipient for test",
    )
    parser_notify.set_defaults(func=cmd_notify_test)

    # Parse arguments
    args = parser.parse_args()

    # Show help if no command
    if not args.command:
        parser.print_help()
        return 0

    # Handle schedule subcommand
    if args.command == "schedule":
        if not args.schedule_command:
            parser_schedule.print_help()
            return 0

    # Run command
    return args.func(args)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
