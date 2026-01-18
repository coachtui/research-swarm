# Phase 5 Builder Handoff

**Date**: 2026-01-17
**From**: CTO Architect Agent
**To**: Builder Agent
**Status**: Infrastructure complete, ready for core implementation

---

## 🎯 What You're Building

The **Quant Agent** - the third AI agent that combines:
- **Technical Analysis** (SMA 50/200, RSI, volume, relative strength)
- **Supply Chain Mapping** (NetworkX graphs with tier-2 detection)
- **Quantitative Scoring** (0-10 scores)

**Success Criteria**: Map NVDA → TSMC → ASML → Nittobo Glass supply chain

---

## ✅ What's Already Done

### 1. Dependencies Installed
```bash
# Added to requirements.txt:
yfinance>=0.2.31
networkx>=3.1
numpy>=1.24.0
pandas>=2.0.0
```

### 2. Market Data Client Created
**File**: [research_swarm/data/market_data_client.py](research_swarm/data/market_data_client.py)
- `MarketDataClient` class with yfinance integration
- Methods: `get_historical_data()`, `get_current_price()`, `get_company_info()`, `get_sector_etf()`, `calculate_return()`
- Caching: 1-day TTL for historical data
- Rate limiting: 2 req/sec
- **Status**: ✅ Production ready

### 3. Infrastructure Updated
- ✅ Rate limiter: Added yfinance limit (2 req/sec)
- ✅ Data exports: Added market_data_client to research_swarm/data/__init__.py
- ✅ Directory created: research_swarm/agents/quant/

### 4. Detailed Implementation Plan
**File**: [~/.claude/plans/kind-humming-popcorn.md](~/.claude/plans/kind-humming-popcorn.md)
- 8-step implementation guide
- Complete file specifications
- Cost analysis (~$0.04 per company)
- Testing strategy

---

## 🔲 What You Need to Build

### Priority Order

**1. Models** (quant/models.py) - ~300 lines
- Pydantic models for validation
- See [fundamentalist/models.py](research_swarm/agents/fundamentalist/models.py) as reference
- Models needed:
  - `MovingAverages`, `RSIData`, `VolumeAnalysis`, `RelativeStrength`
  - `TechnicalIndicators` (combined)
  - `SupplyChainNode`, `SupplyChainEdge`, `SupplyChainGraph`
  - `TechnicalScoreBreakdown`
  - `QuantOutput` (final output)

**2. Technical Analyzer** (quant/technical.py) - ~250 lines
- Pure Python calculations (no external TA libs)
- Methods:
  - `calculate_sma(prices, period)` - Rolling average
  - `calculate_rsi(prices, period=14)` - Momentum indicator
  - `get_moving_averages()`, `get_rsi()`, `get_volume_analysis()`, `get_relative_strength()`
  - `analyze_ticker(ticker)` - Main entry point

**3. Supply Chain Builder** (quant/supply_chain.py) - ~200 lines
- NetworkX graph construction
- Methods:
  - `build_from_fundamentalist_data()` - Reuse Phase 3 data
  - `extend_graph_tier2()` - Add tier-2 suppliers
  - `to_networkx()` - Convert to DiGraph
  - `find_critical_paths()`, `identify_hidden_dependencies()`
- Ticker mappings: TSMC→TSM, ASML→ASML, etc.

**4. LangGraph Workflow** (quant/graph.py) - ~400 lines
- 6-node sequential workflow
- See [fundamentalist/graph.py](research_swarm/agents/fundamentalist/graph.py) as reference
- Nodes:
  1. fetch_market_data
  2. calculate_indicators
  3. build_supply_chain
  4. identify_hidden_deps (LLM - Haiku)
  5. analyze_combined (LLM - Sonnet)
  6. score_quant

**5. Supporting Files**
- quant/state.py (~50 lines) - TypedDict for LangGraph state
- quant/prompts.py (~150 lines) - LLM prompt templates
- quant/analyzer.py (~150 lines) - LLM analysis orchestration
- quant/scorer.py (~150 lines) - Scoring logic
- quant/__init__.py (~20 lines) - Exports

**6. Tests** (tests/test_quant.py) - ~400 lines
- Unit tests: Model validation, calculation correctness
- Integration tests: Full workflow, NVDA chain mapping
- See [tests/test_fundamentalist.py](tests/test_fundamentalist.py) as reference

**7. Integration**
- Update research_swarm/agents/__init__.py with exports

---

## 📊 File Checklist

```
research_swarm/agents/quant/
├── __init__.py           🔲 20 lines
├── state.py             🔲 50 lines
├── models.py            🔲 300 lines ⭐ Start here
├── prompts.py           🔲 150 lines
├── technical.py         🔲 250 lines ⭐ Second priority
├── supply_chain.py      🔲 200 lines ⭐ Third priority
├── analyzer.py          🔲 150 lines
├── scorer.py            🔲 150 lines
└── graph.py             🔲 400 lines ⭐ Fourth priority

tests/
└── test_quant.py        🔲 400 lines

research_swarm/agents/
└── __init__.py          🔲 Update exports
```

**Total**: ~2,070 lines to write

---

## 🎓 Pattern Reference

### Pydantic Models
```python
# See: research_swarm/agents/fundamentalist/models.py
class TechnicalScoreBreakdown(BaseModel):
    trend_score: float = Field(..., ge=0, le=10)
    momentum_score: float = Field(..., ge=0, le=10)

    def weighted_average(self) -> float:
        return self.trend_score * 0.35 + self.momentum_score * 0.25
```

### LangGraph Workflow
```python
# See: research_swarm/agents/fundamentalist/graph.py
from langgraph.graph import StateGraph

workflow = StateGraph(QuantState)
workflow.add_node("fetch_market_data", fetch_market_data_node)
workflow.add_node("calculate_indicators", calculate_indicators_node)
# ... more nodes
workflow.add_edge("fetch_market_data", "calculate_indicators")
workflow.set_entry_point("fetch_market_data")
workflow.set_finish_point("score_quant")
graph = workflow.compile()
```

### Using Market Data Client
```python
from research_swarm.data import market_data_client

df = market_data_client.get_historical_data("NVDA", period="1y")
price = market_data_client.get_current_price("NVDA")
sector_etf = market_data_client.get_sector_etf("NVDA")  # Returns "SOXX"
```

---

## 💰 Cost Targets

| Component | Model | Target Cost |
|-----------|-------|-------------|
| Hidden dependency analysis | Haiku | ~$0.005 |
| Technical narrative | Sonnet | ~$0.017 |
| Supply chain narrative | Sonnet | ~$0.020 |
| **Total per company** | - | **~$0.04** |

**Cumulative (Phases 3+4+5)**: $0.42 per company
**Bi-weekly (20 companies)**: $8.40 ✅

---

## 🧪 Testing Strategy

### Unit Tests (10 tests)
```python
def test_technical_score_breakdown_weighted_average():
    """Test weighted average calculation."""
    breakdown = TechnicalScoreBreakdown(
        trend_score=8.0,
        momentum_score=7.0,
        volume_score=6.0,
        relative_strength_score=8.0
    )
    assert abs(breakdown.weighted_average() - 7.45) < 0.01
```

### Integration Tests (3 tests)
```python
@pytest.mark.integration
def test_analyze_nvda_technical():
    """Full technical analysis for NVDA."""
    from research_swarm.agents.quant import analyze_quant
    result = analyze_quant("NVDA")
    assert 0 <= result.technical_score <= 10
    assert result.supply_chain_graph.root_ticker == "NVDA"
```

### Success Criteria Test
```python
@pytest.mark.integration
def test_nvda_tsmc_asml_chain():
    """Map NVDA → TSMC → ASML chain."""
    result = analyze_quant("NVDA", supply_chain_depth=2)
    node_names = [n.name.upper() for n in result.supply_chain_graph.nodes]
    assert any("TSMC" in name for name in node_names)
    assert any("ASML" in name for name in node_names)
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd /Users/tui/Desktop/DevProjects/research-swarm
pip install -r requirements.txt
```

### 2. Verify Market Data Client
```python
from research_swarm.data import market_data_client

# Test basic functionality
df = market_data_client.get_historical_data("NVDA", period="1y")
print(f"Fetched {len(df)} days of data")
print(df.tail())
```

### 3. Start Implementation
```bash
# Create models.py first
code research_swarm/agents/quant/models.py
```

---

## 📚 Documentation

### Updated Files
- ✅ [progress.md](progress.md) - Phase 5 section added
- ✅ [plans/current-phase.md](plans/current-phase.md) - Full Phase 5 status
- ✅ [plans/kind-humming-popcorn.md](~/.claude/plans/kind-humming-popcorn.md) - Detailed implementation plan

### Reference Files
- [fundamentalist/models.py](research_swarm/agents/fundamentalist/models.py) - Pydantic patterns
- [fundamentalist/graph.py](research_swarm/agents/fundamentalist/graph.py) - LangGraph workflow
- [news_hound/scorer.py](research_swarm/agents/news_hound/scorer.py) - Scoring pattern
- [data/market_data_client.py](research_swarm/data/market_data_client.py) - yfinance integration
- [tests/test_fundamentalist.py](tests/test_fundamentalist.py) - Test patterns

---

## ✅ Definition of Done

- [ ] All 10 files created
- [ ] 13+ tests passing (10 unit + 3 integration)
- [ ] NVDA → TSMC → ASML chain successfully mapped
- [ ] Cost per company < $0.05
- [ ] Technical indicators calculate correctly (SMA, RSI, volume, RS)
- [ ] NetworkX graph builds with 2+ tiers
- [ ] Hidden dependencies identified
- [ ] Documentation updated
- [ ] Git commit: "Phase 5: Quant Agent complete"

---

## 🆘 Need Help?

### Common Issues
1. **yfinance rate limiting**: Use `market_data_client` (has caching + rate limiting)
2. **Ticker mapping**: See `supply_chain.py` spec for known mappings
3. **RSI calculation**: Formula is `100 - (100 / (1 + RS))` where RS = avg_gain / avg_loss

### Key Design Principles
1. **Reuse Fundamentalist data**: Don't re-extract supply chain from 10-Ks
2. **Pure Python**: No ta-lib or pandas-ta needed
3. **Graceful degradation**: Return defaults on failures
4. **Pydantic validation**: Validate everything

---

**Good luck! The infrastructure is solid - just need the core logic.**

**Questions?** Check the detailed plan in `~/.claude/plans/kind-humming-popcorn.md`
