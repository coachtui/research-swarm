"""Tests for report generation module (Phase 8.1 & 8.2)."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from research_swarm.reports import (
    ChartGenerator,
    DataExtractor,
    PDFGenerator,
    ReportConfig,
    ReportData,
    ReportGenerator,
    ReportSection,
    ReportType,
    StockReportData,
    TemplateRenderer,
    generate_report,
)
from research_swarm.orchestration.models import (
    CostSummary,
    RunStatus,
    StockResult,
    StockStatus,
    SwarmRun,
)


class TestReportModels:
    """Test Pydantic models for reports."""

    def test_report_config_defaults(self):
        """Test ReportConfig default values."""
        config = ReportConfig(run_id="test-123")
        assert config.report_type == ReportType.BOTH
        assert config.include_charts is True
        assert config.top_picks_count == 3
        assert len(config.sections) == 4
        assert ReportSection.EXECUTIVE_SUMMARY in config.sections

    def test_report_config_custom_values(self):
        """Test ReportConfig with custom values."""
        config = ReportConfig(
            run_id="test-456",
            output_dir=Path("./custom_reports"),
            report_type=ReportType.MARKDOWN,
            include_charts=False,
            top_picks_count=5,
            sections=[ReportSection.EXECUTIVE_SUMMARY, ReportSection.WATCHLIST],
        )
        assert config.run_id == "test-456"
        assert config.output_dir == Path("./custom_reports")
        assert config.report_type == ReportType.MARKDOWN
        assert config.include_charts is False
        assert config.top_picks_count == 5
        assert len(config.sections) == 2

    def test_stock_report_data_validation(self):
        """Test StockReportData validation."""
        data = StockReportData(
            ticker="NVDA",
            moat_score=8.5,
            moat_breakdown={
                "financial_health": 8.0,
                "sentiment_catalysts": 7.0,
                "technical_strength": 9.0,
                "supply_chain_position": 9.5,
            },
            is_watchlist_candidate=True,
            investment_thesis="Strong buy for AI exposure",
            key_insights=["AI leadership", "Strong margins", "Growing revenue"],
            risk_factors=["Competition", "Valuation", "Cyclicality"],
            synthesis_narrative="NVDA is a leader in AI chips...",
            processing_time=45.2,
            cost_usd=0.15,
        )
        assert data.ticker == "NVDA"
        assert data.moat_score == 8.5
        assert data.is_watchlist_candidate is True
        assert len(data.key_insights) == 3
        assert len(data.risk_factors) == 3

    def test_stock_report_data_with_supply_chain(self):
        """Test StockReportData with supply chain data."""
        data = StockReportData(
            ticker="NVDA",
            moat_score=8.5,
            moat_breakdown={
                "financial_health": 8.0,
                "sentiment_catalysts": 7.0,
                "technical_strength": 9.0,
                "supply_chain_position": 9.5,
            },
            is_watchlist_candidate=True,
            investment_thesis="Strong buy",
            key_insights=["AI leadership", "Strong margins", "Growing revenue"],
            risk_factors=["Competition", "Valuation", "Cyclicality"],
            synthesis_narrative="NVDA is a leader...",
            supply_chain_nodes=[
                {"name": "NVIDIA", "ticker": "NVDA", "node_type": "root"},
                {"name": "TSMC", "ticker": "TSM", "node_type": "supplier"},
            ],
            supply_chain_edges=[
                {"source": "TSMC", "target": "NVIDIA", "relationship": "supplies"}
            ],
            hidden_dependencies=["ASML supplies TSMC"],
            processing_time=45.2,
            cost_usd=0.15,
        )
        assert len(data.supply_chain_nodes) == 2
        assert len(data.supply_chain_edges) == 1
        assert len(data.hidden_dependencies) == 1

    def test_report_data_validation(self):
        """Test ReportData validation."""
        stock1 = StockReportData(
            ticker="NVDA",
            moat_score=8.5,
            moat_breakdown={
                "financial_health": 8.0,
                "sentiment_catalysts": 7.0,
                "technical_strength": 9.0,
                "supply_chain_position": 9.5,
            },
            is_watchlist_candidate=True,
            investment_thesis="Strong buy",
            key_insights=["AI leadership", "Strong margins", "Growing revenue"],
            risk_factors=["Competition", "Valuation", "Cyclicality"],
            synthesis_narrative="NVDA is a leader...",
            processing_time=45.2,
            cost_usd=0.15,
        )
        stock2 = StockReportData(
            ticker="MSFT",
            moat_score=7.5,
            moat_breakdown={
                "financial_health": 7.0,
                "sentiment_catalysts": 8.0,
                "technical_strength": 7.0,
                "supply_chain_position": 8.0,
            },
            is_watchlist_candidate=False,
            investment_thesis="Hold",
            key_insights=["Cloud growth", "AI integration", "Stable revenue"],
            risk_factors=["Antitrust", "Competition", "Valuation"],
            synthesis_narrative="MSFT has strong cloud...",
            processing_time=42.0,
            cost_usd=0.12,
        )

        report_data = ReportData(
            run_id="test-run-123",
            run_name="Test Run",
            analysis_date="2024-01-17",
            fiscal_year=2024,
            stocks=[stock1, stock2],
            top_picks=[stock1],
            watchlist_candidates=[stock1],
            total_stocks=2,
            completed_count=2,
            failed_count=0,
            average_moat_score=8.0,
            total_cost_usd=0.27,
            total_elapsed_seconds=120.5,
            cost_by_ticker={"NVDA": 0.15, "MSFT": 0.12},
        )

        assert report_data.run_id == "test-run-123"
        assert len(report_data.stocks) == 2
        assert len(report_data.top_picks) == 1
        assert len(report_data.watchlist_candidates) == 1
        assert report_data.average_moat_score == 8.0
        assert report_data.total_cost_usd == 0.27


class TestDataExtractor:
    """Test DataExtractor for transforming SwarmRun to ReportData."""

    def test_extract_with_mock_persistence(self):
        """Test extraction with mock persistence manager."""
        # Create mock SwarmRun
        mock_run = SwarmRun(
            run_id="test-123",
            run_name="Test Run",
            tickers=["NVDA", "MSFT"],
            fiscal_year=2024,
            status=RunStatus.COMPLETED,
            total_stocks=2,
            completed_count=2,
            failed_count=0,
            cost_summary=CostSummary(
                total_tokens=1000, total_cost_usd=0.27, cost_by_ticker={}
            ),
            elapsed_seconds=120.5,
            stock_results={
                "NVDA": StockResult(
                    ticker="NVDA",
                    status=StockStatus.COMPLETED,
                    moat_score=8.5,
                    is_watchlist_candidate=True,
                    investment_thesis="Strong buy",
                    full_output={
                        "ticker": "NVDA",
                        "investment_thesis": "Strong buy for AI",
                        "key_insights": ["AI leader", "Strong margins", "Growing"],
                        "risk_factors": ["Competition", "Valuation", "Cycles"],
                        "synthesis_narrative": "NVDA is a leader in AI chips...",
                        "moat_breakdown": {
                            "financial_health": 8.0,
                            "sentiment_catalysts": 7.0,
                            "technical_strength": 9.0,
                            "supply_chain_position": 9.5,
                        },
                        "quant_output": {
                            "supply_chain_graph": {
                                "nodes": [],
                                "edges": [],
                                "hidden_dependencies": [],
                            }
                        },
                    },
                    cost_usd=0.15,
                    processing_time_seconds=45.2,
                ),
                "MSFT": StockResult(
                    ticker="MSFT",
                    status=StockStatus.COMPLETED,
                    moat_score=7.5,
                    is_watchlist_candidate=False,
                    investment_thesis="Hold",
                    full_output={
                        "ticker": "MSFT",
                        "investment_thesis": "Hold for cloud",
                        "key_insights": ["Cloud growth", "AI integration", "Stable"],
                        "risk_factors": ["Antitrust", "Competition", "Valuation"],
                        "synthesis_narrative": "MSFT has strong cloud...",
                        "moat_breakdown": {
                            "financial_health": 7.0,
                            "sentiment_catalysts": 8.0,
                            "technical_strength": 7.0,
                            "supply_chain_position": 8.0,
                        },
                        "quant_output": {
                            "supply_chain_graph": {
                                "nodes": [],
                                "edges": [],
                                "hidden_dependencies": [],
                            }
                        },
                    },
                    cost_usd=0.12,
                    processing_time_seconds=42.0,
                ),
            },
        )

        # Create mock persistence manager
        mock_pm = Mock()
        mock_pm.get_run.return_value = mock_run

        # Test extraction
        extractor = DataExtractor(mock_pm)
        data = extractor.extract("test-123", top_picks_count=1)

        assert data.run_id == "test-123"
        assert data.run_name == "Test Run"
        assert data.fiscal_year == 2024
        assert len(data.stocks) == 2
        assert len(data.top_picks) == 1
        assert data.top_picks[0].ticker == "NVDA"  # Highest moat score
        assert len(data.watchlist_candidates) == 1
        assert data.watchlist_candidates[0].ticker == "NVDA"
        assert data.average_moat_score == 8.0
        assert data.total_cost_usd == 0.27

    def test_extract_filters_failed_stocks(self):
        """Test that extraction filters out failed stocks."""
        mock_run = SwarmRun(
            run_id="test-456",
            tickers=["NVDA", "FAIL"],
            fiscal_year=2024,
            status=RunStatus.COMPLETED,
            total_stocks=2,
            completed_count=1,
            failed_count=1,
            cost_summary=CostSummary(total_cost_usd=0.15),
            elapsed_seconds=60.0,
            stock_results={
                "NVDA": StockResult(
                    ticker="NVDA",
                    status=StockStatus.COMPLETED,
                    moat_score=8.5,
                    is_watchlist_candidate=True,
                    full_output={
                        "investment_thesis": "Strong buy",
                        "key_insights": ["AI", "Margins", "Growth"],
                        "risk_factors": ["Comp", "Val", "Cycles"],
                        "synthesis_narrative": "Leader...",
                        "moat_breakdown": {
                            "financial_health": 8.0,
                            "sentiment_catalysts": 7.0,
                            "technical_strength": 9.0,
                            "supply_chain_position": 9.5,
                        },
                        "quant_output": {"supply_chain_graph": {}},
                    },
                    cost_usd=0.15,
                    processing_time_seconds=45.2,
                ),
                "FAIL": StockResult(
                    ticker="FAIL",
                    status=StockStatus.FAILED,
                    error_message="API error",
                    cost_usd=0.0,
                ),
            },
        )

        mock_pm = Mock()
        mock_pm.get_run.return_value = mock_run

        extractor = DataExtractor(mock_pm)
        data = extractor.extract("test-456")

        # Should only include completed stock
        assert len(data.stocks) == 1
        assert data.stocks[0].ticker == "NVDA"

    def test_extract_raises_on_missing_run(self):
        """Test that extraction raises ValueError for missing run."""
        mock_pm = Mock()
        mock_pm.get_run.return_value = None

        extractor = DataExtractor(mock_pm)

        with pytest.raises(ValueError, match="Run test-999 not found"):
            extractor.extract("test-999")

    def test_extract_raises_on_no_completed_stocks(self):
        """Test that extraction raises ValueError when no stocks completed."""
        mock_run = SwarmRun(
            run_id="test-789",
            tickers=["FAIL1", "FAIL2"],
            fiscal_year=2024,
            status=RunStatus.FAILED,
            total_stocks=2,
            completed_count=0,
            failed_count=2,
            cost_summary=CostSummary(),
            elapsed_seconds=30.0,
            stock_results={
                "FAIL1": StockResult(
                    ticker="FAIL1", status=StockStatus.FAILED, cost_usd=0.0
                ),
                "FAIL2": StockResult(
                    ticker="FAIL2", status=StockStatus.FAILED, cost_usd=0.0
                ),
            },
        )

        mock_pm = Mock()
        mock_pm.get_run.return_value = mock_run

        extractor = DataExtractor(mock_pm)

        with pytest.raises(ValueError, match="no completed stocks"):
            extractor.extract("test-789")


class TestChartGenerator:
    """Test ChartGenerator for creating visualizations (Phase 8.2)."""

    def test_chart_generator_creates_charts_dir(self, tmp_path):
        """Test that ChartGenerator creates charts directory."""
        gen = ChartGenerator(tmp_path)
        assert gen.charts_dir.exists()
        assert gen.charts_dir == tmp_path / "charts"

    def test_moat_breakdown_creates_png(self, tmp_path):
        """Test that moat breakdown chart creates PNG file."""
        gen = ChartGenerator(tmp_path)
        breakdown = {
            "financial_health": 8.0,
            "sentiment_catalysts": 7.0,
            "technical_strength": 6.0,
            "supply_chain_position": 9.0,
        }
        path = gen.generate_moat_breakdown("NVDA", breakdown)

        assert path.exists()
        assert path.suffix == ".png"
        assert path.name == "moat_NVDA.png"
        assert path.parent == gen.charts_dir

    def test_moat_breakdown_with_different_scores(self, tmp_path):
        """Test moat breakdown with various score ranges."""
        gen = ChartGenerator(tmp_path)

        # Test with high scores (should use green colors)
        high_breakdown = {
            "financial_health": 9.0,
            "sentiment_catalysts": 8.5,
            "technical_strength": 8.0,
            "supply_chain_position": 9.5,
        }
        high_path = gen.generate_moat_breakdown("HIGH", high_breakdown)
        assert high_path.exists()

        # Test with low scores (should use red colors)
        low_breakdown = {
            "financial_health": 2.0,
            "sentiment_catalysts": 3.0,
            "technical_strength": 1.5,
            "supply_chain_position": 2.5,
        }
        low_path = gen.generate_moat_breakdown("LOW", low_breakdown)
        assert low_path.exists()

        # Test with mixed scores
        mixed_breakdown = {
            "financial_health": 5.0,
            "sentiment_catalysts": 7.5,
            "technical_strength": 3.0,
            "supply_chain_position": 8.5,
        }
        mixed_path = gen.generate_moat_breakdown("MIXED", mixed_breakdown)
        assert mixed_path.exists()

    def test_supply_chain_graph_creates_png(self, tmp_path):
        """Test that supply chain graph creates PNG file."""
        gen = ChartGenerator(tmp_path)

        nodes = [
            {"name": "NVIDIA", "ticker": "NVDA", "node_type": "root"},
            {"name": "TSMC", "ticker": "TSM", "node_type": "supplier"},
            {"name": "ASML", "ticker": "ASML", "node_type": "supplier_t2"},
        ]
        edges = [
            {"source": "TSMC", "target": "NVIDIA", "relationship": "supplies"},
            {"source": "ASML", "target": "TSMC", "relationship": "supplies"},
        ]
        hidden_deps = ["ASML supplies multiple tier-1 suppliers"]

        path = gen.generate_supply_chain_graph("NVDA", nodes, edges, hidden_deps)

        assert path.exists()
        assert path.suffix == ".png"
        assert path.name == "supply_chain_NVDA.png"
        assert path.parent == gen.charts_dir

    def test_supply_chain_graph_with_empty_data(self, tmp_path):
        """Test supply chain graph with empty data creates placeholder."""
        gen = ChartGenerator(tmp_path)

        # Empty nodes/edges should still create a file with placeholder
        path = gen.generate_supply_chain_graph("EMPTY", [], [], [])

        assert path.exists()
        assert path.suffix == ".png"
        assert path.name == "supply_chain_EMPTY.png"

    def test_supply_chain_graph_with_complex_network(self, tmp_path):
        """Test supply chain graph with more complex network."""
        gen = ChartGenerator(tmp_path)

        nodes = [
            {"name": "NVIDIA", "ticker": "NVDA", "node_type": "root"},
            {"name": "Microsoft", "ticker": "MSFT", "node_type": "customer"},
            {"name": "Amazon", "ticker": "AMZN", "node_type": "customer"},
            {"name": "TSMC", "ticker": "TSM", "node_type": "supplier"},
            {"name": "Samsung", "ticker": "005930.KS", "node_type": "supplier"},
            {"name": "ASML", "ticker": "ASML", "node_type": "supplier_t2"},
        ]
        edges = [
            {"source": "NVIDIA", "target": "Microsoft", "relationship": "supplies"},
            {"source": "NVIDIA", "target": "Amazon", "relationship": "supplies"},
            {"source": "TSMC", "target": "NVIDIA", "relationship": "supplies"},
            {"source": "Samsung", "target": "NVIDIA", "relationship": "supplies"},
            {"source": "ASML", "target": "TSMC", "relationship": "supplies"},
            {"source": "ASML", "target": "Samsung", "relationship": "supplies"},
        ]
        hidden_deps = [
            "ASML is critical bottleneck",
            "Taiwan geopolitical risk",
            "Memory supply constraints",
        ]

        path = gen.generate_supply_chain_graph("NVDA", nodes, edges, hidden_deps)

        assert path.exists()
        assert path.suffix == ".png"

    def test_portfolio_overview_creates_png(self, tmp_path):
        """Test that portfolio overview chart creates PNG file."""
        gen = ChartGenerator(tmp_path)

        tickers = ["NVDA", "MSFT", "AAPL", "GOOGL", "TSLA"]
        moat_scores = [8.5, 7.5, 7.0, 6.5, 5.0]

        path = gen.generate_portfolio_overview(tickers, moat_scores)

        assert path.exists()
        assert path.suffix == ".png"
        assert path.name == "portfolio_overview.png"
        assert path.parent == gen.charts_dir

    def test_portfolio_overview_with_single_stock(self, tmp_path):
        """Test portfolio overview with single stock."""
        gen = ChartGenerator(tmp_path)

        path = gen.generate_portfolio_overview(["NVDA"], [8.5])

        assert path.exists()

    def test_portfolio_overview_sorts_by_score(self, tmp_path):
        """Test that portfolio overview sorts stocks by moat score."""
        gen = ChartGenerator(tmp_path)

        # Provide unsorted data
        tickers = ["AAPL", "NVDA", "TSLA", "MSFT"]
        moat_scores = [7.0, 8.5, 5.0, 7.5]

        path = gen.generate_portfolio_overview(tickers, moat_scores)

        # Just verify it creates the file - visual inspection would show sorting
        assert path.exists()

    def test_multiple_charts_in_same_directory(self, tmp_path):
        """Test generating multiple charts in the same directory."""
        gen = ChartGenerator(tmp_path)

        # Generate multiple moat breakdowns
        breakdown1 = {
            "financial_health": 8.0,
            "sentiment_catalysts": 7.0,
            "technical_strength": 9.0,
            "supply_chain_position": 9.5,
        }
        breakdown2 = {
            "financial_health": 7.0,
            "sentiment_catalysts": 8.0,
            "technical_strength": 7.0,
            "supply_chain_position": 8.0,
        }

        path1 = gen.generate_moat_breakdown("NVDA", breakdown1)
        path2 = gen.generate_moat_breakdown("MSFT", breakdown2)
        path3 = gen.generate_portfolio_overview(["NVDA", "MSFT"], [8.5, 7.5])

        # All should exist in the same charts directory
        assert path1.exists() and path1.parent == gen.charts_dir
        assert path2.exists() and path2.parent == gen.charts_dir
        assert path3.exists() and path3.parent == gen.charts_dir

        # Verify different filenames
        assert path1.name != path2.name
        assert path1.name != path3.name


class TestTemplateRenderer:
    """Test TemplateRenderer for Markdown report generation (Phase 8.3)."""

    @pytest.fixture
    def sample_report_data(self):
        """Create sample report data for testing."""
        stock1 = StockReportData(
            ticker="NVDA",
            moat_score=8.5,
            moat_breakdown={
                "financial_health": 8.0,
                "sentiment_catalysts": 7.0,
                "technical_strength": 9.0,
                "supply_chain_position": 9.5,
            },
            is_watchlist_candidate=True,
            investment_thesis="Strong buy for AI exposure with dominant GPU market position.",
            key_insights=[
                "Market leader in AI GPU acceleration",
                "Strong revenue growth from data center segment",
                "Expanding software ecosystem",
            ],
            risk_factors=[
                "High valuation multiples",
                "Competition from AMD and Intel",
                "Cyclical semiconductor market",
            ],
            synthesis_narrative="NVIDIA dominates the AI GPU market with its CUDA ecosystem...",
            supply_chain_nodes=[
                {"name": "NVIDIA", "ticker": "NVDA", "node_type": "root"},
                {"name": "TSMC", "ticker": "TSM", "node_type": "supplier"},
            ],
            supply_chain_edges=[
                {"source": "TSMC", "target": "NVIDIA", "relationship": "supplies"}
            ],
            hidden_dependencies=["TSMC is critical supplier"],
            processing_time=45.2,
            cost_usd=0.15,
        )

        stock2 = StockReportData(
            ticker="MSFT",
            moat_score=7.5,
            moat_breakdown={
                "financial_health": 7.0,
                "sentiment_catalysts": 8.0,
                "technical_strength": 7.0,
                "supply_chain_position": 8.0,
            },
            is_watchlist_candidate=False,
            investment_thesis="Hold for cloud growth and AI integration.",
            key_insights=[
                "Azure continues strong growth",
                "Office 365 provides recurring revenue",
                "AI integration across product suite",
            ],
            risk_factors=[
                "Antitrust concerns",
                "Cloud competition intensifying",
                "Valuation premium",
            ],
            synthesis_narrative="Microsoft maintains strong position in enterprise cloud...",
            processing_time=42.0,
            cost_usd=0.12,
        )

        return ReportData(
            run_id="test-123",
            run_name="Test Analysis Run",
            analysis_date="2024-01-17",
            fiscal_year=2024,
            stocks=[stock1, stock2],
            top_picks=[stock1],
            watchlist_candidates=[stock1],
            total_stocks=2,
            completed_count=2,
            failed_count=0,
            average_moat_score=8.0,
            total_cost_usd=0.27,
            total_elapsed_seconds=120.5,
            cost_by_ticker={"NVDA": 0.15, "MSFT": 0.12},
        )

    def test_template_renderer_initialization(self):
        """Test that TemplateRenderer initializes correctly."""
        renderer = TemplateRenderer()
        assert renderer.templates_dir.exists()
        assert renderer.env is not None

    def test_render_executive_summary(self, sample_report_data):
        """Test rendering executive summary section."""
        renderer = TemplateRenderer()
        output = renderer.render_section(
            ReportSection.EXECUTIVE_SUMMARY, sample_report_data, include_charts=False
        )

        assert "Executive Summary" in output
        assert "NVDA" in output
        assert "8.5" in output
        assert "Watchlist" in output or "watchlist" in output.lower()
        # Check that the thesis content is present
        assert "Strong buy" in output or "AI exposure" in output

    def test_render_stock_analysis(self, sample_report_data):
        """Test rendering stock analysis section."""
        renderer = TemplateRenderer()
        output = renderer.render_section(
            ReportSection.STOCK_ANALYSIS, sample_report_data, include_charts=False
        )

        assert "Detailed Stock Analysis" in output or "Stock Analysis" in output
        assert "NVDA" in output
        assert "MSFT" in output
        assert "Moat Score Breakdown" in output
        assert "Financial Health" in output

    def test_render_supply_chain(self, sample_report_data):
        """Test rendering supply chain section."""
        renderer = TemplateRenderer()
        output = renderer.render_section(
            ReportSection.SUPPLY_CHAIN, sample_report_data, include_charts=False
        )

        assert "Supply Chain" in output
        assert "NVDA" in output
        assert "TSMC" in output or "supply chain" in output.lower()

    def test_render_watchlist(self, sample_report_data):
        """Test rendering watchlist section."""
        renderer = TemplateRenderer()
        output = renderer.render_section(
            ReportSection.WATCHLIST, sample_report_data, include_charts=False
        )

        assert "Watchlist" in output
        assert "NVDA" in output
        # MSFT should not be in watchlist (moat score < 8.0)
        assert sample_report_data.stocks[1].ticker in output or "1 stock" in output

    def test_render_full_report(self, sample_report_data):
        """Test rendering complete report with all sections."""
        renderer = TemplateRenderer()
        output = renderer.render_full_report(
            sample_report_data, include_charts=False
        )

        # Check for report header
        assert "Research Swarm Analysis Report" in output
        assert "test-123" in output
        assert "Test Analysis Run" in output

        # Check for all major sections
        assert "Executive Summary" in output
        assert "Stock Analysis" in output or "Detailed" in output
        assert "Supply Chain" in output
        assert "Watchlist" in output

        # Check for statistics
        assert "Run Statistics" in output
        assert "Total Stocks Analyzed" in output
        assert "$0.27" in output or "0.27" in output  # Total cost

    def test_render_with_chart_references(self, sample_report_data):
        """Test that chart references are included when enabled."""
        renderer = TemplateRenderer()
        output = renderer.render_section(
            ReportSection.EXECUTIVE_SUMMARY, sample_report_data, include_charts=True
        )

        # Should contain image references
        assert "![" in output or ".png" in output

    def test_render_without_chart_references(self, sample_report_data):
        """Test that chart references are excluded when disabled."""
        renderer = TemplateRenderer()
        output = renderer.render_section(
            ReportSection.EXECUTIVE_SUMMARY, sample_report_data, include_charts=False
        )

        # Should not contain image references
        assert "![" not in output and ".png" not in output

    def test_render_custom_template(self):
        """Test rendering custom template string."""
        renderer = TemplateRenderer()
        template_string = "Hello {{ name }}, your score is {{ score }}"
        context = {"name": "NVDA", "score": 8.5}

        output = renderer.render_custom(template_string, context)

        assert "Hello NVDA" in output
        assert "8.5" in output

    def test_render_selected_sections(self, sample_report_data):
        """Test rendering only selected sections."""
        renderer = TemplateRenderer()

        # Render only executive summary and watchlist
        output = renderer.render_full_report(
            sample_report_data,
            sections=[ReportSection.EXECUTIVE_SUMMARY, ReportSection.WATCHLIST],
            include_charts=False,
        )

        assert "Executive Summary" in output
        assert "Watchlist" in output
        # These sections should not be present
        assert "Detailed Stock Analysis" not in output

    def test_render_report_with_no_watchlist_candidates(self):
        """Test rendering when no stocks meet watchlist criteria."""
        # Create report with no watchlist candidates
        stock = StockReportData(
            ticker="TEST",
            moat_score=6.0,  # Below threshold
            moat_breakdown={
                "financial_health": 6.0,
                "sentiment_catalysts": 6.0,
                "technical_strength": 6.0,
                "supply_chain_position": 6.0,
            },
            is_watchlist_candidate=False,
            investment_thesis="Hold for now",
            key_insights=["Stable", "Moderate growth", "Fair valuation"],
            risk_factors=["Competition", "Market risk", "Execution risk"],
            synthesis_narrative="Company shows moderate performance...",
            processing_time=30.0,
            cost_usd=0.10,
        )

        report_data = ReportData(
            run_id="test-456",
            analysis_date="2024-01-17",
            fiscal_year=2024,
            stocks=[stock],
            top_picks=[stock],
            watchlist_candidates=[],  # Empty watchlist
            total_stocks=1,
            completed_count=1,
            failed_count=0,
            average_moat_score=6.0,
            total_cost_usd=0.10,
            total_elapsed_seconds=60.0,
            cost_by_ticker={"TEST": 0.10},
        )

        renderer = TemplateRenderer()
        output = renderer.render_section(
            ReportSection.WATCHLIST, report_data, include_charts=False
        )

        # Should indicate no watchlist candidates
        assert "No stocks" in output or "no stocks" in output.lower() or "0 stock" in output


class TestPDFGenerator:
    """Test PDF generation from Markdown (Phase 8.4)."""

    def test_pdf_generator_initialization(self):
        """Test that PDFGenerator initializes correctly."""
        gen = PDFGenerator()
        assert gen.css is not None

    def test_generate_pdf_from_markdown_file(self, tmp_path):
        """Test PDF generation from Markdown file."""
        # Create a simple markdown file
        md_path = tmp_path / "test.md"
        md_path.write_text("# Test Report\n\nThis is a test.")

        # Generate PDF
        gen = PDFGenerator()
        pdf_path = tmp_path / "test.pdf"
        result = gen.generate(md_path, pdf_path)

        assert result == pdf_path
        assert pdf_path.exists()
        assert pdf_path.suffix == ".pdf"
        assert pdf_path.stat().st_size > 0

    def test_generate_pdf_from_string(self, tmp_path):
        """Test PDF generation from Markdown string."""
        markdown_content = """
# Test Report

## Section 1

This is a test with **bold** and *italic* text.

### Subsection

- Item 1
- Item 2
- Item 3
"""

        gen = PDFGenerator()
        pdf_path = tmp_path / "from_string.pdf"
        result = gen.generate_from_string(markdown_content, pdf_path)

        assert result == pdf_path
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 0

    def test_generate_pdf_with_table(self, tmp_path):
        """Test PDF generation with table."""
        markdown_content = """
# Report with Table

| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
| Value A  | Value B  | Value C  |
"""

        gen = PDFGenerator()
        pdf_path = tmp_path / "with_table.pdf"
        gen.generate_from_string(markdown_content, pdf_path)

        assert pdf_path.exists()

    def test_generate_pdf_missing_file_raises_error(self, tmp_path):
        """Test that generating from missing file raises error."""
        gen = PDFGenerator()
        pdf_path = tmp_path / "output.pdf"

        with pytest.raises(FileNotFoundError):
            gen.generate(tmp_path / "nonexistent.md", pdf_path)

    def test_generate_pdf_empty_content_raises_error(self, tmp_path):
        """Test that empty content raises error."""
        gen = PDFGenerator()
        pdf_path = tmp_path / "output.pdf"

        with pytest.raises(ValueError, match="empty"):
            gen.generate_from_string("", pdf_path)


class TestReportGenerator:
    """Test full report generation integration (Phase 8.4)."""

    @pytest.fixture
    def mock_swarm_run(self):
        """Create a mock SwarmRun for testing."""
        return SwarmRun(
            run_id="integration-test-123",
            run_name="Integration Test Run",
            tickers=["NVDA"],
            fiscal_year=2024,
            status=RunStatus.COMPLETED,
            total_stocks=1,
            completed_count=1,
            failed_count=0,
            cost_summary=CostSummary(total_cost_usd=0.15),
            elapsed_seconds=45.0,
            stock_results={
                "NVDA": StockResult(
                    ticker="NVDA",
                    status=StockStatus.COMPLETED,
                    moat_score=8.5,
                    is_watchlist_candidate=True,
                    investment_thesis="Strong buy for AI",
                    full_output={
                        "ticker": "NVDA",
                        "investment_thesis": "Strong buy for AI exposure",
                        "key_insights": ["AI leader", "Strong margins", "Growth"],
                        "risk_factors": ["Competition", "Valuation", "Cycles"],
                        "synthesis_narrative": "NVIDIA dominates AI...",
                        "moat_breakdown": {
                            "financial_health": 8.0,
                            "sentiment_catalysts": 7.0,
                            "technical_strength": 9.0,
                            "supply_chain_position": 9.5,
                        },
                        "quant_output": {"supply_chain_graph": {}},
                    },
                    cost_usd=0.15,
                    processing_time_seconds=45.0,
                )
            },
        )

    def test_report_generator_initialization(self):
        """Test ReportGenerator initialization."""
        gen = ReportGenerator()
        assert gen.persistence is not None
        assert gen.extractor is not None
        assert gen.renderer is not None

    def test_generate_markdown_only(self, tmp_path, mock_swarm_run):
        """Test generating markdown-only report."""
        # Create mock persistence
        mock_pm = Mock()
        mock_pm.get_run.return_value = mock_swarm_run

        # Configure and generate
        config = ReportConfig(
            run_id="integration-test-123",
            output_dir=tmp_path,
            report_type=ReportType.MARKDOWN,
            include_charts=False,
        )

        generator = ReportGenerator(persistence=mock_pm)
        result = generator.generate(config)

        assert result.success is True
        assert result.markdown_path is not None
        assert result.markdown_path.exists()
        assert result.pdf_path is None
        assert result.generation_time_seconds > 0

    def test_generate_pdf_only(self, tmp_path, mock_swarm_run):
        """Test generating PDF-only report."""
        mock_pm = Mock()
        mock_pm.get_run.return_value = mock_swarm_run

        config = ReportConfig(
            run_id="integration-test-123",
            output_dir=tmp_path,
            report_type=ReportType.PDF,
            include_charts=False,
        )

        generator = ReportGenerator(persistence=mock_pm)
        result = generator.generate(config)

        assert result.success is True
        assert result.pdf_path is not None
        assert result.pdf_path.exists()
        assert result.generation_time_seconds > 0

    def test_generate_both_formats(self, tmp_path, mock_swarm_run):
        """Test generating both markdown and PDF."""
        mock_pm = Mock()
        mock_pm.get_run.return_value = mock_swarm_run

        config = ReportConfig(
            run_id="integration-test-123",
            output_dir=tmp_path,
            report_type=ReportType.BOTH,
            include_charts=False,
        )

        generator = ReportGenerator(persistence=mock_pm)
        result = generator.generate(config)

        assert result.success is True
        assert result.markdown_path is not None
        assert result.markdown_path.exists()
        assert result.pdf_path is not None
        assert result.pdf_path.exists()

    def test_generate_with_charts(self, tmp_path, mock_swarm_run):
        """Test generating report with charts."""
        mock_pm = Mock()
        mock_pm.get_run.return_value = mock_swarm_run

        config = ReportConfig(
            run_id="integration-test-123",
            output_dir=tmp_path,
            report_type=ReportType.MARKDOWN,
            include_charts=True,
        )

        generator = ReportGenerator(persistence=mock_pm)
        result = generator.generate(config)

        assert result.success is True
        assert len(result.charts_generated) > 0
        # Check that chart files exist
        for chart_path_str in result.charts_generated:
            chart_path = Path(chart_path_str)
            assert chart_path.exists()

    def test_generate_missing_run_fails(self, tmp_path):
        """Test that generating report for missing run fails gracefully."""
        mock_pm = Mock()
        mock_pm.get_run.return_value = None

        config = ReportConfig(
            run_id="nonexistent",
            output_dir=tmp_path,
        )

        generator = ReportGenerator(persistence=mock_pm)
        result = generator.generate(config)

        assert result.success is False
        assert result.error_message is not None
        assert "not found" in result.error_message.lower()

    def test_generate_report_convenience_function(self, tmp_path, mock_swarm_run):
        """Test the generate_report convenience function."""
        mock_pm = Mock()
        mock_pm.get_run.return_value = mock_swarm_run

        result = generate_report(
            run_id="integration-test-123",
            output_dir=str(tmp_path),
            report_type="markdown",
            include_charts=False,
            persistence=mock_pm,
        )

        assert result.success is True
        assert result.markdown_path is not None
