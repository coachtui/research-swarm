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
