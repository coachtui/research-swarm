# Phase 12: Documentation & Maintenance

**Status**: 🚀 READY TO START
**Duration**: ~3-4 sessions
**Owner**: CTO Architect Agent
**Dependencies**: Phases 1-11 Complete (264 tests total)
**Started**: 2026-01-18

---

## Objectives

1. Create comprehensive user guide for running and customizing the system
2. Document system architecture with diagrams and workflows
3. Write maintenance procedures for long-term sustainability
4. Create handoff checklist for future developers
5. Address Python version requirement documentation
6. Create troubleshooting guide for common issues

**Success Criteria**: Someone with basic Python knowledge can run the system and maintain it with 30 minutes of onboarding

---

## Phase 12 Overview

This phase focuses on making the Research Swarm system maintainable and accessible to future users or developers. With Phases 1-11 complete and 264 tests passing, we now need comprehensive documentation to ensure long-term sustainability.

**Key Stats from Phases 1-11**:
- ✅ 264 total tests passing (233 unit + 31 optimization tests)
- ✅ 54% code coverage
- ✅ 92% cost reduction achieved (Haiku 3.5 optimization)
- ✅ $0.73 per bi-weekly run (99% under budget)
- ✅ Complete automation with email notifications
- ✅ Professional PDF reports with charts

---

## Session Plan

### Session 12.1: User Guide & Quick Start (2-3 hours)

**Goal**: Enable new users to run the system within 30 minutes

#### Tasks:

1. **Create `/docs/` directory structure**
   - `docs/user-guide.md`
   - `docs/architecture.md`
   - `docs/maintenance.md`
   - `docs/troubleshooting.md`
   - `docs/api-reference.md`

2. **Write `docs/user-guide.md`** (~1,500 words)
   - **Quick Start** (5 min)
     - Python 3.10+ requirement (pyenv setup)
     - Clone and install dependencies
     - Configure API keys (.env file)
     - First test run
   - **CLI Commands Overview** (10 min)
     - `run` - Execute batch analysis
     - `report` - Generate reports
     - `schedule` - Manage automation
     - `cache` - Cache management
     - `cost` - Cost tracking and dashboard
     - `history` - View past runs
   - **Running Manual Analysis** (5 min)
     - Single stock: `python -m research_swarm run AAPL`
     - Multiple stocks: `python -m research_swarm run AAPL NVDA MSFT`
     - From file: `python -m research_swarm run --from-file watchlist.txt`
     - Custom parameters: fiscal year, news lookback
   - **Interpreting Reports** (10 min)
     - Executive summary section
     - Moat score breakdown (what each component means)
     - Watchlist candidates (≥8.0 threshold)
     - Supply chain visualizations
     - Cost summary interpretation
   - **Customizing Stock Universe**
     - Editing `watchlist.txt`
     - Sector-specific lists
     - Adding new tickers
   - **Email Notifications**
     - SMTP vs SendGrid configuration
     - Priority alerts (moat ≥9)
     - Cost alerts ($180 threshold)

3. **Update README.md** with better quick start
   - Link to comprehensive docs
   - System requirements (Python 3.10+, macOS/Linux)
   - 5-minute quick start guide
   - Architecture diagram (ASCII or link to docs)
   - Link to troubleshooting

4. **Create `docs/examples.md`**
   - Example commands with expected outputs
   - Sample report walkthrough
   - Cost dashboard interpretation
   - Common workflows (weekly vs bi-weekly)

**Deliverables**:
- [ ] User guide (1,500+ words)
- [ ] Updated README.md
- [ ] Examples documentation
- [ ] Quick start can be completed in <30 minutes

---

### Session 12.2: Architecture Documentation (2-3 hours)

**Goal**: Explain how the system works for future maintenance or extension

#### Tasks:

1. **Write `docs/architecture.md`** (~2,000 words)

   **Section 1: System Overview**
   - High-level architecture diagram (ASCII or Mermaid)
   - 4 agents + manager orchestration
   - Data flow: APIs → Cache → Agents → Manager → Reports
   - State persistence with SQLite

   **Section 2: Agent Responsibilities**
   - **Fundamentalist Agent**
     - Input: Ticker, fiscal year
     - Data sources: SEC Edgar (10-K filings)
     - Output: financial_health_score (0-10), metrics, supply chain
     - LangGraph workflow: 6 nodes (fetch → parse → extract → analyze → score → output)
     - Models: Haiku (extraction), Sonnet (analysis)
     - Cost: ~$0.01 per company

   - **News Hound Agent**
     - Input: Ticker, lookback days
     - Data sources: NewsAPI.org
     - Output: sentiment_score (0-10), catalysts, events
     - LangGraph workflow: 6 nodes (fetch → dedupe → catalysts → regulatory → sentiment → score)
     - Models: Haiku (filtering, extraction), Sonnet (sentiment)
     - Cost: ~$0.01 per company

   - **Quant Agent**
     - Input: Ticker, fundamentalist supply chain data
     - Data sources: Yahoo Finance (yfinance)
     - Output: technical_score (0-10), supply_chain_score (0-10), graph
     - LangGraph workflow: 6 nodes (fetch → technical → graph → hidden_deps → narratives → score)
     - Models: Haiku (hidden deps), Sonnet (narratives)
     - Cost: ~$0.005 per company

   - **Manager Agent**
     - Input: Ticker, fiscal year, news days
     - Orchestrates: Fundamentalist → News Hound → Quant
     - Output: moat_score (0-10), thesis, watchlist recommendation
     - LangGraph workflow: 6 nodes (fundamentalist → news → quant → synthesize → score → thesis)
     - Models: Sonnet (synthesis, thesis)
     - Moat formula: 30% financial + 20% sentiment + 20% technical + 30% supply chain
     - Cost: ~$0.015 per company

   **Section 3: Orchestration Layer**
   - Batch workflow: initialize → select_next → analyze → finalize
   - Persistence: 3 SQLite tables (swarm_runs, stock_results, cost_log)
   - Error handling: Per-stock retry with exponential backoff (3 attempts)
   - Resume capability: Can restart from any failed stock
   - Cost tracking: Per-agent and per-ticker granularity

   **Section 4: Data Pipeline**
   - Caching strategy: 10-Ks (90 days), news (7 days), market data (24 hours)
   - Rate limiting: Token bucket algorithm per API
   - API clients: SEC Edgar, FMP, NewsAPI, Yahoo Finance
   - Cache database: `data/cache/api_cache.db`

   **Section 5: Report Generation**
   - Input: SwarmRun from persistence
   - Templates: Jinja2 (5 modular templates)
   - Charts: matplotlib + NetworkX (moat breakdown, supply chain graphs)
   - PDF: WeasyPrint with professional CSS
   - Cost: $0 (no LLM calls)

   **Section 6: Automation System**
   - Scheduler: macOS launchd with bi-weekly logic
   - Runner: run → report → notify pipeline
   - Notifier: SMTP/SendGrid with HTML templates
   - Cost monitor: Budget alerts at $180 threshold

2. **Create workflow diagrams**
   - LangGraph state flow diagrams (Mermaid or ASCII)
   - Data flow: API → Cache → Agent → Persistence
   - Orchestration sequence diagram

3. **Write `docs/api-reference.md`**
   - Public API functions in each module
   - Function signatures and parameters
   - Return types and schemas
   - Usage examples

4. **Document key design decisions**
   - Why LangGraph over CrewAI
   - Why SQLite over PostgreSQL
   - Why Haiku for extraction, Sonnet for analysis
   - Why 30/20/20/30 moat scoring weights
   - Caching TTL rationale

**Deliverables**:
- [ ] Architecture documentation (2,000+ words)
- [ ] Workflow diagrams (ASCII/Mermaid)
- [ ] API reference
- [ ] Design decisions log

---

### Session 12.3: Maintenance & Troubleshooting (2-3 hours)

**Goal**: Enable long-term maintenance without context loss

#### Tasks:

1. **Write `docs/maintenance.md`** (~1,500 words)

   **Section 1: Routine Maintenance**
   - **API Key Rotation** (quarterly)
     - Update `.env` file
     - Test with single stock run
     - Verify cost tracking

   - **Cache Management** (monthly)
     - Check cache size: `python -m research_swarm cache stats`
     - Clear expired: `python -m research_swarm cache clear`
     - Full reset if needed: `cache clear --all --force`

   - **Cost Monitoring** (bi-weekly)
     - Review dashboard: `python -m research_swarm cost --dashboard`
     - Check budget utilization (<4% per run)
     - Investigate spikes (agent breakdown)
     - Monthly trend analysis

   - **Database Cleanup** (quarterly)
     - Check persistence DB size
     - Archive old runs (>6 months)
     - Vacuum SQLite: `sqlite3 data/persistence.db "VACUUM;"`

   - **Dependency Updates** (quarterly)
     - Update requirements.txt
     - Test with: `pytest -m "not integration"`
     - Check for breaking changes

   **Section 2: Updating API Keys**
   - Where to get keys:
     - Anthropic Claude: https://console.anthropic.com/
     - NewsAPI: https://newsapi.org/
     - Financial Modeling Prep: https://financialmodelingprep.com/
   - How to update `.env`
   - Testing after update
   - Key rotation best practices

   **Section 3: Adding New Data Sources**
   - Create client in `research_swarm/data/`
   - Add to `data/__init__.py`
   - Update rate limiter
   - Add caching support
   - Write tests
   - Update agent to use new data

   **Section 4: Modifying Moat Scoring**
   - Current weights: 30/20/20/30
   - Edit `research_swarm/agents/manager/scorer.py`
   - Update tests in `tests/test_manager.py`
   - Document rationale for changes

   **Section 5: Extending Agents**
   - Adding new agent:
     1. Create `research_swarm/agents/new_agent/` directory
     2. Implement state.py, models.py, prompts.py, analyzer.py, scorer.py, graph.py
     3. Export from `agents/__init__.py`
     4. Add to manager orchestration
     5. Update moat scoring formula
     6. Write comprehensive tests

   - Modifying existing agent:
     1. Update prompts in `prompts.py`
     2. Adjust scoring in `scorer.py`
     3. Update tests
     4. Run regression suite

2. **Write `docs/troubleshooting.md`** (~1,000 words)

   **Common Issues & Solutions**:

   **Issue 1: Tests fail with "unsupported operand type(s) for |"**
   - **Cause**: Python version <3.10 doesn't support `|` union syntax
   - **Solution**: Use pyenv to switch to Python 3.11.9
     ```bash
     eval "$(pyenv init -)"
     python --version  # Should show 3.11.9
     pytest -m "not integration"
     ```
   - **Prevention**: Always run tests with pyenv shell activated

   **Issue 2: API rate limit exceeded**
   - **Symptoms**: 429 status code, failed stock analysis
   - **Cause**: Too many requests, cache miss
   - **Solution**:
     - Wait 1 hour (rate limits reset)
     - Check cache stats: `cache stats`
     - Reduce batch size
   - **Prevention**: Use cache aggressively, stagger runs

   **Issue 3: Cost spike above $50**
   - **Symptoms**: High cost in dashboard
   - **Diagnosis**: Check agent breakdown
   - **Common causes**:
     - Scorer using Sonnet instead of Haiku (check models.py)
     - Cache miss causing redundant API calls
     - Large batch without caching
   - **Solution**: Review `cost --dashboard`, verify Haiku usage

   **Issue 4: Report generation fails**
   - **Symptoms**: WeasyPrint error, missing charts
   - **Causes**:
     - WeasyPrint not installed: `pip install weasyprint`
     - Missing fonts: Install system fonts
     - Bad data in run: Check run status
   - **Solution**: Verify dependencies, check logs

   **Issue 5: Email notifications not working**
   - **Symptoms**: No emails received
   - **Diagnosis**: Test email: `python -m research_swarm notify --test`
   - **Common causes**:
     - SMTP credentials wrong (.env file)
     - Gmail "Less secure apps" disabled
     - SendGrid API key expired
   - **Solution**: Verify .env, check provider settings

   **Issue 6: Schedule not running**
   - **Symptoms**: No automated runs
   - **Diagnosis**: Check launchd status
     ```bash
     launchctl list | grep research_swarm
     tail -f ~/Library/Logs/research_swarm/stdout.log
     ```
   - **Solutions**:
     - Reinstall: `python -m research_swarm schedule install`
     - Check permissions on script
     - Verify .env file readable by launchd

   **Issue 7: Supply chain graph incomplete**
   - **Symptoms**: Missing tier-2 relationships
   - **Cause**: Hardcoded mappings in `quant/supply_chain.py`
   - **Solution**: Add ticker mappings to TIER_2_MAPPINGS dict

   **Issue 8: High memory usage**
   - **Symptoms**: System slowdown during batch runs
   - **Cause**: Large cache, many stocks in memory
   - **Solutions**:
     - Clear cache: `cache clear`
     - Reduce batch size
     - Run stocks sequentially (current design)

   **Debugging Tips**:
   - Check logs: `tail -f research_swarm.log`
   - Run with debug: `LOG_LEVEL=DEBUG python -m research_swarm run AAPL`
   - Inspect persistence: `sqlite3 data/persistence.db .dump`
   - Test agents individually (unit tests)

3. **Create `docs/handoff-checklist.md`**
   - For delegating to new developer:
     - [ ] API keys transferred
     - [ ] Repository access granted
     - [ ] Local environment setup (Python 3.11.9)
     - [ ] First test run completed
     - [ ] User guide reviewed
     - [ ] Architecture overview reviewed
     - [ ] Maintenance procedures reviewed
     - [ ] Troubleshooting guide reviewed
     - [ ] Schedule configured for their machine
     - [ ] Email notifications tested
     - [ ] Cost monitoring explained
   - Success criteria: New dev can run system independently

4. **Document Python version requirement**
   - Update README with Python 3.10+ requirement
   - Add pyenv setup instructions
   - Note shell defaults to Anaconda Python 3.9
   - Add version check to CLI startup

**Deliverables**:
- [ ] Maintenance procedures (1,500+ words)
- [ ] Troubleshooting guide (1,000+ words)
- [ ] Handoff checklist
- [ ] Python version documentation

---

### Session 12.4: Final Polish & Validation (1-2 hours)

**Goal**: Validate documentation completeness and accessibility

#### Tasks:

1. **Create table of contents in all docs**
   - Add navigation links
   - Consistent formatting
   - Cross-reference between docs

2. **Add diagrams where helpful**
   - System architecture (high-level)
   - LangGraph workflows (per agent)
   - Data flow (APIs → Cache → Agents)
   - Orchestration sequence

3. **Write `docs/faq.md`** (Frequently Asked Questions)
   - When to run the system?
   - How to interpret moat scores?
   - What's a good watchlist size?
   - How to add new stocks?
   - How to change email settings?
   - What if costs spike?
   - How to backup data?

4. **Create `CHANGELOG.md`**
   - Document phases 1-11 as releases
   - Major features per phase
   - Breaking changes (Python 3.9 → 3.11)
   - Cost optimizations

5. **Validation test**: 30-minute onboarding
   - Pretend you're a new user
   - Follow quick start guide
   - Time yourself
   - Note friction points
   - Update docs to smooth issues

6. **Update master-plan.md**
   - Mark Phase 12 as COMPLETE
   - Add Phase 12 statistics
   - Document total project stats

**Deliverables**:
- [ ] FAQ documentation
- [ ] Changelog
- [ ] 30-minute onboarding validated
- [ ] All documentation polished

---

## Documentation Structure

```
docs/
├── README.md                    → Overview + links to all docs
├── user-guide.md                → Quick start, CLI, customization
├── architecture.md              → System design, agents, workflows
├── maintenance.md               → Routine maintenance, updates
├── troubleshooting.md           → Common issues + solutions
├── api-reference.md             → Public API functions
├── examples.md                  → Command examples, walkthroughs
├── faq.md                       → Frequently asked questions
└── handoff-checklist.md         → Onboarding new developers

Root files:
├── README.md                    → Quick start (link to docs/)
├── CHANGELOG.md                 → Version history
└── LICENSE                      → MIT/Apache (if open sourcing)
```

---

## Success Metrics

### Must Have
- [ ] New user can run first analysis in <30 minutes
- [ ] All CLI commands documented with examples
- [ ] Architecture diagrams for all 4 agents + orchestration
- [ ] Troubleshooting covers 8+ common issues
- [ ] Maintenance procedures for API keys, cache, costs
- [ ] Handoff checklist validated

### Nice to Have
- [ ] Video walkthrough (optional)
- [ ] Mermaid diagrams for workflows
- [ ] Screenshots in user guide
- [ ] Jupyter notebook examples

---

## Critical Notes

### Python Version Issue
**Problem**: Shell defaults to Anaconda Python 3.9.13, but project requires Python 3.10+ for `|` union type syntax.

**Solution**: Always use pyenv shell:
```bash
eval "$(pyenv init -)"
python --version  # Must show 3.11.9
```

**Documentation**: Add Python version check to CLI startup, prominent README warning.

### Test Suite Status
Before Phase 12:
- 233 unit tests passing (Phase 10)
- 31 optimization tests passing (Phase 11)
- **Total: 264 tests passing**
- 1 skipped, 10 deselected (integration tests)
- 54% code coverage

### Cost Optimization Results (Phase 11)
- Switched scorers to Haiku 3.5: **92% cost reduction**
- Per-run cost: $9.14 → $0.73
- Monthly cost (2 runs): ~$1.46
- **99% under $200 budget** ✅

---

## Files to Create

| File | Size (est.) | Description |
|------|-------------|-------------|
| docs/user-guide.md | 1,500 words | Quick start, CLI, customization |
| docs/architecture.md | 2,000 words | System design, agents, workflows |
| docs/maintenance.md | 1,500 words | Routine procedures, updates |
| docs/troubleshooting.md | 1,000 words | Common issues + solutions |
| docs/api-reference.md | 800 words | Public API functions |
| docs/examples.md | 600 words | Command examples |
| docs/faq.md | 500 words | Frequently asked questions |
| docs/handoff-checklist.md | 200 words | Onboarding checklist |
| CHANGELOG.md | 400 words | Version history |
| **TOTAL** | **~8,500 words** | Complete documentation |

## Files to Modify

| File | Change | Lines (est.) |
|------|--------|--------------|
| README.md | Better quick start, links to docs/ | +100 |
| research_swarm/__main__.py | Add Python version check | +15 |

---

## Verification Commands

```bash
# Check Python version
eval "$(pyenv init -)" && python --version

# Run tests (unit only, no API keys needed)
eval "$(pyenv init -)" && pytest -m "not integration" -v

# Verify all CLI commands
python -m research_swarm --help
python -m research_swarm run --help
python -m research_swarm report --help
python -m research_swarm schedule --help
python -m research_swarm cache --help
python -m research_swarm cost --help

# Test quick start (30-minute onboarding)
time ./docs/quick-start.sh

# Check documentation links
cd docs && grep -r "](/" *.md  # Verify no broken links
```

---

## Cost Target

| Component | Cost |
|-----------|------|
| API calls | $0 (no LLM calls) |
| Development time | ~8-10 hours (3-4 sessions) |

**Phase 12 has zero API costs - pure documentation.**

---

## Phase 12 Timeline

| Session | Duration | Deliverable |
|---------|----------|-------------|
| 12.1 | 2-3 hours | User guide + quick start |
| 12.2 | 2-3 hours | Architecture docs + diagrams |
| 12.3 | 2-3 hours | Maintenance + troubleshooting |
| 12.4 | 1-2 hours | Polish + validation |
| **Total** | **7-11 hours** | **Complete documentation** |

---

## Post-Phase 12: Project Complete 🎉

After Phase 12, the Research Swarm system will be:
- ✅ Fully functional with 264 tests passing
- ✅ Optimized for cost ($0.73 per bi-weekly run)
- ✅ Automated with email notifications
- ✅ Comprehensively documented
- ✅ Maintainable by new developers (30-min onboarding)

**Total project stats** (Phases 1-12):
- **Duration**: ~3 weeks (part-time)
- **Files created**: ~80 Python modules + 10 test files + 10 docs
- **Lines of code**: ~15,000
- **Tests**: 264 passing
- **Coverage**: 54%
- **Cost per run**: $0.73 (99% under budget)
- **Monthly cost**: $1.46 (for 2 bi-weekly runs)

**Optional future enhancements** (Phase 13+):
- Web dashboard for browsing reports
- Slack integration
- Backtesting engine
- Real-time alerts
- Mobile notifications

---

**Last Updated**: 2026-01-18
**Status**: READY FOR IMPLEMENTATION
**Previous Phase**: Phase 11 ✅ (Optimization & Cost Control Complete)
**Next Phase**: Phase 12 Documentation & Maintenance
