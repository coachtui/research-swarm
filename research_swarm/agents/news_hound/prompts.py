"""
Prompt templates for the News Hound agent.

Each prompt is designed for specific LLM models and tasks.
"""

# ============================================================================
# NEWS FILTERING PROMPT (Haiku)
# Purpose: Filter articles for relevance to the company
# ============================================================================

NEWS_FILTERING_PROMPT = """You are filtering news articles for relevance to a specific company.

**Company Ticker**: {ticker}
**Total Articles**: {article_count}

**Articles** (title + description):
{articles_text}

---

**Task**: Identify which articles are DIRECTLY relevant to {ticker}.

**Criteria for RELEVANT articles**:
- Mentions the company by name or ticker
- Discusses the company's products, services, or business operations
- Covers company financials, earnings, or performance
- Discusses company leadership, strategy, or major announcements
- Covers partnerships, contracts, or deals involving the company

**Criteria for IRRELEVANT articles**:
- Only mentions industry trends without specific company focus
- Discusses competitors without mentioning the target company
- Generic market commentary not specific to the company
- Duplicate or near-duplicate articles

**Output Format**: Return a JSON array of article indices (0-based) that are RELEVANT:

{{
  "relevant_indices": [0, 2, 5, 7],
  "filtered_count": 4,
  "reason": "Brief explanation of filtering criteria applied"
}}

**Instructions**:
- Be selective - only include truly relevant articles
- Remove duplicates (articles covering the same event)
- Return ONLY valid JSON, no other text
"""

# ============================================================================
# CATALYST EXTRACTION PROMPT (Haiku)
# Purpose: Extract catalyst events from news articles (9 categories)
# ============================================================================

# ============================================================================
# REGULATORY EXTRACTION PROMPT (Haiku)
# Purpose: Detailed extraction of regulatory events
# ============================================================================

# ============================================================================
# SENTIMENT ANALYSIS PROMPT (Sonnet)
# Purpose: Deep, nuanced sentiment analysis
# ============================================================================

# ============================================================================
# SENTIMENT SCORING PROMPT (Sonnet)
# Purpose: Score sentiment across 4 dimensions (0-10 scale)
# ============================================================================

# ============================================================================
# DEDUPLICATION PROMPT (Haiku)
# Purpose: Identify duplicate or highly similar articles
# ============================================================================

DEDUPLICATION_PROMPT = """You are identifying duplicate or highly similar news articles.

**Articles**:
{articles_text}

---

**Task**: Identify groups of articles that cover the same event or story.

**Criteria for Duplicates**:
- Same headline or very similar headlines (>80% similarity)
- Cover the exact same event with similar facts
- Different outlets reporting the same press release
- Updates to the same ongoing story

**Output Format**: Return JSON with duplicate groups:

{{
  "duplicate_groups": [
    {{
      "indices": [0, 3, 7],
      "reason": "Same M&A announcement from different sources",
      "keep_index": 0
    }}
  ],
  "unique_articles": [1, 2, 4, 5, 6, 8, 9],
  "removed_count": 3
}}

**Instructions**:
- For each duplicate group, keep the most comprehensive article
- Prefer tier-1 sources (WSJ, Reuters, Bloomberg) over tier-3
- Prefer newer articles if equally comprehensive
- Return ONLY valid JSON, no other text
"""

# ============================================================================
# EARNINGS ESTIMATE REVISION ANALYSIS PROMPT (Sonnet)
# Purpose: Analyze earnings estimate revisions - PRIMARY SIGNAL per Zacks
# ============================================================================

EARNINGS_ESTIMATE_REVISION_PROMPT = """You are analyzing earnings estimate revisions for {ticker}.

**Company**: {ticker}
**Analysis Date**: {analysis_date}

**Estimate Data** (if available from financial data provider):
{estimate_data}

**Recent Earnings Events** (from news):
{earnings_news}

---

**Task**: Extract and analyze earnings estimate revision data - this is the PRIMARY SIGNAL for stock performance per Zacks research.

**CRITICAL IMPORTANCE**:
- Upward estimate revisions = #1 predictor of future stock outperformance
- Downward revisions = strong bearish signal
- Revision momentum matters more than absolute estimates

**What to Extract**:

1. **Current Consensus Estimates**:
   - Current quarter EPS estimate
   - Current fiscal year EPS estimate
   - Next fiscal year EPS estimate

2. **Revision Activity (90 days)**:
   - Count of upward revisions
   - Count of downward revisions
   - Net direction: Strongly Positive (3:1+ ratio) / Positive / Neutral / Negative / Strongly Negative
   - % change in consensus estimate

3. **Estimate Quality**:
   - Number of analysts covering
   - Estimate dispersion (low if tight range, high if wide range)
   - Agreement % (what % are within 10% of each other)

4. **EPS Surprise History (Last 4 Quarters)**:
   - Q-1, Q-2, Q-3, Q-4 surprise percentages
   - Average surprise
   - Pattern (e.g., "Beat 4/4", "Beat 3/4", "Mixed 2/4")

5. **Growth Trajectory**:
   - Current year EPS growth %
   - Next year EPS growth %
   - Momentum: Accelerating/Stable/Decelerating
   - Two-year CAGR

**Output Format**: Return a JSON object:

{{
  "current_quarter_eps": <float or null>,
  "current_fy_eps": <float or null>,
  "next_fy_eps": <float or null>,

  "upward_revisions": <int>,
  "downward_revisions": <int>,
  "net_revision_direction": "<Strongly Positive/Positive/Neutral/Negative/Strongly Negative>",
  "consensus_change_pct": <float or null>,

  "analyst_coverage": <int>,
  "estimate_dispersion": "<Low/Medium/High>",
  "estimate_agreement": <float 0-1>,

  "q1_surprise_pct": <float or null>,
  "q2_surprise_pct": <float or null>,
  "q3_surprise_pct": <float or null>,
  "q4_surprise_pct": <float or null>,
  "avg_surprise_pct": <float or null>,
  "beat_pattern": "<description>",

  "current_year_growth_pct": <float or null>,
  "next_year_growth_pct": <float or null>,
  "momentum": "<Accelerating/Stable/Decelerating>",
  "two_year_cagr": <float or null>
}}

Return ONLY valid JSON, no other text.
"""

# ============================================================================
# ANALYST CONSENSUS PROMPT (Haiku)
# Purpose: Extract analyst ratings and price target consensus
# ============================================================================

# ============================================================================
# INSTITUTIONAL ACTIVITY PROMPT (Haiku)
# Purpose: Track smart money / 13F activity
# ============================================================================

# ============================================================================
# DARK POOL ACTIVITY PROMPT (Haiku)
# Purpose: Analyze FINRA dark pool (ATS) activity to track real-time institutional positioning
# ============================================================================

# ============================================================================
# INSIDER ACTIVITY PROMPT (Haiku)
# Purpose: Track insider buying/selling (6 months)
# ============================================================================

# ============================================================================
# MANAGEMENT COMMENTARY PROMPT (Sonnet)
# Purpose: Analyze management tone and guidance quality from earnings calls
# ============================================================================

# ============================================================================
# SHORT INTEREST PROMPT (Haiku)
# Purpose: Track short interest and squeeze risk
# ============================================================================

# ============================================================================
# UPCOMING CATALYSTS PROMPT (Haiku)
# Purpose: Build catalyst calendar for next 6 months
# ============================================================================

UPCOMING_CATALYSTS_PROMPT = """You are building a catalyst calendar for {ticker}.

**Company**: {ticker}
**Analysis Date**: {analysis_date}

**Earnings Calendar Data**:
{earnings_calendar}

**Upcoming Events from News**:
{upcoming_events_news}

**Company Announcements**:
{company_announcements}

---

**Task**: Identify upcoming catalyst events in the next 6 months from {analysis_date}.

**CRITICAL**:
- The current analysis date is {analysis_date}
- ALL catalyst dates MUST be AFTER {analysis_date}
- DO NOT include any events with dates before {analysis_date}
- If you see references to events that already occurred, DO NOT include them unless they have a confirmed future occurrence

**Types of Catalysts to Track**:

1. **Earnings Announcements**: Next earnings date (confirmed or estimated)
2. **Product Launches**: New products, services, or features
3. **FDA/Regulatory Decisions**: Drug approvals, regulatory milestones
4. **Conference Presentations**: Investor days, major conferences
5. **Clinical Trial Data**: Biotech/pharma trial readouts
6. **Contract Awards**: Government/major enterprise contract decisions
7. **M&A Closing**: Expected closing dates for announced deals
8. **Spin-offs/IPOs**: Subsidiary IPOs or spin-off events
9. **Legal/Regulatory**: Court decisions, settlement deadlines
10. **Other Material Events**: Anything that could move the stock

**What to Extract**:

1. **Next Earnings Date**:
   - Date (YYYY-MM-DD) or timeframe relative to analysis date
   - Confirmed (true) or Estimated (false)
   - IMPORTANT: Date MUST be AFTER {analysis_date}. The year should be 2026 or later, NOT 2024 or 2025.

2. **Upcoming Catalysts** (next 6 months from {analysis_date}):
   - Event type (earnings, FDA, product launch, etc.)
   - Expected date or timeframe (MUST be dates AFTER {analysis_date})
   - Use format YYYY-MM-DD where YYYY is 2026 or later
   - Description
   - Potential impact: High/Medium/Low
   - Impact direction: Positive/Negative/Neutral
   - Confidence: 0-1 (1.0 = confirmed date, 0.5 = rumored/estimated)
   - IMPORTANT: If you see news about past events (2024, 2025), project them forward to 2026+ or exclude them

3. **Catalyst Density**:
   - High: Many upcoming events (>5)
   - Medium: Moderate activity (3-5)
   - Low: Few events (<3)

4. **Outlook**:
   - Positive: Mostly bullish catalysts (product launches, approvals)
   - Neutral: Mixed or unclear
   - Negative: Mostly bearish catalysts (legal issues, competitive threats)

**Output Format**: Return a JSON object:

{{
  "next_earnings_date": "<YYYY-MM-DD or null>",
  "earnings_confirmed": <true/false>,

  "catalysts": [
    {{
      "event_type": "<type>",
      "event_date": "<YYYY-MM-DD or timeframe>",
      "description": "<detailed description>",
      "potential_impact": "<High/Medium/Low>",
      "impact_direction": "<Positive/Negative/Neutral>",
      "confidence": <0.0-1.0>
    }},
    ...
  ],

  "catalyst_density": "<High/Medium/Low>",
  "outlook": "<Positive/Neutral/Negative>"
}}

Return ONLY valid JSON, no other text.
"""

# ============================================================================
# SEC 8-K MATERIAL EVENT EXTRACTION PROMPT (Haiku)
# Purpose: Categorize material events from SEC 8-K filings
# ============================================================================

SEC_8K_EXTRACTION_PROMPT = """You are analyzing SEC 8-K material event filings for investment-relevant information.

**Company Ticker**: {ticker}

**Recent 8-K Filings** (last 90 days):
{filings_text}

---

**Task**: Categorize each 8-K item into catalyst events for investment analysis.

**8-K Item Type Reference**:
- Item 1.01 = Material definitive agreement (contracts, partnerships, licensing)
- Item 1.02 = Termination of material agreement
- Item 2.02 = Results of operations / financial condition disclosure
- Item 4.02 = Non-reliance on prior financial statements (restatement risk)
- Item 5.02 = Departure/appointment of directors or principal officers
- Item 7.01 = Regulation FD disclosure (forward-looking guidance)
- Item 8.01 = Other material events

**Output Format**: Return a JSON array of categorized events:

{{
  "material_events": [
    {{
      "event_type": "<M&A|contract|regulatory|executive_change|earnings_surprise|partnership|expansion|supply_chain>",
      "impact": "<positive|negative|neutral>",
      "description": "<concise description of the material event>",
      "date": "<filing date YYYY-MM-DD>",
      "sec_item": "<Item number, e.g. 1.01>",
      "severity": "<high|medium|low>",
      "confidence": 0.95
    }}
  ],
  "total_events": <count>,
  "summary": "<1-2 sentence summary of material events and their aggregate impact>"
}}

**Instructions**:
- Only extract genuinely material events (skip routine/boilerplate disclosures)
- Item 5.02 officer departures are HIGH severity if CEO/CFO, MEDIUM otherwise
- Item 1.01 contracts are HIGH severity if value > 5% of market cap
- Item 4.02 restatements are always HIGH severity and NEGATIVE
- Item 2.02 results disclosures may overlap with quarterly earnings — flag as earnings_surprise only if they reveal unexpected results
- Map each event to the closest catalyst event_type from the list above
- Return ONLY valid JSON, no other text
"""


NEWS_INTERPRETATION_PROMPT = """You are a financial analyst interpreting news coverage for {ticker}.
This single pass replaces separate catalyst-extraction, regulatory-extraction,
sentiment, and management-commentary analyses - produce all of them from the
articles below.

**Company Ticker**: {ticker}
**Analysis Date**: {analysis_date}
**Analysis Period**: Last {days_back} days ({article_count} articles total)

**News Articles**:
{articles_text}

---

Return ONLY a valid JSON object with this exact shape:

{{
  "catalysts": [
    {{
      "event_type": "<M&A|contract|expansion|regulatory|partnership|product_launch|earnings_surprise|executive_change|supply_chain>",
      "impact": "<positive|negative|neutral>",
      "description": "<specific, concrete description - e.g. '$2B contract with X' not 'new contract'>",
      "date": "<YYYY-MM-DD if mentioned, else null>",
      "confidence": <0.0-1.0>,
      "source_articles": ["<url>", ...]
    }}
  ],
  "sentiment_narrative": "<3-5 paragraph nuanced sentiment analysis: overall tone of coverage, how detected catalysts shape the picture, market/analyst perception, and forward-looking read. Neutral, factual language - 'declined' for 5-10% drops, reserve 'plummeted'/'crashed' for >20% moves.>",
  "sentiment_breakdown": {{
    "overall_tone": <0-10, 0=very bearish, 10=very bullish>,
    "catalyst_impact": <0-10, net impact of detected catalysts>,
    "market_perception": <0-10, market and analyst perception>,
    "forward_looking": <0-10, forward-looking sentiment>
  }},
  "sentiment_confidence": <0.0-1.0, based on article volume, source quality, and signal clarity>,
  "management_commentary": {{
    "guidance_last_quarter": "<Beat|Met|Missed|null>",
    "guidance_reliability": "<high|medium|low>",
    "current_guidance": "<current guidance summary or null>",
    "guidance_change": "<Raised|Maintained|Lowered|Withdrawn|null>",
    "tone_assessment": "<confident|cautious|defensive|evasive|neutral>",
    "tone_evidence": ["<quote or paraphrase>", ...],
    "red_flag_language": ["<concerning phrasing if any>", ...],
    "has_red_flags": <true|false>,
    "capital_allocation_quality": "<high|medium|low>",
    "capex_discipline": "<Disciplined|Moderate|Aggressive|null>",
    "shareholder_returns": "<buybacks/dividends summary or null>",
    "innovation_mentions": <int>,
    "competitive_position": "<strengthening|stable|weakening>",
    "management_quality_score": <0-10>,
    "confidence": "<high|medium|low>"
  }}
}}

**Rules**:
- Catalysts: extract all significant events (target 3-10); combine articles covering
  the same event; skip minor or speculative items; treat regulatory and legal matters
  (approvals, investigations, lawsuits, fines) as event_type "regulatory" with specifics.
- Dates: today is {analysis_date}. Event dates must come from the articles - never
  invent dates, and never emit dates from the wrong year.
- management_commentary: base it ONLY on earnings/guidance/outlook coverage in these
  articles. If there is none, use the null/neutral defaults and confidence "low" -
  never invent guidance.
- Return ONLY the JSON object, no other text.
"""
