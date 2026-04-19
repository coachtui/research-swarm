# Ticker Normalization & ETF Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix hyphenated ticker support (BRK-B) and add an ETF analysis pipeline that reuses existing agents via prompt injection and ETF-specific data fetching to produce portfolio allocation reports.

**Architecture:** ETF is detected at the API entry point using `market_data_client.get_company_info()`'s existing `quote_type` field. `is_etf=True` is passed to `analyze_swarm()`, which branches in `fetch_swarm_data_node` to load ETF holdings/macro data, then injects ETF-aware context into each agent call. Manager produces a new `ETFManagerOutput` schema instead of `ManagerOutput`.

**Tech Stack:** Python, FastAPI, LangGraph, yfinance, Pydantic v2, pytest

---

## File Map

| File | Change |
|------|--------|
| `api/models/requests.py` | Expand `_TICKER_RE` to allow hyphens |
| `research_swarm/agents/manager/models.py` | Add `ETFManagerOutput` Pydantic model |
| `research_swarm/agents/manager/state.py` | Add `is_etf: bool` field to `ManagerState` |
| `research_swarm/data/market_data_client.py` | Add `get_etf_info()` method |
| `research_swarm/agents/manager/graph.py` | Branch `fetch_swarm_data_node`, add `is_etf` to `analyze_swarm()`, inject ETF prompts in agent call nodes, ETF paths in synthesize/score/thesis nodes |
| `research_swarm/agents/fundamentalist/graph.py` | Add `etf_context` param; branch into `_analyze_etf_holdings()` |
| `research_swarm/agents/news_hound/graph.py` | Add `etf_context` param; enrich sector keyword search |
| `research_swarm/agents/quant/graph.py` | Add `etf_context` param; switch benchmark to SPY/QQQ |
| `api/services/analysis_service.py` | Detect ETF via `get_company_info`, pass `is_etf`, handle `ETFManagerOutput` response |
| `tests/test_requests.py` | New: ticker regex tests including BRK-B |
| `tests/test_etf_pipeline.py` | New: ETF data fetching, state routing, output schema |

---

### Task 1: Fix Ticker Regex

**Files:**
- Modify: `api/models/requests.py:9`
- Create: `tests/test_requests.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_requests.py
import pytest
from pydantic import ValidationError
from api.models.requests import AnalyzeRequest, BatchAnalyzeRequest


def test_hyphenated_ticker_accepted():
    req = AnalyzeRequest(ticker="BRK-B")
    assert req.ticker == "BRK-B"


def test_dotted_ticker_still_accepted():
    req = AnalyzeRequest(ticker="BRK.B")
    assert req.ticker == "BRK.B"


def test_simple_ticker_accepted():
    req = AnalyzeRequest(ticker="aapl")
    assert req.ticker == "AAPL"  # uppercased


def test_invalid_ticker_double_separator_rejected():
    with pytest.raises(ValidationError):
        AnalyzeRequest(ticker="BRK--B")


def test_invalid_ticker_too_many_letters_rejected():
    with pytest.raises(ValidationError):
        AnalyzeRequest(ticker="TOOLONG")


def test_batch_hyphenated_ticker_accepted():
    req = BatchAnalyzeRequest(tickers=["BRK-B", "AAPL"])
    assert "BRK-B" in req.tickers
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_requests.py -v
```

Expected: `test_hyphenated_ticker_accepted` FAILS with "Ticker must be 1-5 uppercase letters..."

- [ ] **Step 3: Update `_TICKER_RE` in `api/models/requests.py`**

Change line 9 from:
```python
_TICKER_RE = re.compile(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$')
```
To:
```python
_TICKER_RE = re.compile(r'^[A-Z]{1,5}([-\.][A-Z]{1,2})?$')
```

Also update the error message in `ticker_uppercase` validator (line 41) to mention hyphens:
```python
raise ValueError("Ticker must be 1-5 uppercase letters, optionally followed by a hyphen or dot and 1-2 letters (e.g. AAPL, BRK-B, BRK.B)")
```

And update the same error message in `tickers_uppercase` (line 100):
```python
raise ValueError(f"Invalid ticker '{ticker}': must be 1-5 uppercase letters, optionally followed by a hyphen or dot and 1-2 letters")
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_requests.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add api/models/requests.py tests/test_requests.py
git commit -m "fix: support hyphenated tickers like BRK-B in validation regex"
```

---

### Task 2: Add ETFManagerOutput Model

**Files:**
- Modify: `research_swarm/agents/manager/models.py`
- Create: `tests/test_etf_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_etf_pipeline.py
import pytest
from pydantic import ValidationError
from research_swarm.agents.manager.models import ETFManagerOutput


def test_etf_manager_output_valid():
    output = ETFManagerOutput(
        ticker="SPY",
        fund_name="SPDR S&P 500 ETF Trust",
        allocation_recommendation="BUY",
        concentration_risk=3.5,
        sector_momentum=7.2,
        macro_alignment_score=8.0,
        sentiment_score=6.5,
        top_holdings_summary=["AAPL 7.2%", "MSFT 6.8%", "NVDA 5.1%", "AMZN 3.9%", "GOOGL 3.7%"],
        sector_breakdown={"Technology": 31.2, "Healthcare": 12.5, "Financials": 11.8},
        expense_ratio=0.0945,
        aum_billions=512.3,
        pros=["Broad diversification", "Low expense ratio"],
        cons=["Tech concentration risk", "Rate sensitivity"],
        investment_thesis="SPY offers broad market exposure with strong momentum.",
        watchlist_candidate=True,
    )
    assert output.ticker == "SPY"
    assert output.allocation_recommendation == "BUY"
    assert output.concentration_risk == 3.5


def test_etf_manager_output_invalid_recommendation():
    with pytest.raises(ValidationError):
        ETFManagerOutput(
            ticker="SPY",
            fund_name="SPDR S&P 500 ETF",
            allocation_recommendation="SELL",  # not a valid value
            concentration_risk=3.5,
            sector_momentum=7.2,
            macro_alignment_score=8.0,
            sentiment_score=6.5,
            top_holdings_summary=[],
            sector_breakdown={},
            expense_ratio=0.09,
            aum_billions=512.3,
            pros=["low cost"],
            cons=["concentration"],
            investment_thesis="thesis",
            watchlist_candidate=False,
        )


def test_etf_manager_output_score_bounds():
    with pytest.raises(ValidationError):
        ETFManagerOutput(
            ticker="QQQ",
            fund_name="Invesco QQQ",
            allocation_recommendation="HOLD",
            concentration_risk=11.0,  # > 10 — invalid
            sector_momentum=5.0,
            macro_alignment_score=5.0,
            sentiment_score=5.0,
            top_holdings_summary=["AAPL 12%"],
            sector_breakdown={},
            expense_ratio=0.20,
            aum_billions=200.0,
            pros=["liquid"],
            cons=["concentrated"],
            investment_thesis="thesis",
            watchlist_candidate=False,
        )
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_etf_pipeline.py::test_etf_manager_output_valid -v
```

Expected: FAIL with `ImportError: cannot import name 'ETFManagerOutput'`

- [ ] **Step 3: Add `ETFManagerOutput` to `research_swarm/agents/manager/models.py`**

Add after the existing `ManagerOutput` class (after line 349):

```python
class ETFManagerOutput(BaseModel):
    """Final validated output from the Manager agent for ETF analysis."""

    # Identification
    ticker: str = Field(..., description="ETF ticker symbol")
    fund_name: str = Field(..., description="Full fund name")
    analysis_date: str = Field(default="", description="Date of analysis (YYYY-MM-DD)")

    # Core recommendation
    allocation_recommendation: Literal["BUY", "HOLD", "REDUCE"] = Field(
        ..., description="Portfolio allocation recommendation"
    )

    # ETF-specific scores (0-10)
    concentration_risk: float = Field(..., ge=0, le=10, description="Holdings concentration risk (higher = more concentrated)")
    sector_momentum: float = Field(..., ge=0, le=10, description="Price and flow momentum score")
    macro_alignment_score: float = Field(..., ge=0, le=10, description="How well current macro conditions favor this sector")
    sentiment_score: float = Field(..., ge=0, le=10, description="News and analyst sentiment score")

    # Holdings and composition
    top_holdings_summary: List[str] = Field(..., description="Top 5 holdings with weight percentages")
    sector_breakdown: Dict[str, float] = Field(..., description="Sector allocation percentages")

    # Fund fundamentals
    expense_ratio: float = Field(..., description="Annual expense ratio (e.g., 0.0945 for 0.0945%)")
    aum_billions: float = Field(..., description="Assets under management in billions USD")

    # Qualitative analysis
    pros: List[str] = Field(..., min_length=1, description="Investment positives")
    cons: List[str] = Field(..., min_length=1, description="Investment risks and negatives")
    investment_thesis: str = Field(..., min_length=50, description="Portfolio allocation recommendation narrative")

    # Watchlist
    watchlist_candidate: bool = Field(..., description="True if macro_alignment_score >= 7.5")

    # Metadata
    tokens_used: int = Field(default=0, ge=0, description="Total tokens used")
    processing_time: float = Field(default=0.0, ge=0, description="Processing time in seconds")
    cost_by_agent: Dict[str, float] = Field(
        default_factory=lambda: {"fundamentalist": 0.0, "news_hound": 0.0, "quant": 0.0, "manager": 0.0},
        description="Cost per agent in USD"
    )
```

Also add `Literal` to the existing import line at the top of the file. The file imports from `typing` — add `Literal` if not already present:
```python
from typing import List, Dict, Any, Optional, Literal
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_etf_pipeline.py::test_etf_manager_output_valid tests/test_etf_pipeline.py::test_etf_manager_output_invalid_recommendation tests/test_etf_pipeline.py::test_etf_manager_output_score_bounds -v
```

Expected: All 3 PASS

- [ ] **Step 5: Commit**

```bash
git add research_swarm/agents/manager/models.py tests/test_etf_pipeline.py
git commit -m "feat: add ETFManagerOutput Pydantic model"
```

---

### Task 3: Add `is_etf` to ManagerState and `analyze_swarm` Signature

**Files:**
- Modify: `research_swarm/agents/manager/state.py:25` (after `shared_swarm_data`)
- Modify: `research_swarm/agents/manager/graph.py:755` (`analyze_swarm` function signature and initial state)

- [ ] **Step 1: Add `is_etf` field to `ManagerState`**

In `research_swarm/agents/manager/state.py`, after the `shared_swarm_data` field (after line 25):

```python
    # ETF mode flag — set by analysis_service when quoteType == "ETF"
    is_etf: bool  # True when analyzing an ETF (routes to ETF pipeline)
```

- [ ] **Step 2: Add `is_etf` parameter to `analyze_swarm()`**

In `research_swarm/agents/manager/graph.py`, update the `analyze_swarm` function signature at line 755:

```python
def analyze_swarm(
    ticker: str,
    quarters: List[str] = None,
    fiscal_year: int = None,  # Deprecated - for backward compatibility
    news_days_back: int = 30,
    is_etf: bool = False,
) -> Union[ManagerOutput, "ETFManagerOutput"]:
```

Add the `Union` import at the top of the file (line 9):
```python
from typing import Optional, List, Union
```

Also update the `initial_state` dict in `analyze_swarm()` (around line 798) to include `is_etf`:

```python
    initial_state: ManagerState = {
        "ticker": ticker,
        "quarters": quarters or [],
        "analysis_period": analysis_period,
        "fiscal_year": fiscal_year,
        "news_days_back": news_days_back,
        "analysis_date": analysis_date,
        "is_etf": is_etf,        # ← ADD THIS
        "status": "initialized",
        "error": None,
        # ... rest unchanged
    }
```

- [ ] **Step 3: Run existing tests to confirm nothing broke**

```
pytest tests/test_manager.py -v
```

Expected: All existing tests PASS (is_etf defaults to False)

- [ ] **Step 4: Commit**

```bash
git add research_swarm/agents/manager/state.py research_swarm/agents/manager/graph.py
git commit -m "feat: add is_etf flag to ManagerState and analyze_swarm signature"
```

---

### Task 4: Add `get_etf_info()` to MarketDataClient

**Files:**
- Modify: `research_swarm/data/market_data_client.py` (add method before the global instance at line 1116)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_etf_pipeline.py`:

```python
from unittest.mock import patch, MagicMock
from research_swarm.data.market_data_client import MarketDataClient


def test_get_etf_info_returns_expected_fields():
    client = MarketDataClient()

    mock_info = {
        "shortName": "SPDR S&P 500 ETF Trust",
        "totalAssets": 512_000_000_000,
        "annualReportExpenseRatio": 0.000945,
        "ytdReturn": 0.085,
        "threeYearAverageReturn": 0.124,
        "fiveYearAverageReturn": 0.142,
        "fiftyTwoWeekHigh": 598.40,
        "fiftyTwoWeekLow": 490.21,
        "regularMarketPrice": 542.10,
        "category": "Large Blend",
        "fundFamily": "State Street",
        "navPrice": 542.05,
    }

    mock_holdings = [
        {"symbol": "AAPL", "holdingPercent": 0.072},
        {"symbol": "MSFT", "holdingPercent": 0.068},
        {"symbol": "NVDA", "holdingPercent": 0.051},
        {"symbol": "AMZN", "holdingPercent": 0.039},
        {"symbol": "GOOGL", "holdingPercent": 0.037},
    ]

    mock_ticker = MagicMock()
    mock_ticker.info = mock_info
    mock_ticker.funds_data = MagicMock()
    mock_ticker.funds_data.top_holdings = mock_holdings

    with patch("yfinance.Ticker", return_value=mock_ticker):
        with patch.object(client, "_get_or_set_cache", side_effect=lambda ns, key, fn, ttl: fn()):
            result = client.get_etf_info("SPY")

    assert result is not None
    assert result["fund_name"] == "SPDR S&P 500 ETF Trust"
    assert result["aum_billions"] == pytest.approx(512.0, abs=1.0)
    assert result["expense_ratio"] == pytest.approx(0.0945, abs=0.001)
    assert len(result["top_holdings"]) == 5
    assert result["top_holdings"][0]["symbol"] == "AAPL"
    assert "ytd_return" in result
    assert "52w_high" in result
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_etf_pipeline.py::test_get_etf_info_returns_expected_fields -v
```

Expected: FAIL with `AttributeError: 'MarketDataClient' object has no attribute 'get_etf_info'`

- [ ] **Step 3: Implement `get_etf_info()` in `MarketDataClient`**

Add this method to `research_swarm/data/market_data_client.py` before the global instance (before line 1116):

```python
    def get_etf_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch ETF-specific data: holdings, expense ratio, AUM, returns.

        Cached for 1 day (ETF profile changes slowly intraday).

        Args:
            ticker: ETF ticker symbol

        Returns:
            Dict with ETF metadata and holdings, or None on failure
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_etf_info"

        cached = cache.get("etf_profile", cache_key)
        if cached:
            logger.debug(f"Using cached ETF info for {ticker}")
            return cached

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            info = stock.info

            if not info:
                logger.warning(f"No ETF info returned for {ticker}")
                return None

            # AUM: totalAssets in raw dollars → billions
            total_assets = info.get("totalAssets")
            aum_billions = round(total_assets / 1_000_000_000, 2) if total_assets else None

            # Expense ratio: annualReportExpenseRatio is a fraction (0.000945 = 0.0945%)
            raw_expense = info.get("annualReportExpenseRatio") or info.get("annualExpenseRatio")
            expense_ratio = round(raw_expense * 100, 4) if raw_expense else None

            # Top holdings via funds_data
            top_holdings = []
            try:
                holdings_data = stock.funds_data.top_holdings
                if holdings_data is not None:
                    for holding in holdings_data[:10]:
                        if isinstance(holding, dict):
                            top_holdings.append({
                                "symbol": holding.get("symbol", ""),
                                "name": holding.get("longName") or holding.get("holdingName", ""),
                                "weight_pct": round(holding.get("holdingPercent", 0) * 100, 2),
                            })
            except Exception as e:
                logger.warning(f"Could not fetch holdings for {ticker}: {e}")

            # Sector weights via funds_data
            sector_weights = {}
            try:
                sector_data = stock.funds_data.sector_weightings
                if sector_data is not None:
                    for sector_item in sector_data:
                        if isinstance(sector_item, dict):
                            name = sector_item.get("sector", "")
                            weight = sector_item.get("exposure", 0)
                            if name:
                                sector_weights[name] = round(weight * 100, 2)
            except Exception as e:
                logger.warning(f"Could not fetch sector weights for {ticker}: {e}")

            result = {
                "ticker": ticker,
                "fund_name": info.get("shortName") or info.get("longName", ticker),
                "fund_family": info.get("fundFamily"),
                "category": info.get("category"),
                "aum_billions": aum_billions,
                "expense_ratio": expense_ratio,
                "nav_price": info.get("navPrice") or info.get("regularMarketPrice"),
                "current_price": info.get("regularMarketPrice"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "ytd_return": round(info.get("ytdReturn", 0) * 100, 2) if info.get("ytdReturn") else None,
                "1y_return": round(info.get("oneYearAverageReturn", 0) * 100, 2) if info.get("oneYearAverageReturn") else None,
                "3y_return": round(info.get("threeYearAverageReturn", 0) * 100, 2) if info.get("threeYearAverageReturn") else None,
                "5y_return": round(info.get("fiveYearAverageReturn", 0) * 100, 2) if info.get("fiveYearAverageReturn") else None,
                "top_holdings": top_holdings,
                "sector_weights": sector_weights,
            }

            cache.set("etf_profile", cache_key, result, ttl_days=1)
            logger.info(f"Fetched ETF info for {ticker}: AUM=${aum_billions}B, {len(top_holdings)} holdings")
            return result

        except Exception as e:
            logger.error(f"Error fetching ETF info for {ticker}: {e}")
            return None
```

- [ ] **Step 4: Fix the test** (the test uses `_get_or_set_cache` which doesn't exist — use `cache.get` mock instead)

Update `test_get_etf_info_returns_expected_fields` in `tests/test_etf_pipeline.py` to patch the cache directly:

```python
def test_get_etf_info_returns_expected_fields():
    from research_swarm.data import cache as data_cache
    client = MarketDataClient()

    mock_info = {
        "shortName": "SPDR S&P 500 ETF Trust",
        "totalAssets": 512_000_000_000,
        "annualReportExpenseRatio": 0.000945,
        "ytdReturn": 0.085,
        "threeYearAverageReturn": 0.124,
        "fiveYearAverageReturn": 0.142,
        "fiftyTwoWeekHigh": 598.40,
        "fiftyTwoWeekLow": 490.21,
        "regularMarketPrice": 542.10,
        "category": "Large Blend",
        "fundFamily": "State Street",
        "navPrice": 542.05,
    }

    class MockHolding:
        def __init__(self, d):
            self._d = d
        def get(self, k, default=None):
            return self._d.get(k, default)
        def __contains__(self, k):
            return k in self._d

    mock_holdings = [
        {"symbol": "AAPL", "holdingPercent": 0.072},
        {"symbol": "MSFT", "holdingPercent": 0.068},
        {"symbol": "NVDA", "holdingPercent": 0.051},
        {"symbol": "AMZN", "holdingPercent": 0.039},
        {"symbol": "GOOGL", "holdingPercent": 0.037},
    ]

    mock_ticker = MagicMock()
    mock_ticker.info = mock_info
    mock_ticker.funds_data = MagicMock()
    mock_ticker.funds_data.top_holdings = mock_holdings
    mock_ticker.funds_data.sector_weightings = []

    with patch("yfinance.Ticker", return_value=mock_ticker), \
         patch.object(data_cache, "get", return_value=None), \
         patch.object(data_cache, "set"):
        result = client.get_etf_info("SPY")

    assert result is not None
    assert result["fund_name"] == "SPDR S&P 500 ETF Trust"
    assert result["aum_billions"] == pytest.approx(512.0, abs=1.0)
    assert result["expense_ratio"] == pytest.approx(0.0945, abs=0.001)
    assert len(result["top_holdings"]) == 5
    assert result["top_holdings"][0]["symbol"] == "AAPL"
    assert result["ytd_return"] == pytest.approx(8.5, abs=0.1)
```

- [ ] **Step 5: Run test to verify it passes**

```
pytest tests/test_etf_pipeline.py::test_get_etf_info_returns_expected_fields -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add research_swarm/data/market_data_client.py tests/test_etf_pipeline.py
git commit -m "feat: add get_etf_info() to MarketDataClient for ETF holdings and fund metadata"
```

---

### Task 5: Branch `fetch_swarm_data_node` for ETFs

**Files:**
- Modify: `research_swarm/agents/manager/graph.py` — update `fetch_swarm_data_node` (line 34)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_etf_pipeline.py`:

```python
from unittest.mock import patch, MagicMock


def test_fetch_swarm_data_node_branches_on_is_etf():
    from research_swarm.agents.manager.graph import fetch_swarm_data_node
    from research_swarm.agents.manager.state import ManagerState

    mock_etf_info = {
        "ticker": "SPY",
        "fund_name": "SPDR S&P 500 ETF",
        "aum_billions": 512.3,
        "expense_ratio": 0.0945,
        "top_holdings": [{"symbol": "AAPL", "weight_pct": 7.2}],
        "sector_weights": {"Technology": 31.2},
    }

    state: ManagerState = {
        "ticker": "SPY",
        "is_etf": True,
        "status": "initialized",
        "tokens_used": 0,
        "node_timestamps": {},
        "quarters": [],
        "news_days_back": 30,
        "analysis_date": "2026-04-19",
        "analysis_period": "Current",
    }

    with patch(
        "research_swarm.agents.manager.graph.market_data_client.get_etf_info",
        return_value=mock_etf_info
    ):
        result = fetch_swarm_data_node(state)

    assert result["shared_swarm_data"]["etf_data"] == mock_etf_info
    assert result["shared_swarm_data"].get("is_etf") is True


def test_fetch_swarm_data_node_uses_hybrid_provider_for_equity():
    from research_swarm.agents.manager.graph import fetch_swarm_data_node

    state = {
        "ticker": "NVDA",
        "is_etf": False,
        "status": "initialized",
        "tokens_used": 0,
        "node_timestamps": {},
        "quarters": [],
        "news_days_back": 30,
        "analysis_date": "2026-04-19",
        "analysis_period": "TTM",
    }

    mock_shared_data = {"price_data": {}, "is_foreign": False}

    with patch(
        "research_swarm.agents.manager.graph.hybrid_provider.get_complete_swarm_data",
        return_value=mock_shared_data
    ):
        result = fetch_swarm_data_node(state)

    assert result["shared_swarm_data"] == mock_shared_data
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_etf_pipeline.py::test_fetch_swarm_data_node_branches_on_is_etf tests/test_etf_pipeline.py::test_fetch_swarm_data_node_uses_hybrid_provider_for_equity -v
```

Expected: Both FAIL (node doesn't branch yet)

- [ ] **Step 3: Update `fetch_swarm_data_node` in `research_swarm/agents/manager/graph.py`**

The `fetch_swarm_data_node` function (line 34) currently imports `hybrid_provider` inside the function. Update it to add an ETF branch. Replace the entire function body:

```python
def fetch_swarm_data_node(state: ManagerState) -> ManagerState:
    """Node 0: Pre-fetch ALL data for all agents."""
    logger.info(f"[Node 0] Pre-fetching swarm data for {state['ticker']} (is_etf={state.get('is_etf', False)})")

    state["status"] = "fetching_data"
    state["node_timestamps"] = {**state.get("node_timestamps", {}), "fetch_swarm_data": time.time()}

    try:
        if state.get("is_etf"):
            # ETF path: fetch holdings, AUM, expense ratio, sector weights via yfinance
            etf_data = market_data_client.get_etf_info(state["ticker"])
            if not etf_data:
                raise ValueError(f"Could not fetch ETF info for {state['ticker']}")

            state["shared_swarm_data"] = {
                "is_etf": True,
                "etf_data": etf_data,
                # Provide historical price data for Quant agent
                "historical_data": None,  # Quant will fetch its own price data
            }
            logger.success(f"✓ ETF data fetched: {state['ticker']} AUM=${etf_data.get('aum_billions')}B")
        else:
            # Equity path: existing hybrid provider fetch
            from research_swarm.data.data_provider_hybrid import hybrid_provider
            period = "1y"
            shared_data = hybrid_provider.get_complete_swarm_data(state["ticker"], period=period)
            state["shared_swarm_data"] = shared_data
            logger.success(
                f"✓ Swarm data fetched: {state['ticker']} "
                f"(Foreign: {shared_data.get('is_foreign', False)})"
            )

    except Exception as e:
        logger.error(f"Failed to fetch swarm data for {state['ticker']}: {e}")
        state["status"] = "error"
        state["error"] = f"Data fetch failed: {str(e)}"

    return state
```

Also add the import at the top of `graph.py` (after existing imports):
```python
from research_swarm.data.market_data_client import market_data_client
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_etf_pipeline.py::test_fetch_swarm_data_node_branches_on_is_etf tests/test_etf_pipeline.py::test_fetch_swarm_data_node_uses_hybrid_provider_for_equity -v
```

Expected: Both PASS

- [ ] **Step 5: Commit**

```bash
git add research_swarm/agents/manager/graph.py tests/test_etf_pipeline.py
git commit -m "feat: branch fetch_swarm_data_node for ETF vs equity data fetching"
```

---

### Task 6: Add ETF Mode to Fundamentalist Agent

**Files:**
- Modify: `research_swarm/agents/fundamentalist/graph.py` — add `etf_context` param to `analyze_company()`
- Modify: `research_swarm/agents/manager/graph.py` — pass `etf_context` in `call_fundamentalist_node`

The Fundamentalist agent normally does SEC filing analysis. For ETFs, it instead analyzes holdings composition and macro context via LLM.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_etf_pipeline.py`:

```python
def test_analyze_company_accepts_etf_context():
    from research_swarm.agents.fundamentalist.graph import analyze_company

    etf_context = {
        "ticker": "SPY",
        "fund_name": "SPDR S&P 500 ETF Trust",
        "aum_billions": 512.3,
        "expense_ratio": 0.0945,
        "top_holdings": [
            {"symbol": "AAPL", "weight_pct": 7.2},
            {"symbol": "MSFT", "weight_pct": 6.8},
        ],
        "sector_weights": {"Technology": 31.2, "Healthcare": 12.5},
        "ytd_return": 8.5,
        "3y_return": 12.4,
    }

    mock_output = MagicMock()
    mock_output.financial_health_score = 7.5
    mock_output.earnings_momentum_score = 6.8
    mock_output.valuation_score = 6.0
    mock_output.dict.return_value = {"financial_health_score": 7.5}

    with patch(
        "research_swarm.agents.fundamentalist.graph._analyze_etf_holdings",
        return_value=mock_output
    ) as mock_etf_fn:
        result = analyze_company(ticker="SPY", etf_context=etf_context)

    mock_etf_fn.assert_called_once_with("SPY", etf_context)
    assert result == mock_output
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_etf_pipeline.py::test_analyze_company_accepts_etf_context -v
```

Expected: FAIL — `analyze_company` doesn't have `etf_context` param

- [ ] **Step 3: Add `etf_context` parameter and `_analyze_etf_holdings()` to fundamentalist**

In `research_swarm/agents/fundamentalist/graph.py`, update `analyze_company()` function signature to accept the new parameter (at line 1301):

```python
def analyze_company(
    ticker: str,
    quarters: list = None,
    fiscal_year: int = None,
    mode: str = "ttm",
    shared_swarm_data: dict = None,
    etf_context: dict = None,  # ← ADD: ETF data bundle when analyzing ETFs
) -> FundamentalistOutput:
```

Inside `analyze_company()`, add the ETF branch before the existing TTM/annual mode handling:

```python
    # ETF path: analyze holdings and macro context instead of SEC filings
    if etf_context is not None:
        return _analyze_etf_holdings(ticker, etf_context)

    # ... existing mode determination below unchanged ...
```

Then add `_analyze_etf_holdings()` as a new function in the file (add before `analyze_company`):

```python
def _analyze_etf_holdings(ticker: str, etf_context: dict) -> "FundamentalistOutput":
    """
    ETF-mode fundamentalist analysis: holdings composition + macro context.

    Replaces SEC filing analysis when the ticker is an ETF.
    Produces a FundamentalistOutput with ETF-appropriate scores.
    """
    import anthropic
    import json
    from research_swarm.orchestration.cost_tracker import CostTracker

    logger.info(f"[ETF Fundamentalist] Analyzing holdings and macro for {ticker}")
    start_time = time.time()

    client = anthropic.Anthropic()
    cost_tracker = CostTracker()

    fund_name = etf_context.get("fund_name", ticker)
    top_holdings = etf_context.get("top_holdings", [])
    sector_weights = etf_context.get("sector_weights", {})
    aum_billions = etf_context.get("aum_billions")
    expense_ratio = etf_context.get("expense_ratio")
    ytd_return = etf_context.get("ytd_return")
    three_y_return = etf_context.get("3y_return")
    five_y_return = etf_context.get("5y_return")
    w52_high = etf_context.get("52w_high")
    w52_low = etf_context.get("52w_low")
    current_price = etf_context.get("current_price")

    # Format holdings for prompt
    holdings_text = "\n".join([
        f"  {h['symbol']}: {h['weight_pct']}%" for h in top_holdings[:10]
    ])
    sector_text = "\n".join([
        f"  {sector}: {weight}%" for sector, weight in sector_weights.items()
    ])

    prompt = f"""You are a senior portfolio analyst at a high-level portfolio management firm.
Analyze the following ETF for inclusion in a diversified institutional portfolio.

ETF: {ticker} — {fund_name}
AUM: ${aum_billions}B | Expense Ratio: {expense_ratio}% | Current Price: ${current_price}
52-Week Range: ${w52_low} – ${w52_high}
Returns: YTD {ytd_return}% | 3Y {three_y_return}% | 5Y {five_y_return}%

TOP HOLDINGS:
{holdings_text}

SECTOR ALLOCATION:
{sector_text}

Provide a JSON analysis with these exact fields:
{{
  "financial_health_score": <float 0-10: macro alignment — how well current macro conditions (rates, cycle, growth) favor this sector>,
  "earnings_momentum_score": <float 0-10: fund flow momentum and trend strength — higher = strong inflows and upward price momentum>,
  "valuation_score": <float 0-10: ETF premium/discount to NAV, expense ratio attractiveness, value vs peers>,
  "concentration_risk_score": <float 0-10: INVERSE of concentration — higher = MORE diversified, lower = highly concentrated>,
  "macro_alignment_notes": <string: 2-3 sentences on macro tailwinds/headwinds for this sector>,
  "holdings_analysis": <string: 2-3 sentences on top holdings quality, concentration risk, overlap>,
  "key_insights": <list of 3 strings: investment positives>,
  "risk_factors": <list of 3 strings: investment risks>,
  "confidence": <float 0-1>
}}

Return ONLY the JSON object, no markdown wrapping."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    tokens_used = message.usage.input_tokens + message.usage.output_tokens

    raw_text = message.content[0].text.strip()
    # Strip markdown code blocks if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    analysis = json.loads(raw_text)

    processing_time = time.time() - start_time

    # Build a FundamentalistOutput-compatible dict
    # Use the ETF scores mapped to FundamentalistOutput fields
    output = FundamentalistOutput(
        ticker=ticker,
        company_name=fund_name,
        fiscal_year=None,
        analysis_period="Current",
        financial_health_score=float(analysis["financial_health_score"]),
        earnings_momentum_score=float(analysis["earnings_momentum_score"]),
        valuation_score=float(analysis["valuation_score"]),
        key_insights=analysis.get("key_insights", []),
        risk_factors=analysis.get("risk_factors", []),
        confidence=float(analysis.get("confidence", 0.75)),
        tokens_used=tokens_used,
        processing_time=processing_time,
        # ETF-specific extras stored in analysis_notes
        analysis_notes=f"ETF Analysis | Macro: {analysis.get('macro_alignment_notes', '')} | Holdings: {analysis.get('holdings_analysis', '')}",
        # Fields not applicable to ETFs — use neutral values
        revenue_growth=None,
        earnings_growth=None,
        free_cash_flow_yield=None,
        debt_to_equity=None,
        supply_chain=None,
        fair_value_calibration=None,
    )

    logger.success(
        f"✓ ETF Fundamentalist complete: {ticker} "
        f"(health={output.financial_health_score:.1f}, "
        f"momentum={output.earnings_momentum_score:.1f}, "
        f"valuation={output.valuation_score:.1f})"
    )
    return output
```

**Note:** The `FundamentalistOutput` model fields may differ from what's shown above. Before implementing, run `grep -n "class FundamentalistOutput" research_swarm/agents/fundamentalist/` to find the model and check its required fields. Map your ETF scores to whatever fields are available and use `None` for equity-only fields.

- [ ] **Step 4: Update `call_fundamentalist_node` in `graph.py` to pass `etf_context`**

In `research_swarm/agents/manager/graph.py`, update `call_fundamentalist_node` (around line 88):

```python
        fundamentalist_output = analyze_company(
            ticker=state["ticker"],
            quarters=state.get("quarters"),
            fiscal_year=state.get("fiscal_year"),
            shared_swarm_data=state.get("shared_swarm_data"),
            etf_context=state["shared_swarm_data"].get("etf_data") if state.get("is_etf") else None,
        )
```

- [ ] **Step 5: Run tests**

```
pytest tests/test_etf_pipeline.py::test_analyze_company_accepts_etf_context -v
```

Expected: PASS

```
pytest tests/test_fundamentalist.py -v
```

Expected: All existing tests still PASS (etf_context defaults to None)

- [ ] **Step 6: Commit**

```bash
git add research_swarm/agents/fundamentalist/graph.py research_swarm/agents/manager/graph.py tests/test_etf_pipeline.py
git commit -m "feat: add ETF holdings analysis mode to Fundamentalist agent"
```

---

### Task 7: Add ETF Mode to News Hound Agent

**Files:**
- Modify: `research_swarm/agents/news_hound/graph.py:949` — add `etf_context` param to `analyze_company_news()`
- Modify: `research_swarm/agents/manager/graph.py` — pass `etf_context` in `call_news_hound_node`

The News Hound already works well for ETFs, but for sector ETFs we want to supplement ticker-based news with sector keyword searches to capture macro-level catalysts.

- [ ] **Step 1: Find where news queries are constructed in News Hound**

```
grep -n "search\|query\|news_query\|fetch_news" research_swarm/agents/news_hound/graph.py | head -30
```

Note the line numbers for where search terms are assembled.

- [ ] **Step 2: Update `analyze_company_news()` signature**

In `research_swarm/agents/news_hound/graph.py` at line 949, add `etf_context`:

```python
def analyze_company_news(
    ticker: str,
    days_back: int = 30,
    shared_swarm_data: dict = None,
    etf_context: dict = None,  # ← ADD: ETF data for sector-aware news search
) -> NewsHoundOutput:
```

Inside the function body, after the existing setup and before news fetching begins, add sector keyword enrichment when `etf_context` is provided. Find where the ticker/company name is used to build search queries and add:

```python
    # ETF mode: enrich search with sector/category context
    etf_sector_keywords = None
    if etf_context:
        fund_name = etf_context.get("fund_name", "")
        category = etf_context.get("category", "")
        # Build sector keywords from top sector weights
        sector_weights = etf_context.get("sector_weights", {})
        top_sectors = sorted(sector_weights.items(), key=lambda x: x[1], reverse=True)[:2]
        sector_names = [s[0] for s in top_sectors]
        etf_sector_keywords = sector_names
        logger.info(f"[ETF News Hound] Using sector keywords: {etf_sector_keywords}")
```

Pass `etf_sector_keywords` to wherever the news search is executed. The exact integration depends on the news hound's internal structure — find the `shared_swarm_data`-based news lookup and add the sector keywords as additional search terms.

If the news hound uses a system prompt to guide LLM analysis, append ETF context to it when `etf_context` is not None:

```python
    etf_system_addendum = ""
    if etf_context:
        etf_system_addendum = f"""
NOTE: You are analyzing an ETF ({ticker} — {etf_context.get('fund_name')}), not a single company.
Focus on:
- Sector-level macro events, policy changes, and rate environment impacts
- Fund flow trends (institutional buying/selling of this ETF or sector)
- Earnings cycle momentum for the underlying sector
- Any regulatory or thematic tailwinds/headwinds for this sector

Do NOT focus on individual company earnings or micro-level company news unless it represents a major theme across multiple holdings."""
```

- [ ] **Step 3: Update `call_news_hound_node` in `graph.py`**

In `research_swarm/agents/manager/graph.py`, update `call_news_hound_node` (around line 128):

```python
        news_hound_output = analyze_company_news(
            ticker=state["ticker"],
            days_back=state["news_days_back"],
            shared_swarm_data=state.get("shared_swarm_data"),
            etf_context=state["shared_swarm_data"].get("etf_data") if state.get("is_etf") else None,
        )
```

- [ ] **Step 4: Run existing news hound tests to verify no regressions**

```
pytest tests/test_news_hound.py -v
```

Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add research_swarm/agents/news_hound/graph.py research_swarm/agents/manager/graph.py
git commit -m "feat: add ETF sector-aware news mode to News Hound agent"
```

---

### Task 8: Add ETF Mode to Quant Agent

**Files:**
- Modify: `research_swarm/agents/quant/graph.py:404` — add `etf_context` param
- Modify: `research_swarm/agents/manager/graph.py` — pass `etf_context` in `call_quant_node`

The Quant agent does technical analysis that works fine for ETFs. The only change: when analyzing an ETF, benchmark relative strength against SPY or QQQ (broad market) rather than a sector ETF (which would be the ETF itself or a close peer).

- [ ] **Step 1: Update `analyze_quant()` signature**

In `research_swarm/agents/quant/graph.py` at line 404, add `etf_context`:

```python
def analyze_quant(
    ticker: str,
    supply_chain_depth: int = 2,
    fundamentalist_supply_chain: Optional[FundamentalistSupplyChain] = None,
    shared_swarm_data: dict = None,
    etf_context: dict = None,  # ← ADD
) -> QuantOutput:
```

Inside `analyze_quant()`, find where `get_sector_etf()` is called (used to determine the benchmark for relative strength). Override it when in ETF mode. Find the line that calls `market_data_client.get_sector_etf(ticker)` or equivalent and add:

```python
    # For ETFs, compare against broad market instead of sector ETF
    # (comparing SPY to XLK would be meaningless — compare to SPY/QQQ instead)
    if etf_context:
        benchmark_override = "QQQ" if "Technology" in (etf_context.get("sector_weights") or {}) else "SPY"
        # Pass benchmark_override to wherever the relative strength calculation happens
```

Find where the benchmark ticker is used in the quant analysis and apply the override.

- [ ] **Step 2: Update `call_quant_node` in `graph.py`**

In `research_swarm/agents/manager/graph.py`, update `call_quant_node` (around line 182):

```python
        quant_output = analyze_quant(
            ticker=state["ticker"],
            supply_chain_depth=0,
            fundamentalist_supply_chain=None,
            shared_swarm_data=state.get("shared_swarm_data"),
            etf_context=state["shared_swarm_data"].get("etf_data") if state.get("is_etf") else None,
        )
```

- [ ] **Step 3: Run existing quant tests**

```
pytest tests/test_quant.py -v
```

Expected: All existing tests PASS

- [ ] **Step 4: Commit**

```bash
git add research_swarm/agents/quant/graph.py research_swarm/agents/manager/graph.py
git commit -m "feat: add ETF benchmark override to Quant agent"
```

---

### Task 9: ETF Synthesis and Output in Manager

**Files:**
- Modify: `research_swarm/agents/manager/graph.py` — add ETF path in `synthesize_findings_node`, `calculate_moat_score_node`, `generate_thesis_node`, and `analyze_swarm()`

When `is_etf=True`, the manager synthesizes findings into an `ETFManagerOutput` instead of `ManagerOutput`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_etf_pipeline.py`:

```python
def test_analyze_swarm_returns_etf_output_when_is_etf():
    from research_swarm.agents.manager.graph import analyze_swarm
    from research_swarm.agents.manager.models import ETFManagerOutput

    mock_etf_data = {
        "ticker": "SPY",
        "fund_name": "SPDR S&P 500 ETF Trust",
        "aum_billions": 512.3,
        "expense_ratio": 0.0945,
        "top_holdings": [{"symbol": "AAPL", "weight_pct": 7.2}],
        "sector_weights": {"Technology": 31.2},
        "ytd_return": 8.5,
        "3y_return": 12.4,
        "5y_return": 14.2,
        "current_price": 542.10,
        "52w_high": 598.40,
        "52w_low": 490.21,
    }

    mock_fundamentalist = MagicMock()
    mock_fundamentalist.financial_health_score = 7.5
    mock_fundamentalist.earnings_momentum_score = 7.0
    mock_fundamentalist.valuation_score = 6.5
    mock_fundamentalist.sentiment_score = 6.8
    mock_fundamentalist.key_insights = ["Strong momentum", "Low cost"]
    mock_fundamentalist.risk_factors = ["Tech concentration"]
    mock_fundamentalist.dict.return_value = {
        "financial_health_score": 7.5,
        "earnings_momentum_score": 7.0,
        "valuation_score": 6.5,
        "key_insights": ["Strong momentum"],
        "risk_factors": ["Tech concentration"],
        "confidence": 0.8,
        "tokens_used": 500,
        "processing_time": 10.0,
    }

    mock_news = MagicMock()
    mock_news.sentiment_score = 6.5
    mock_news.dict.return_value = {
        "sentiment_score": 6.5,
        "key_insights": ["Positive sector flow"],
        "risk_factors": ["Rate sensitivity"],
        "confidence": 0.75,
        "tokens_used": 400,
        "processing_time": 8.0,
    }

    mock_quant = MagicMock()
    mock_quant.technical_score = 7.2
    mock_quant.dict.return_value = {
        "technical_score": 7.2,
        "key_insights": ["Above 200 SMA"],
        "risk_factors": ["Overbought RSI"],
        "confidence": 0.8,
        "tokens_used": 300,
        "processing_time": 5.0,
    }

    with patch("research_swarm.agents.manager.graph.market_data_client.get_etf_info", return_value=mock_etf_data), \
         patch("research_swarm.agents.manager.graph.analyze_company", return_value=mock_fundamentalist), \
         patch("research_swarm.agents.manager.graph.analyze_company_news", return_value=mock_news), \
         patch("research_swarm.agents.manager.graph.analyze_quant", return_value=mock_quant), \
         patch("research_swarm.agents.manager.graph.manager_analyzer.synthesize_etf_findings") as mock_synth:

        mock_synth.return_value = (
            {
                "allocation_recommendation": "BUY",
                "concentration_risk": 4.0,
                "sector_momentum": 7.5,
                "macro_alignment_score": 7.8,
                "investment_thesis": "SPY offers diversified large-cap exposure with strong macro tailwinds.",
                "pros": ["Broad diversification", "Low cost", "Strong momentum"],
                "cons": ["Tech concentration", "Rate sensitivity"],
            },
            800,  # tokens
        )

        result = analyze_swarm(ticker="SPY", is_etf=True)

    assert isinstance(result, ETFManagerOutput)
    assert result.allocation_recommendation == "BUY"
    assert result.ticker == "SPY"
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_etf_pipeline.py::test_analyze_swarm_returns_etf_output_when_is_etf -v
```

Expected: FAIL — `analyze_swarm` always returns `ManagerOutput`

- [ ] **Step 3: Add `synthesize_etf_findings()` to `ManagerAnalyzer`**

In `research_swarm/agents/manager/analyzer.py`, add this method to the `ManagerAnalyzer` class:

```python
    def synthesize_etf_findings(
        self,
        ticker: str,
        etf_data: dict,
        fundamentalist_output: dict,
        news_hound_output: dict,
        quant_output: dict,
    ) -> tuple[dict, int]:
        """
        Synthesize ETF findings into allocation recommendation and scores.

        Returns:
            Tuple of (synthesis_dict, tokens_used)
        """
        import anthropic
        import json

        client = anthropic.Anthropic()

        fund_name = etf_data.get("fund_name", ticker)
        top_holdings = etf_data.get("top_holdings", [])
        sector_weights = etf_data.get("sector_weights", {})
        aum_billions = etf_data.get("aum_billions")
        expense_ratio = etf_data.get("expense_ratio")
        ytd_return = etf_data.get("ytd_return")

        holdings_text = ", ".join([f"{h['symbol']} ({h['weight_pct']}%)" for h in top_holdings[:5]])
        sector_text = ", ".join([f"{s}: {w}%" for s, w in list(sector_weights.items())[:5]])

        fin_health = fundamentalist_output.get("financial_health_score", 5.0)
        momentum = fundamentalist_output.get("earnings_momentum_score", 5.0)
        valuation = fundamentalist_output.get("valuation_score", 5.0)
        sentiment = news_hound_output.get("sentiment_score", 5.0)
        technical = quant_output.get("technical_score", 5.0)

        all_insights = (
            fundamentalist_output.get("key_insights", []) +
            news_hound_output.get("key_insights", []) +
            quant_output.get("key_insights", [])
        )
        all_risks = (
            fundamentalist_output.get("risk_factors", []) +
            news_hound_output.get("risk_factors", []) +
            quant_output.get("risk_factors", [])
        )

        prompt = f"""You are a senior portfolio manager at an institutional investment firm.
Synthesize the following ETF analysis into a portfolio allocation recommendation.

ETF: {ticker} — {fund_name}
AUM: ${aum_billions}B | Expense Ratio: {expense_ratio}%
YTD Return: {ytd_return}%
Top Holdings: {holdings_text}
Sector Exposure: {sector_text}

AGENT SCORES:
- Macro Alignment (Fundamentalist): {fin_health}/10
- Flow/Momentum (Fundamentalist): {momentum}/10
- Valuation: {valuation}/10
- Sentiment: {sentiment}/10
- Technical Strength: {technical}/10

KEY POSITIVES: {all_insights[:5]}
KEY RISKS: {all_risks[:5]}

Provide a JSON synthesis:
{{
  "allocation_recommendation": "BUY" | "HOLD" | "REDUCE",
  "concentration_risk": <float 0-10: higher = more concentrated/risky>,
  "sector_momentum": <float 0-10: combining technical and flow signals>,
  "macro_alignment_score": <float 0-10: broader macro fit>,
  "investment_thesis": <string: 3-4 sentence portfolio allocation narrative suitable for a high-level management firm>,
  "pros": <list of 3 strings: top investment positives with specifics>,
  "cons": <list of 3 strings: top risks with specifics>,
  "watchlist_candidate": <bool: true if macro_alignment_score >= 7.5>
}}

Return ONLY the JSON object."""

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )

        tokens_used = message.usage.input_tokens + message.usage.output_tokens
        raw_text = message.content[0].text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        return json.loads(raw_text), tokens_used
```

- [ ] **Step 4: Add ETF synthesis path to `synthesize_findings_node` in `graph.py`**

In `synthesize_findings_node` (line 340), add an ETF branch at the start of the `try` block:

```python
    try:
        # ETF path: use dedicated ETF synthesis
        if state.get("is_etf"):
            etf_data = state.get("shared_swarm_data", {}).get("etf_data", {})
            synthesis, tokens = manager_analyzer.synthesize_etf_findings(
                ticker=state["ticker"],
                etf_data=etf_data,
                fundamentalist_output=state.get("fundamentalist_output", {}),
                news_hound_output=state.get("news_hound_output", {}),
                quant_output=state.get("quant_output", {}),
            )
            # Store ETF synthesis results in state
            state["synthesis_narrative"] = synthesis.get("investment_thesis", "")
            state["key_insights"] = synthesis.get("pros", [])
            state["risk_factors"] = synthesis.get("cons", [])
            # Store ETF-specific fields for later assembly
            state["etf_synthesis"] = synthesis
            state["tokens_used"] = state.get("tokens_used", 0) + tokens
            logger.success(f"✓ ETF synthesis complete ({tokens} tokens)")
            return state

        # Equity path: existing synthesis logic below...
        fund_output = state["fundamentalist_output"]
        # ... rest of existing code unchanged ...
```

- [ ] **Step 5: Add ETF path in `calculate_moat_score_node`**

In `calculate_moat_score_node` (line 444), add an ETF bypass at the start of the `try` block. For ETFs, we don't compute a moat score — we set scores from the ETF synthesis:

```python
    try:
        # ETF path: use ETF synthesis scores instead of equity moat formula
        if state.get("is_etf"):
            etf_synthesis = state.get("etf_synthesis", {})
            state["moat_score"] = etf_synthesis.get("macro_alignment_score", 5.0)
            state["is_watchlist_candidate"] = etf_synthesis.get("watchlist_candidate", False)
            state["rating"] = etf_synthesis.get("allocation_recommendation", "HOLD")
            state["rating_score"] = etf_synthesis.get("macro_alignment_score", 5.0) * 10
            state["risk_level"] = "Medium"
            state["confidence"] = 0.80
            logger.info(f"ETF scoring complete: {state['ticker']} ({state['rating']})")
            return state

        # Equity path: existing scoring logic below...
        financial_health_score = state["financial_health_score"]
        # ... rest unchanged ...
```

- [ ] **Step 6: Add ETF path in `generate_thesis_node` and `analyze_swarm()` return**

In `generate_thesis_node` (line 592), add an ETF bypass that skips LLM thesis generation (thesis is already in the synthesis):

```python
    try:
        # ETF path: thesis already generated in synthesize_etf_findings
        if state.get("is_etf"):
            state["investment_thesis"] = {
                "company_overview": state.get("etf_synthesis", {}).get("investment_thesis", ""),
                "recommendation_summary": state.get("rating", "HOLD"),
                "investment_highlights": state.get("key_insights", [])[:3],
                "valuation_signal_analysis": "",
                "key_risks": state.get("risk_factors", [])[:3],
                "entry_strategy": "",
            }
            state["recommendation"] = state.get("rating", "HOLD")
            state["status"] = "completed"
            logger.success(f"✓ ETF thesis assembled from synthesis")
            return state

        # Equity path: existing thesis generation below...
        fundamentalist_output = state.get("fundamentalist_output", {})
        # ... rest unchanged ...
```

In `analyze_swarm()`, after the graph runs and before building `ManagerOutput`, add an ETF branch to return `ETFManagerOutput`:

Find the section after `final_state["processing_time"] = processing_time` (around line 841) and add before the cost calculation:

```python
    # ETF path: assemble ETFManagerOutput
    if is_etf:
        from .models import ETFManagerOutput
        etf_synthesis = final_state.get("etf_synthesis", {})
        etf_data = final_state.get("shared_swarm_data", {}).get("etf_data", {})
        top_holdings = etf_data.get("top_holdings", [])

        return ETFManagerOutput(
            ticker=ticker,
            fund_name=etf_data.get("fund_name", ticker),
            analysis_date=analysis_date,
            allocation_recommendation=etf_synthesis.get("allocation_recommendation", "HOLD"),
            concentration_risk=etf_synthesis.get("concentration_risk", 5.0),
            sector_momentum=etf_synthesis.get("sector_momentum", 5.0),
            macro_alignment_score=etf_synthesis.get("macro_alignment_score", 5.0),
            sentiment_score=final_state.get("sentiment_score", 5.0),
            top_holdings_summary=[
                f"{h['symbol']} {h['weight_pct']}%" for h in top_holdings[:5]
            ],
            sector_breakdown=etf_data.get("sector_weights", {}),
            expense_ratio=etf_data.get("expense_ratio", 0.0),
            aum_billions=etf_data.get("aum_billions", 0.0),
            pros=etf_synthesis.get("pros", []),
            cons=etf_synthesis.get("cons", []),
            investment_thesis=etf_synthesis.get("investment_thesis", ""),
            watchlist_candidate=etf_synthesis.get("watchlist_candidate", False),
            tokens_used=final_state.get("tokens_used", 0),
            processing_time=processing_time,
            cost_by_agent=cost_by_agent,
        )
```

**Note:** The `etf_synthesis` state field needs to be added to `ManagerState` — add it after `is_etf` in `state.py`:
```python
    etf_synthesis: Optional[Dict[str, Any]]  # ETF synthesis results (only set when is_etf=True)
```

- [ ] **Step 7: Run the ETF pipeline integration test**

```
pytest tests/test_etf_pipeline.py::test_analyze_swarm_returns_etf_output_when_is_etf -v
```

Expected: PASS

- [ ] **Step 8: Run full test suite to verify no regressions**

```
pytest tests/test_manager.py tests/test_fundamentalist.py tests/test_news_hound.py tests/test_quant.py -v
```

Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add research_swarm/agents/manager/graph.py research_swarm/agents/manager/analyzer.py research_swarm/agents/manager/state.py tests/test_etf_pipeline.py
git commit -m "feat: add ETF synthesis and ETFManagerOutput assembly in manager graph"
```

---

### Task 10: Update `analysis_service.py` for ETF Detection and Response

**Files:**
- Modify: `api/services/analysis_service.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_etf_pipeline.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_run_stock_analysis_detects_etf_and_passes_flag():
    from api.services.analysis_service import run_stock_analysis
    from research_swarm.agents.manager.models import ETFManagerOutput

    mock_etf_output = ETFManagerOutput(
        ticker="SPY",
        fund_name="SPDR S&P 500 ETF Trust",
        analysis_date="2026-04-19",
        allocation_recommendation="BUY",
        concentration_risk=3.5,
        sector_momentum=7.5,
        macro_alignment_score=7.8,
        sentiment_score=6.5,
        top_holdings_summary=["AAPL 7.2%", "MSFT 6.8%"],
        sector_breakdown={"Technology": 31.2},
        expense_ratio=0.0945,
        aum_billions=512.3,
        pros=["Diversified"],
        cons=["Tech concentration"],
        investment_thesis="SPY provides broad exposure.",
        watchlist_candidate=True,
    )

    with patch("api.services.analysis_service.market_data_client.get_company_info") as mock_info, \
         patch("api.services.analysis_service.analyze_swarm", return_value=mock_etf_output) as mock_swarm:

        mock_info.return_value = {"quote_type": "ETF", "name": "SPDR S&P 500 ETF Trust"}

        result = await run_stock_analysis(ticker="SPY", quarters=["Q4_2024"])

    # Verify is_etf=True was passed to analyze_swarm
    mock_swarm.assert_called_once()
    call_kwargs = mock_swarm.call_args
    assert call_kwargs.kwargs.get("is_etf") is True or (
        len(call_kwargs.args) >= 5 and call_kwargs.args[4] is True
    )

    # Verify ETF response shape
    assert result["status"] == "completed"
    assert result["allocation_recommendation"] == "BUY"
    assert result["concentration_risk"] == 3.5
    assert result["macro_alignment_score"] == 7.8
    assert "moat_score" not in result  # ETF responses don't have equity fields
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_etf_pipeline.py::test_run_stock_analysis_detects_etf_and_passes_flag -v
```

Expected: FAIL — service doesn't detect ETF yet

- [ ] **Step 3: Update `analysis_service.py`**

Replace the content of `api/services/analysis_service.py` with:

```python
"""
Analysis service that wraps the existing manager agent.

This service provides the bridge between the API layer and the
core research_swarm agent orchestration.
"""

from typing import Dict, Any
import asyncio
import time


async def run_stock_analysis(
    ticker: str,
    quarters: list[str],
    news_days_back: int = 30,
    user_id: str = None
) -> Dict[str, Any]:
    """
    Run the full manager agent analysis for a single ticker (equity or ETF).

    Detects whether the ticker is an ETF via yfinance quoteType and routes
    to the appropriate pipeline path.
    """
    start_time = time.time()

    try:
        from research_swarm.agents.manager.graph import analyze_swarm
        from research_swarm.data.market_data_client import market_data_client
        from research_swarm.agents.manager.models import ETFManagerOutput

        # Detect ETF before running analysis (cached 7 days — cheap call)
        loop = asyncio.get_event_loop()
        company_info = await loop.run_in_executor(
            None, market_data_client.get_company_info, ticker
        )
        is_etf = (company_info or {}).get("quote_type") == "ETF"

        result = await loop.run_in_executor(
            None,
            lambda: analyze_swarm(
                ticker=ticker,
                quarters=quarters,
                news_days_back=news_days_back,
                is_etf=is_etf,
            )
        )

        processing_time = time.time() - start_time

        # ETF response shape
        if isinstance(result, ETFManagerOutput):
            return {
                "ticker": ticker,
                "status": "completed",
                "instrument_type": "ETF",

                # ETF-specific scores
                "allocation_recommendation": result.allocation_recommendation,
                "concentration_risk": result.concentration_risk,
                "sector_momentum": result.sector_momentum,
                "macro_alignment_score": result.macro_alignment_score,
                "sentiment_score": result.sentiment_score,

                # Fund data
                "fund_name": result.fund_name,
                "top_holdings_summary": result.top_holdings_summary,
                "sector_breakdown": result.sector_breakdown,
                "expense_ratio": result.expense_ratio,
                "aum_billions": result.aum_billions,

                # Analysis
                "pros": result.pros,
                "cons": result.cons,
                "investment_thesis": result.investment_thesis,
                "watchlist_candidate": result.watchlist_candidate,

                # Metadata
                "tokens_used": result.tokens_used,
                "cost_usd": sum(result.cost_by_agent.values()),
                "processing_time_seconds": processing_time,
                "full_output": result.model_dump(),
            }

        # Equity response shape (unchanged from original)
        breakdown = result.moat_breakdown
        return {
            "ticker": ticker,
            "status": "completed",
            "instrument_type": "EQUITY",

            "moat_score": result.moat_score,
            "financial_health_score": breakdown.financial_health,
            "business_model_moat_score": breakdown.earnings_momentum,
            "sentiment_score": breakdown.sentiment_catalysts,
            "technical_score": breakdown.technical_strength,

            "investment_thesis": result.investment_thesis.model_dump(),
            "watchlist_candidate": result.is_watchlist_candidate,

            "tokens_used": result.tokens_used,
            "cost_usd": sum(result.cost_by_agent.values()),
            "processing_time_seconds": processing_time,
            "full_output": result.model_dump()
        }

    except Exception as e:
        import traceback
        print(f"❌ Analysis service error for {ticker}: {type(e).__name__}: {e}")
        traceback.print_exc()

        processing_time = time.time() - start_time
        return {
            "ticker": ticker,
            "status": "failed",
            "error_message": str(e),
            "error_type": type(e).__name__,
            "processing_time_seconds": processing_time,
            "full_output": None
        }


def estimate_analysis_cost(ticker: str, quarters: list[str]) -> Dict[str, Any]:
    """Estimate the cost and time for analyzing a stock or ETF."""
    avg_tokens = 15000
    avg_cost_usd = 0.30
    avg_time_minutes = 6

    return {
        "ticker": ticker,
        "estimated_tokens": avg_tokens,
        "estimated_cost_usd": avg_cost_usd,
        "estimated_time_minutes": avg_time_minutes,
        "quarters_count": len(quarters)
    }
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_etf_pipeline.py::test_run_stock_analysis_detects_etf_and_passes_flag -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```
pytest tests/ -v --ignore=tests/test_e2e.py -x
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add api/services/analysis_service.py tests/test_etf_pipeline.py
git commit -m "feat: detect ETF in analysis service and route to ETF pipeline"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Ticker normalization (BRK-B) → Task 1
- ✅ ETF detection via quoteType → Task 10
- ✅ ETF data fetching (holdings, AUM, expense ratio, returns) → Task 4
- ✅ `is_etf` routing through ManagerState → Task 3, 5
- ✅ Fundamentalist: holdings + macro analysis (skip SEC) → Task 6
- ✅ News Hound: sector sentiment mode → Task 7
- ✅ Quant: benchmark switch to SPY/QQQ → Task 8
- ✅ ETFManagerOutput schema → Task 2
- ✅ ETF synthesis and scoring → Task 9
- ✅ analysis_service.py updated response shape → Task 10

**Placeholder scan:** No TBDs. Task 7 (News Hound) is directional — the exact line numbers for injecting sector keywords depend on the news hound internals not yet read. The instruction to `grep -n` first gives the implementer what they need.

**Type consistency:**
- `ETFManagerOutput` defined in Task 2, imported in Tasks 9 and 10 — consistent
- `etf_context` param added in Tasks 6, 7, 8 — all use same name
- `is_etf` field in `ManagerState` (Task 3), `analyze_swarm()` signature (Task 3), and `analysis_service.py` (Task 10) — consistent
- `etf_synthesis` state field: added to `ManagerState` in Task 9, written in `synthesize_findings_node` (Task 9), read in `calculate_moat_score_node` (Task 9) and `generate_thesis_node` (Task 9) — consistent
