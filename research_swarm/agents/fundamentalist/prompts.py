"""
Prompt templates for the Fundamentalist agent.

Each prompt is designed for specific LLM models and tasks.
"""

# ============================================================================
# SECTION EXTRACTION PROMPT (Haiku)
# Purpose: Extract key facts from a specific 10-K section
# ============================================================================

SECTION_EXTRACTION_PROMPT = """You are analyzing a section from a company's 10-K SEC filing.

**Section**: {section_name}
**Company**: {ticker}
**Fiscal Year**: {fiscal_year}

**Section Content** (truncated to ~30k chars):
{section_text}

---

**Task**: Extract the most important facts and data points from this section. Focus on:
- Specific numbers, percentages, and metrics
- Key business activities and operations
- Risk factors and challenges
- Strategic initiatives and changes

**Output**: Return a concise summary of key facts (max 2000 words). Be factual and specific.
"""

# ============================================================================
# FINANCIAL METRICS PROMPT (Haiku)
# Purpose: Extract structured financial metrics as JSON
# ============================================================================

FINANCIAL_METRICS_PROMPT = """You are extracting financial metrics from a 10-K filing.

**Company**: {ticker}
**Fiscal Year**: {fiscal_year}

**Relevant Sections**:
{parsed_sections}

---

**Task**: Extract the following financial metrics. If a metric is not found, use null.

Return your response as a JSON object with these fields:

{{
  "revenue": <float in millions USD>,
  "revenue_growth_yoy": <float as percentage>,
  "gross_margin": <float as percentage>,
  "operating_margin": <float as percentage>,
  "net_margin": <float as percentage>,
  "debt_to_equity": <float ratio>,
  "current_ratio": <float ratio>,
  "interest_coverage": <float ratio>,
  "rd_expense": <float in millions USD>,
  "rd_as_pct_revenue": <float as percentage>,
  "capex": <float in millions USD>,
  "capex_as_pct_revenue": <float as percentage>,
  "free_cash_flow": <float in millions USD>,
  "cash_and_equivalents": <float in millions USD>
}}

**Instructions**:
- Extract exact values from the filing
- Convert all monetary values to millions USD
- Express margins and growth rates as percentages (e.g., 25.5 not 0.255)
- Use null for metrics not found
- Return ONLY valid JSON, no other text
"""

# ============================================================================
# SUPPLY CHAIN PROMPT (Haiku)
# Purpose: Extract supply chain and business relationship data
# ============================================================================

SUPPLY_CHAIN_PROMPT = """You are extracting supply chain information from a 10-K filing.

**Company**: {ticker}
**Fiscal Year**: {fiscal_year}

**Relevant Sections**:
{parsed_sections}

---

**Task**: Extract supply chain and business relationship information. Look for BOTH explicit names AND indirect clues.

Return your response as a JSON object with these fields:

{{
  "major_customers": [<list of customer names or descriptions>],
  "customer_concentration": "<description of customer concentration risk with percentages if mentioned>",
  "major_suppliers": [<list of supplier/partner names or descriptions>],
  "supplier_dependencies": "<description of critical dependencies, even if names not disclosed>",
  "geographic_revenue": {{"<region>": <revenue in millions or percentage>}},
  "geographic_risks": [<list of geographic/geopolitical risks>]
}}

**Instructions - Be Thorough**:

1. **Look for EXPLICIT names**: "We rely on TSMC for chip manufacturing"
2. **Look for INDIRECT clues**:
   - "third-party foundries in Taiwan" → likely TSMC
   - "contract manufacturers primarily located in China" → likely Foxconn
   - "leading display manufacturers in South Korea" → likely Samsung/LG
   - "semiconductor equipment suppliers" → Applied Materials, Lam Research, ASML
   - "single-source or limited-source suppliers" → DOCUMENT THIS EVEN WITHOUT NAMES

3. **Customer Concentration**:
   - Extract ANY percentages: "largest customer 20% of revenue"
   - Note if customers are unnamed: "single customer represents significant revenue"
   - Look for phrases like "customer concentration", "major customer", "significant customer"

4. **Geographic Dependencies**:
   - Asia manufacturing → note the specific countries mentioned
   - Taiwan chips → DOCUMENT THIS (implies TSMC dependency)
   - China assembly → DOCUMENT THIS (implies Foxconn-type contractors)
   - South Korea displays/memory → DOCUMENT THIS

5. **Supply Chain Risks**:
   - Single-source suppliers (even if unnamed)
   - Geographic concentration risks
   - Geopolitical tensions mentioned
   - Natural disaster risks
   - Pandemic-related vulnerabilities

6. **What to include in lists**:
   - Explicit company names if mentioned
   - Descriptive entries if names not given: "sole-source chip manufacturer in Taiwan"
   - Industry categories: "contract manufacturers", "semiconductor foundries"

**Examples of good extraction**:
- major_suppliers: ["TSMC", "contract manufacturers in China (likely Foxconn)", "display suppliers in South Korea"]
- supplier_dependencies: "Heavily dependent on single-source semiconductor foundry in Taiwan for advanced chips. Contract manufacturing concentrated in China with limited alternatives. Critical components sourced from limited suppliers."

**Return ONLY valid JSON, no other text**
"""

# ============================================================================
# QUALITATIVE ANALYSIS PROMPT (Sonnet)
# Purpose: Deep qualitative analysis of business health
# ============================================================================

QUALITATIVE_ANALYSIS_PROMPT = """You are a seasoned financial analyst conducting a comprehensive analysis of a company's 10-K filing.

**Company**: {ticker}
**Fiscal Year**: {fiscal_year}

**Financial Metrics**:
{financial_metrics}

**Supply Chain Data**:
{supply_chain_data}

**Key Sections from 10-K**:
{parsed_sections}

---

**Task**: Provide a comprehensive qualitative analysis of the company's financial health and business position.

Your analysis should cover:

1. **Business Model & Competitive Position**
   - Core business strengths and competitive advantages
   - Market position and industry dynamics
   - Product/service differentiation

2. **Financial Performance**
   - Revenue and profitability trends
   - Margin analysis and efficiency
   - Cash generation and capital allocation

3. **Risk Assessment**
   - Key business risks and challenges
   - Supply chain vulnerabilities
   - Market, regulatory, or technological risks
   - Customer/supplier concentration risks

4. **Growth & Innovation**
   - R&D investment and innovation pipeline
   - Market expansion opportunities
   - Strategic initiatives

5. **Balance Sheet & Liquidity**
   - Debt levels and capital structure
   - Cash position and financial flexibility
   - Ability to weather downturns

**Output**: Write a clear, analytical summary (800-1200 words) that synthesizes these elements. Be balanced, noting both strengths and concerns. Focus on insights, not just restating numbers.
"""

# ============================================================================
# HEALTH SCORE PROMPT (Sonnet)
# Purpose: Score financial health across 5 dimensions
# ============================================================================

HEALTH_SCORE_PROMPT = """You are a financial analyst scoring a company's financial health on a 0-10 scale.

**Company**: {ticker}
**Fiscal Year**: {fiscal_year}

**Financial Metrics**:
{financial_metrics}

**Supply Chain Data**:
{supply_chain_data}

**Qualitative Analysis**:
{financial_analysis}

---

**Task**: Score the company's financial health across 5 dimensions on a 0-10 scale.

**Scoring Dimensions**:

1. **Profitability (0-10)**
   - Gross, operating, and net margins
   - Margin trends and sustainability
   - Return on capital
   - 10 = exceptional margins, highly profitable
   - 0 = unprofitable or negative margins

2. **Growth (0-10)**
   - Revenue growth trajectory
   - Market expansion
   - Innovation and R&D investment
   - 10 = strong, sustainable growth with innovation
   - 0 = declining revenue, no growth drivers

3. **Balance Sheet (0-10)**
   - Debt levels and leverage
   - Current ratio and liquidity
   - Asset quality
   - 10 = fortress balance sheet, minimal debt
   - 0 = overleveraged, liquidity concerns

4. **Cash Flow (0-10)**
   - Free cash flow generation
   - Cash conversion efficiency
   - Capital allocation
   - 10 = strong, consistent cash generation
   - 0 = negative cash flow, burning cash

5. **Supply Chain (0-10)**
   - Customer diversification
   - Supplier resilience
   - Geographic risk management
   - 10 = diversified, resilient supply chain
   - 0 = high concentration risk, vulnerable

**Output Format**: Return a JSON object:

{{
  "profitability": <float 0-10>,
  "growth": <float 0-10>,
  "balance_sheet": <float 0-10>,
  "cash_flow": <float 0-10>,
  "supply_chain": <float 0-10>,
  "confidence": <float 0-1>,
  "rationale": {{
    "profitability": "<brief justification>",
    "growth": "<brief justification>",
    "balance_sheet": "<brief justification>",
    "cash_flow": "<brief justification>",
    "supply_chain": "<brief justification>"
  }}
}}

**Instructions**:
- Be objective and evidence-based
- Use the full 0-10 range (avoid clustering around 5-7)
- Confidence should reflect data quality and completeness (0.7-0.95 typical)
- Each rationale should be 1-2 sentences explaining the score
- Return ONLY valid JSON, no other text
"""

# ============================================================================
# TTM-SPECIFIC PROMPTS
# ============================================================================

# ============================================================================
# FINANCIAL METRICS PROMPT - TTM (Haiku)
# Purpose: Extract quarterly metrics and calculate TTM aggregates
# ============================================================================

FINANCIAL_METRICS_PROMPT_TTM = """You are extracting financial metrics from SEC filings.

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
    "ttm_free_cash_flow": <sum>,
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
- Calculate margins from TTM figures (e.g., gross_margin = ttm_gross_profit / ttm_revenue * 100)
- Determine trend direction based on sequential growth (improving if mostly positive, declining if mostly negative)
- Use null for metrics not found
- Return ONLY valid JSON, no other text
"""

# ============================================================================
# QUALITATIVE ANALYSIS PROMPT - TTM (Sonnet)
# Purpose: Analyze TTM performance with quarterly trend context
# ============================================================================

QUALITATIVE_ANALYSIS_PROMPT_TTM = """You are a seasoned financial analyst conducting a comprehensive analysis of a company's trailing twelve months performance.

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

# ============================================================================
# HEALTH SCORE PROMPT - TTM (Haiku)
# Purpose: Score financial health with trend adjustments
# ============================================================================

HEALTH_SCORE_PROMPT_TTM = """You are a financial analyst scoring a company's financial health on a 0-10 scale.

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
