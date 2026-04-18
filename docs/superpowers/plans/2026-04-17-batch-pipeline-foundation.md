# Batch Pipeline Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the weekly batch pipeline that screens 500+ stocks, runs full analysis on the top 25-30 candidates, and stores all signals in a `WeeklySignal` table — powering every downstream monetization surface from a single Sunday-night compute cycle.

**Architecture:** A new Inngest cron function fires Sunday nights, runs a two-stage pipeline (cheap screener → full LangGraph analysis), and writes a `WeeklySignal` row per ticker. A new `WeeklySignalService` handles extraction and alert diffing. All downstream surfaces (leaderboard, alerts, portfolio scan, teasers) query this table — no re-computation.

**Tech Stack:** Prisma ORM (asyncio), FastAPI, Inngest Python SDK, LangGraph agents, yfinance, OpenInsider, pytest/pytest-asyncio, anthropic SDK.

> **Cost optimization note:** The spec references Claude Batch API (50% discount). Integrating Batch API requires restructuring the LangGraph agents to decouple data-gathering from inference — a significant refactor beyond Phase 0 scope. Task 8 instead implements prompt caching, which is a zero-refactor ~15-20% cost reduction. Full Batch API migration is deferred to Phase 3.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `db/schema.prisma` (modify) | Add `WeeklySignal` model |
| Create | `research_swarm/data/universes/sp500_universe.json` | Curated ticker universe (~200 tickers) |
| Create | `research_swarm/data/screener.py` | Stage 1 screener — scores and ranks tickers |
| Create | `api/services/market_context_service.py` | Fetch ES/NQ/DOW week-over-week changes |
| Create | `api/services/weekly_signal_service.py` | Extract signals from analysis result, store/diff WeeklySignal rows |
| Create | `inngest/functions/weekly_batch.py` | Inngest cron function — orchestrates full weekly pipeline |
| Modify | `inngest/index.py` | Register weekly_batch function |
| Modify | `research_swarm/agents/manager/graph.py` (or LLM client) | Enable prompt caching |
| Create | `tests/test_screener.py` | Screener unit tests |
| Create | `tests/test_market_context_service.py` | Market context unit tests |
| Create | `tests/test_weekly_signal_service.py` | Signal extraction + diff unit tests |

---

## Task 1: WeeklySignal Prisma Model

**Files:**
- Modify: `db/schema.prisma`

- [ ] **Step 1: Add WeeklySignal model to schema.prisma**

Open `db/schema.prisma` and add the following model at the end of the file:

```prisma
model WeeklySignal {
  id                  String   @id @default(cuid())
  ticker              String
  runDate             DateTime // The date the batch ran (Sunday midnight UTC)

  // Core verdict
  verdict             String?  // "buy" | "hold" | "avoid"
  currentPrice        Float?
  fairValue           Float?
  fairValueGapPct     Float?   // (fairValue - currentPrice) / currentPrice * 100

  // Probabilistic signals
  evProbability       Float?   // 0.0–1.0
  stopLossProbability Float?   // 0.0–1.0

  // Activity signals
  insiderScore        Float?   // 0.0–10.0
  darkPoolScore       Float?   // 0.0–10.0
  sentimentScore      Float?   // 0.0–10.0

  // Text
  synthesisSummary    String?  // 2–3 sentence thesis lead for teasers/leaderboard
  catalystSummary     String?  // key catalyst bullet points

  // Position
  positionSizeRec     String?  // e.g. "2.5% initial, scale to 5%"

  // Market context (week-over-week %)
  esChangePct         Float?   // S&P 500
  nqChangePct         Float?   // Nasdaq 100
  dowChangePct        Float?   // Dow Jones

  // Alert diffing — prior week values
  priorVerdict        String?
  priorEvProbability  Float?

  // Screener metadata
  screenerScore       Float?   // Stage 1 score that selected this ticker

  createdAt           DateTime @default(now())
  updatedAt           DateTime @updatedAt

  @@unique([ticker, runDate])
  @@index([runDate])
  @@index([ticker])
}
```

- [ ] **Step 2: Generate and apply migration**

```bash
cd /Users/tui/research-swarm
prisma migrate dev --name add_weekly_signal
```

Expected output:
```
✔ Generated Prisma Client
✔ Applying migration `..._add_weekly_signal`
```

- [ ] **Step 3: Verify the table exists**

```bash
prisma db pull --force 2>&1 | grep -i weekly_signal
# Should show: model WeeklySignal
```

- [ ] **Step 4: Commit**

```bash
git add db/schema.prisma db/migrations/
git commit -m "feat: add WeeklySignal table for batch pipeline storage"
```

---

## Task 2: Stock Universe File

**Files:**
- Create: `research_swarm/data/universes/sp500_universe.json`

This file is the universe screened each week. Start with ~200 high-attention tickers (S&P 500 large caps + sector representatives). The screener will score and rank these down to 25-30 candidates for full analysis.

- [ ] **Step 1: Create the universe directory and file**

```bash
mkdir -p /Users/tui/research-swarm/research_swarm/data/universes
```

Create `research_swarm/data/universes/sp500_universe.json`:

```json
{
  "version": "1.0",
  "description": "S&P 500 screener universe — updated quarterly",
  "tickers": [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK.B",
    "UNH", "LLY", "JPM", "V", "XOM", "MA", "AVGO", "PG", "HD", "COST",
    "MRK", "ABBV", "CVX", "KO", "PEP", "ADBE", "WMT", "BAC", "CRM",
    "TMO", "ACN", "MCD", "CSCO", "NKE", "ABT", "TXN", "DHR", "NEE",
    "PM", "LIN", "ORCL", "RTX", "MS", "AMGN", "INTU", "GS", "ISRG",
    "CAT", "SYK", "AMAT", "BKNG", "PLD", "T", "MDT", "ADP", "GILD",
    "BLK", "ADI", "LRCX", "DE", "NOW", "MDLZ", "REGN", "AMT", "PANW",
    "VRTX", "C", "MMC", "SBUX", "TJX", "ETN", "ZTS", "BSX", "IBM",
    "CB", "KLAC", "SNPS", "AXP", "CDNS", "CMG", "WM", "SLB", "MO",
    "SO", "FIS", "NOC", "EOG", "PGR", "HCA", "DUK", "MCK", "GD", "ITW",
    "EW", "MSI", "APH", "EMR", "NSC", "PSA", "CTAS", "USB", "ROP",
    "FCX", "HUM", "F", "GM", "INTC", "AMD", "MU", "QCOM", "UBER",
    "LYFT", "SNAP", "RBLX", "COIN", "HOOD", "PLTR", "SOFI", "RIVN",
    "LCID", "NIO", "XPEV", "LI", "SHOP", "SQ", "PYPL", "DKNG", "MGM",
    "WYNN", "LVS", "CZR", "NFLX", "DIS", "WBD", "PARA", "CMCSA",
    "CHTR", "TMUS", "VZ", "AMC", "GE", "BA", "LMT", "RCL", "CCL",
    "DAL", "UAL", "AAL", "NCLH", "MAR", "HLT", "H", "ABNB", "EXPE",
    "PTON", "BYND", "MRNA", "BNTX", "PFE", "JNJ", "AZN", "NVO",
    "DXCM", "IDXX", "ILMN", "VRTX", "BIIB", "ALGN", "IQV", "CNC",
    "CVS", "CI", "ELV", "HIG", "ALL", "TRV", "MET", "PRU", "WFC",
    "PNC", "SCHW", "ICE", "CME", "NDAQ", "MELI", "SE", "GRAB",
    "BABA", "JD", "PDD", "TCEHY", "NTES", "BIDU", "TSM"
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add research_swarm/data/universes/sp500_universe.json
git commit -m "feat: add S&P 500 screener universe file"
```

---

## Task 3: StockScreener (TDD)

**Files:**
- Create: `research_swarm/data/screener.py`
- Create: `tests/test_screener.py`

The screener scores each ticker on cheap signals (no Claude calls) and returns the top N candidates for full analysis.

- [ ] **Step 1: Write failing tests first**

Create `tests/test_screener.py`:

```python
"""Tests for Stage 1 stock screener."""
import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from research_swarm.data.screener import StockScreener, ScreenerSignals, score_ticker


class TestScorerFunction:
    def test_insider_buying_adds_points(self):
        signals = ScreenerSignals(
            ticker="AAPL",
            has_insider_buying=True,
            days_to_earnings=None,
            weekly_price_change_pct=0.0,
        )
        assert score_ticker(signals) >= 3.0

    def test_no_signals_scores_zero(self):
        signals = ScreenerSignals(
            ticker="AAPL",
            has_insider_buying=False,
            days_to_earnings=None,
            weekly_price_change_pct=0.0,
        )
        assert score_ticker(signals) == 0.0

    def test_earnings_this_week_adds_points(self):
        signals = ScreenerSignals(
            ticker="AAPL",
            has_insider_buying=False,
            days_to_earnings=2,
            weekly_price_change_pct=0.0,
        )
        assert score_ticker(signals) >= 2.0

    def test_earnings_next_week_scores_less_than_this_week(self):
        this_week = ScreenerSignals("X", False, 2, 0.0)
        next_week = ScreenerSignals("X", False, 8, 0.0)
        assert score_ticker(this_week) > score_ticker(next_week)

    def test_big_price_move_adds_points(self):
        signals = ScreenerSignals(
            ticker="AAPL",
            has_insider_buying=False,
            days_to_earnings=None,
            weekly_price_change_pct=12.0,
        )
        assert score_ticker(signals) >= 2.0

    def test_negative_price_move_also_adds_points(self):
        """Large drops are also screener-worthy."""
        signals = ScreenerSignals(
            ticker="AAPL",
            has_insider_buying=False,
            days_to_earnings=None,
            weekly_price_change_pct=-11.0,
        )
        assert score_ticker(signals) >= 2.0


class TestStockScreener:
    @pytest.fixture
    def mock_market_client(self):
        client = MagicMock()
        client.calculate_return.return_value = 3.0  # 3% weekly return
        client.get_earnings_dates.return_value = None  # No upcoming earnings
        return client

    @pytest.fixture
    def mock_insider_client(self):
        client = MagicMock()
        client.get_insider_transactions.return_value = []
        return client

    @pytest.fixture
    def screener(self, mock_market_client, mock_insider_client):
        return StockScreener(
            market_client=mock_market_client,
            insider_client=mock_insider_client,
        )

    def test_returns_list_of_strings(self, screener):
        candidates = screener.screen(["AAPL", "MSFT", "NVDA"])
        assert isinstance(candidates, list)
        assert all(isinstance(t, str) for t in candidates)

    def test_respects_max_candidates(self, screener):
        universe = [f"T{i:03d}" for i in range(100)]
        candidates = screener.screen(universe, max_candidates=10)
        assert len(candidates) <= 10

    def test_ticker_with_insider_buying_ranks_higher(self, mock_market_client):
        def mock_insider_transactions(ticker, **kwargs):
            if ticker == "NVDA":
                return [{"transaction_type": "P", "value": 500000, "date": "2026-04-10"}]
            return []

        mock_insider = MagicMock()
        mock_insider.get_insider_transactions.side_effect = mock_insider_transactions

        screener = StockScreener(
            market_client=mock_market_client,
            insider_client=mock_insider,
        )
        candidates = screener.screen(["AAPL", "NVDA"], max_candidates=2)
        assert candidates[0] == "NVDA"

    def test_handles_client_errors_gracefully(self, screener, mock_market_client):
        mock_market_client.calculate_return.side_effect = Exception("API error")
        # Should not raise — failed tickers get score 0
        candidates = screener.screen(["AAPL", "MSFT"])
        assert isinstance(candidates, list)

    def test_loads_universe_from_json(self, screener):
        tickers = StockScreener.load_universe()
        assert len(tickers) > 50
        assert all(isinstance(t, str) for t in tickers)
        assert "AAPL" in tickers
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/tui/research-swarm
python -m pytest tests/test_screener.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'research_swarm.data.screener'`

- [ ] **Step 3: Implement screener**

Create `research_swarm/data/screener.py`:

```python
"""Stage 1 stock screener — cheap signal scoring to select analysis candidates."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_UNIVERSE_PATH = Path(__file__).parent / "universes" / "sp500_universe.json"


@dataclass
class ScreenerSignals:
    ticker: str
    has_insider_buying: bool
    days_to_earnings: Optional[int]  # None = no upcoming earnings in 30d
    weekly_price_change_pct: Optional[float]  # None = data unavailable


def score_ticker(signals: ScreenerSignals) -> float:
    """Score a ticker's screener signals. Higher = more worth analyzing."""
    score = 0.0

    if signals.has_insider_buying:
        score += 3.0

    if signals.days_to_earnings is not None:
        if signals.days_to_earnings <= 3:
            score += 2.5
        elif signals.days_to_earnings <= 7:
            score += 2.0
        elif signals.days_to_earnings <= 14:
            score += 1.0

    if signals.weekly_price_change_pct is not None:
        abs_change = abs(signals.weekly_price_change_pct)
        if abs_change > 10:
            score += 2.0
        elif abs_change > 5:
            score += 1.0

    return score


class StockScreener:
    """
    Stage 1 screener: scores a universe of tickers on cheap signals
    and returns the top N candidates for full LangGraph analysis.
    """

    def __init__(self, market_client: Any, insider_client: Any) -> None:
        self._market = market_client
        self._insider = insider_client

    @staticmethod
    def load_universe() -> List[str]:
        """Load the ticker universe from the JSON file."""
        with open(_UNIVERSE_PATH) as f:
            data = json.load(f)
        return [str(t).upper().strip() for t in data["tickers"]]

    def _collect_signals(self, ticker: str) -> ScreenerSignals:
        """Collect cheap signals for a single ticker. Never raises."""
        has_insider_buying = False
        days_to_earnings: Optional[int] = None
        weekly_price_change_pct: Optional[float] = None

        try:
            transactions = self._insider.get_insider_transactions(ticker, days_back=7)
            has_insider_buying = any(
                str(t.get("transaction_type", "")).upper() == "P"
                for t in (transactions or [])
            )
        except Exception as e:
            logger.debug("Insider data error for %s: %s", ticker, e)

        try:
            weekly_price_change_pct = self._market.calculate_return(ticker, days=7)
        except Exception as e:
            logger.debug("Price data error for %s: %s", ticker, e)

        try:
            earnings_df = self._market.get_earnings_dates(ticker)
            if earnings_df is not None and not earnings_df.empty:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                future_dates = [
                    d for d in earnings_df.index
                    if hasattr(d, "tzinfo") and d > now
                ]
                if future_dates:
                    next_earnings = min(future_dates)
                    days_to_earnings = (next_earnings - now).days
        except Exception as e:
            logger.debug("Earnings data error for %s: %s", ticker, e)

        return ScreenerSignals(
            ticker=ticker,
            has_insider_buying=has_insider_buying,
            days_to_earnings=days_to_earnings,
            weekly_price_change_pct=weekly_price_change_pct,
        )

    def screen(self, universe: List[str], max_candidates: int = 25) -> List[str]:
        """
        Score and rank tickers from universe, return top max_candidates.

        Args:
            universe: List of ticker symbols to evaluate.
            max_candidates: Maximum number of tickers to return for full analysis.

        Returns:
            Sorted list of tickers (highest score first), length <= max_candidates.
        """
        scored: List[tuple[float, str]] = []

        for ticker in universe:
            signals = self._collect_signals(ticker)
            score = score_ticker(signals)
            scored.append((score, ticker))
            logger.debug("Screener %s: score=%.1f", ticker, score)

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ticker for _, ticker in scored[:max_candidates]]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_screener.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add research_swarm/data/screener.py tests/test_screener.py
git commit -m "feat: add Stage 1 StockScreener with insider/earnings/price scoring"
```

---

## Task 4: MarketContextService (TDD)

**Files:**
- Create: `api/services/market_context_service.py`
- Create: `tests/test_market_context_service.py`

Fetches ES/NQ/DOW week-over-week percentage changes to embed in each weekly signal.

- [ ] **Step 1: Write failing tests**

Create `tests/test_market_context_service.py`:

```python
"""Tests for market context (ES/NQ/DOW) fetcher."""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from api.services.market_context_service import MarketContextService, MarketContext


class TestMarketContext:
    @pytest.fixture
    def mock_market_client(self):
        client = MagicMock()
        # Returns a DataFrame with 'Close' column
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_market_context_service.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'api.services.market_context_service'`

- [ ] **Step 3: Implement MarketContextService**

Create `api/services/market_context_service.py`:

```python
"""Fetches ES/NQ/DOW market context for embedding in weekly signals."""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any, Optional

logger = logging.getLogger(__name__)

# yfinance ticker symbols for each index
_ES_TICKER = "^GSPC"   # S&P 500
_NQ_TICKER = "^NDX"    # Nasdaq 100
_DOW_TICKER = "^DJI"   # Dow Jones Industrial Average


@dataclass
class MarketContext:
    es_change_pct: Optional[float]
    nq_change_pct: Optional[float]
    dow_change_pct: Optional[float]

    def to_dict(self) -> dict:
        return asdict(self)


class MarketContextService:
    def __init__(self, market_client: Any) -> None:
        self._market = market_client

    def _week_over_week_change(self, ticker: str) -> Optional[float]:
        """Return the 5-trading-day price change percentage for a ticker."""
        try:
            df = self._market.get_historical_data(ticker, period="1mo")
            if df is None or df.empty or len(df) < 6:
                return None
            close = df["Close"].dropna()
            if len(close) < 6:
                return None
            current = float(close.iloc[-1])
            prior = float(close.iloc[-6])  # ~5 trading days ago
            if prior == 0:
                return None
            return round((current - prior) / prior * 100, 2)
        except Exception as e:
            logger.warning("Market context error for %s: %s", ticker, e)
            return None

    def get_context(self) -> MarketContext:
        """Fetch week-over-week changes for ES, NQ, and DOW."""
        return MarketContext(
            es_change_pct=self._week_over_week_change(_ES_TICKER),
            nq_change_pct=self._week_over_week_change(_NQ_TICKER),
            dow_change_pct=self._week_over_week_change(_DOW_TICKER),
        )
```

- [ ] **Step 4: Run tests to confirm passing**

```bash
python -m pytest tests/test_market_context_service.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/services/market_context_service.py tests/test_market_context_service.py
git commit -m "feat: add MarketContextService for ES/NQ/DOW weekly changes"
```

---

## Task 5: Inspect Analysis Output + WeeklySignalService (TDD)

**Files:**
- Create: `api/services/weekly_signal_service.py`
- Create: `tests/test_weekly_signal_service.py`

Before writing extraction code, inspect a real analysis result to get exact output keys.

- [ ] **Step 1: Inspect actual analysis output structure**

Run this one-time inspection (costs ~$0.50):

```bash
cd /Users/tui/research-swarm
python -c "
import asyncio, json
from research_swarm.services.analysis_service import run_stock_analysis

async def main():
    result = await run_stock_analysis(
        ticker='AAPL',
        quarters=['Q4_2024'],
        news_days_back=7,
        user_id='system'
    )
    print('STATUS:', result.get('status'))
    print('TOP-LEVEL KEYS:', list(result.keys()))
    # Print a truncated view of the full output
    full = result.get('full_output') or result.get('fullOutput') or result
    print('FULL OUTPUT KEYS:', list(full.keys()) if isinstance(full, dict) else type(full))
    print(json.dumps(result, indent=2, default=str)[:8000])

asyncio.run(main())
" 2>&1 | tee /tmp/analysis_output_sample.txt
```

Study the output and note the exact key names for: verdict, fair_value, current_price, ev_probability, stop_loss_probability / stop_probability, insider_score, dark_pool_score, synthesis/summary text, catalyst. Update the extraction keys in the implementation below to match what you observe.

- [ ] **Step 2: Write failing tests**

Create `tests/test_weekly_signal_service.py`:

```python
"""Tests for WeeklySignalService — extraction, storage, and alert diffing."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from api.services.weekly_signal_service import WeeklySignalService, extract_signals_from_result


SAMPLE_RESULT = {
    "status": "completed",
    "verdict": "buy",
    "fair_value": 213.50,
    "current_price": 175.20,
    "ev_probability": 0.72,
    "stop_probability": 0.15,
    "insider_score": 7.2,
    "dark_pool_score": 5.8,
    "sentiment_score": 6.5,
    "investment_thesis": "Apple's services segment is accelerating revenue per device. "
                         "Management buyback program reduces float aggressively. "
                         "Key risk: China sales represent 19% of revenue.",
    "catalyst_summary": "Services growth, buyback acceleration",
    "position_size": "2.5% initial",
    "moat_score": 7.8,
}


class TestExtractSignalsFromResult:
    def test_extracts_verdict(self):
        signals = extract_signals_from_result(SAMPLE_RESULT, ticker="AAPL")
        assert signals["verdict"] == "buy"

    def test_extracts_fair_value_gap(self):
        signals = extract_signals_from_result(SAMPLE_RESULT, ticker="AAPL")
        # (213.50 - 175.20) / 175.20 * 100 = ~21.8%
        assert signals["fair_value_gap_pct"] is not None
        assert abs(signals["fair_value_gap_pct"] - 21.8) < 0.5

    def test_extracts_ev_probability(self):
        signals = extract_signals_from_result(SAMPLE_RESULT, ticker="AAPL")
        assert signals["ev_probability"] == 0.72

    def test_extracts_stop_loss_probability(self):
        signals = extract_signals_from_result(SAMPLE_RESULT, ticker="AAPL")
        assert signals["stop_loss_probability"] == 0.15

    def test_extracts_synthesis_as_first_two_sentences(self):
        signals = extract_signals_from_result(SAMPLE_RESULT, ticker="AAPL")
        summary = signals["synthesis_summary"]
        assert summary is not None
        assert len(summary) < len(SAMPLE_RESULT["investment_thesis"])
        # Should contain at least the first sentence
        assert "services segment" in summary

    def test_handles_missing_fields_gracefully(self):
        minimal = {"status": "completed", "verdict": "hold"}
        signals = extract_signals_from_result(minimal, ticker="AAPL")
        assert signals["verdict"] == "hold"
        assert signals["fair_value_gap_pct"] is None
        assert signals["ev_probability"] is None

    def test_handles_failed_result(self):
        failed = {"status": "failed", "error_message": "timeout"}
        signals = extract_signals_from_result(failed, ticker="AAPL")
        assert signals is None


class TestWeeklySignalService:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.weeklysignal = MagicMock()
        db.weeklysignal.create = AsyncMock()
        db.weeklysignal.find_first = AsyncMock(return_value=None)
        return db

    @pytest.fixture
    def market_context(self):
        from api.services.market_context_service import MarketContext
        return MarketContext(es_change_pct=1.2, nq_change_pct=2.3, dow_change_pct=0.8)

    @pytest.mark.asyncio
    async def test_store_signal_creates_db_record(self, mock_db, market_context):
        service = WeeklySignalService(db=mock_db)
        await service.store_signal(
            ticker="AAPL",
            result=SAMPLE_RESULT,
            run_date=datetime(2026, 4, 13, tzinfo=timezone.utc),
            screener_score=4.5,
            market_context=market_context,
        )
        mock_db.weeklysignal.create.assert_called_once()
        call_data = mock_db.weeklysignal.create.call_args[1]["data"]
        assert call_data["ticker"] == "AAPL"
        assert call_data["verdict"] == "buy"

    @pytest.mark.asyncio
    async def test_store_signal_includes_market_context(self, mock_db, market_context):
        service = WeeklySignalService(db=mock_db)
        await service.store_signal(
            ticker="AAPL",
            result=SAMPLE_RESULT,
            run_date=datetime(2026, 4, 13, tzinfo=timezone.utc),
            screener_score=4.5,
            market_context=market_context,
        )
        call_data = mock_db.weeklysignal.create.call_args[1]["data"]
        assert call_data["esChangePct"] == 1.2
        assert call_data["nqChangePct"] == 2.3

    @pytest.mark.asyncio
    async def test_prior_week_verdict_is_attached_when_present(self, mock_db, market_context):
        prior = MagicMock()
        prior.verdict = "hold"
        prior.evProbability = 0.55
        mock_db.weeklysignal.find_first = AsyncMock(return_value=prior)

        service = WeeklySignalService(db=mock_db)
        await service.store_signal(
            ticker="AAPL",
            result=SAMPLE_RESULT,
            run_date=datetime(2026, 4, 13, tzinfo=timezone.utc),
            screener_score=4.5,
            market_context=market_context,
        )
        call_data = mock_db.weeklysignal.create.call_args[1]["data"]
        assert call_data["priorVerdict"] == "hold"
        assert call_data["priorEvProbability"] == 0.55

    @pytest.mark.asyncio
    async def test_skips_failed_result(self, mock_db, market_context):
        service = WeeklySignalService(db=mock_db)
        await service.store_signal(
            ticker="AAPL",
            result={"status": "failed"},
            run_date=datetime(2026, 4, 13, tzinfo=timezone.utc),
            screener_score=2.0,
            market_context=market_context,
        )
        mock_db.weeklysignal.create.assert_not_called()
```

- [ ] **Step 3: Run to confirm failure**

```bash
python -m pytest tests/test_weekly_signal_service.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError`

- [ ] **Step 4: Implement WeeklySignalService**

Create `api/services/weekly_signal_service.py`:

```python
"""Extracts signals from analysis results and persists WeeklySignal records."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from api.services.market_context_service import MarketContext

logger = logging.getLogger(__name__)


def _first_n_sentences(text: str, n: int = 2) -> str:
    """Extract the first n sentences from a block of text."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return " ".join(sentences[:n])


def extract_signals_from_result(
    result: Dict[str, Any],
    ticker: str,
) -> Optional[Dict[str, Any]]:
    """
    Extract WeeklySignal fields from a raw analysis result dict.

    Returns None if the result has status != 'completed'.

    NOTE: Key names below (fair_value, ev_probability, etc.) were confirmed
    by inspecting a real analysis output in Task 5 Step 1. If the analysis
    engine changes its output schema, update these keys accordingly.
    """
    if result.get("status") != "completed":
        return None

    verdict = result.get("verdict")
    fair_value = result.get("fair_value")
    current_price = result.get("current_price")
    ev_probability = result.get("ev_probability")
    stop_loss_probability = result.get("stop_probability") or result.get("stop_loss_probability")
    insider_score = result.get("insider_score")
    dark_pool_score = result.get("dark_pool_score")
    sentiment_score = result.get("sentiment_score")
    investment_thesis = result.get("investment_thesis") or ""
    catalyst_summary = result.get("catalyst_summary")
    position_size_rec = result.get("position_size") or result.get("position_size_recommendation")

    # Compute fair value gap
    fair_value_gap_pct: Optional[float] = None
    if fair_value is not None and current_price and current_price != 0:
        fair_value_gap_pct = round((fair_value - current_price) / current_price * 100, 2)

    # Extract synthesis summary (first 2 sentences of thesis)
    synthesis_summary = _first_n_sentences(investment_thesis, n=2) if investment_thesis else None

    return {
        "verdict": verdict,
        "currentPrice": current_price,
        "fairValue": fair_value,
        "fairValueGapPct": fair_value_gap_pct,
        "evProbability": ev_probability,
        "stopLossProbability": stop_loss_probability,
        "insiderScore": insider_score,
        "darkPoolScore": dark_pool_score,
        "sentimentScore": sentiment_score,
        "synthesisSummary": synthesis_summary,
        "catalystSummary": catalyst_summary,
        "positionSizeRec": position_size_rec,
    }


class WeeklySignalService:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def _get_prior_week_signal(
        self, ticker: str, before: datetime
    ) -> Optional[Any]:
        """Fetch the most recent WeeklySignal for ticker before the given date."""
        try:
            return await self._db.weeklysignal.find_first(
                where={
                    "ticker": ticker,
                    "runDate": {"lt": before},
                },
                order={"runDate": "desc"},
            )
        except Exception as e:
            logger.warning("Could not fetch prior signal for %s: %s", ticker, e)
            return None

    async def store_signal(
        self,
        ticker: str,
        result: Dict[str, Any],
        run_date: datetime,
        screener_score: float,
        market_context: MarketContext,
    ) -> None:
        """
        Extract signals from an analysis result and upsert a WeeklySignal row.

        Silently skips if the result failed.
        """
        signals = extract_signals_from_result(result, ticker=ticker)
        if signals is None:
            logger.info("Skipping %s — analysis did not complete", ticker)
            return

        prior = await self._get_prior_week_signal(ticker, before=run_date)

        data = {
            "ticker": ticker,
            "runDate": run_date,
            "screenerScore": screener_score,
            # Core signals
            **signals,
            # Market context
            "esChangePct": market_context.es_change_pct,
            "nqChangePct": market_context.nq_change_pct,
            "dowChangePct": market_context.dow_change_pct,
            # Alert diffing
            "priorVerdict": prior.verdict if prior else None,
            "priorEvProbability": prior.evProbability if prior else None,
        }

        try:
            await self._db.weeklysignal.create(data=data)
            logger.info("Stored WeeklySignal for %s (verdict=%s)", ticker, signals.get("verdict"))
        except Exception as e:
            logger.error("Failed to store WeeklySignal for %s: %s", ticker, e)
```

- [ ] **Step 5: Run tests to confirm passing**

```bash
python -m pytest tests/test_weekly_signal_service.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add api/services/weekly_signal_service.py tests/test_weekly_signal_service.py
git commit -m "feat: add WeeklySignalService for signal extraction and storage"
```

---

## Task 6: Weekly Batch Inngest Function

**Files:**
- Create: `inngest/functions/weekly_batch.py`

This is the cron function that orchestrates the full Sunday-night pipeline: screener → analysis → signal storage.

- [ ] **Step 1: Inspect the existing analyze_stock.py for patterns**

```bash
cat /Users/tui/research-swarm/inngest/functions/analyze_stock.py
```

Note how `step.run()` is called, how the Inngest client is imported, and how the DB is accessed. Match those patterns.

- [ ] **Step 2: Create weekly_batch.py**

Create `inngest/functions/weekly_batch.py`:

```python
"""
Weekly batch pipeline: screener → full analysis → signal storage.

Fires every Sunday night (Monday 03:00 UTC = Sunday 11:00 PM ET).
Each ticker is analyzed in a separate Inngest step, giving each up to
15 minutes of execution time. The function is fully durable — if it
restarts, already-completed steps are not re-executed.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from inngest import Inngest

from api.lib.db import get_db
from api.services.analysis_service import run_stock_analysis
from api.services.market_context_service import MarketContextService
from api.services.weekly_signal_service import WeeklySignalService
from research_swarm.data.market_data_client import MarketDataClient
from research_swarm.data.openinsider_client import OpenInsiderClient
from research_swarm.data.screener import StockScreener

logger = logging.getLogger(__name__)

inngest = Inngest(
    app_id="research-swarm",
    signing_key=os.getenv("INNGEST_SIGNING_KEY"),
    event_key=os.getenv("INNGEST_EVENT_KEY"),
)

# System user for batch-initiated analyses (set BATCH_SYSTEM_USER_ID in .env / Vercel)
BATCH_USER_ID = os.getenv("BATCH_SYSTEM_USER_ID", "")
if not BATCH_USER_ID:
    raise RuntimeError(
        "BATCH_SYSTEM_USER_ID env var is not set. "
        "Set it to the UUID of your admin user in the User table."
    )

# Analysis parameters for weekly batch
_QUARTERS = ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"]
_NEWS_DAYS_BACK = 30
_MAX_CANDIDATES = int(os.getenv("BATCH_MAX_CANDIDATES", "25"))


@inngest.create_function(
    fn_id="weekly-batch",
    trigger=inngest.trigger.cron(cron="0 3 * * 1"),  # Monday 03:00 UTC = Sunday 11:00 PM ET
    name="Weekly Batch Analysis",
    retries=1,
)
async def weekly_batch(ctx: Any, step: Any) -> Dict[str, Any]:
    """
    Full weekly analysis pipeline.

    Steps:
      1. Run Stage 1 screener — selects 25-30 tickers from universe
      2. Fetch market context (ES/NQ/DOW)
      3. Analyze each selected ticker (one step per ticker)
      4. Store all signals in WeeklySignal table
    """
    run_date = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # ── Step 1: Screen the universe ──────────────────────────────────────────
    async def run_screener() -> List[str]:
        market_client = MarketDataClient()
        insider_client = OpenInsiderClient()
        screener = StockScreener(
            market_client=market_client,
            insider_client=insider_client,
        )
        universe = StockScreener.load_universe()
        candidates = screener.screen(universe, max_candidates=_MAX_CANDIDATES)
        logger.info("Screener selected %d candidates: %s", len(candidates), candidates)
        return candidates

    candidates: List[str] = await step.run("screen-universe", run_screener)

    if not candidates:
        logger.error("Screener returned no candidates — aborting batch")
        return {"status": "aborted", "reason": "empty_candidates"}

    # ── Step 2: Market context ───────────────────────────────────────────────
    async def fetch_market_context() -> Dict[str, Any]:
        market_client = MarketDataClient()
        service = MarketContextService(market_client=market_client)
        ctx = service.get_context()
        return ctx.to_dict()

    market_ctx_dict: Dict[str, Any] = await step.run(
        "fetch-market-context", fetch_market_context
    )

    # ── Steps 3+N: Analyze each ticker ──────────────────────────────────────
    results: Dict[str, Any] = {}
    scored_candidates = list(enumerate(candidates))  # preserve screener rank order

    for rank, ticker in scored_candidates:
        async def analyze_one(t: str = ticker) -> Dict[str, Any]:
            logger.info("Batch analyzing %s", t)
            result = await run_stock_analysis(
                ticker=t,
                quarters=_QUARTERS,
                news_days_back=_NEWS_DAYS_BACK,
                user_id=BATCH_USER_ID,
            )
            return result

        result = await step.run(f"analyze-{ticker.lower()}", analyze_one)
        results[ticker] = {"result": result, "rank": rank}

    # ── Final step: Extract and store signals ────────────────────────────────
    async def store_all_signals() -> Dict[str, int]:
        from api.services.market_context_service import MarketContext

        market_context = MarketContext(
            es_change_pct=market_ctx_dict.get("es_change_pct"),
            nq_change_pct=market_ctx_dict.get("nq_change_pct"),
            dow_change_pct=market_ctx_dict.get("dow_change_pct"),
        )

        db = await get_db()
        signal_service = WeeklySignalService(db=db)
        stored = 0
        failed = 0

        for ticker, data in results.items():
            try:
                screener_score = float(_MAX_CANDIDATES - data["rank"])
                await signal_service.store_signal(
                    ticker=ticker,
                    result=data["result"],
                    run_date=run_date,
                    screener_score=screener_score,
                    market_context=market_context,
                )
                stored += 1
            except Exception as e:
                logger.error("Failed to store signal for %s: %s", ticker, e)
                failed += 1

        logger.info("Weekly batch complete: stored=%d failed=%d", stored, failed)
        return {"stored": stored, "failed": failed}

    summary = await step.run("store-signals", store_all_signals)

    return {
        "status": "completed",
        "run_date": run_date.isoformat(),
        "candidates": candidates,
        **summary,
    }
```

- [ ] **Step 3: Add BATCH_SYSTEM_USER_ID to your environment**

In your local `.env` file (never commit this), add:
```
BATCH_SYSTEM_USER_ID=<your_admin_user_uuid_from_the_users_table>
```

Look up the ID:
```bash
# Run in your DB console or via psql
# SELECT id FROM "User" WHERE "isAdmin" = true LIMIT 1;
```

Also add it to your Vercel environment variables.

- [ ] **Step 4: Commit**

```bash
git add inngest/functions/weekly_batch.py
git commit -m "feat: add weekly batch Inngest cron function"
```

---

## Task 7: Register Weekly Batch in Inngest

**Files:**
- Modify: `inngest/index.py`

- [ ] **Step 1: Read the current inngest/index.py**

```bash
cat /Users/tui/research-swarm/inngest/index.py
```

- [ ] **Step 2: Add the weekly_batch import and registration**

In `inngest/index.py`, import the new function alongside the existing `analyze_stock` import:

```python
from inngest.functions.analyze_stock import analyze_stock
from inngest.functions.weekly_batch import weekly_batch  # add this line
```

Then in the `serve()` call or functions list, add `weekly_batch`:

```python
# Before (example — match the exact pattern you see in the file):
serve("research-swarm", [analyze_stock])

# After:
serve("research-swarm", [analyze_stock, weekly_batch])
```

- [ ] **Step 3: Verify the app starts without errors**

```bash
cd /Users/tui/research-swarm
python -m uvicorn api.main:app --reload --port 8000 2>&1 | head -20
```

Expected: no import errors, server starts on port 8000.

- [ ] **Step 4: Trigger a test run manually via Inngest Dev Server**

Start the Inngest dev server in a second terminal:
```bash
npx inngest-cli@latest dev -u http://localhost:8000/api/inngest
```

In the Inngest UI (http://localhost:8288), find `weekly-batch` and trigger it manually. Watch the steps execute.

- [ ] **Step 5: Commit**

```bash
git add inngest/index.py
git commit -m "feat: register weekly-batch Inngest function"
```

---

## Task 8: Enable Prompt Caching

**Files:**
- Modify: Anthropic client initialization (find with: `grep -r "anthropic.AsyncAnthropic\|Anthropic(" research_swarm/ api/ --include="*.py" -l`)

Prompt caching cuts costs when the same context (SEC filings, system prompts) is reused across calls. This is a quick win requiring only a flag change.

- [ ] **Step 1: Find where the Anthropic client is initialized**

```bash
grep -r "anthropic.Anthropic\|AsyncAnthropic\|anthropic.AsyncAnthropic" \
  /Users/tui/research-swarm/research_swarm /Users/tui/research-swarm/api \
  --include="*.py" -n
```

Note every file and line where the client is instantiated.

- [ ] **Step 2: Add cache_control to large, repeated context blocks**

For every place where a large, repeated block of text is passed as a message (system prompts, SEC filing text, financial data blocks), add `"cache_control": {"type": "ephemeral"}` to that content block. Example pattern:

```python
# Before
messages = [
    {"role": "user", "content": [
        {"type": "text", "text": large_sec_filing_text},
        {"type": "text", "text": user_question},
    ]}
]

# After — cache the large block that repeats across calls
messages = [
    {"role": "user", "content": [
        {
            "type": "text",
            "text": large_sec_filing_text,
            "cache_control": {"type": "ephemeral"},  # add this
        },
        {"type": "text", "text": user_question},
    ]}
]
```

Apply this to system prompts and any content blocks longer than ~1000 tokens that appear in repeated calls.

- [ ] **Step 3: Verify cache headers appear in API responses**

After applying cache_control, run one analysis and check the response headers or usage object:

```bash
python -c "
import asyncio
from research_swarm.services.analysis_service import run_stock_analysis
# Run once to populate cache
r1 = asyncio.run(run_stock_analysis('AAPL', ['Q4_2024'], 7, 'system'))
print('Cost 1:', r1.get('cost_usd'))
# Run again — should be cheaper due to cache hit
r2 = asyncio.run(run_stock_analysis('AAPL', ['Q4_2024'], 7, 'system'))
print('Cost 2:', r2.get('cost_usd'))
"
```

Second run should show lower cost if cache is working.

- [ ] **Step 4: Commit**

```bash
git add -p  # review and stage only the cache_control changes
git commit -m "perf: enable Anthropic prompt caching for repeated context blocks"
```

---

## Task 9: Legal Disclaimer Checklist

**Non-code task.** Complete before any public surface goes live.

- [ ] **Step 1: Review existing Terms of Service and Privacy Policy**

Check your current terms at whatever URL they're hosted. Verify the following language exists or add it:

- "Information provided is for educational and informational purposes only."
- "Nothing on this site constitutes investment advice, financial advice, trading advice, or any other sort of advice."
- "Past performance of any analysis, signal, or recommendation does not guarantee future results."
- "Users should conduct their own due diligence before making any investment decisions."

- [ ] **Step 2: Add a persistent disclaimer to the leaderboard and report pages**

In the frontend, add a small disclaimer text to the footer or below any page that shows verdicts/signals:

```tsx
<p className="text-xs text-muted-foreground">
  For informational purposes only. Not financial advice. Past signals do not
  guarantee future performance. Always conduct your own research.
</p>
```

- [ ] **Step 3: Schedule a 30-minute call with a securities attorney**

Research: *"Do I need to register as an investment advisor if I publish automated stock analysis reports for a subscription fee?"*

In most cases, providing general research (not personalized advice) does not require RIA registration, but the attorney can confirm for your specific jurisdiction and business model. Recommended: find a securities attorney via the State Bar referral service or a firm that specializes in fintech startups.

- [ ] **Step 4: Document the decision**

After the call, write a one-paragraph note in `docs/legal-notes.md` (do not commit sensitive details — just: "consulted on [date], outcome: [register/not required/etc.]").

---

## Verification: Full Pipeline Smoke Test

After all tasks are complete, run the following end-to-end smoke test to verify the pipeline works:

- [ ] **Step 1: Trigger batch via Inngest dev server and confirm at least 3 WeeklySignal rows are created**

```bash
# Check the DB after triggering the batch in the Inngest UI
python -c "
import asyncio
from prisma import Prisma
async def main():
    db = Prisma()
    await db.connect()
    signals = await db.weeklysignal.find_many(take=5, order={'createdAt': 'desc'})
    for s in signals:
        print(s.ticker, s.verdict, s.evProbability, s.synthesisSummary[:80] if s.synthesisSummary else None)
    await db.disconnect()
asyncio.run(main())
"
```

Expected: 3+ rows with non-null verdict, evProbability, and synthesisSummary.

- [ ] **Step 2: Confirm market context is stored**

```python
# In the output above, also check:
print(s.esChangePct, s.nqChangePct, s.dowChangePct)
# Should show actual values, not None
```

- [ ] **Step 3: Run the full test suite to confirm no regressions**

```bash
cd /Users/tui/research-swarm
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all previously passing tests still pass; new tests (screener, market context, weekly signal) pass.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: Phase 0 complete — weekly batch pipeline operational"
```
