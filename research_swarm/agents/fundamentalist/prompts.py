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

**Task**: Extract supply chain and business relationship information.

Return your response as a JSON object with these fields:

{{
  "major_customers": [<list of customer names>],
  "customer_concentration": "<description of customer concentration risk>",
  "major_suppliers": [<list of supplier/partner names>],
  "supplier_dependencies": "<description of critical dependencies>",
  "geographic_revenue": {{"<region>": <revenue in millions or percentage>}},
  "geographic_risks": [<list of geographic/geopolitical risks>]
}}

**Instructions**:
- Extract specific company names when mentioned
- Identify concentration risks (e.g., "largest customer represents 20% of revenue")
- Note critical supplier dependencies (e.g., single-source suppliers)
- Extract revenue by geographic region if available
- Identify geopolitical or regional risks mentioned
- Use empty lists/objects if information not found
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
