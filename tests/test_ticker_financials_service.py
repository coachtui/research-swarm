"""Tests for ticker_financials_service — DB-client seam.

Regression coverage for the closed-loop poisoning incident (2026-07-10):
get_quarterly_financials must accept an injected db client and never fall
back to the shared api.lib.db.get_db() singleton when one is supplied, so
callers running on a throwaway event loop (e.g. the fundamentalist DCF
supplement) can pass a dedicated client scoped to that loop.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from api.services.ticker_financials_service import get_quarterly_financials


def _row(period="2026-Q1"):
    return MagicMock(
        period=period,
        periodEnd=datetime(2026, 3, 31, tzinfo=timezone.utc),
        source="yfinance",
        revenue=100.0,
        operatingIncome=10.0,
        operatingMargin=10.0,
        grossProfit=50.0,
        netIncome=8.0,
        ebitda=12.0,
        operatingCashFlow=15.0,
        capex=5.0,
        freeCashFlow=10.0,
        totalDebt=20.0,
        cash=30.0,
    )


def _mock_db_with_full_cache(min_quarters=8):
    """A db mock whose cache already satisfies min_quarters — no upstream fetch."""
    db = MagicMock()
    db.tickerfinancials = MagicMock()
    db.tickerfinancials.find_many = AsyncMock(
        return_value=[_row() for _ in range(min_quarters)]
    )
    return db


class TestDbSeam:
    @pytest.mark.asyncio
    async def test_injected_db_used_exclusively_shared_client_never_touched(self):
        mock_db = _mock_db_with_full_cache(min_quarters=8)

        with patch("api.lib.db.get_db", side_effect=AssertionError(
            "shared client must not be used when db is injected"
        )):
            rows = await get_quarterly_financials("NVDA", min_quarters=8, db=mock_db)

        assert len(rows) == 8
        mock_db.tickerfinancials.find_many.assert_awaited()

    @pytest.mark.asyncio
    async def test_db_none_falls_back_to_shared_get_db(self):
        mock_db = _mock_db_with_full_cache(min_quarters=8)

        with patch("api.lib.db.get_db", new=AsyncMock(return_value=mock_db)) as mock_get_db:
            rows = await get_quarterly_financials("NVDA", min_quarters=8, db=None)

        mock_get_db.assert_awaited_once()
        assert len(rows) == 8
