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
# QUALITATIVE ANALYSIS PROMPT (Sonnet)
# Purpose: Deep qualitative analysis of business health
# ============================================================================

QUALITATIVE_ANALYSIS_PROMPT = """You are a seasoned financial analyst conducting a comprehensive analysis of a company's 10-K filing.

**Company**: {ticker}
**Fiscal Year**: {fiscal_year}

**Financial Metrics**:
{financial_metrics}

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
   - Market, regulatory, or technological risks
   - Operational risks and challenges

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

**Qualitative Analysis**:
{financial_analysis}

---

**Task**: Score the company's financial health across 4 dimensions on a 0-10 scale.

**Scoring Dimensions**:

1. **Profitability (0-10)** - Weight: 30%
   - Gross, operating, and net margins
   - Margin trends and sustainability
   - Return on capital
   - 10 = exceptional margins, highly profitable
   - 0 = unprofitable or negative margins

2. **Growth (0-10)** - Weight: 25%
   - Revenue growth trajectory
   - Market expansion
   - Innovation and R&D investment
   - 10 = strong, sustainable growth with innovation
   - 0 = declining revenue, no growth drivers

3. **Balance Sheet (0-10)** - Weight: 25%
   - Debt levels and leverage
   - Current ratio and liquidity
   - Asset quality
   - 10 = fortress balance sheet, minimal debt
   - 0 = overleveraged, liquidity concerns

4. **Cash Flow (0-10)** - Weight: 20%
   - Free cash flow generation
   - Cash conversion efficiency
   - Capital allocation
   - 10 = strong, consistent cash generation
   - 0 = negative cash flow, burning cash

**Output Format**: Return a JSON object:

{{
  "profitability": <float 0-10>,
  "growth": <float 0-10>,
  "balance_sheet": <float 0-10>,
  "cash_flow": <float 0-10>,
  "confidence": <float 0-1>,
  "rationale": {{
    "profitability": "<brief justification>",
    "growth": "<brief justification>",
    "balance_sheet": "<brief justification>",
    "cash_flow": "<brief justification>"
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

**TTM Financial Metrics** (from SEC filings):
{ttm_metrics}

**Quarterly Trends**:
{quarterly_trends}

**Market Data & Key Ratios** (from market data — use these to anchor your analysis):
{supplemental_market_data}

**Key Sections from Most Recent Filing**:
{parsed_sections}

---

**Task**: Provide a comprehensive qualitative analysis of the company's financial health and business position, with emphasis on recent trends. Use ALL data provided above — especially the Market Data & Key Ratios — to deliver specific, data-anchored insights.

Your analysis MUST cover:

1. **Business Model & Competitive Position**
   - Core business strengths and competitive advantages
   - Market position and industry dynamics

2. **Financial Performance & Trends**
   - TTM revenue and profitability analysis with specific numbers
   - **Quarter-over-quarter trends** (improving, stable, or declining)
   - Margin analysis: gross, operating, net margins with context on sector norms
   - Operating margin and net margin levels — are they above/below industry?

3. **Capital Efficiency & Returns**
   - Return on Equity (ROE) and Return on Assets (ROA) — assess whether the company earns above its cost of capital
   - Free cash flow generation and FCF margin (FCF as % of revenue if calculable)
   - EBITDA and cash conversion quality

4. **Valuation Context**
   - Current P/E vs. sector average — premium or discount, and whether justified
   - Forward P/E and PEG ratio interpretation
   - EV/EBITDA vs sector average
   - What growth rate is being priced in?

5. **Risk Assessment**
   - Key business risks and challenges
   - Balance sheet leverage: total debt, debt-to-equity, interest coverage
   - Any deteriorating trends to watch
   - Short interest signal (if elevated, note the bear case implied)

6. **Growth & Innovation**
   - Forward earnings growth estimate vs historical revenue growth
   - R&D investment trajectory
   - Market expansion signals and strategic initiatives

7. **Balance Sheet & Liquidity**
   - Total debt vs. cash position (net debt)
   - Cash flow coverage of debt obligations
   - Financial flexibility for reinvestment or buybacks

**Output**: Write a clear, analytical summary (800-1200 words) that synthesizes these elements. **Reference specific numbers** from the Market Data section (ROE, ROA, FCF, P/E vs sector, etc.) throughout your analysis. Do not hedge by saying data is unavailable if it is provided above.
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

**Qualitative Analysis**:
{financial_analysis}

**Data Quality** (which quarters had data):
{data_quality}

---

**Task**: Score the company's financial health across 4 dimensions on a 0-10 scale.

**IMPORTANT**: Factor in quarterly trends when scoring:
- **Improving trends** should boost scores by 0.5-1.0 points
- **Declining trends** should reduce scores by 0.5-1.0 points
- **Missing data** should reduce confidence

**Scoring Dimensions**:

1. **Profitability (0-10)** - Weight: 30%
   - TTM margins and profitability
   - **Margin trend over 4 quarters**

2. **Growth (0-10)** - Weight: 25%
   - TTM revenue level
   - **Sequential quarter growth trajectory**
   - Momentum direction

3. **Balance Sheet (0-10)** - Weight: 25%
   - Debt levels and leverage
   - Liquidity position

4. **Cash Flow (0-10)** - Weight: 20%
   - TTM free cash flow
   - **Cash flow trend direction**

**Output Format**: Return a JSON object:

{{
  "profitability": <float 0-10>,
  "growth": <float 0-10>,
  "balance_sheet": <float 0-10>,
  "cash_flow": <float 0-10>,
  "confidence": <float 0-1>,
  "rationale": {{
    "profitability": "<brief justification including trend>",
    "growth": "<brief justification including trend>",
    "balance_sheet": "<brief justification>",
    "cash_flow": "<brief justification including trend>"
  }}
}}

**Confidence Adjustments**:
- 4/4 quarters available: confidence 0.8-0.95
- 3/4 quarters available: confidence 0.6-0.8
- 2/4 quarters available: confidence 0.4-0.6
- 1/4 quarters available: confidence 0.3-0.4

Return ONLY valid JSON, no other text.
"""

# ============================================================================
# BUSINESS MODEL PROMPT - TTM (Haiku)
# Purpose: Extract business model and competitive moat analysis
# ============================================================================

BUSINESS_MODEL_PROMPT_TTM = """You are extracting business model and competitive moat information from SEC filings.

**Company**: {ticker}
**Analysis Period**: {analysis_period}

**Key Sections from Most Recent Filing**:
{parsed_sections}

---

**Task**: Extract business model structure and competitive advantages.

Return your response as a JSON object with these fields:

{{
  "revenue_streams": [
    {{"name": "<stream name>", "percentage": <% of revenue or null>, "description": "<brief description>"}},
    // ... additional streams
  ],
  "business_segments": {{"<segment name>": <revenue % or millions USD or null>}},
  "revenue_concentration": "<assessment of revenue concentration risk>",
  "moat_characteristics": [
    "<competitive moat 1>",
    "<competitive moat 2>",
    // ... e.g., "Strong brand recognition", "High switching costs", "Network effects"
  ]
}}

**Instructions**:

1. **Revenue Streams**: Identify how the company makes money
   - Product sales, service revenue, subscriptions, licensing, etc.
   - Include percentages if disclosed, otherwise null
   - Brief description of each stream

2. **Business Segments**: Extract segment breakdown if disclosed
   - Geographic segments (Americas, EMEA, APAC, etc.)
   - Product segments (iPhone, Mac, Services, etc.)
   - Include revenue figures (as % or millions) if available

3. **Revenue Concentration**: Assess concentration risk
   - "Diversified across multiple products and regions"
   - "Concentrated in single product line with 70%+ revenue"
   - "Heavily dependent on few large customers"

4. **Moat Characteristics**: Identify competitive advantages
   - **Brand power**: Strong brand recognition, pricing power
   - **Switching costs**: Customer lock-in, high cost to switch
   - **Network effects**: Value increases with more users
   - **Cost advantages**: Structural cost advantages over competitors
   - **Scale economies**: Benefits from large scale operations
   - **Intangible assets**: Patents, IP, proprietary data, trade secrets
   - **Regulatory barriers**: Licenses, regulations that limit competition
   - **Distribution advantages**: Unique distribution channels or partnerships

**Return ONLY valid JSON, no other text**
"""

# ============================================================================
# BUSINESS MODEL SCORE PROMPT - TTM (Haiku)
# Purpose: Score business model moat strength across categories
# ============================================================================

BUSINESS_MODEL_SCORE_PROMPT_TTM = """You are scoring a company's business model and competitive moat strength.

**Company**: {ticker}
**Analysis Period**: {analysis_period}

**Business Model Data**:
{business_model_data}

**Financial Analysis Context**:
{financial_analysis_summary}

---

**Task**: Score the business model across 2 dimensions and provide enhanced moat breakdown.

**Output Format**: Return a JSON object:

{{
  "revenue_diversification": <float 0-10>,
  "competitive_moat": <float 0-10>,
  "confidence": <float 0-1>,
  "rationale": {{
    "revenue_diversification": "<brief justification>",
    "competitive_moat": "<brief justification>"
  }},
  "enhanced_moat": {{
    "network_effects": <float 0-10>,
    "switching_costs": <float 0-10>,
    "brand_power": <float 0-10>,
    "cost_advantages": <float 0-10>,
    "scale_economies": <float 0-10>,
    "intangible_assets": <float 0-10>,
    "regulatory_barriers": <float 0-10>,
    "distribution_advantages": <float 0-10>,
    "moat_width": "<Wide|Moderate|Narrow|None>",
    "moat_durability": "<High|Medium|Low>"
  }}
}}

**Scoring Dimensions**:

1. **Revenue Diversification (0-10)**
   - Multiple revenue streams vs single product
   - Geographic diversification
   - Customer diversification
   - 10 = highly diversified across products, regions, customers
   - 0 = single product, single market, concentrated customers

2. **Competitive Moat (0-10)**
   - Strength and sustainability of competitive advantages
   - Barriers to entry
   - Defensibility against competition
   - 10 = wide, durable moat with multiple strong advantages
   - 0 = commoditized business with no defensible advantages

**Enhanced Moat Categories** (0-10 each, use 0 if not applicable):

- **Network Effects**: Platform value increases with users (e.g., social networks, marketplaces)
- **Switching Costs**: Customer lock-in, high friction to change vendors (e.g., enterprise software)
- **Brand Power**: Premium pricing from brand recognition and customer loyalty
- **Cost Advantages**: Structural cost advantages (proprietary tech, unique assets, location)
- **Scale Economies**: Unit costs decline with volume, large fixed cost leverage
- **Intangible Assets**: Patents, proprietary technology, data moats, trade secrets
- **Regulatory Barriers**: Licenses, certifications, compliance requirements limit entrants
- **Distribution Advantages**: Exclusive channels, partnerships, installed base

**Moat Width Assessment**:
- **Wide**: Multiple strong moats (7-10 in 3+ categories), highly defensible, 5-10+ year durability
- **Moderate**: Some moats (5-7 in 2-3 categories), decent defensibility, 3-5 year durability
- **Narrow**: Weak moats (3-5 in 1-2 categories), limited defensibility, 1-3 year durability
- **None**: No moats (0-3 in all categories), commoditized, no sustainable advantage

**Moat Durability**:
- **High**: Structural advantages that are hard to erode (network effects, regulation, brand)
- **Medium**: Advantages that require ongoing investment to maintain (R&D, brand marketing)
- **Low**: Advantages that can be quickly competed away (cost, distribution)

**Instructions**:
- Be objective and evidence-based
- Use the full 0-10 range
- Only score moat categories that are clearly present (use 0 for non-applicable)
- Confidence should reflect data quality (0.6-0.95 typical)
- Each rationale should be 1-2 sentences
- Return ONLY valid JSON, no other text
"""

# ============================================================================
# STRUCTURED FILING EXTRACTION PROMPT (Haiku)
# Purpose: Extract structured data from any SEC filing type (10-K, 20-F, 6-K)
# ============================================================================

STRUCTURED_EXTRACTION_PROMPT = """You are extracting structured data from a SEC {filing_type} filing.

**Company**: {ticker}

**Filing Text** (truncated to ~30k chars):
{filing_text}

---

**Task**: Extract the following information as JSON.

{{
  "business_description": "<2-3 sentence summary of how the company makes money>",
  "risk_factors": [
    "<risk 1 - most material>",
    "<risk 2>",
    "<risk 3>",
    "<risk 4>",
    "<risk 5>"
  ],
  "financial_metrics": {{
    "revenue_millions": <float or null>,
    "gross_profit_millions": <float or null>,
    "operating_income_millions": <float or null>,
    "net_income_millions": <float or null>,
    "free_cash_flow_millions": <float or null>,
    "total_debt_millions": <float or null>,
    "cash_millions": <float or null>,
    "shares_outstanding_millions": <float or null>
  }},
  "management_outlook": "<summary of management's forward guidance and expectations>",
  "competitive_position": "<market position, key competitive advantages, and market share if disclosed>",
  "growth_drivers": [
    "<growth driver 1>",
    "<growth driver 2>",
    "<growth driver 3>"
  ]
}}

**Instructions**:
- Extract exact values from the filing where available
- For risk_factors, prioritize risks that could materially impact the business
- For management_outlook, focus on forward-looking statements and guidance
- For competitive_position, note market share, competitive advantages, and positioning
- Use null for metrics not found in the filing
- Return ONLY valid JSON, no other text
"""

# ============================================================================
# DCF INPUTS EXTRACTION PROMPT (Haiku)
# Purpose: Extract inputs for DCF valuation model from SEC filings
# ============================================================================

DCF_INPUTS_EXTRACTION_PROMPT = """You are extracting DCF valuation inputs from a SEC filing.

**Company**: {ticker}

**Filing Text** (truncated):
{filing_text}

**Current Market Data** (from yfinance):
{market_data}

---

**Task**: Extract inputs needed to build a Discounted Cash Flow model.

{{
  "fcf_history": [<list of annual free cash flow in millions USD, oldest to newest, 3-5 years>],
  "revenue_growth_rate": <most recent YoY revenue growth as percentage, e.g. 15.2>,
  "operating_margin_trend": "<expanding|stable|contracting>",
  "capex_as_pct_revenue": <capital expenditures as percentage of revenue>,
  "effective_tax_rate": <effective tax rate as percentage>,
  "total_debt": <total debt in millions USD>,
  "cash_and_equivalents": <cash and equivalents in millions USD>,
  "shares_outstanding": <diluted shares outstanding in millions>,
  "growth_drivers": "<key factors that support or limit future growth>",
  "risk_factors": "<top risks that could impact valuation>"
}}

**Instructions**:
- For fcf_history, extract Free Cash Flow = Operating Cash Flow - Capital Expenditures
- If FCF is not directly stated, calculate from cash flow statement items
- Include at least 3 years of FCF history if available in the filing
- Revenue growth rate should be the most recent full-year YoY change
- Operating margin trend: "expanding" if margins are improving, "contracting" if declining
- Use the filing's effective tax rate, not statutory rate
- Shares outstanding should be diluted shares if available
- Use null for scalar metrics not found (e.g. revenue_growth_rate, capex_as_pct_revenue)
- For fcf_history: always return a list — use [] if no FCF data found, never null
- Return ONLY valid JSON, no other text
"""
