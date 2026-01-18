# Phase 7: Orchestration & Workflow

**Status**: ✅ IMPLEMENTATION COMPLETE
**Duration**: 3 hours (1 session)
**Owner**: Builder Agent
**Dependencies**: Phase 6 Complete ✅
**Handoff Doc**: `PHASE_7_HANDOFF.md`
**Plan**: `/Users/tui/.claude/plans/polymorphic-booping-sketch.md`
**Started**: 2026-01-17
**Completed**: 2026-01-17

---

## 🎯 Phase Objectives

Build the **Orchestration System** that:
1. **Coordinates** all 4 agents (Manager, Fundamentalist, News Hound, Quant) in a unified LangGraph workflow
2. **Persists** intermediate results to SQLite (enables resume on failure)
3. **Handles errors** gracefully with retry logic and fallbacks
4. **Tracks costs** per run (API calls, tokens, dollars)
5. **Visualizes** workflow execution (LangGraph built-in tools)

**Success Criteria**: End-to-end run for 5 stocks completes in <30 min

---

## 📋 Tasks

### Infrastructure Layer
- [x] Create `research_swarm/orchestration/` module structure
- [x] Create `__init__.py` with exports

### Core Implementation
- [x] **Step 1**: Implement `state.py` (SwarmState TypedDict for full workflow)
- [x] **Step 2**: Implement `models.py` (SwarmRun, StockResult, CostSummary)
- [x] **Step 3**: Implement `persistence.py` (SQLite state persistence)
- [x] **Step 4**: Implement `error_handler.py` (retry logic, fallbacks)
- [x] **Step 5**: Implement `cost_tracker.py` (token/cost logging per agent)
- [x] **Step 6**: Implement `graph.py` (master LangGraph workflow)

### CLI & Visualization
- [ ] **Step 7**: Implement `visualizer.py` (workflow diagram generation) - DEFERRED
- [x] **Step 8**: Update CLI (`__main__.py`) with full swarm execution command
- [x] **Step 9**: Add progress reporting (real-time status updates)

### Testing
- [x] **Step 10**: Create `tests/test_orchestration.py` (unit tests)
- [x] **Step 11**: Create `tests/test_e2e.py` (end-to-end integration tests)
- [ ] **Step 12**: Run full swarm on 5 test stocks, verify <30 min completion - BLOCKED (yfinance Python 3.9 compatibility)

---

## 🎯 Success Criteria

### Must Have
1. [x] Unified workflow orchestrates all 4 agents in correct sequence
2. [x] State persistence allows resume after failure
3. [x] Retry logic handles transient API failures (3 retries with exponential backoff)
4. [x] Fallback strategy: skip failed stocks, continue with remaining
5. [x] Cost tracking shows per-agent and total run costs
6. [ ] End-to-end run for 5 stocks completes successfully - BLOCKED (dependency issue)
7. [ ] Execution time < 30 minutes for 5 stocks - BLOCKED (dependency issue)

### Nice to Have 🎁
- [ ] Parallel execution of independent stocks (batch processing) - FUTURE
- [ ] Workflow visualization as PNG/SVG - DEFERRED
- [ ] Progress bar during execution - PARTIAL (console logging)
- [x] Cost estimates before run starts - IMPLEMENTED

---

## 💰 Cost Target

| Component | Target Cost |
|-----------|-------------|
| 5-stock run | ~$2.50 |
| Per-stock (all agents) | ~$0.50 |
| 20-stock bi-weekly run | ~$10.00 |

**Monthly projection (2 runs)**: ~$20 ✅ Well under $200 budget

---

## 🛠️ Technical Architecture

### Master Workflow Sequence
```
1. Initialize: Load stock universe (e.g., 5 semiconductor stocks)
   ↓
2. For each stock (parallel or sequential):
   a. call_manager(ticker) → orchestrates agents 1-3 internally
   b. Persist intermediate results to SQLite
   c. Track costs
   ↓
3. Aggregate: Combine all stock results
   ↓
4. Generate: Create ranked watchlist + summary report
   ↓
5. Finalize: Log total costs, execution time
```

### State Persistence Schema (SQLite)
```sql
-- runs table
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT,  -- 'running', 'completed', 'failed', 'partial'
    total_cost REAL,
    stocks_requested INTEGER,
    stocks_completed INTEGER
);

-- stock_results table
CREATE TABLE stock_results (
    run_id TEXT,
    ticker TEXT,
    status TEXT,
    moat_score REAL,
    recommendation TEXT,
    fundamentalist_output JSON,
    news_hound_output JSON,
    quant_output JSON,
    manager_output JSON,
    cost REAL,
    processing_time REAL,
    error_message TEXT,
    PRIMARY KEY (run_id, ticker)
);
```

### Error Handling Strategy
```python
# Retry policy
MAX_RETRIES = 3
RETRY_BACKOFF = [5, 15, 30]  # seconds

# Fallback behavior
- API rate limit hit → wait and retry
- API key invalid → skip stock, log error
- Parsing error → retry with relaxed validation
- Timeout → retry, then skip stock
- All retries exhausted → mark stock as failed, continue with others
```

### File Structure
```
research_swarm/orchestration/
├── __init__.py
├── state.py           # SwarmState TypedDict
├── models.py          # SwarmRun, StockResult, CostSummary
├── persistence.py     # SQLite state management
├── error_handler.py   # Retry logic, fallbacks
├── cost_tracker.py    # Token/cost logging
├── graph.py           # Master LangGraph workflow
└── visualizer.py      # Workflow diagram generation
```

---

## 📝 Key Design Decisions

1. **Sequential vs Parallel**: Start with sequential per-stock execution (simpler debugging), add parallel option later
2. **Persistence Granularity**: Save after each agent completes (enables mid-run resume)
3. **Cost Tracking**: Log at agent level, aggregate at run level
4. **Error Isolation**: One stock failure shouldn't crash entire run
5. **State Design**: Use TypedDict for LangGraph compatibility with Pydantic for validation

---

## 🔗 Integration Points

### Existing Components to Integrate
- `research_swarm.agents.manager.analyze_swarm()` - Main entry for per-stock analysis
- `research_swarm.data.cache` - Reuse existing SQLite caching
- `research_swarm.logger` - Existing loguru setup
- `research_swarm.config` - API keys, model settings

### New CLI Commands
```bash
# Run full swarm analysis
python -m research_swarm run --stocks NVDA,AMD,TSM,ASML,INTC

# Run with custom stock universe file
python -m research_swarm run --universe stocks.txt

# Resume a failed run
python -m research_swarm resume --run-id abc123

# Show run history
python -m research_swarm history

# Estimate cost before running
python -m research_swarm estimate --stocks NVDA,AMD,TSM
```

---

## 📊 Testing Strategy

### Unit Tests (`test_orchestration.py`)
- [ ] State persistence: save/load stock results
- [ ] Error handler: retry logic with mock failures
- [ ] Cost tracker: accumulation accuracy
- [ ] Workflow: node sequencing validation

### Integration Tests (`test_e2e.py`)
- [ ] Single stock end-to-end (with mock LLM responses)
- [ ] 5-stock run with simulated failures
- [ ] Resume after partial completion
- [ ] Cost tracking accuracy

### Performance Tests
- [ ] 5-stock run in <30 minutes (real APIs)
- [ ] Memory usage stays under 500MB
- [ ] SQLite DB size reasonable (<10MB for 100 runs)

---

## 🚀 Implementation Order

Recommended sequence for builder agent:

1. **Foundation first**: `state.py` + `models.py` + `persistence.py`
2. **Core workflow**: `graph.py` (basic sequential flow)
3. **Reliability**: `error_handler.py` + `cost_tracker.py`
4. **Polish**: CLI updates + `visualizer.py`
5. **Validation**: Tests + 5-stock integration run

---

**Last Updated**: 2026-01-17
**Status**: Ready to Start
**Previous Phase**: Phase 6 - Manager Agent ✅
**Next Phase**: Phase 8 - Report Generation
