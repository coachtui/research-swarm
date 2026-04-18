"""Tests for market context (ES/NQ/DOW) fetcher."""
import pytest
from unittest.mock import MagicMock
import pandas as pd
from datetime import datetime, timezone

from api.services.market_context_service import MarketContextService, MarketContext


class TestMarketContext:
    @pytest.fixture
    def mock_market_client(self):
        client = MagicMock()
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=10, freq='D', tz='UTC')
        df = pd.DataFrame({'Close': [100.0, 101, 102, 103, 100, 99, 98, 101, 103, 105]}, index=dates)
        client.get_historical_data.return_value = df
        return client

    @pytest.fixture
    def service(self, mock_market_client):
        return MarketContextService(market_client=mock_market_client)

    def test_returns_market_context_dataclass(self, service):
        ctx = service.get_context()
        assert isinstance(ctx, MarketContext)

    def test_context_has_three_indices(self, service):
        ctx = service.get_context()
        assert ctx.es_change_pct is not None
        assert ctx.nq_change_pct is not None
        assert ctx.dow_change_pct is not None

    def test_change_pct_is_float(self, service):
        ctx = service.get_context()
        assert isinstance(ctx.es_change_pct, float)
        assert isinstance(ctx.nq_change_pct, float)
        assert isinstance(ctx.dow_change_pct, float)

    def test_returns_none_on_client_failure(self, mock_market_client):
        mock_market_client.get_historical_data.side_effect = Exception("API down")
        service = MarketContextService(market_client=mock_market_client)
        ctx = service.get_context()
        assert ctx.es_change_pct is None
        assert ctx.nq_change_pct is None
        assert ctx.dow_change_pct is None

    def test_to_dict(self, service):
        ctx = service.get_context()
        d = ctx.to_dict()
        assert "es_change_pct" in d
        assert "nq_change_pct" in d
        assert "dow_change_pct" in d
