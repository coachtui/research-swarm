"""Shared test fixtures for Research Swarm test suite."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def temp_db(tmp_path):
    """Temporary SQLite database for testing."""
    db_path = tmp_path / "test_swarm.db"
    yield db_path
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def temp_cache_db(tmp_path):
    """Temporary cache database."""
    return tmp_path / "test_cache.db"


# ============================================================================
# LLM Mocking Fixtures
# ============================================================================

@pytest.fixture
def mock_anthropic():
    """Mock Anthropic client for testing without API calls."""
    with patch("langchain_anthropic.ChatAnthropic") as mock:
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = Mock(content='{"score": 7.5}')
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_llm_responses():
    """Factory for creating LLM response mocks based on prompt type."""
    def create_mock_response(response_type: str):
        responses = {
            "financial_metrics": {
                "revenue": 100000000,
                "gross_margin": 45.0,
                "operating_margin": 20.0,
                "net_margin": 15.0,
                "debt_to_equity": 0.5,
            },
            "sentiment": {
                "score": 7.5,
                "tone": "positive",
                "catalysts": ["expansion", "new_contract"],
            },
            "synthesis": {
                "narrative": "Strong financial position with growth potential.",
                "key_insights": ["Revenue growing", "Market expanding"],
                "risk_factors": ["Competition", "Regulation"],
            },
            "moat_score": {
                "moat_score": 8.2,
                "financial_health": 8.0,
                "sentiment_catalysts": 7.5,
                "technical_strength": 7.0,
                "supply_chain_position": 9.0,
            },
        }
        return Mock(content=str(responses.get(response_type, {"result": "mock"})))

    return create_mock_response


# ============================================================================
# API Mocking Fixtures
# ============================================================================

@pytest.fixture
def mock_requests():
    """Mock requests library for API testing."""
    with patch("requests.get") as mock_get:
        def configure_response(url, *args, **kwargs):
            response = Mock()
            response.status_code = 200
            response.headers = {"Content-Type": "application/json"}

            if "sec.gov" in url:
                response.json.return_value = {
                    "cik": "0000320193",
                    "entityType": "operating",
                    "sic": "3571",
                    "sicDescription": "Electronic Computers",
                    "filings": {
                        "recent": {
                            "form": ["10-K", "10-Q"],
                            "filingDate": ["2024-10-30", "2024-07-30"],
                            "primaryDocument": ["aapl-20240928.htm", "aapl-20240629.htm"],
                        }
                    }
                }
            elif "newsapi" in url:
                response.json.return_value = {
                    "status": "ok",
                    "totalResults": 10,
                    "articles": [
                        {"title": "Test Article", "description": "Test", "source": {"name": "Test"}},
                    ]
                }
            else:
                response.json.return_value = {}

            return response

        mock_get.side_effect = configure_response
        yield mock_get


# ============================================================================
# Sample Output Fixtures
# ============================================================================

@pytest.fixture
def sample_fundamentalist_output():
    """Sample FundamentalistOutput for testing."""
    return {
        "ticker": "NVDA",
        "fiscal_year": 2024,
        "financial_health_score": 8.5,
        "score_breakdown": {
            "profitability": 9.0,
            "growth": 8.5,
            "balance_sheet": 8.0,
            "cash_flow": 8.5,
            "supply_chain": 8.0,
        },
        "analysis_narrative": "Strong financial position...",
        "customers": ["Microsoft", "Amazon"],
        "suppliers": ["TSMC", "Samsung"],
    }


@pytest.fixture
def sample_news_hound_output():
    """Sample NewsHoundOutput for testing."""
    return {
        "ticker": "NVDA",
        "sentiment_score": 7.5,
        "confidence": 0.8,
        "articles_analyzed": 25,
        "catalysts": [
            {"type": "expansion", "description": "New data center", "impact": "positive"},
        ],
        "sentiment_breakdown": {
            "tone": 8.0,
            "catalyst_impact": 7.0,
            "market_perception": 7.5,
            "forward_looking": 7.5,
        },
    }


@pytest.fixture
def sample_quant_output():
    """Sample QuantOutput for testing."""
    return {
        "ticker": "NVDA",
        "technical_score": 7.8,
        "supply_chain_score": 8.5,
        "quant_score": 8.15,
        "technical_indicators": {
            "sma_50": 500.0,
            "sma_200": 450.0,
            "rsi_14": 55.0,
            "volume_trend": "increasing",
        },
        "supply_chain_graph": {
            "nodes": [
                {"name": "NVIDIA", "ticker": "NVDA", "node_type": "root"},
                {"name": "TSMC", "ticker": "TSM", "node_type": "supplier"},
            ],
            "edges": [
                {"source": "TSMC", "target": "NVIDIA", "relationship": "supplies"},
            ],
            "hidden_dependencies": ["ASML supplies multiple tier-1 foundries"],
        },
    }


@pytest.fixture
def sample_manager_output():
    """Sample ManagerOutput for testing."""
    return {
        "ticker": "NVDA",
        "moat_score": 8.5,
        "moat_breakdown": {
            "financial_health": 8.5,
            "sentiment_catalysts": 7.5,
            "technical_strength": 7.8,
            "supply_chain_position": 8.5,
        },
        "is_watchlist_candidate": True,
        "investment_thesis": "Strong buy candidate...",
        "key_insights": ["Market leader", "Growing demand"],
        "risk_factors": ["Concentration risk", "Geopolitical concerns"],
        "synthesis_narrative": "NVIDIA demonstrates strong fundamentals...",
        "confidence": 0.85,
    }


@pytest.fixture
def sample_swarm_run():
    """Sample SwarmRun for testing."""
    from research_swarm.orchestration.models import SwarmRun, StockResult, CostSummary, RunStatus, StockStatus

    return SwarmRun(
        run_id="test-run-123",
        run_name="test_run",
        tickers=["NVDA", "AAPL"],
        fiscal_year=2024,
        status=RunStatus.COMPLETED,
        total_stocks=2,
        completed_count=2,
        failed_count=0,
        stock_results={
            "NVDA": StockResult(
                ticker="NVDA",
                status=StockStatus.COMPLETED,
                moat_score=8.5,
                is_watchlist_candidate=True,
                investment_thesis="Strong buy",
                cost_usd=0.45,
                processing_time_seconds=30.0,
            ),
            "AAPL": StockResult(
                ticker="AAPL",
                status=StockStatus.COMPLETED,
                moat_score=7.2,
                is_watchlist_candidate=False,
                investment_thesis="Hold",
                cost_usd=0.42,
                processing_time_seconds=28.0,
            ),
        },
        cost_summary=CostSummary(
            total_tokens=50000,
            total_cost_usd=0.87,
            cost_by_agent={
                "fundamentalist": 0.20,
                "news_hound": 0.25,
                "quant": 0.15,
                "manager": 0.27,
            },
            cost_by_ticker={
                "NVDA": 0.45,
                "AAPL": 0.42,
            },
        ),
        elapsed_seconds=58.0,
    )
