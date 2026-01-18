"""Main report generator orchestrator."""

import time
from pathlib import Path
from typing import Optional

from ..logger import logger
from ..orchestration import PersistenceManager
from .data_extractor import DataExtractor
from .models import ReportConfig, ReportOutput, ReportType
from .pdf_generator import PDFGenerator
from .renderer import TemplateRenderer
from .visualizations import ChartGenerator


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

            # Step 4: Save Markdown file
            config.output_dir.mkdir(parents=True, exist_ok=True)
            md_path = config.output_dir / f"report_{config.run_id[:8]}.md"
            md_path.write_text(markdown_content, encoding="utf-8")
            logger.info(f"Saved Markdown report: {md_path}")

            # Step 5: Generate PDF if requested
            pdf_path = None
            if config.report_type in [ReportType.PDF, ReportType.BOTH]:
                logger.debug("Generating PDF...")
                pdf_gen = PDFGenerator()
                pdf_path = config.output_dir / f"report_{config.run_id[:8]}.pdf"

                try:
                    pdf_gen.generate(md_path, pdf_path)
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
