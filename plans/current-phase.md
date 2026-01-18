# Phase 11 Session 3: Cost Dashboard & Visibility

**Status**: 🚧 IN PROGRESS
**Duration**: ~2 hours
**Owner**: Lead Builder Agent
**Dependencies**: Phase 11 Sessions 1 & 2 Complete (24 tests passing)
**Started**: 2026-01-18

---

## Objectives

1. Add per-agent cost tracking to ManagerOutput
2. Implement cost aggregation by agent in persistence layer
3. Enhance cost CLI with comprehensive dashboard
4. Add cost section to report templates
5. Create comprehensive tests (~10-12 tests)

**Success Criteria**: Full visibility into cost breakdown by agent, trends, and budget utilization

---

## Tasks

### Task 3.1: Add cost_by_agent to ManagerOutput
- [ ] **Step 1**: Add cost_by_agent field to ManagerOutput model (research_swarm/agents/manager/models.py:153)
- [ ] **Step 2**: Find where ManagerOutput is instantiated (likely research_swarm/orchestration/graph.py)
- [ ] **Step 3**: Wire up cost_tracker to populate the new field

### Task 3.2: Add get_cost_by_agent() to Persistence
- [ ] **Step 4**: Add get_cost_by_agent() method to PersistenceManager (research_swarm/orchestration/persistence.py:468)
- [ ] **Step 5**: Verify method queries cost_log table correctly

### Task 3.3: Enhance cost CLI Command
- [ ] **Step 6**: Add --dashboard flag to cost command parser (research_swarm/__main__.py:658)
- [ ] **Step 7**: Replace cmd_cost() function with enhanced dashboard version (research_swarm/__main__.py:384-411)
- [ ] **Step 8**: Test dashboard displays monthly summary, agent breakdown, and 3-month trend

### Task 3.4: Add Cost Section to Report Template
- [ ] **Step 9**: Add cost summary section to executive_summary.md.j2 (research_swarm/reports/templates/executive_summary.md.j2:35)
- [ ] **Step 10**: Verify template renders cost_by_ticker data

### Task 3.5: Create Comprehensive Tests
- [ ] **Step 11**: Create tests/test_cost_dashboard.py with:
  - [ ] TestGetCostByAgent (3 tests)
  - [ ] TestCostDashboard (3 tests)
  - [ ] TestReportCostSection (1 test)
- [ ] **Step 12**: Run all Phase 11 Session 3 tests
- [ ] **Step 13**: Run full test suite to verify no regressions

### Final Verification
- [ ] **Step 14**: Test dashboard CLI manually: `python -m research_swarm cost --dashboard`
- [ ] **Step 15**: Verify all ~236 tests passing (226 existing + ~10 new)
- [ ] **Step 16**: Create PHASE_11_SESSION_3_COMPLETE.md handoff

---

## Success Criteria

### Must Have
1. [ ] cost_by_agent field added to ManagerOutput with proper wiring
2. [ ] get_cost_by_agent() method working in persistence layer
3. [ ] `python -m research_swarm cost --dashboard` shows:
   - Monthly summary
   - Per-agent cost breakdown
   - 3-month trend with bar charts
4. [ ] Cost section appears in generated reports
5. [ ] All new tests passing (~10-12 tests)
6. [ ] Full test suite still passing (226+ tests)

---

## Cost Target

| Component | Cost |
|-----------|------|
| API calls | $0 (all mocked in tests) |
| Development time | ~2 hours |

**This session has zero API costs - all tests use mocked data.**

---

## Technical Details

### New ManagerOutput Field
```python
cost_by_agent: Dict[str, float] = Field(
    default_factory=lambda: {
        "fundamentalist": 0.0,
        "news_hound": 0.0,
        "quant": 0.0,
        "manager": 0.0,
    },
    description="Cost breakdown by agent (USD)"
)
```

### New Persistence Method
```python
def get_cost_by_agent(self, year: int, month: int) -> Dict[str, float]:
    """Aggregate costs by agent for a specific month."""
    # SQL query against cost_log table grouping by agent_name
```

### Dashboard Output Format
```
=================================================
       RESEARCH SWARM COST DASHBOARD
=================================================

--- 2026-01 Summary ---
Total Spend:     $9.14
Budget:          $200.00
Remaining:       $190.86
Utilization:     4.6%
Runs:            1
Stocks Analyzed: 20

--- Cost by Agent ---
  fundamentalist  $0.0040 (40.0%)
  news_hound     $0.0030 (30.0%)
  quant          $0.0020 (20.0%)
  manager        $0.0010 (10.0%)

--- 3-Month Trend ---
  2025-11: $  8.00 [########            ] OK
  2025-12: $  9.00 [#########           ] OK
  2026-01: $ 10.00 [##########          ] OK
```

---

## Files to Create

| File | Lines (est.) | Tests | Description |
|------|--------------|-------|-------------|
| tests/test_cost_dashboard.py | ~500 | 7-10 | Cost dashboard tests |

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| research_swarm/agents/manager/models.py | +8 | Add cost_by_agent field |
| research_swarm/orchestration/persistence.py | +25 | Add get_cost_by_agent() |
| research_swarm/orchestration/graph.py | +10 | Wire cost_tracker to ManagerOutput |
| research_swarm/__main__.py | +50 | Add dashboard CLI |
| research_swarm/reports/templates/executive_summary.md.j2 | +20 | Add cost section |

---

## Critical Notes

### 1. ManagerOutput Instantiation
After adding cost_by_agent field, MUST find where ManagerOutput is created and populate it. Search strategy:
```bash
grep -r "ManagerOutput(" research_swarm/
grep -r "cost_tracker" research_swarm/orchestration/
```

### 2. Backward Compatibility
Adding cost_by_agent with default_factory ensures backward compatibility with existing persisted data.

### 3. Cost Log Schema
The cost_log table has: timestamp, ticker, agent_name, cost_usd
The get_cost_by_agent() method uses the existing agent_name column.

---

## Verification Commands

```bash
# Test new persistence method
python -m pytest tests/test_cost_dashboard.py::TestGetCostByAgent -v

# Test dashboard CLI
python -m pytest tests/test_cost_dashboard.py::TestCostDashboard -v

# Test template changes
python -m pytest tests/test_cost_dashboard.py::TestReportCostSection -v

# Run full test suite
eval "$(pyenv init -)" && pytest -m "not integration" -v

# Test dashboard manually
python -m research_swarm cost --dashboard
```

---

**Last Updated**: 2026-01-18
**Status**: READY FOR IMPLEMENTATION
**Previous Phase**: Phase 11 Sessions 1 & 2 ✅ (24 tests passing)
**Next Phase**: Phase 11 Complete
