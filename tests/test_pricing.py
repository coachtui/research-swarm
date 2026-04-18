"""Unit tests for the pricing service."""
import sys
import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

_prisma_stub = types.ModuleType("prisma")
_prisma_stub.Prisma = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("prisma", _prisma_stub)

import pytest
from api.services.pricing import get_latest_price, refresh_position_prices


def _make_stock_result(current_price):
    """Build a mock StockResult with price nested in fullOutput."""
    r = MagicMock()
    if current_price is not None:
        r.fullOutput = {
            "quant_output": {
                "technical_indicators": {
                    "moving_averages": {
                        "current_price": current_price
                    }
                }
            }
        }
    else:
        r.fullOutput = {}
    return r


# ── get_latest_price ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_latest_price_found():
    mock_db = MagicMock()
    mock_db.stockresult.find_first = AsyncMock(return_value=_make_stock_result(142.50))

    with patch("api.services.pricing.get_db", new_callable=AsyncMock, return_value=mock_db):
        price, as_of = await get_latest_price("AAPL", user_id="u1")

    assert price == pytest.approx(142.50)
    assert as_of is not None

@pytest.mark.asyncio
async def test_get_latest_price_no_result():
    mock_db = MagicMock()
    mock_db.stockresult.find_first = AsyncMock(return_value=None)

    with patch("api.services.pricing.get_db", new_callable=AsyncMock, return_value=mock_db):
        price, as_of = await get_latest_price("UNKNOWN", user_id="u1")

    assert price is None
    assert as_of is None

@pytest.mark.asyncio
async def test_get_latest_price_empty_full_output():
    mock_db = MagicMock()
    mock_db.stockresult.find_first = AsyncMock(return_value=_make_stock_result(None))

    with patch("api.services.pricing.get_db", new_callable=AsyncMock, return_value=mock_db):
        price, as_of = await get_latest_price("MSFT", user_id="u1")

    assert price is None
    assert as_of is None


# ── refresh_position_prices ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_position_prices_updates_known():
    mock_db = MagicMock()

    pos1 = MagicMock()
    pos1.id = "pos1"
    pos1.ticker = "NVDA"

    mock_db.position.find_many = AsyncMock(return_value=[pos1])
    mock_db.stockresult.find_first = AsyncMock(return_value=_make_stock_result(875.0))
    mock_db.position.update = AsyncMock()

    with patch("api.services.pricing.get_db", new_callable=AsyncMock, return_value=mock_db):
        updated, skipped = await refresh_position_prices("portfolio1", user_id="u1")

    assert updated == 1
    assert skipped == 0
    mock_db.position.update.assert_called_once()
    call_kwargs = mock_db.position.update.call_args
    assert call_kwargs.kwargs["data"]["lastKnownPrice"] == pytest.approx(875.0)

@pytest.mark.asyncio
async def test_refresh_position_prices_skips_no_result():
    mock_db = MagicMock()

    pos1 = MagicMock()
    pos1.id = "pos1"
    pos1.ticker = "UNKNOWN"

    mock_db.position.find_many = AsyncMock(return_value=[pos1])
    mock_db.stockresult.find_first = AsyncMock(return_value=None)
    mock_db.position.update = AsyncMock()

    with patch("api.services.pricing.get_db", new_callable=AsyncMock, return_value=mock_db):
        updated, skipped = await refresh_position_prices("portfolio1", user_id="u1")

    assert updated == 0
    assert skipped == 1
    mock_db.position.update.assert_not_called()
