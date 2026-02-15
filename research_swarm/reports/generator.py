"""Main report generator orchestrator."""

import time
from pathlib import Path
from typing import Optional

from ..logger import logger
from ..orchestration import PersistenceManager
from .data_extractor import DataExtractor
from .models import ReportConfig, ReportOutput, ReportType
from .renderer import TemplateRenderer
from .visualizations import ChartGenerator

# PDF generator is optional (requires system dependencies)
try:
    from .pdf_generator import PDFGenerator
except (ImportError, OSError):
    PDFGenerator = None


class ReportGenerator:
    """Main orchestrator for generating reports from SwarmRun data."""

    def __init__(self, persistence: Optional[PersistenceManager] = None):
        """Initialize report generator.

        Args:
            persistence: Optional PersistenceManager instance.
                        Creates new instance if not provided.
        """
        self.persistence = persistence or PersistenceManager()
        self.extractor = DataExtractor(self.persistence)
        self.renderer = TemplateRenderer()

    def generate(self, config: ReportConfig) -> ReportOutput:
        """Generate report based on configuration.

        Args:
            config: Report configuration

        Returns:
            ReportOutput with paths to generated files

        Raises:
            ValueError: If run_id not found or has no completed stocks
            Exception: If report generation fails
        """
        start_time = time.time()
        charts_generated = []

        try:
            logger.info(f"Starting report generation for run {config.run_id}")

            # Step 1: Extract data from persistence
            logger.debug("Extracting data from SwarmRun...")
            report_data = self.extractor.extract(
                config.run_id, top_picks_count=config.top_picks_count
            )
            logger.info(
                f"Extracted data for {len(report_data.stocks)} stocks "
                f"({len(report_data.watchlist_candidates)} watchlist candidates)"
            )

            # Step 2: Generate charts if requested
            if config.include_charts:
                logger.debug("Generating charts...")
                chart_gen = ChartGenerator(config.output_dir)

                for stock in report_data.stocks:
                    # Moat breakdown chart
                    try:
                        chart_path = chart_gen.generate_moat_breakdown(
                            stock.ticker, stock.moat_breakdown
                        )
                        charts_generated.append(str(chart_path))
                        logger.debug(f"Generated moat chart for {stock.ticker}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to generate moat chart for {stock.ticker}: {e}"
                        )

                    # Signal comparison chart (if signal breakdown available)
                    if stock.signal_breakdown:
                        try:
                            from ..visualization.signal_comparison import create_signal_comparison_chart
                            from ..agents.news_hound.models import NewsHoundOutput

                            # Get news_hound_output from persistence
                            run = self.persistence.get_run(config.run_id)
                            stock_result = run.stock_results.get(stock.ticker)
                            if stock_result and stock_result.full_output:
                                news_hound_data = stock_result.full_output.get("news_hound_output")
                                if news_hound_data:
                                    news_output = NewsHoundOutput(**news_hound_data)
                                    chart_path = create_signal_comparison_chart(
                                        news_output,
                                        save_path=config.output_dir / f"charts/signals_{stock.ticker}_comparison.png",
                                        show=False
                                    )
                                    if chart_path:
                                        charts_generated.append(str(chart_path))
                                        logger.debug(f"Generated signal comparison chart for {stock.ticker}")
                        except Exception as e:
                            logger.warning(
                                f"Failed to generate signal comparison chart for {stock.ticker}: {e}"
                            )

                    # Supply chain graph (if data available)
                    if stock.supply_chain_nodes:
                        try:
                            chart_path = chart_gen.generate_supply_chain_graph(
                                stock.ticker,
                                stock.supply_chain_nodes,
                                stock.supply_chain_edges,
                                stock.hidden_dependencies,
                            )
                            charts_generated.append(str(chart_path))
                            logger.debug(
                                f"Generated supply chain chart for {stock.ticker}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to generate supply chain chart for {stock.ticker}: {e}"
                            )

                # Portfolio overview chart
                if len(report_data.stocks) > 1:
                    try:
                        tickers = [s.ticker for s in report_data.stocks]
                        moat_scores = [s.moat_score for s in report_data.stocks]
                        chart_path = chart_gen.generate_portfolio_overview(
                            tickers, moat_scores
                        )
                        charts_generated.append(str(chart_path))
                        logger.debug("Generated portfolio overview chart")
                    except Exception as e:
                        logger.warning(f"Failed to generate portfolio overview: {e}")

                logger.info(f"Generated {len(charts_generated)} charts")

            # Step 3: Render Markdown
            logger.debug("Rendering Markdown report...")
            markdown_content = self.renderer.render_full_report(
                report_data, config.sections, config.include_charts
            )

            # Step 3.5: Store report snapshots for track record
            logger.debug("Storing report snapshots for track record...")
            for stock in report_data.stocks:
                try:
                    # Extract price and target from stock data
                    price_at_analysis = 0.0
                    price_target = 0.0

                    if stock.valuation_metrics:
                        price_at_analysis = stock.valuation_metrics.get("current_price", 0.0)

                    if stock.price_targets:
                        price_target = stock.price_targets.get("base_target", 0.0)

                    # Only store if we have valid price data
                    if price_at_analysis > 0:
                        snapshot_data = {
                            "moat_score": stock.moat_score,
                            "rating": stock.rating,
                            "investment_thesis": stock.investment_thesis,
                            "key_insights": stock.key_insights,
                            "risk_factors": stock.risk_factors,
                        }

                        self.persistence.store_report_snapshot(
                            ticker=stock.ticker,
                            run_id=config.run_id,
                            analysis_date=report_data.analysis_date,
                            rating=stock.rating,
                            price_at_analysis=price_at_analysis,
                            price_target=price_target,
                            moat_score=stock.moat_score,
                            snapshot_data=snapshot_data
                        )
                        logger.debug(f"Stored snapshot for {stock.ticker}")
                except Exception as e:
                    logger.warning(f"Failed to store snapshot for {stock.ticker}: {e}")

            # Step 4: Save Markdown file
            config.output_dir.mkdir(parents=True, exist_ok=True)
            md_path = config.output_dir / f"report_{config.run_id[:8]}.md"
            md_path.write_text(markdown_content, encoding="utf-8")
            logger.info(f"Saved Markdown report: {md_path}")

            # Step 5: Generate PDF if requested (uses DVRG HTML template)
            pdf_path = None
            if config.report_type in [ReportType.PDF, ReportType.BOTH]:
                if PDFGenerator is None:
                    logger.warning("PDF generation unavailable (missing system dependencies). Skipping PDF generation.")
                    logger.info("To enable PDF generation, install system dependencies: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation")
                else:
                    logger.debug("Generating DVRG-branded PDF...")
                    pdf_gen = PDFGenerator()
                    pdf_path = config.output_dir / f"report_{config.run_id[:8]}.pdf"

                    try:
                        html_content = self.renderer.render_pdf_report(
                            report_data, include_charts=config.include_charts
                        )
                        pdf_gen.generate_from_html(
                            html_content, pdf_path, base_dir=config.output_dir
                        )
                        logger.info(f"Saved PDF report: {pdf_path}")
                    except Exception as e:
                        logger.error(f"PDF generation failed: {e}")
                        # Continue even if PDF fails - we still have markdown
                        pdf_path = None

            generation_time = time.time() - start_time

            result = ReportOutput(
                markdown_path=md_path if config.report_type != ReportType.PDF else None,
                pdf_path=pdf_path,
                charts_generated=charts_generated,
                generation_time_seconds=generation_time,
                success=True,
            )

            logger.success(
                f"Report generation complete in {generation_time:.1f}s "
                f"({len(charts_generated)} charts)"
            )

            return result

        except Exception as e:
            generation_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Report generation failed: {error_msg}")

            return ReportOutput(
                markdown_path=None,
                pdf_path=None,
                charts_generated=charts_generated,
                generation_time_seconds=generation_time,
                success=False,
                error_message=error_msg,
            )


def generate_report(
    run_id: str,
    output_dir: str = "./reports",
    report_type: str = "both",
    include_charts: bool = True,
    top_picks: int = 3,
    persistence: Optional[PersistenceManager] = None,
) -> ReportOutput:
    """Convenience function to generate a report.

    Args:
        run_id: Run ID to generate report for
        output_dir: Output directory for reports (default: ./reports)
        report_type: Type of report - "markdown", "pdf", or "both" (default: both)
        include_charts: Whether to generate charts (default: True)
        top_picks: Number of top picks to highlight (default: 3)
        persistence: Optional PersistenceManager instance

    Returns:
        ReportOutput with generation results

    Example:
        >>> result = generate_report("abc123", report_type="pdf", top_picks=5)
        >>> if result.success:
        ...     print(f"Report saved to: {result.pdf_path}")
    """
    config = ReportConfig(
        run_id=run_id,
        output_dir=Path(output_dir),
        report_type=ReportType(report_type),
        include_charts=include_charts,
        top_picks_count=top_picks,
    )

    generator = ReportGenerator(persistence=persistence)
    return generator.generate(config)
