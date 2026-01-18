# Phase 8: Report Generation

**Status**: Planning Complete - Ready for Implementation
**Duration**: ~8 hours (2-3 sessions)
**Owner**: Builder Agent
**Dependencies**: Phase 7 Complete (Orchestration)
**Handoff Doc**: `PHASE_8_HANDOFF.md`
**Plan**: `/Users/tui/.claude/plans/polymorphic-tinkering-clock.md`
**Started**: 2026-01-17

---

## Phase Objectives

Build the **Report Generation System** that:
1. **Extracts** analysis data from completed SwarmRun instances
2. **Generates** professional Markdown reports with Jinja2 templates
3. **Creates** visualizations (moat charts, supply chain graphs) with matplotlib
4. **Converts** to PDF using WeasyPrint
5. **Integrates** with CLI via new `report` command

**Success Criteria**: Generate a professional PDF report with charts from a completed swarm run.

---

## Tasks

### Infrastructure Layer
- [ ] Add dependencies (weasyprint, jinja2, markdown) to requirements.txt
- [ ] Install system dependencies (brew install cairo pango gdk-pixbuf)
- [ ] Create `research_swarm/reports/` module structure

### Core Implementation
- [ ] **Step 1**: Implement `models.py` (ReportConfig, ReportData, StockReportData, ReportOutput)
- [ ] **Step 2**: Implement `data_extractor.py` (SwarmRun → ReportData transformation)
- [ ] **Step 3**: Create Jinja2 templates (5 templates in templates/ directory)
- [ ] **Step 4**: Implement `renderer.py` (Jinja2 template rendering)
- [ ] **Step 5**: Implement `visualizations.py` (matplotlib charts + NetworkX graphs)
- [ ] **Step 6**: Implement `pdf_generator.py` (Markdown → PDF via WeasyPrint)
- [ ] **Step 7**: Implement `generator.py` (main ReportGenerator orchestrator)
- [ ] **Step 8**: Update `__init__.py` (public API exports)

### CLI Integration
- [ ] **Step 9**: Add `report` command to `__main__.py`

### Testing
- [ ] **Step 10**: Create `tests/test_reports.py` (unit + integration tests)
- [ ] **Step 11**: Manual verification with real swarm run data

---

## Success Criteria

### Must Have
1. [ ] `pip install weasyprint jinja2 markdown` succeeds
2. [ ] `pytest tests/test_reports.py -v` passes
3. [ ] `python -m research_swarm report <run_id>` generates MD + PDF
4. [ ] Markdown renders correctly in viewer
5. [ ] PDF renders with embedded charts
6. [ ] Supply chain graph shows nodes/edges
7. [ ] Moat breakdown charts are color-coded (green/yellow/red)
8. [ ] Watchlist section highlights correct candidates
9. [ ] Report generation < 30 seconds
10. [ ] Cost = $0 (no LLM API calls)

### Nice to Have
- [ ] Custom CSS styling for PDF
- [ ] Company logo support
- [ ] Multi-format export (HTML)
- [ ] Interactive supply chain visualization

---

## Cost Target

| Component | Cost |
|-----------|------|
| Report generation | $0 |
| Dependencies | Free (open source) |

**This phase has zero API costs** - it's pure data transformation.

---

## Technical Architecture

### Module Structure
```
research_swarm/reports/
├── __init__.py              # Public API: generate_report()
├── models.py                # Pydantic models
├── data_extractor.py        # SwarmRun → ReportData
├── visualizations.py        # matplotlib + networkx charts
├── templates/               # Jinja2 templates
│   ├── base.md.j2
│   ├── executive_summary.md.j2
│   ├── stock_analysis.md.j2
│   ├── supply_chain.md.j2
│   └── watchlist.md.j2
├── renderer.py              # Jinja2 rendering
├── pdf_generator.py         # WeasyPrint PDF generation
└── generator.py             # Main ReportGenerator class
```

### Data Flow
```
1. User runs: python -m research_swarm report <run_id>
   ↓
2. Load SwarmRun from SQLite persistence
   ↓
3. Extract ReportData (stocks, top_picks, watchlist, costs)
   ↓
4. Generate charts (moat breakdowns, supply chain graphs)
   ↓
5. Render Jinja2 templates → Markdown
   ↓
6. Convert Markdown → PDF (WeasyPrint)
   ↓
7. Output: reports/report_<run_id>.md + .pdf + charts/
```

### Report Sections
1. **Executive Summary**: Overview, top N picks with thesis/insights
2. **Stock Analysis**: Per-stock moat breakdown tables, narratives
3. **Supply Chain**: Network graphs, hidden dependencies
4. **Watchlist**: Candidates comparison, investment theses

---

## Key Design Decisions

1. **WeasyPrint over Pandoc**: Pure Python, no external binary dependencies
2. **Jinja2 templates**: Flexible, maintainable, industry standard
3. **matplotlib + NetworkX**: Existing dependencies, proven libraries
4. **Markdown intermediate**: Human-readable, versionable output
5. **Charts as PNG**: Simple, universal, embedded in both MD and PDF

---

## CLI Commands

```bash
# Full report (markdown + PDF + charts)
python -m research_swarm report <run_id>

# Markdown only, no charts
python -m research_swarm report <run_id> --format markdown --no-charts

# PDF to custom directory with 5 top picks
python -m research_swarm report <run_id> --format pdf --output-dir ./output --top-picks 5
```

---

## Files to Create

| File | Lines (est.) | Description |
|------|--------------|-------------|
| models.py | ~150 | Pydantic models |
| data_extractor.py | ~100 | Data transformation |
| visualizations.py | ~200 | Chart generation |
| templates/*.j2 | ~200 | 5 Jinja2 templates |
| renderer.py | ~80 | Template rendering |
| pdf_generator.py | ~100 | PDF generation |
| generator.py | ~150 | Main orchestrator |
| __init__.py | ~50 | Public API |
| test_reports.py | ~200 | Tests |
| **Total** | ~1,230 | |

---

## Implementation Order

1. Models (foundation)
2. Data extractor (data access)
3. Templates (output structure)
4. Renderer (template processing)
5. Visualizations (charts)
6. PDF generator (final output)
7. Main generator (orchestration)
8. CLI integration
9. Tests
10. Manual verification

---

**Last Updated**: 2026-01-17
**Status**: Planning Complete - Ready for Builder Agent
**Previous Phase**: Phase 7 - Orchestration & Workflow ✅
**Next Phase**: Phase 9 - Scheduling & Automation
