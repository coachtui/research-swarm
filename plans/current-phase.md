# Phase 6: Manager Agent

**Status**: IMPLEMENTATION COMPLETE - Testing Pending
**Duration**: 1 session
**Owner**: Builder Agent
**Dependencies**: Phase 5 Complete ✅
**Started**: 2026-01-17
**Completed**: 2026-01-17

---

## 🎯 Phase Objectives

Build the **Manager Agent** - the fourth AI agent that:
1. **Orchestrates** calls to Fundamentalist, News Hound, and Quant agents
2. **Synthesizes** findings into a unified investment analysis
3. **Calculates** moat scores using weighted formula
4. **Generates** watchlist for high-scoring opportunities (≥8)

**Success Criteria**: Produce moat scores for 10 stocks, pick top 3

---

## 📋 Tasks

### Infrastructure Layer
- [x] Create `research_swarm/agents/manager/` directory
- [x] Create `__init__.py` with exports

### Core Implementation
- [x] **Step 1**: Implement `state.py` (ManagerState TypedDict)
- [x] **Step 2**: Implement `models.py` (ManagerOutput, MoatScoreBreakdown)
- [x] **Step 3**: Implement `prompts.py` (synthesis, thesis, scoring prompts)
- [x] **Step 4**: Implement `analyzer.py` (synthesis logic)
- [x] **Step 5**: Implement `scorer.py` (moat scoring with weights)
- [x] **Step 6**: Implement `graph.py` (6-node LangGraph workflow)

### Integration
- [x] **Step 7**: Update `research_swarm/agents/__init__.py` exports
- [x] **Step 8**: Add Phase 6 demo to CLI (`__main__.py`)

### Testing
- [x] **Step 9**: Create `tests/test_manager.py` (unit + integration tests)
- [ ] **Step 10**: Verify success criteria (10 stocks analysis) - PENDING INTEGRATION TEST

---

## 🎯 Success Criteria

### Must Have ✅
1. ✅ Manager agent calls all 3 agents (Fundamentalist, News Hound, Quant)
2. ✅ Moat score calculation with correct weights:
   - Financial Health: 30%
   - Sentiment/Catalysts: 20%
   - Technical Strength: 20%
   - Supply Chain Position: 30%
3. ✅ Watchlist generation (moat_score ≥ 8)
4. ✅ ManagerOutput Pydantic model with validation
5. ⏳ All tests passing (unit tests complete, integration test pending)
6. ⏳ Cost per company < $0.05 (pending integration test)

### Nice to Have 🎁
- ✅ Investment thesis generation (buy/hold/avoid)
- ✅ Risk factor summary
- ✅ Agent score consistency analysis

---

## 💰 Cost Target

| Component | Model | Target Cost |
|-----------|-------|-------------|
| Synthesis narrative | Sonnet | ~$0.02 |
| Investment thesis | Sonnet | ~$0.01 |
| Score refinement | Haiku | ~$0.005 |
| **Manager total** | - | **<$0.05** |

**Cumulative (all 4 agents)**: ~$0.47 per company
**Bi-weekly run (20 companies)**: ~$9.40

---

## 🛠️ Technical Architecture

### Moat Scoring Formula
```
moat_score = (
    fundamentalist.financial_health_score * 0.30 +
    news_hound.sentiment_score * 0.20 +
    quant.technical_score * 0.20 +
    quant.supply_chain_score * 0.30
)
```

### LangGraph Workflow (6 nodes)
```
1. call_fundamentalist → 2. call_news_hound → 3. call_quant
                                                    ↓
                    6. generate_thesis ← 5. calculate_moat ← 4. synthesize_findings
```

### File Structure
```
research_swarm/agents/manager/
├── __init__.py
├── state.py
├── models.py
├── prompts.py
├── analyzer.py
├── scorer.py
└── graph.py
```

---

## 📝 Key Design Decisions

1. **Call Agents Sequentially**: Fundamentalist first (supplies data to Quant), then News Hound and Quant
2. **Pass Supply Chain Data**: Quant receives Fundamentalist's supply chain for enrichment
3. **Moat Weights from Master Plan**: Use exact weights specified (30/20/20/30)
4. **Watchlist Threshold**: ≥8 (from master-plan.md)
5. **Confidence Calculation**: Based on agent score variance (agreement = higher confidence)

---

**Last Updated**: 2026-01-17
**Status**: Implementation Complete - Ready for Integration Testing
**Next Phase**: Phase 7 - Orchestration & Workflow
