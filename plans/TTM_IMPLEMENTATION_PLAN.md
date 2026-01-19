# TTM Quarterly Analysis Implementation Plan

## Overview

This plan details the remaining changes needed to convert the Fundamentalist agent from analyzing a single fiscal year (10-K) to analyzing trailing twelve months (TTM) using quarterly data (10-Q filings).

**Already Completed:**
- Cost tracking fix (tokens now tracked in Fundamentalist and News Hound agents)
- SEC client `get_10q_filing()` and `get_ttm_filings()` methods

**Remaining Work:**
- Fundamentalist agent refactoring (state, models, prompts, analyzer, graph, scorer)
- Manager agent updates
- Report template updates

---

## Phase 1: Update Fundamentalist State Schema

**File:** `research_swarm/agents/fundamentalist/state.py`

### Current State
```python
class FundamentalistState(TypedDict, total=False):
    ticker: str
    fiscal_year: int  # <-- CHANGE THIS
    # ... rest of fields
```

### Required Changes

Replace `fiscal_year: int` with quarterly-aware fields:

```python
class FundamentalistState(TypedDict, total=False):
    # Input fields
    ticker: str
    # REMOVED: fiscal_year: int

    # NEW: Quarterly analysis fields
    quarters: List[str]  # ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"]
    analysis_period: str  # "TTM Q4 2024 - Q3 2025"
    analysis_mode: str  # "ttm" or "annual" (for backward compatibility)

    # Status tracking (unchanged)
    status: str
    error: Optional[str]

    # Raw filing data - CHANGED
    # REMOVED: filing_raw: Optional[Dict[str, Any]]
    filings_raw: Optional[Dict[str, Dict[str, Any]]]  # Keyed by quarter label
    parsed_sections_by_quarter: Optional[Dict[str, Dict[str, str]]]

    # For backward compatibility (annual mode)
    filing_raw: Optional[Dict[str, Any]]
    parsed_sections: Optional[Dict[str, str]]

    # Extracted data - CHANGED
    financial_metrics_by_quarter: Optional[Dict[str, Dict[str, Any]]]
    quarterly_trends: Optional[Dict[str, Any]]

    # Keep existing for backward compatibility
    financial_metrics: Optional[Dict[str, Any]]
    supply_chain_data: Optional[Dict[str, Any]]

    # Analysis results (unchanged)
    financial_analysis: Optional[str]
    financial_health_score: Optional[float]
    score_breakdown: Optional[Dict[str, float]]
    confidence: Optional[float]

    # NEW: Data quality tracking
    data_quality: Optional[Dict[str, str]]  # Quarter -> "10-Q" | "10-K" | "missing"

    # Metadata (unchanged)
    tokens_used: int
    processing_time: Optional[float]
```

---

## Phase 2: Add Quarterly Models

**File:** `research_swarm/agents/fundamentalist/models.py`

### Add New Pydantic Models

Add these new classes after the existing models:

```python
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class QuarterlyMetrics(BaseModel):
    """Financial metrics for a single quarter."""
    quarter: str = Field(..., description="Quarter label (e.g., 'Q3_2025')")
    period_end_date: Optional[str] = Field(None, description="Fiscal period end date")

    # Core metrics (in millions USD)
    revenue: Optional[float] = Field(None, description="Quarterly revenue")
    gross_profit: Optional[float] = Field(None, description="Quarterly gross profit")
    operating_income: Optional[float] = Field(None, description="Quarterly operating income")
    net_income: Optional[float] = Field(None, description="Quarterly net income")

    # Cash flow
    operating_cash_flow: Optional[float] = Field(None, description="Operating cash flow")
    free_cash_flow: Optional[float] = Field(None, description="Free cash flow")


class TTMMetrics(BaseModel):
    """Trailing Twelve Month aggregated metrics."""
    quarters_included: List[str] = Field(..., description="Quarters in TTM calculation")

    # Aggregated TTM figures (in millions USD)
    ttm_revenue: Optional[float] = Field(None, description="TTM total revenue")
    ttm_gross_profit: Optional[float] = Field(None, description="TTM gross profit")
    ttm_operating_income: Optional[float] = Field(None, description="TTM operating income")
    ttm_net_income: Optional[float] = Field(None, description="TTM net income")
    ttm_free_cash_flow: Optional[float] = Field(None, description="TTM free cash flow")

    # Calculated margins (percentages)
    gross_margin: Optional[float] = Field(None, description="Gross margin %")
    operating_margin: Optional[float] = Field(None, description="Operating margin %")
    net_margin: Optional[float] = Field(None, description="Net margin %")

    # Growth (vs prior TTM if calculable)
    revenue_growth_yoy: Optional[float] = Field(None, description="YoY revenue growth %")


class QuarterlyTrends(BaseModel):
    """Quarter-over-quarter trend analysis."""
    # Revenue trend (chronological order, oldest to newest)
    revenue_trend: List[Optional[float]] = Field(default_factory=list)
    margin_trend: List[Optional[float]] = Field(default_factory=list)

    # Calculated trends
    trend_direction: str = Field("stable", description="'improving', 'stable', or 'declining'")
    sequential_growth_rates: List[Optional[float]] = Field(default_factory=list, description="QoQ growth rates")

    # Momentum indicator
    momentum_score: float = Field(5.0, ge=0, le=10, description="Trend momentum 0-10")


class TTMAnalysisOutput(BaseModel):
    """Extended output for TTM analysis mode."""
    quarterly_metrics: List[QuarterlyMetrics] = Field(default_factory=list)
    ttm_metrics: TTMMetrics
    quarterly_trends: QuarterlyTrends
    data_quality: Dict[str, str] = Field(default_factory=dict)
```

### Update FundamentalistOutput

Modify the existing `FundamentalistOutput` class:

```python
class FundamentalistOutput(BaseModel):
    """Output from the Fundamentalist agent."""
    ticker: str

    # CHANGED: Replace fiscal_year with analysis_period
    # fiscal_year: int  # REMOVE
    analysis_period: str = Field(..., description="Analysis period (e.g., 'TTM Q4 2024 - Q3 2025')")
    quarters_analyzed: List[str] = Field(default_factory=list, description="Quarters analyzed")
    analysis_mode: str = Field("ttm", description="'ttm' or 'annual'")

    filing_date: Optional[str] = Field(None, description="Most recent filing date")
    filing_dates: Dict[str, str] = Field(default_factory=dict, description="Filing dates by quarter")

    # NEW: Quarterly data
    quarterly_metrics: List[QuarterlyMetrics] = Field(default_factory=list)
    ttm_metrics: Optional[TTMMetrics] = None
    quarterly_trends: Optional[QuarterlyTrends] = None

    # PRESERVED: For backward compatibility
    financial_metrics: FinancialMetricsOutput
    supply_chain_data: SupplyChainOutput
    financial_analysis: str
    financial_health_score: float
    score_breakdown: ScoreBreakdown
    confidence: float

    # NEW: Data quality
    data_quality: Dict[str, str] = Field(default_factory=dict)

    tokens_used: int
    processing_time: float
```

---

## Phase 3: Update Prompts

**File:** `research_swarm/agents/fundamentalist/prompts.py`

### Changes Required

**1. SECTION_EXTRACTION_PROMPT** (Line 12-30)

Replace:
```python
**Fiscal Year**: {fiscal_year}
```

With:
```python
**Quarter**: {quarter}
**Filing Type**: {filing_type}
**Analysis Period**: {analysis_period}
```

**2. FINANCIAL_METRICS_PROMPT** (Lines 37-74)

Replace the entire prompt with a quarterly-aware version:

```python
FINANCIAL_METRICS_PROMPT = """You are extracting financial metrics from SEC filings.

**Company**: {ticker}
**Analysis Period**: {analysis_period}
**Quarters Being Analyzed**: {quarters}

**Quarterly Filing Data**:
{quarterly_sections}

---

**Task**: Extract financial metrics for each quarter AND calculate TTM totals.

Return your response as a JSON object:

{{
  "quarterly": [
    {{
      "quarter": "Q4_2024",
      "revenue": <float in millions USD>,
      "gross_profit": <float in millions USD>,
      "operating_income": <float in millions USD>,
      "net_income": <float in millions USD>,
      "operating_cash_flow": <float in millions USD or null>,
      "free_cash_flow": <float in millions USD or null>
    }},
    // ... Q1_2025, Q2_2025, Q3_2025
  ],
  "ttm": {{
    "ttm_revenue": <sum of quarterly revenues>,
    "ttm_gross_profit": <sum>,
    "ttm_operating_income": <sum>,
    "ttm_net_income": <sum>,
    "gross_margin": <float as percentage>,
    "operating_margin": <float as percentage>,
    "net_margin": <float as percentage>,
    "revenue_growth_yoy": <float as percentage vs prior TTM if calculable, else null>
  }},
  "trends": {{
    "revenue_trend": [<Q4 rev>, <Q1 rev>, <Q2 rev>, <Q3 rev>],
    "margin_trend": [<Q4 margin>, <Q1 margin>, <Q2 margin>, <Q3 margin>],
    "trend_direction": "<improving|stable|declining>",
    "sequential_growth_rates": [<Q4-Q1 growth %>, <Q1-Q2 growth %>, <Q2-Q3 growth %>]
  }}
}}

**Instructions**:
- Extract metrics for each quarter separately
- Sum quarterly figures for TTM totals
- Calculate margins from TTM figures
- Determine trend direction based on sequential growth
- Use null for metrics not found
- Return ONLY valid JSON, no other text
"""
```

**3. QUALITATIVE_ANALYSIS_PROMPT** (Lines 119-166)

Update to reference quarterly data:

```python
QUALITATIVE_ANALYSIS_PROMPT = """You are a seasoned financial analyst conducting a comprehensive analysis of a company's trailing twelve months performance.

**Company**: {ticker}
**Analysis Period**: {analysis_period}
**Quarters Analyzed**: {quarters}

**TTM Financial Metrics**:
{ttm_metrics}

**Quarterly Trends**:
{quarterly_trends}

**Supply Chain Data**:
{supply_chain_data}

**Key Sections from Most Recent Filing**:
{parsed_sections}

---

**Task**: Provide a comprehensive qualitative analysis of the company's financial health and business position, with emphasis on recent trends.

Your analysis should cover:

1. **Business Model & Competitive Position**
   - Core business strengths and competitive advantages
   - Market position and industry dynamics

2. **Financial Performance & Trends**
   - TTM revenue and profitability analysis
   - **Quarter-over-quarter trends** (improving, stable, or declining)
   - Margin analysis and efficiency changes over the 4 quarters
   - Momentum assessment

3. **Risk Assessment**
   - Key business risks and challenges
   - Supply chain vulnerabilities
   - Any deteriorating trends to watch

4. **Growth & Innovation**
   - R&D investment trajectory
   - Market expansion signals
   - Strategic initiatives

5. **Balance Sheet & Liquidity**
   - Debt levels and capital structure
   - Cash flow trends
   - Financial flexibility

**Output**: Write a clear, analytical summary (800-1200 words) that synthesizes these elements. **Explicitly reference quarter-over-quarter trends** and whether the company's trajectory is improving or declining.
"""
```

**4. HEALTH_SCORE_PROMPT** (Lines 173-252)

Update scoring criteria to include trend factors:

```python
HEALTH_SCORE_PROMPT = """You are a financial analyst scoring a company's financial health on a 0-10 scale.

**Company**: {ticker}
**Analysis Period**: {analysis_period}

**TTM Financial Metrics**:
{ttm_metrics}

**Quarterly Trends**:
{quarterly_trends}

**Supply Chain Data**:
{supply_chain_data}

**Qualitative Analysis**:
{financial_analysis}

**Data Quality** (which quarters had data):
{data_quality}

---

**Task**: Score the company's financial health across 5 dimensions on a 0-10 scale.

**IMPORTANT**: Factor in quarterly trends when scoring:
- **Improving trends** should boost scores by 0.5-1.0 points
- **Declining trends** should reduce scores by 0.5-1.0 points
- **Missing data** should reduce confidence

**Scoring Dimensions**:

1. **Profitability (0-10)** - Weight: 25%
   - TTM margins and profitability
   - **Margin trend over 4 quarters**

2. **Growth (0-10)** - Weight: 20%
   - TTM revenue level
   - **Sequential quarter growth trajectory**
   - Momentum direction

3. **Balance Sheet (0-10)** - Weight: 20%
   - Debt levels and leverage
   - Liquidity position

4. **Cash Flow (0-10)** - Weight: 15%
   - TTM free cash flow
   - **Cash flow trend direction**

5. **Supply Chain (0-10)** - Weight: 20%
   - Customer/supplier diversification
   - Geographic risk

**Output Format**: Return a JSON object:

{{
  "profitability": <float 0-10>,
  "growth": <float 0-10>,
  "balance_sheet": <float 0-10>,
  "cash_flow": <float 0-10>,
  "supply_chain": <float 0-10>,
  "confidence": <float 0-1>,
  "rationale": {{
    "profitability": "<brief justification including trend>",
    "growth": "<brief justification including trend>",
    "balance_sheet": "<brief justification>",
    "cash_flow": "<brief justification including trend>",
    "supply_chain": "<brief justification>"
  }}
}}

**Confidence Adjustments**:
- 4/4 quarters available: confidence 0.8-0.95
- 3/4 quarters available: confidence 0.6-0.8
- 2/4 quarters available: confidence 0.4-0.6
- 1/4 quarters available: confidence 0.3-0.4

Return ONLY valid JSON, no other text.
"""
```

**5. SUPPLY_CHAIN_PROMPT** (Lines 81-112)

Minimal change - just update the header:

```python
**Analysis Period**: {analysis_period}
```

Instead of:
```python
**Fiscal Year**: {fiscal_year}
```

---

## Phase 4: Update Analyzer

**File:** `research_swarm/agents/fundamentalist/analyzer.py`

### Add New Methods

Add these methods to the `FinancialAnalyzer` class:

```python
def extract_metrics_quarterly(
    self,
    ticker: str,
    analysis_period: str,
    quarters: List[str],
    parsed_sections_by_quarter: Dict[str, Dict[str, str]]
) -> Tuple[List[QuarterlyMetrics], TTMMetrics, QuarterlyTrends, int]:
    """
    Extract metrics from multiple quarters and calculate TTM.

    Args:
        ticker: Stock ticker
        analysis_period: Period string (e.g., "TTM Q4 2024 - Q3 2025")
        quarters: List of quarter labels in chronological order
        parsed_sections_by_quarter: Parsed sections keyed by quarter

    Returns:
        Tuple of (quarterly_metrics_list, ttm_metrics, trends, tokens_used)
    """
    logger.info(f"Extracting quarterly metrics for {ticker} {analysis_period}")

    # Format quarterly sections for prompt
    quarterly_sections = self._format_quarterly_sections(parsed_sections_by_quarter)

    prompt = FINANCIAL_METRICS_PROMPT_TTM.format(
        ticker=ticker,
        analysis_period=analysis_period,
        quarters=", ".join(quarters),
        quarterly_sections=quarterly_sections
    )

    try:
        response = self.haiku.invoke(prompt)
        response_text = response.content.strip()
        tokens_used = response.response_metadata.get("usage", {}).get("total_tokens", 0)

        json_text = self._extract_json(response_text)
        data = json.loads(json_text)

        # Parse quarterly metrics
        quarterly_metrics = []
        for q_data in data.get("quarterly", []):
            quarterly_metrics.append(QuarterlyMetrics(**q_data))

        # Parse TTM metrics
        ttm_data = data.get("ttm", {})
        ttm_metrics = TTMMetrics(
            quarters_included=quarters,
            **ttm_data
        )

        # Parse trends
        trends_data = data.get("trends", {})
        quarterly_trends = QuarterlyTrends(**trends_data)

        logger.success(f"✓ Extracted quarterly metrics for {ticker} ({tokens_used} tokens)")
        return quarterly_metrics, ttm_metrics, quarterly_trends, tokens_used

    except Exception as e:
        logger.error(f"Error extracting quarterly metrics: {e}")
        # Return empty defaults
        return [], TTMMetrics(quarters_included=quarters), QuarterlyTrends(), 0


def analyze_qualitative_ttm(
    self,
    ticker: str,
    analysis_period: str,
    quarters: List[str],
    parsed_sections_by_quarter: Dict[str, Dict[str, str]],
    ttm_metrics: TTMMetrics,
    quarterly_trends: QuarterlyTrends,
    supply_chain_data: SupplyChainOutput
) -> Tuple[str, int]:
    """
    Perform qualitative analysis on TTM data with trend context.

    Returns:
        Tuple of (analysis_text, tokens_used)
    """
    logger.info(f"Performing TTM qualitative analysis for {ticker}")

    # Use most recent quarter's sections for detailed analysis
    most_recent_quarter = quarters[-1]
    parsed_sections = parsed_sections_by_quarter.get(most_recent_quarter, {})

    sections_text = self._format_sections_for_prompt(
        parsed_sections,
        sections=["Item 1", "Item 1A", "Item 7"],
        max_length=15000
    )

    prompt = QUALITATIVE_ANALYSIS_PROMPT_TTM.format(
        ticker=ticker,
        analysis_period=analysis_period,
        quarters=", ".join(quarters),
        ttm_metrics=json.dumps(ttm_metrics.model_dump(), indent=2),
        quarterly_trends=json.dumps(quarterly_trends.model_dump(), indent=2),
        supply_chain_data=json.dumps(supply_chain_data.model_dump(), indent=2),
        parsed_sections=sections_text
    )

    try:
        response = self.sonnet.invoke(prompt)
        analysis = response.content.strip()
        tokens_used = response.response_metadata.get("usage", {}).get("total_tokens", 0)
        logger.success(f"✓ Generated TTM qualitative analysis ({len(analysis)} chars, {tokens_used} tokens)")
        return analysis, tokens_used
    except Exception as e:
        logger.error(f"Error in TTM qualitative analysis: {e}")
        return f"Error performing analysis: {str(e)}", 0


def _format_quarterly_sections(
    self,
    parsed_sections_by_quarter: Dict[str, Dict[str, str]],
    max_per_quarter: int = 8000
) -> str:
    """Format quarterly sections for prompt."""
    output = []
    for quarter, sections in parsed_sections_by_quarter.items():
        output.append(f"\n## {quarter}\n")
        for section_name, content in sections.items():
            truncated = content[:max_per_quarter] if len(content) > max_per_quarter else content
            output.append(f"### {section_name}\n{truncated}\n")
    return "\n".join(output)
```

### Keep Existing Methods

Keep the existing `extract_metrics()`, `extract_supply_chain()`, and `analyze_qualitative()` methods for backward compatibility (annual mode).

---

## Phase 5: Update Graph Workflow

**File:** `research_swarm/agents/fundamentalist/graph.py`

### New Node Functions

Add these new node functions for TTM mode:

```python
def fetch_quarterly_filings_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 1 (TTM): Fetch trailing 4 quarters of filings.
    """
    logger.info(f"[Node 1-TTM] Fetching quarterly filings for {state['ticker']}")

    state["status"] = "fetching"

    # Use SEC client to get TTM filings
    ttm_result = sec_client.get_ttm_filings(state["ticker"])

    metadata = ttm_result.pop("_metadata", {})

    # Store filings keyed by quarter
    state["filings_raw"] = ttm_result
    state["quarters"] = metadata.get("quarters", [])
    state["analysis_period"] = metadata.get("analysis_period", "")
    state["data_quality"] = metadata.get("data_quality", {})

    available = metadata.get("available_quarters", 0)
    if available == 0:
        state["status"] = "error"
        state["error"] = f"No quarterly filings found for {state['ticker']}"
        return state

    logger.success(f"✓ Fetched {available}/4 quarterly filings")
    return state


def parse_quarterly_sections_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 2 (TTM): Parse sections for each quarter.
    """
    logger.info(f"[Node 2-TTM] Parsing quarterly sections for {state['ticker']}")

    state["status"] = "parsing"

    parsed_by_quarter = {}
    for quarter_label, filing in state["filings_raw"].items():
        if filing is None:
            continue

        filing_text = filing.get("text", "")
        if len(filing_text) < 1000:
            logger.warning(f"Insufficient text for {quarter_label}")
            continue

        parsed = parser.parse_filing(
            state["ticker"],
            filing.get("year", 0),
            filing_text
        )

        if parsed and any(v for v in parsed.values()):
            parsed_by_quarter[quarter_label] = parsed

    if not parsed_by_quarter:
        state["status"] = "error"
        state["error"] = "Failed to parse any quarterly sections"
        return state

    state["parsed_sections_by_quarter"] = parsed_by_quarter
    logger.success(f"✓ Parsed {len(parsed_by_quarter)} quarters")
    return state


def extract_metrics_ttm_node(state: FundamentalistState) -> FundamentalistState:
    """
    Node 3 (TTM): Extract quarterly metrics and calculate TTM.
    """
    logger.info(f"[Node 3-TTM] Extracting TTM metrics for {state['ticker']}")

    state["status"] = "analyzing"

    try:
        quarterly_metrics, ttm_metrics, trends, tokens = analyzer.extract_metrics_quarterly(
            state["ticker"],
            state["analysis_period"],
            state["quarters"],
            state["parsed_sections_by_quarter"]
        )

        state["quarterly_metrics"] = [m.model_dump() for m in quarterly_metrics]
        state["ttm_metrics"] = ttm_metrics.model_dump()
        state["quarterly_trends"] = trends.model_dump()
        state["tokens_used"] = state.get("tokens_used", 0) + tokens

        # Also populate legacy financial_metrics for compatibility
        state["financial_metrics"] = {
            "revenue": ttm_metrics.ttm_revenue,
            "gross_margin": ttm_metrics.gross_margin,
            "operating_margin": ttm_metrics.operating_margin,
            "net_margin": ttm_metrics.net_margin,
            "revenue_growth_yoy": ttm_metrics.revenue_growth_yoy,
            # ... other fields as needed
        }

    except Exception as e:
        logger.error(f"Failed to extract TTM metrics: {e}")
        state["status"] = "error"
        state["error"] = f"Failed to extract TTM metrics: {str(e)}"

    return state
```

### Update Main Function

Update `analyze_company()` to support both modes:

```python
def analyze_company(
    ticker: str,
    quarters: List[str] = None,
    fiscal_year: int = None,  # Deprecated, for backward compatibility
    fallback_to_annual: bool = True
) -> FundamentalistOutput:
    """
    Analyze a company's financial health.

    Args:
        ticker: Stock ticker
        quarters: List of quarters to analyze (TTM mode)
        fiscal_year: Deprecated - fiscal year for annual mode
        fallback_to_annual: If TTM fails, fall back to annual 10-K

    Returns:
        FundamentalistOutput
    """
    # Determine analysis mode
    if quarters:
        analysis_mode = "ttm"
    elif fiscal_year:
        analysis_mode = "annual"
        logger.warning("fiscal_year parameter is deprecated, use quarters for TTM analysis")
    else:
        analysis_mode = "ttm"  # Default to TTM

    if analysis_mode == "ttm":
        return _analyze_company_ttm(ticker, quarters, fallback_to_annual)
    else:
        return _analyze_company_annual(ticker, fiscal_year)


def _analyze_company_ttm(ticker: str, quarters: List[str], fallback_to_annual: bool) -> FundamentalistOutput:
    """TTM analysis mode."""
    # Build and run TTM workflow
    # ... implementation
    pass


def _analyze_company_annual(ticker: str, fiscal_year: int) -> FundamentalistOutput:
    """Annual analysis mode (legacy)."""
    # Existing implementation
    pass
```

---

## Phase 6: Update Scorer

**File:** `research_swarm/agents/fundamentalist/scorer.py`

### Add Trend-Aware Scoring

```python
def score_health_ttm(
    self,
    ticker: str,
    analysis_period: str,
    ttm_metrics: TTMMetrics,
    quarterly_trends: QuarterlyTrends,
    supply_chain_data: SupplyChainOutput,
    financial_analysis: str,
    data_quality: Dict[str, str]
) -> Tuple[float, ScoreBreakdown, float, int]:
    """
    Score financial health with trend adjustments.

    Trend adjustments:
    - Improving trends: +0.5 to +1.0 on relevant scores
    - Declining trends: -0.5 to -1.0 on relevant scores
    - Missing quarters: reduce confidence
    """
    # ... implementation using updated HEALTH_SCORE_PROMPT
```

---

## Phase 7: Update Manager Agent

**File:** `research_swarm/agents/manager/prompts.py`

### Update SYNTHESIS_PROMPT

Replace:
```python
**Fiscal Year**: {fiscal_year}
```

With:
```python
**Analysis Period**: {analysis_period}
**Trend Direction**: {trend_direction}
```

Add a new section for quarterly trends:
```
**Quarterly Trends**:
{quarterly_trends_summary}
```

**File:** `research_swarm/agents/manager/graph.py`

Update `analyze_swarm()` signature:

```python
def analyze_swarm(
    ticker: str,
    quarters: List[str] = None,  # NEW
    fiscal_year: int = None,  # Deprecated
    news_days_back: int = 30
) -> ManagerOutput:
```

**File:** `research_swarm/agents/manager/state.py`

Replace:
```python
fiscal_year: int
```

With:
```python
quarters: List[str]
analysis_period: str
```

---

## Phase 8: Update Report Templates

**File:** `research_swarm/reports/templates/base.md.j2`

Replace:
```jinja2
**Fiscal Year:** {{ report.fiscal_year }}
```

With:
```jinja2
**Analysis Period:** {{ report.analysis_period }}
```

**File:** `research_swarm/reports/templates/executive_summary.md.j2`

Replace:
```jinja2
Analyzed **{{ report.total_stocks }}** stocks for fiscal year {{ report.fiscal_year }}.
```

With:
```jinja2
Analyzed **{{ report.total_stocks }}** stocks for {{ report.analysis_period }}.
```

**File:** `research_swarm/reports/models.py`

Replace:
```python
fiscal_year: int = Field(..., description="Fiscal year analyzed")
```

With:
```python
analysis_period: str = Field(..., description="Analysis period (e.g., 'TTM Q4 2024 - Q3 2025')")
quarters_analyzed: List[str] = Field(default_factory=list, description="Quarters analyzed")
```

---

## Phase 9: Update Orchestration Layer

**File:** `research_swarm/orchestration/models.py`

Update `SwarmRun`:
```python
class SwarmRun(BaseModel):
    # Replace fiscal_year with:
    analysis_period: str
    quarters: List[str]
```

**File:** `research_swarm/__main__.py`

Update CLI arguments:
```python
parser_run.add_argument(
    "--quarters",
    nargs=4,
    metavar="QUARTER",
    default=None,
    help="Quarters to analyze (e.g., Q4_2024 Q1_2025 Q2_2025 Q3_2025)"
)
parser_run.add_argument(
    "--fiscal-year",
    type=int,
    default=None,
    help="[Deprecated] Fiscal year for annual analysis"
)
```

---

## Implementation Order

1. **Phase 2 (Models)** - Add new models first (no breaking changes)
2. **Phase 1 (State)** - Update state schema (add new fields, keep old for compat)
3. **Phase 3 (Prompts)** - Update prompts (create new TTM variants)
4. **Phase 4 (Analyzer)** - Add new methods (keep existing)
5. **Phase 5 (Graph)** - Add new nodes, update main function
6. **Phase 6 (Scorer)** - Add TTM scoring method
7. **Phase 7 (Manager)** - Update manager to pass new parameters
8. **Phase 8 (Templates)** - Update display text
9. **Phase 9 (Orchestration)** - Update CLI and models

---

## Testing Checklist

- [ ] Unit test: `get_10q_filing()` returns valid data
- [ ] Unit test: `get_ttm_filings()` returns 4 quarters
- [ ] Unit test: QuarterlyMetrics/TTMMetrics models validate correctly
- [ ] Integration test: Full TTM analysis for AAPL
- [ ] Regression test: Annual mode still works with `--fiscal-year`
- [ ] Report test: Executive summary shows "TTM Q4 2024 - Q3 2025"
- [ ] Cost test: `tokens_used` and costs are non-zero

---

## Fallback Behavior

If TTM mode fails (no 10-Q filings available):
1. Log warning about limited data
2. If `fallback_to_annual=True`, use 10-K for most recent fiscal year
3. Set `analysis_mode: "annual"` in output
4. Reduce confidence score by 0.2
5. Add note in analysis about data limitations
