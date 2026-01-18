# Phase 8 Handoff: Report Generation

**From**: CTO Architect Agent
**To**: Builder Agent
**Date**: 2026-01-17
**Status**: Ready for Implementation

---

## Mission

Build a report generation module that transforms completed `SwarmRun` analysis data into professional Markdown and PDF reports with visualizations.

**No LLM calls required** - this is pure data transformation. Cost = $0.

---

## What You're Building

```
research_swarm/reports/
├── __init__.py              # Public API: generate_report()
├── models.py                # Pydantic models for report data
├── data_extractor.py        # SwarmRun → ReportData transformation
├── visualizations.py        # matplotlib charts (moat, supply chain)
├── templates/               # Jinja2 templates
│   ├── base.md.j2
│   ├── executive_summary.md.j2
│   ├── stock_analysis.md.j2
│   ├── supply_chain.md.j2
│   └── watchlist.md.j2
├── renderer.py              # Jinja2 template rendering
├── pdf_generator.py         # Markdown → PDF via WeasyPrint
└── generator.py             # Main ReportGenerator orchestrator
```

---

## Dependencies to Install

**Python packages** (add to requirements.txt):
```
weasyprint>=60.0
jinja2>=3.0
markdown>=3.5
```

**System dependencies** (Mac):
```bash
brew install cairo pango gdk-pixbuf libffi
```

---

## Data Sources

### SwarmRun (from orchestration)

Location: `research_swarm/orchestration/models.py`

```python
class SwarmRun(BaseModel):
    run_id: str
    run_name: Optional[str]
    tickers: List[str]
    fiscal_year: int
    status: RunStatus
    stock_results: Dict[str, StockResult]  # Key data
    cost_summary: CostSummary
    elapsed_seconds: float

    @property
    def watchlist_candidates(self) -> List[StockResult]
```

### StockResult (per stock)

```python
class StockResult(BaseModel):
    ticker: str
    status: StockStatus
    moat_score: Optional[float]
    is_watchlist_candidate: Optional[bool]
    investment_thesis: Optional[str]
    full_output: Optional[Dict]  # Contains ManagerOutput.model_dump()
    cost_usd: float
    processing_time_seconds: Optional[float]
```

### ManagerOutput (inside full_output)

Location: `research_swarm/agents/manager/models.py`

```python
class ManagerOutput(BaseModel):
    ticker: str
    synthesis_narrative: str        # 400-600 words
    key_insights: List[str]         # 3-5 items
    risk_factors: List[str]         # 3-5 items
    investment_thesis: str          # One paragraph
    moat_score: float               # 0-10
    moat_breakdown: MoatScoreBreakdown

    # Nested agent outputs
    fundamentalist_output: Dict[str, Any]
    news_hound_output: Dict[str, Any]
    quant_output: Dict[str, Any]    # Contains supply_chain_graph

class MoatScoreBreakdown(BaseModel):
    financial_health: float         # 30% weight
    sentiment_catalysts: float      # 20% weight
    technical_strength: float       # 20% weight
    supply_chain_position: float    # 30% weight
```

### Supply Chain Graph (inside quant_output)

Path: `full_output["quant_output"]["supply_chain_graph"]`

```python
{
    "nodes": [
        {"name": "NVIDIA", "ticker": "NVDA", "node_type": "root"},
        {"name": "TSMC", "ticker": "TSM", "node_type": "supplier"},
        {"name": "ASML", "ticker": "ASML", "node_type": "supplier_t2"},
        ...
    ],
    "edges": [
        {"source": "TSMC", "target": "NVIDIA", "relationship": "supplies"},
        ...
    ],
    "critical_paths": [...],
    "hidden_dependencies": ["ASML supplies multiple tier-1 suppliers"]
}
```

---

## Implementation Guide

### Step 1: Models (`models.py`)

Create these Pydantic models:

```python
class ReportType(str, Enum):
    MARKDOWN = "markdown"
    PDF = "pdf"
    BOTH = "both"

class ReportSection(str, Enum):
    EXECUTIVE_SUMMARY = "executive_summary"
    STOCK_ANALYSIS = "stock_analysis"
    SUPPLY_CHAIN = "supply_chain"
    WATCHLIST = "watchlist"

class ReportConfig(BaseModel):
    run_id: str
    output_dir: Path = Path("./reports")
    report_type: ReportType = ReportType.BOTH
    sections: List[ReportSection] = [all sections]
    top_picks_count: int = 3
    include_charts: bool = True

class StockReportData(BaseModel):
    ticker: str
    moat_score: float
    moat_breakdown: Dict[str, float]
    is_watchlist_candidate: bool
    investment_thesis: str
    key_insights: List[str]
    risk_factors: List[str]
    synthesis_narrative: str
    supply_chain_nodes: List[Dict] = []
    supply_chain_edges: List[Dict] = []
    hidden_dependencies: List[str] = []
    processing_time: float
    cost_usd: float

class ReportData(BaseModel):
    run_id: str
    run_name: Optional[str]
    generated_at: datetime
    analysis_date: str
    fiscal_year: int
    stocks: List[StockReportData]
    top_picks: List[StockReportData]
    watchlist_candidates: List[StockReportData]
    total_stocks: int
    completed_count: int
    failed_count: int
    average_moat_score: float
    total_cost_usd: float
    total_elapsed_seconds: float
    cost_by_ticker: Dict[str, float]

class ReportOutput(BaseModel):
    markdown_path: Optional[Path] = None
    pdf_path: Optional[Path] = None
    charts_generated: List[str] = []
    generation_time_seconds: float
    success: bool
    error_message: Optional[str] = None
```

### Step 2: Data Extractor (`data_extractor.py`)

```python
from research_swarm.orchestration import PersistenceManager

class DataExtractor:
    def __init__(self, persistence: PersistenceManager):
        self.persistence = persistence

    def extract(self, run_id: str, top_picks_count: int = 3) -> ReportData:
        # 1. Load SwarmRun from persistence
        run = self.persistence.get_run(run_id)

        # 2. Transform each completed StockResult → StockReportData
        stocks = []
        for ticker, result in run.stock_results.items():
            if result.status == StockStatus.COMPLETED:
                stock_data = self._extract_stock(result)
                stocks.append(stock_data)

        # 3. Sort by moat_score for top_picks
        top_picks = sorted(stocks, key=lambda s: s.moat_score, reverse=True)[:top_picks_count]

        # 4. Filter watchlist (moat >= 8.0)
        watchlist = [s for s in stocks if s.is_watchlist_candidate]

        # 5. Calculate averages
        avg_moat = sum(s.moat_score for s in stocks) / len(stocks) if stocks else 0

        return ReportData(...)

    def _extract_stock(self, result: StockResult) -> StockReportData:
        output = result.full_output  # ManagerOutput dict

        # Extract supply chain from quant_output
        quant = output.get("quant_output", {})
        sc_graph = quant.get("supply_chain_graph", {})

        return StockReportData(
            ticker=result.ticker,
            moat_score=result.moat_score,
            moat_breakdown=output["moat_breakdown"],
            is_watchlist_candidate=result.is_watchlist_candidate,
            investment_thesis=output["investment_thesis"],
            key_insights=output["key_insights"],
            risk_factors=output["risk_factors"],
            synthesis_narrative=output["synthesis_narrative"],
            supply_chain_nodes=sc_graph.get("nodes", []),
            supply_chain_edges=sc_graph.get("edges", []),
            hidden_dependencies=sc_graph.get("hidden_dependencies", []),
            processing_time=result.processing_time_seconds or 0,
            cost_usd=result.cost_usd,
        )
```

### Step 3: Visualizations (`visualizations.py`)

```python
import matplotlib.pyplot as plt
import networkx as nx
from pathlib import Path

class ChartGenerator:
    def __init__(self, output_dir: Path):
        self.charts_dir = output_dir / "charts"
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        plt.style.use("seaborn-v0_8-whitegrid")

    def generate_moat_breakdown(self, ticker: str, breakdown: Dict[str, float]) -> Path:
        """Horizontal bar chart of moat components."""
        fig, ax = plt.subplots(figsize=(8, 4))

        components = ["Financial Health (30%)", "Sentiment (20%)",
                      "Technical (20%)", "Supply Chain (30%)"]
        values = [breakdown["financial_health"], breakdown["sentiment_catalysts"],
                  breakdown["technical_strength"], breakdown["supply_chain_position"]]
        colors = ["green" if v >= 7 else "gold" if v >= 4 else "red" for v in values]

        ax.barh(components, values, color=colors)
        ax.set_xlim(0, 10)
        ax.set_xlabel("Score")
        ax.set_title(f"{ticker} Moat Score Breakdown")

        path = self.charts_dir / f"moat_{ticker}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return path

    def generate_supply_chain_graph(self, ticker: str, nodes: List, edges: List,
                                     hidden_deps: List) -> Path:
        """NetworkX supply chain visualization."""
        G = nx.DiGraph()

        # Add nodes with colors
        node_colors = {
            "root": "#4361ee",       # Blue
            "customer": "#2ecc71",   # Green
            "supplier": "#e67e22",   # Orange
            "supplier_t2": "#f1c40f" # Yellow
        }

        for node in nodes:
            G.add_node(node["name"],
                       node_type=node.get("node_type", "supplier"),
                       ticker=node.get("ticker"))

        for edge in edges:
            G.add_edge(edge["source"], edge["target"])

        fig, ax = plt.subplots(figsize=(12, 8))
        pos = nx.spring_layout(G, k=2, iterations=50)

        colors = [node_colors.get(G.nodes[n].get("node_type", "supplier"), "#gray")
                  for n in G.nodes()]

        nx.draw(G, pos, ax=ax, node_color=colors, node_size=2000,
                with_labels=True, font_size=8, arrows=True)

        ax.set_title(f"{ticker} Supply Chain Network")

        path = self.charts_dir / f"supply_chain_{ticker}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return path
```

### Step 4: Jinja2 Templates

**templates/executive_summary.md.j2**:
```jinja2
## Executive Summary

Analyzed **{{ report.total_stocks }}** stocks | Average Moat: **{{ "%.1f"|format(report.average_moat_score) }}/10**

### Top {{ top_picks|length }} Picks

{% for stock in top_picks %}
#### {{ loop.index }}. {{ stock.ticker }} ({{ "%.1f"|format(stock.moat_score) }}/10) {% if stock.is_watchlist_candidate %}*Watchlist*{% endif %}

{{ stock.investment_thesis }}

**Key Insights**:
{% for insight in stock.key_insights %}
- {{ insight }}
{% endfor %}

{% if include_charts %}
![{{ stock.ticker }} Moat](./charts/moat_{{ stock.ticker }}.png)
{% endif %}
---
{% endfor %}
```

### Step 5: PDF Generator (`pdf_generator.py`)

```python
import markdown
from weasyprint import HTML, CSS

class PDFGenerator:
    def __init__(self):
        self.css = CSS(string="""
            @page { size: letter; margin: 1in; }
            body { font-family: Arial, sans-serif; font-size: 11pt; }
            h1 { color: #1a1a2e; border-bottom: 2px solid #4361ee; }
            h2 { color: #16213e; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; }
            th { background: #4361ee; color: white; }
            img { max-width: 100%; }
        """)

    def generate(self, markdown_path: Path, output_path: Path) -> Path:
        with open(markdown_path) as f:
            md_content = f.read()

        html = markdown.markdown(md_content, extensions=["tables", "fenced_code"])
        # Fix relative image paths to absolute
        html = self._fix_image_paths(html, markdown_path.parent)

        HTML(string=f"<html><body>{html}</body></html>",
             base_url=str(markdown_path.parent)).write_pdf(
            output_path, stylesheets=[self.css])

        return output_path
```

### Step 6: Main Generator (`generator.py`)

```python
class ReportGenerator:
    def __init__(self, persistence=None):
        self.persistence = persistence or PersistenceManager()
        self.extractor = DataExtractor(self.persistence)
        self.renderer = TemplateRenderer()

    def generate(self, config: ReportConfig) -> ReportOutput:
        start = time.time()

        # 1. Extract data
        report_data = self.extractor.extract(config.run_id, config.top_picks_count)

        # 2. Generate charts
        charts = []
        if config.include_charts:
            chart_gen = ChartGenerator(config.output_dir)
            for stock in report_data.stocks:
                charts.append(str(chart_gen.generate_moat_breakdown(
                    stock.ticker, stock.moat_breakdown)))
                if stock.supply_chain_nodes:
                    charts.append(str(chart_gen.generate_supply_chain_graph(
                        stock.ticker, stock.supply_chain_nodes,
                        stock.supply_chain_edges, stock.hidden_dependencies)))

        # 3. Render markdown
        markdown_content = self.renderer.render_full_report(
            report_data, config.sections, config.include_charts)

        # 4. Save markdown
        md_path = config.output_dir / f"report_{config.run_id[:8]}.md"
        md_path.write_text(markdown_content)

        # 5. Generate PDF if requested
        pdf_path = None
        if config.report_type in [ReportType.PDF, ReportType.BOTH]:
            pdf_gen = PDFGenerator()
            pdf_path = config.output_dir / f"report_{config.run_id[:8]}.pdf"
            pdf_gen.generate(md_path, pdf_path)

        return ReportOutput(
            markdown_path=md_path,
            pdf_path=pdf_path,
            charts_generated=charts,
            generation_time_seconds=time.time() - start,
            success=True
        )
```

### Step 7: CLI Integration

Add to `__main__.py`:

```python
# In main():
parser_report = subparsers.add_parser("report", help="Generate report")
parser_report.add_argument("run_id", help="Run ID")
parser_report.add_argument("--format", choices=["markdown", "pdf", "both"], default="both")
parser_report.add_argument("--output-dir", default="./reports")
parser_report.add_argument("--no-charts", action="store_true")
parser_report.add_argument("--top-picks", type=int, default=3)
parser_report.set_defaults(func=cmd_report)

def cmd_report(args):
    from research_swarm.reports import generate_report

    result = generate_report(
        run_id=args.run_id,
        output_dir=args.output_dir,
        report_type=args.format,
        include_charts=not args.no_charts,
        top_picks=args.top_picks,
    )

    if result.success:
        logger.success("Report generated!")
        if result.markdown_path:
            logger.info(f"Markdown: {result.markdown_path}")
        if result.pdf_path:
            logger.info(f"PDF: {result.pdf_path}")
        return 0
    else:
        logger.error(f"Failed: {result.error_message}")
        return 1
```

---

## Testing

Create `tests/test_reports.py`:

```python
import pytest
from pathlib import Path
from unittest.mock import Mock

from research_swarm.reports.models import ReportConfig, StockReportData, ReportType
from research_swarm.reports.data_extractor import DataExtractor
from research_swarm.reports.visualizations import ChartGenerator
from research_swarm.reports.generator import ReportGenerator

class TestModels:
    def test_report_config_defaults(self):
        config = ReportConfig(run_id="test-123")
        assert config.report_type == ReportType.BOTH
        assert config.include_charts is True

class TestChartGenerator:
    def test_moat_breakdown_creates_png(self, tmp_path):
        gen = ChartGenerator(tmp_path)
        breakdown = {"financial_health": 8.0, "sentiment_catalysts": 7.0,
                     "technical_strength": 6.0, "supply_chain_position": 9.0}
        path = gen.generate_moat_breakdown("NVDA", breakdown)
        assert path.exists()
        assert path.suffix == ".png"

class TestDataExtractor:
    def test_extract_with_mock_persistence(self):
        mock_pm = Mock()
        mock_run = Mock()
        mock_run.run_id = "test"
        mock_run.stock_results = {}
        mock_run.cost_summary.total_cost_usd = 0
        mock_run.elapsed_seconds = 0
        mock_pm.get_run.return_value = mock_run

        extractor = DataExtractor(mock_pm)
        data = extractor.extract("test")
        assert data.run_id == "test"
```

---

## Success Criteria

- [ ] `pip install weasyprint jinja2 markdown` succeeds
- [ ] `pytest tests/test_reports.py -v` passes
- [ ] `python -m research_swarm report <run_id>` generates MD + PDF
- [ ] Markdown displays correctly in viewer
- [ ] PDF renders with embedded charts
- [ ] Supply chain graphs show node hierarchy
- [ ] Moat breakdown charts are color-coded (green/yellow/red)
- [ ] Watchlist candidates correctly identified
- [ ] Report generation < 30 seconds
- [ ] Cost = $0 (no LLM API calls)

---

## CLI Usage

```bash
# Full report with charts
python -m research_swarm report <run_id>

# Markdown only, no charts
python -m research_swarm report <run_id> --format markdown --no-charts

# PDF to custom directory
python -m research_swarm report <run_id> --format pdf --output-dir ./output
```

---

## Files to Create

1. `research_swarm/reports/models.py`
2. `research_swarm/reports/data_extractor.py`
3. `research_swarm/reports/visualizations.py`
4. `research_swarm/reports/templates/base.md.j2`
5. `research_swarm/reports/templates/executive_summary.md.j2`
6. `research_swarm/reports/templates/stock_analysis.md.j2`
7. `research_swarm/reports/templates/supply_chain.md.j2`
8. `research_swarm/reports/templates/watchlist.md.j2`
9. `research_swarm/reports/renderer.py`
10. `research_swarm/reports/pdf_generator.py`
11. `research_swarm/reports/generator.py`
12. `research_swarm/reports/__init__.py` (update)
13. `tests/test_reports.py`

## Files to Modify

1. `research_swarm/__main__.py` - Add `report` command
2. `requirements.txt` - Add weasyprint, jinja2, markdown

---

## Estimated Time: ~8 hours

Good luck, Builder!
