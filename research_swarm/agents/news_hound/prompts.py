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

CATALYST_EXTRACTION_PROMPT = """You are extracting business catalyst events from news articles.

**Company Ticker**: {ticker}
**Analysis Period**: Last {days_back} days

**News Articles**:
{articles_text}

---

**Task**: Identify and extract catalyst events in these 9 categories:

1. **M&A** - Mergers, acquisitions, divestitures
2. **contract** - Major contracts, deals, purchase orders
3. **expansion** - Facility expansions, market expansion, new locations
4. **regulatory** - Regulatory approvals, compliance issues, legal matters
5. **partnership** - Strategic partnerships, joint ventures, collaborations
6. **product_launch** - New product launches, product announcements
7. **earnings_surprise** - Earnings beats/misses, guidance changes
8. **executive_change** - CEO, CFO, or other C-suite changes
9. **supply_chain** - Supply chain disruptions, supplier issues, logistics problems

**Output Format**: Return a JSON array of catalyst events:

{{
  "catalysts": [
    {{
      "event_type": "<one of the 9 types>",
      "impact": "<positive/negative/neutral>",
      "description": "<concise description of the event>",
      "date": "<YYYY-MM-DD if mentioned, else null>",
      "confidence": <0.0-1.0>,
      "source_urls": ["<url1>", "<url2>"]
    }}
  ],
  "total_detected": <count>
}}

**Instructions**:
- Extract all significant catalyst events (target: 3-10 events)
- Avoid extracting minor or speculative events
- Combine related articles covering the same event
- Confidence reflects how clear and well-sourced the event is
- Be specific in descriptions (e.g., "$2B contract" not just "new contract")
- Return ONLY valid JSON, no other text
"""

# ============================================================================
# REGULATORY EXTRACTION PROMPT (Haiku)
# Purpose: Detailed extraction of regulatory events
# ============================================================================

REGULATORY_EXTRACTION_PROMPT = """You are extracting regulatory and legal events from news articles.

**Company Ticker**: {ticker}

**News Articles**:
{articles_text}

---

**Task**: Extract regulatory and legal events with high detail.

**Types of Regulatory Events**:
- FDA/regulatory approvals or rejections
- Export control or trade restrictions
- Antitrust investigations or actions
- Environmental regulations or violations
- Data privacy or cybersecurity regulations
- Industry-specific compliance matters
- Government contracts or relations

**Output Format**: Return a JSON array:

{{
  "regulatory_events": [
    {{
      "event_type": "regulatory",
      "impact": "<positive/negative/neutral>",
      "description": "<detailed description>",
      "date": "<YYYY-MM-DD if mentioned>",
      "confidence": <0.0-1.0>,
      "source_urls": ["<url>"],
      "regulatory_body": "<name of regulatory agency if mentioned>"
    }}
  ],
  "total_detected": <count>
}}

**Instructions**:
- Focus on material regulatory events that could impact business
- Include details about regulatory bodies involved
- Assess impact on business operations and revenue
- High confidence (>0.8) for official announcements
- Lower confidence (<0.6) for speculation or rumors
- Return ONLY valid JSON, no other text
"""

# ============================================================================
# SENTIMENT ANALYSIS PROMPT (Sonnet)
# Purpose: Deep, nuanced sentiment analysis
# ============================================================================

SENTIMENT_ANALYSIS_PROMPT = """You are a financial analyst performing nuanced sentiment analysis on news coverage.

**Company Ticker**: {ticker}
**Analysis Period**: Last {days_back} days
**Articles Analyzed**: {article_count}

**News Articles**:
{articles_text}

**Detected Catalyst Events**:
{catalyst_events}

---

**Task**: Provide a comprehensive sentiment analysis of the news coverage.

Your analysis should cover:

1. **Overall Narrative Tone**
   - What is the dominant narrative around the company?
   - Is coverage primarily positive, negative, or mixed?
   - Are there shifts in sentiment over the period?

2. **Catalyst Impact Assessment**
   - How significant are the detected catalyst events?
   - What is the net positive/negative impact of these events?
   - Which events are most material to the business?

3. **Market and Analyst Perception**
   - How are markets and analysts responding to news?
   - Are there concerns or enthusiasm in coverage?
   - Any notable analyst ratings or price target changes?

4. **Forward-Looking Indicators**
   - What does news suggest about future prospects?
   - Are there growth drivers or headwinds mentioned?
   - Is innovation and competitive position strengthening or weakening?

5. **Risk Factors**
   - What risks or challenges are highlighted in coverage?
   - Supply chain issues, regulatory concerns, competition?
   - How material are these risks?

6. **Source Diversity and Quality**
   - Quality of sources (tier-1 vs tier-3 publications)
   - Diversity of perspectives
   - Any bias or lack of substantiation?

**Output**: Write a comprehensive sentiment analysis (400-600 words) that:
- Goes beyond surface-level positive/negative classification
- Provides context and nuance about the sentiment drivers
- Identifies conflicting signals or areas of uncertainty
- Makes evidence-based assessments tied to specific events
- Balances short-term news against longer-term implications

**Tone**: Professional, analytical, balanced. Avoid hyperbole or speculation.
"""

# ============================================================================
# SENTIMENT SCORING PROMPT (Sonnet)
# Purpose: Score sentiment across 4 dimensions (0-10 scale)
# ============================================================================

SENTIMENT_SCORING_PROMPT = """You are scoring news sentiment across 4 key dimensions.

**Company Ticker**: {ticker}
**Analysis Period**: Last {days_back} days
**Articles Analyzed**: {article_count}

**Sentiment Analysis**:
{sentiment_analysis}

**Detected Catalysts**:
{catalyst_events}

---

**Task**: Score news sentiment across 4 dimensions on a 0-10 scale.

**Scoring Dimensions**:

1. **Overall Tone (0-10)**
   - The general tone and framing of news coverage
   - Language used: alarmist vs celebratory
   - Balance of positive vs negative coverage
   - 10 = Overwhelmingly positive, enthusiastic coverage
   - 5 = Neutral, balanced, or mixed coverage
   - 0 = Overwhelmingly negative, crisis narrative

2. **Catalyst Impact (0-10)**
   - Net impact of detected catalyst events on business
   - Magnitude and materiality of events
   - Short-term and long-term implications
   - 10 = Multiple strong positive catalysts, transformative events
   - 5 = Mix of positive and negative, or minor events
   - 0 = Multiple strong negative catalysts, major setbacks

3. **Market Perception (0-10)**
   - How markets, analysts, and investors are responding
   - Analyst sentiment and rating changes
   - Stock performance narrative in coverage
   - 10 = Strong bullish sentiment, upgrades, enthusiasm
   - 5 = Neutral analyst sentiment, hold ratings
   - 0 = Strong bearish sentiment, downgrades, concerns

4. **Forward Looking (0-10)**
   - Sentiment about future prospects and trajectory
   - Growth drivers vs headwinds mentioned
   - Innovation, market position, competitive dynamics
   - 10 = Highly optimistic about future, strong growth narrative
   - 5 = Uncertain outlook, mixed signals
   - 0 = Highly pessimistic, declining prospects

**Confidence Calculation**:
- Based on article quantity (more articles = higher confidence)
- Based on catalyst detection (clear events = higher confidence)
- Based on source diversity (diverse sources = higher confidence)
- Typical range: 0.6 - 0.95

**Output Format**: Return a JSON object:

{{
  "overall_tone": <float 0-10>,
  "catalyst_impact": <float 0-10>,
  "market_perception": <float 0-10>,
  "forward_looking": <float 0-10>,
  "confidence": <float 0-1>,
  "rationale": {{
    "overall_tone": "<1-2 sentence justification>",
    "catalyst_impact": "<1-2 sentence justification>",
    "market_perception": "<1-2 sentence justification>",
    "forward_looking": "<1-2 sentence justification>"
  }}
}}

**Instructions**:
- Use the full 0-10 range (avoid clustering around 5)
- Be evidence-based - tie scores to specific events and coverage
- Balance recent events with overall trajectory
- Consider both quantity and quality of coverage
- Confidence reflects data completeness, not sentiment strength
- Return ONLY valid JSON, no other text
"""

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

ANALYST_CONSENSUS_PROMPT = """You are extracting analyst consensus data for {ticker}.

**Company**: {ticker}
**Analysis Date**: {analysis_date}

**Analyst Data** (if available):
{analyst_data}

**Recent Analyst Actions** (from news):
{analyst_news}

---

**Task**: Extract current analyst ratings distribution and price target consensus.

**What to Extract**:

1. **Rating Distribution**:
   - Strong Buy: [count]
   - Buy: [count]
   - Hold: [count]
   - Sell: [count]
   - Strong Sell: [count]
   - Overall Consensus: Weighted average rating

2. **Price Targets**:
   - Average price target
   - High price target (and which firm)
   - Low price target (and which firm)
   - Upside % to average target

3. **Recent Changes (90 days)**:
   - Number of upgrades
   - Number of downgrades
   - New coverage initiations
   - Rating momentum: Improving/Stable/Deteriorating
   - Target trend: Rising/Stable/Falling

4. **Consensus Quality**:
   - Confidence: High (tight range) / Medium / Low (wide dispersion)

**Output Format**: Return a JSON object:

{{
  "strong_buy": <int>,
  "buy": <int>,
  "hold": <int>,
  "sell": <int>,
  "strong_sell": <int>,
  "consensus_rating": "<Strong Buy/Buy/Hold/Sell/Strong Sell>",

  "avg_price_target": <float or null>,
  "high_price_target": <float or null>,
  "low_price_target": <float or null>,
  "target_upside_pct": <float or null>,

  "upgrades": <int>,
  "downgrades": <int>,
  "new_coverage": <int>,
  "rating_momentum": "<Improving/Stable/Deteriorating>",
  "target_trend": "<Rising/Stable/Falling>",

  "consensus_confidence": "<High/Medium/Low>"
}}

Return ONLY valid JSON, no other text.
"""

# ============================================================================
# INSTITUTIONAL ACTIVITY PROMPT (Haiku)
# Purpose: Track smart money / 13F activity
# ============================================================================

INSTITUTIONAL_ACTIVITY_PROMPT = """You are tracking institutional ownership and smart money activity for {ticker}.

**Company**: {ticker}
**Analysis Date**: {analysis_date}

**13F Filing Data** (if available):
{filing_data}

**Institutional News**:
{institutional_news}

---

**Task**: Analyze institutional (smart money) ownership and recent activity.

**What to Extract**:

1. **Current Ownership**:
   - Institutional ownership % of shares outstanding
   - Quarter-over-quarter change %
   - Number of institutional holders
   - Trend: Accumulation (buying) / Distribution (selling) / Stable

2. **Top 5 Holders**:
   - Fund name, % ownership, recent change

3. **Notable 13F Activity**:
   - Major funds adding/reducing positions
   - New positions by notable investors
   - Complete exits

4. **Sentiment**:
   - Strongly Bullish: Heavy accumulation by smart money
   - Bullish: Net buying
   - Neutral: Mixed/stable
   - Bearish: Net selling

**Output Format**: Return a JSON object:

{{
  "institutional_ownership_pct": <float or null>,
  "qoq_change_pct": <float or null>,
  "num_holders": <int>,
  "trend": "<Accumulation/Distribution/Stable>",

  "top_holders": [
    {{"name": "<fund>", "ownership_pct": <float>, "change": "<Added/Reduced/Held> [X] shares"}},
    ...
  ],

  "notable_activity": [
    "<Description of notable move>",
    ...
  ],

  "institutional_sentiment": "<Strongly Bullish/Bullish/Neutral/Bearish>"
}}

Return ONLY valid JSON, no other text.
"""

# ============================================================================
# INSIDER ACTIVITY PROMPT (Haiku)
# Purpose: Track insider buying/selling (6 months)
# ============================================================================

INSIDER_ACTIVITY_PROMPT = """You are tracking insider trading activity for {ticker}.

**Company**: {ticker}
**Analysis Period**: Last 6 months

**Insider Transaction Data** (if available):
{transaction_data}

**Insider News**:
{insider_news}

---

**Task**: Analyze insider trading patterns and sentiment.

**What to Extract**:

1. **Transaction Summary (6 months)**:
   - Buy transactions: count, total shares, total value
   - Sell transactions: count, total shares, total value
   - Net: shares and value (positive = net buying)

2. **Notable Transactions**:
   - CEO/CFO transactions (especially buys)
   - Clustered buying (multiple insiders buying)
   - Large or unusual transactions

3. **Insider Ownership**:
   - Total insider ownership %
   - CEO ownership %
   - Trend: Increasing/Stable/Decreasing

4. **Sentiment**:
   - Bullish: Net buying, especially clustered buys or CEO purchases
   - Neutral: Routine option exercises/sales, balanced activity
   - Bearish: Heavy selling, especially by CEO/CFO
   
   Confidence: High/Medium/Low based on:
   - High: Clear pattern, significant transactions
   - Medium: Some activity but mixed signals
   - Low: Little activity or routine transactions

**IMPORTANT CONTEXT**:
- Insider BUYING is a strong bullish signal (they have inside info)
- Insider SELLING is often neutral (diversification, taxes, options)
- Only flag selling as bearish if it's unusual/clustered/by CEO

**Output Format**: Return a JSON object:

{{
  "buy_transactions": <int>,
  "buy_shares": <int>,
  "buy_value_usd": <float>,

  "sell_transactions": <int>,
  "sell_shares": <int>,
  "sell_value_usd": <float>,

  "net_shares": <int (can be negative)>,
  "net_value_usd": <float (can be negative)>,

  "notable_transactions": [
    "<Title bought/sold [X] shares at $[Y] on [date] (context)>",
    ...
  ],

  "insider_ownership_pct": <float or null>,
  "ceo_ownership_pct": <float or null>,
  "ownership_trend": "<Increasing/Stable/Decreasing>",

  "insider_sentiment": "<Bullish/Neutral/Bearish>",
  "confidence": "<High/Medium/Low>"
}}

Return ONLY valid JSON, no other text.
"""

# ============================================================================
# MANAGEMENT COMMENTARY PROMPT (Sonnet)
# Purpose: Analyze management tone and guidance quality from earnings calls
# ============================================================================

MANAGEMENT_COMMENTARY_PROMPT = """You are analyzing management commentary and tone for {ticker}.

**Company**: {ticker}
**Analysis Date**: {analysis_date}

**Earnings Call Transcripts** (if available):
{earnings_call_data}

**Management Commentary from News**:
{management_news}

**Guidance History**:
{guidance_history}

---

**Task**: Assess management quality and commentary tone from earnings calls and guidance.

**What to Analyze**:

1. **Guidance Track Record**:
   - How accurate is management guidance historically?
   - Last quarter: Beat/Met/Missed their own guidance?
   - Reliability: High (consistently accurate) / Medium / Low (frequently wrong)
   - Current guidance: What did they guide for?
   - Change: Raised/Maintained/Lowered/Withdrawn?

2. **Tone Assessment** (from earnings call Q&A):
   - Confident: Assertive, detailed, specific about growth drivers
   - Cautious: Hedging, mentioning risks, conservative outlook
   - Defensive: Explaining away problems, blame external factors
   - Evasive: Dodging questions, vague answers, deflecting

   Extract specific quotes or behaviors that indicate tone.

3. **Red Flag Language**:
   - Watch for: "challenging environment", "macro headwinds", "one-time charges"
   - "Investments in growth" (code for declining margins)
   - "Normalizing" (code for deteriorating)
   - "Strategic review" (prelude to bad news)
   - "Optimizing operations" (euphemism for layoffs/restructuring)

4. **Capital Allocation Quality**:
   - High: Disciplined capex, shareholder returns (buybacks/dividends), avoiding bad M&A
   - Medium: Balanced approach
   - Low: Empire building, value-destructive M&A, hoarding cash

   CapEx discipline: Disciplined/Moderate/Aggressive
   Shareholder returns: What are they doing with FCF?

5. **Innovation & Competitive Position**:
   - Count mentions of innovation, R&D, new products
   - Are they strengthening or weakening competitively?

6. **Overall Management Quality Score (0-10)**:
   - 9-10: Excellent guidance, confident tone, strong capital allocation
   - 7-8: Good track record, transparent communication
   - 5-6: Mixed signals, average execution
   - 3-4: Poor guidance, defensive tone, red flags
   - 0-2: Major credibility issues, evasive, value-destructive decisions

**Output Format**: Return a JSON object:

{{
  "guidance_last_quarter": "<Beat/Met/Missed or null>",
  "guidance_reliability": "<High/Medium/Low>",
  "current_guidance": "<description or null>",
  "guidance_change": "<Raised/Maintained/Lowered/Withdrawn or null>",

  "tone_assessment": "<Confident/Cautious/Defensive/Evasive>",
  "tone_evidence": [
    "<quote or behavior 1>",
    "<quote or behavior 2>"
  ],

  "red_flag_language": [
    "<concerning phrase 1>",
    "<concerning phrase 2>"
  ],
  "has_red_flags": <true/false>,

  "capital_allocation_quality": "<High/Medium/Low>",
  "capex_discipline": "<Disciplined/Moderate/Aggressive or null>",
  "shareholder_returns": "<description or null>",

  "innovation_mentions": <int>,
  "competitive_position": "<Strengthening/Stable/Weakening>",

  "management_quality_score": <float 0-10>,
  "confidence": "<High/Medium/Low>"
}}

Return ONLY valid JSON, no other text.
"""

# ============================================================================
# SHORT INTEREST PROMPT (Haiku)
# Purpose: Track short interest and squeeze risk
# ============================================================================

SHORT_INTEREST_PROMPT = """You are tracking short interest and squeeze risk for {ticker}.

**Company**: {ticker}
**Analysis Date**: {analysis_date}

**Short Interest Data** (if available):
{short_data}

**Short Seller News**:
{short_news}

---

**Task**: Analyze short interest metrics and assess squeeze risk.

**What to Extract**:

1. **Current Short Metrics**:
   - Short interest as % of float
   - Total shares sold short
   - Days to cover (short interest / avg daily volume)

2. **Trend**:
   - Increasing/Stable/Decreasing
   - Month-over-month change %

3. **Squeeze Risk Assessment**:
   - High: >20% short interest AND >5 days to cover
   - Medium: 10-20% short interest OR 3-5 days to cover
   - Low: <10% short interest AND <3 days to cover

   Potential triggers:
   - Upcoming earnings (shorts may need to cover)
   - High short % + low float = squeeze potential
   - Positive catalyst + high short interest
   - Short seller report controversy

4. **Notable Short Activity**:
   - Short seller reports (Citron, Muddy Waters, etc.)
   - Activism campaigns
   - Major short position changes

5. **Sentiment**:
   - Bullish: Decreasing short interest (shorts covering)
   - Neutral: Stable short interest
   - Bearish: Increasing short interest (more shorts piling in)

**Output Format**: Return a JSON object:

{{
  "short_interest_pct": <float or null>,
  "short_interest_shares": <int or null>,
  "days_to_cover": <float or null>,

  "short_interest_trend": "<Increasing/Stable/Decreasing>",
  "mom_change_pct": <float or null>,

  "squeeze_risk": "<High/Medium/Low>",
  "squeeze_triggers": [
    "<trigger 1>",
    "<trigger 2>"
  ],

  "notable_short_activity": [
    "<description of activity>",
    ...
  ],

  "short_sentiment": "<Bullish/Neutral/Bearish>"
}}

Return ONLY valid JSON, no other text.
"""

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

**Task**: Identify upcoming catalyst events in the next 6 months.

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
   - Date (YYYY-MM-DD) or timeframe relative to analysis date (e.g., "early Q2")
   - Confirmed (true) or Estimated (false)
   - IMPORTANT: All dates MUST be in the future relative to the analysis date ({analysis_date}). Do NOT generate dates from previous years.

2. **Upcoming Catalysts** (next 6 months from {analysis_date}):
   - Event type (earnings, FDA, product launch, etc.)
   - Expected date or timeframe (must be future dates)
   - Description
   - Potential impact: High/Medium/Low
   - Impact direction: Positive/Negative/Neutral
   - Confidence: 0-1 (1.0 = confirmed date, 0.5 = rumored/estimated)

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
