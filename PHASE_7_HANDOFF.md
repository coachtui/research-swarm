# Phase 7 Handoff: Orchestration & Workflow

**Date**: 2026-01-17
**From**: CTO Architect
**To**: Builder Agent
**Status**: Ready for Implementation

---

## Executive Summary

Build an orchestration layer that enables batch stock analysis with persistence, retry logic, and cost tracking. All 4 agents (Fundamentalist, News Hound, Quant, Manager) are complete and working. This phase wraps them in a higher-level workflow.

**Success Criteria**: 5 stocks analyzed end-to-end in <30 minutes

---

## What Already Exists

### Completed Agents
- **Fundamentalist** (`research_swarm/agents/fundamentalist/`) - 10-K analysis
- **News Hound** (`research_swarm/agents/news_hound/`) - Sentiment/catalysts
- **Quant** (`research_swarm/agents/quant/`) - Technical + supply chain
- **Manager** (`research_swarm/agents/manager/`) - Orchestrates all 3, calculates moat score

### Key Entry Point (DO NOT MODIFY)
```python
# research_swarm/agents/manager/graph.py
def analyze_swarm(ticker: str, fiscal_year: int = 2024, news_days_back: int = 30) -> ManagerOutput
```

This function:
- Calls all 3 agents in sequence
- Returns `ManagerOutput` with moat_score (0-10), watchlist flag, investment thesis
- Tracks tokens and processing time

### Existing Infrastructure
- `research_swarm/data/cache.py` - SQLite cache with TTL (pattern to follow)
- `research_swarm/config.py` - Has `state_dir = Path("./data/state")` for persistence
- `research_swarm/logger.py` - Loguru logging
- `research_swarm/orchestration/` - Empty folder, ready to build

---

## What to Build

### Directory Structure
```
research_swarm/orchestration/
├── __init__.py          # Exports: run_batch, resume_batch, get_run_history, estimate_cost
├── state.py             # SwarmOrchestrationState TypedDict
├── models.py            # Pydantic: SwarmRun, StockResult, CostSummary, RunEstimate
├── persistence.py       # SQLite: 3 tables (swarm_runs, stock_results, cost_log)
├── error_handler.py     # RetryHandler with exponential backoff
├── cost_tracker.py      # CostTracker for token/cost logging
├── graph.py             # LangGraph batch workflow (4 nodes)
└── visualizer.py        # Optional: markdown summary generator

tests/
├── test_orchestration.py  # Unit tests
└── test_e2e.py            # Integration test
```

### File to Modify
- `research_swarm/__main__.py` - Add CLI argument parsing for: run, resume, history, estimate

---

## Implementation Specifications

### 1. models.py - Pydantic Models

```python
class StockStatus(str, Enum):
    PENDING, IN_PROGRESS, COMPLETED, FAILED, RETRYING

class RunStatus(str, Enum):
    INITIALIZED, RUNNING, PAUSED, COMPLETED, FAILED

class CostSummary(BaseModel):
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    cost_by_agent: Dict[str, float] = {}
    cost_by_ticker: Dict[str, float] = {}

class StockResult(BaseModel):
    ticker: str
    status: StockStatus
    retry_count: int = 0
    moat_score: Optional[float]  # 0-10
    is_watchlist_candidate: Optional[bool]
    investment_thesis: Optional[str]
    full_output: Optional[Dict]  # ManagerOutput.model_dump()
    tokens_used: int = 0
    cost_usd: float = 0.0
    error_message: Optional[str]
    processing_time_seconds: Optional[float]

class SwarmRun(BaseModel):
    run_id: str = uuid4()
    tickers: List[str]
    fiscal_year: int = 2024
    news_days_back: int = 30
    max_retries: int = 3
    status: RunStatus
    stock_results: Dict[str, StockResult]
    total_stocks: int
    completed_count: int
    failed_count: int
    cost_summary: CostSummary
    created_at: datetime
    elapsed_seconds: float

class RunEstimate(BaseModel):
    tickers: List[str]
    estimated_total_time_human: str
    estimated_cost_usd: float
    within_budget: bool
    runs_remaining_this_month: int
```

### 2. persistence.py - SQLite Schema

**Database**: `data/state/swarm_runs.db`

```sql
CREATE TABLE swarm_runs (
    run_id TEXT PRIMARY KEY,
    run_name TEXT,
    tickers TEXT NOT NULL,  -- JSON array
    fiscal_year INTEGER,
    news_days_back INTEGER,
    max_retries INTEGER DEFAULT 3,
    status TEXT DEFAULT 'initialized',
    total_stocks INTEGER,
    completed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    cost_summary TEXT,  -- JSON
    created_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    elapsed_seconds REAL DEFAULT 0.0
);

CREATE TABLE stock_results (
    run_id TEXT,
    ticker TEXT,
    status TEXT DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    moat_score REAL,
    is_watchlist_candidate INTEGER,
    investment_thesis TEXT,
    full_output TEXT,  -- JSON
    tokens_used INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    error_message TEXT,
    processing_time_seconds REAL,
    PRIMARY KEY (run_id, ticker)
);

CREATE TABLE cost_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    ticker TEXT,
    agent_name TEXT,
    timestamp TEXT,
    tokens_total INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0
);
```

**Methods**:
- `create_run(swarm_run)` - Insert run + initialize stock_results
- `get_run(run_id)` - Load full run
- `update_run_status(run_id, status, **kwargs)`
- `update_stock_result(run_id, result)`
- `get_resumable_runs()` - Runs with pending stocks
- `get_run_history(limit=20)`

### 3. error_handler.py - Retry Logic

```python
@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

class RetryHandler:
    def calculate_delay(attempt) -> float:
        # min(base * 2^attempt, max) * random(0.5, 1.5)

    def execute(func, *args, on_retry=None, **kwargs):
        # Returns result or raises RetryError

class RetryError(Exception):
    last_exception: Exception
    attempt_count: int
```

**Backoff**: 2s → 4s → 8s (±50% jitter)

### 4. cost_tracker.py - Token Pricing

```python
class CostTracker:
    # Per 1K tokens
    HAIKU_INPUT = 0.00025   # $0.25/M
    HAIKU_OUTPUT = 0.00125  # $1.25/M
    SONNET_INPUT = 0.003    # $3/M
    SONNET_OUTPUT = 0.015   # $15/M

    def calculate_cost(tokens_input, tokens_output, model="haiku") -> float
    def log_usage(run_id, ticker, agent_name, tokens_input, tokens_output)
    def estimate_run_cost(ticker_count, tokens_per_stock=15000) -> float
    def check_budget(estimated_cost, monthly_budget=200.0) -> dict
```

### 5. graph.py - LangGraph Workflow

**4 Nodes**:
```
initialize_run → select_next_ticker → analyze_stock → [check_completion]
                        ↑                                    ↓
                   (continue)                           (complete)
                        ↑                                    ↓
                        └────────────────────────────→ finalize_run
```

**Node Logic**:
1. `initialize_run`: Generate run_id, create in persistence, init stock_statuses
2. `select_next_ticker`: Find next "pending" or "retrying" ticker
3. `analyze_stock`: Call `analyze_swarm()` with retry, update persistence
4. `check_completion`: Return "continue" if pending > 0, else "complete"
5. `finalize_run`: Calculate elapsed, update final status

**Public API**:
```python
def run_batch(tickers, fiscal_year=2024, news_days_back=30, max_retries=3, run_name=None) -> SwarmRun
def resume_batch(run_id) -> SwarmRun
def get_run_history(limit=20) -> List[SwarmRun]
def get_resumable_runs() -> List[SwarmRun]
def estimate_cost(tickers, tokens_per_stock=15000) -> RunEstimate
```

### 6. CLI Commands (__main__.py)

```bash
# Run batch
python -m research_swarm run AAPL NVDA MSFT GOOGL AMZN
python -m research_swarm run --from-file tickers.txt --name "Q4"

# Resume
python -m research_swarm resume <run_id>
python -m research_swarm resume --list

# History
python -m research_swarm history
python -m research_swarm history <run_id> --export report.md

# Estimate
python -m research_swarm estimate AAPL NVDA MSFT GOOGL AMZN
```

---

## Error Handling Strategy

| Scenario | Behavior |
|----------|----------|
| API rate limit | Retry with backoff |
| API failure | Retry 3x, then mark stock failed |
| All retries exhausted | Mark stock failed, continue others |
| Keyboard interrupt | Save state as "paused" |
| One stock fails | Other stocks continue |

---

## Testing

### Unit Tests (test_orchestration.py)
- RetryHandler: success, retry, exhaust
- CostTracker: pricing calculation
- Persistence: CRUD operations
- Models: properties (success_rate, watchlist_candidates)

### Integration Test (test_e2e.py)
- 5-stock batch run
- Verify <30 min completion
- Verify watchlist identification

---

## Implementation Order

| Step | Files |
|------|-------|
| 1 | `models.py`, `state.py` |
| 2 | `persistence.py` + unit tests |
| 3 | `error_handler.py`, `cost_tracker.py` |
| 4 | `graph.py`, `__init__.py` |
| 5 | `__main__.py` CLI updates |
| 6 | `visualizer.py` (optional) |
| 7 | Integration tests |

---

## Cost Projection

| Metric | Value |
|--------|-------|
| Cost per stock | ~$0.46 |
| 5-stock run | ~$2.30 |
| 20-stock bi-weekly | ~$9.20 |
| Monthly (2 runs) | ~$18.40 |
| Budget | $200/month |

---

## Reference Files

- **Plan**: `/Users/tui/.claude/plans/polymorphic-booping-sketch.md`
- **Manager graph**: `research_swarm/agents/manager/graph.py` (line 398: `analyze_swarm()`)
- **Manager output**: `research_swarm/agents/manager/models.py` (`ManagerOutput`)
- **Cache pattern**: `research_swarm/data/cache.py`
- **Config**: `research_swarm/config.py` (`settings.state_dir`)

---

## Verification Checklist

- [ ] `pytest tests/test_orchestration.py -v` passes
- [ ] `python -m research_swarm run NVDA AMD TSM ASML INTC` completes in <30 min
- [ ] Watchlist candidates correctly identified (moat >= 8)
- [ ] Can resume interrupted runs
- [ ] Cost tracking accurate
- [ ] CLI commands work (run, resume, history, estimate)
