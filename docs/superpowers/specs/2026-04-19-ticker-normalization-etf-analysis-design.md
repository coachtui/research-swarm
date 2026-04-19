# Ticker Normalization & ETF Analysis Design

**Date:** 2026-04-19  
**Status:** Approved

---

## Overview

Two enhancements to the research swarm:

1. **Ticker normalization fix** — support hyphenated tickers like `BRK-B` that Yahoo Finance uses
2. **ETF analysis pipeline** — detect ETF tickers and route them through an adapted analysis flow that produces a portfolio allocation report instead of an equity investment thesis

The ETF pipeline reuses the existing four-agent architecture (Fundamentalist, News Hound, Quant, Manager) via prompt injection and ETF-specific data fetching. No new graph, no new API route.

---

## Section 1: Ticker Normalization Fix

**File:** `api/models/requests.py`

**Problem:** Current regex `^[A-Z]{1,5}(\.[A-Z]{1,2})?$` rejects hyphenated tickers like `BRK-B`.

**Fix:** Expand regex to allow hyphens alongside dots:

```
^[A-Z]{1,5}([-\.][A-Z]{1,2})?$
```

Accepts: `BRK-B`, `BRK.B`, `AAPL`, `TSM`. yfinance resolves hyphenated tickers natively — no downstream changes needed.

---

## Section 2: ETF Detection & Routing

**Files:** `api/services/analysis_service.py`, `research_swarm/agents/manager/graph.py`

- `run_stock_analysis()` resolves `quoteType` via `ticker_meta_service` before invoking the manager
- If `quoteType == "ETF"`, passes `is_etf=True` to `analyze_swarm`
- `ManagerState` gains a new `is_etf: bool` field
- `fetch_swarm_data_node` branches on this flag to fetch ETF-specific vs equity data
- Same API entry point, same LangGraph graph, same orchestration — only data payload differs

---

## Section 3: ETF Data Fetching

**File:** `research_swarm/data/market_data_client.py`

New method `get_etf_info(ticker: str)` on `MarketDataClient`:

| Field | Source | Notes |
|-------|--------|-------|
| Top 10 holdings + weight % | yfinance | |
| Sector weight breakdown | yfinance | |
| Expense ratio | yfinance | |
| AUM (billions) | yfinance | |
| Fund family, inception date | yfinance | |
| YTD, 1Y/3Y/5Y returns | yfinance | |
| 52-week high/low | yfinance | |
| Fund flows | yfinance (limited) | AUM trend used as proxy |

Cached in `DataCacheService` under new tier `etf_profile` with 1-day TTL.

`fetch_swarm_data_node` calls `get_etf_info()` instead of `get_complete_swarm_data()` when `is_etf=True`. Result stored in `shared_swarm_data` under the same key so agents receive it uniformly.

---

## Section 4: Agent Adaptations

Agents receive ETF data in `shared_swarm_data`. The manager injects an ETF-aware system prompt before dispatching each agent. No agent-level branching — adaptation is purely via prompt context.

### Fundamentalist → "Holdings Analyst" mode
- Skips SEC filing lookup entirely
- Analyzes top holdings concentration, sector weight distribution, overlap risk
- Assesses macro conditions favorable/unfavorable to the sector (rate environment, cycle positioning, earnings trends of top holdings)

### News Hound → "Sector Sentiment" mode
- Same news aggregation pipeline
- Queries sector/theme keywords alongside the ETF ticker
- Catalyst detection focuses on sector-level events (policy, earnings cycles, macro shifts) rather than single-company events

### Quant → minimal change
- Technical analysis runs as-is (price action, RSI, volume, momentum)
- Benchmark comparison switches from sector ETF to broader index (SPY/QQQ) for relative strength

---

## Section 5: ETF Output Schema & Synthesis

**New model:** `ETFManagerOutput` (alongside existing `ManagerOutput`)

```python
class ETFManagerOutput(BaseModel):
    ticker: str
    fund_name: str
    allocation_recommendation: Literal["BUY", "HOLD", "REDUCE"]
    concentration_risk: float        # 0-10, higher = more concentrated
    sector_momentum: float           # 0-10, price/flow momentum
    macro_alignment_score: float     # 0-10, how well macro favors this sector
    sentiment_score: float           # 0-10, reused from news hound
    top_holdings_summary: list[str]  # top 5 with weights
    sector_breakdown: dict[str, float]
    expense_ratio: float
    aum_billions: float
    pros: list[str]
    cons: list[str]
    investment_thesis: str
    watchlist_candidate: bool
```

Manager's `synthesize_findings_node` uses an ETF-specific synthesis prompt when `is_etf=True`, framing output as a portfolio allocation recommendation. The API `run` record structure stays the same — `full_output` carries `ETFManagerOutput` fields for ETF runs.

---

## Architecture Summary

```
POST /api/analyze {ticker: "SPY"}
  → Validate ticker (regex now supports hyphens)
  → Resolve quoteType via ticker_meta_service → "ETF"
  → run_stock_analysis(ticker, is_etf=True)
    → analyze_swarm(ManagerState{is_etf=True})
      → fetch_swarm_data_node: calls get_etf_info() → shared_swarm_data
      → [Fundamentalist (holdings/macro), News Hound (sector sentiment), Quant (technicals)] in parallel
      → Manager synthesizes → ETFManagerOutput
  → Result saved to Run record
```

---

## Files Changed

| File | Change |
|------|--------|
| `api/models/requests.py` | Expand ticker regex to allow hyphens |
| `api/services/analysis_service.py` | Resolve quoteType, pass `is_etf` to manager |
| `research_swarm/agents/manager/graph.py` | Add `is_etf` to ManagerState, branch in fetch node, ETF synthesis prompt |
| `research_swarm/data/market_data_client.py` | Add `get_etf_info()` method |
| `research_swarm/agents/fundamentalist/graph.py` | ETF prompt injection (holdings/macro mode) |
| `research_swarm/agents/news_hound/graph.py` | ETF prompt injection (sector sentiment mode) |
| `research_swarm/agents/quant/graph.py` | Switch benchmark to SPY/QQQ for ETFs |
| `api/models/responses.py` (or equivalent) | Add `ETFManagerOutput` schema |
