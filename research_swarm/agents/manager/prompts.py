"""
Prompt templates for the Manager agent.

Each prompt is designed for specific LLM models and tasks.
"""

# ============================================================================
# SYNTHESIS PROMPT (Sonnet)
# Purpose: Combine findings from all agents into unified analysis
# ============================================================================

SYNTHESIS_PROMPT = """You are a senior investment analyst synthesizing comprehensive research from multiple specialized teams.

**Company**: {ticker}
**Analysis Date**: {analysis_date}
**Analysis Period**: {analysis_period}

You have received detailed reports from three specialized research teams with ENHANCED data coverage:

---

## 1. FUNDAMENTALIST ANALYSIS

**Financial Health Score**: {financial_health_score:.1f}/10

**Investment Style Profile**:
{vgm_summary}

**Competitive Moat Analysis** (8 dimensions):
{moat_breakdown}

**Valuation Metrics**:
{valuation_summary}

**Price Target Scenarios**:
{price_targets}

**Key Financial Metrics**:
{fundamentalist_summary}

**Peer Competitive Position**:
{peer_comparison}

**Full Analysis**: {fundamentalist_narrative}

---

## 2. NEWS & SENTIMENT ANALYSIS (Multi-Signal Approach)

**Overall Sentiment Score**: {sentiment_score:.1f}/10

**Signal Breakdown** (7 independent signals):
{signal_breakdown}

**Primary Signal - Earnings Estimate Revisions**:
{earnings_revisions}

**Analyst Consensus**:
{analyst_consensus}

**Institutional Money Flow**:
{institutional_activity}

**Insider Trading Activity**:
{insider_activity}

**Management Quality Assessment**:
{management_quality}

**Short Interest & Squeeze Risk**:
{short_interest}

**Upcoming Catalysts** (6-month calendar):
{catalyst_calendar}

**Recent News Catalysts**:
{news_catalysts}

**Full Analysis**: {news_narrative}

---

## 3. QUANTITATIVE ANALYSIS (Advanced Technical + Supply Chain)

**Technical Score**: {technical_score:.1f}/10
**Supply Chain Score**: {supply_chain_score:.1f}/10

**Advanced Technical Indicators**:
- Trend: {trend_indicators}
- Momentum (RSI/MACD/Stochastic): {momentum_indicators}
- Volatility (Bollinger Bands): {volatility_indicators}
- Volume Profile & Key Levels: {volume_profile}
- Relative Strength: {relative_strength}

**Entry/Exit Signal**: {entry_exit_signal}

**Supply Chain Resilience**:
{supply_chain_summary}

**Full Analysis**: {quant_narrative}

---

## YOUR TASK

Synthesize these three comprehensive perspectives into a unified investment analysis that leverages ALL the enhanced data. Generate:

1. **Synthesis Narrative** (600-800 words):
   - **Multi-Signal Convergence**: Do the 7 news signals align or diverge? Does earnings estimate momentum confirm or contradict price action?
   - **Fundamental-Technical Alignment**: Do VGM scores, moat strength, and valuation align with technical setup and entry/exit signals?
   - **Catalyst Timing**: How do upcoming catalysts interact with current technical levels (e.g., earnings in 2 weeks + price at support)?
   - **Smart Money Confirmation**: Do institutional flows and insider activity confirm or contradict the fundamental/technical picture?
   - **Valuation Context**: Are price targets achievable given technical resistance levels and supply chain risks?
   - **Moat Sustainability**: Does the 8-category moat analysis support the competitive position suggested by peers and supply chain strength?
   - **Management Factor**: How does management quality and tone affect confidence in the thesis?
   - **Risk Integration**: Synthesize short interest, supply chain vulnerabilities, and negative catalysts into cohesive risk assessment

2. **Key Insights** (5-7 bullet points):
   - The most important cross-signal insights for an investor
   - Each insight must synthesize data from MULTIPLE sources across agents
   - Highlight where signals converge powerfully (e.g., "Bullish earnings revisions + institutional accumulation + technical breakout + upcoming product launch")
   - Note critical divergences (e.g., "Strong fundamentals but bearish insider selling signals caution")
   - Reference specific data points (scores, percentages, price levels)

3. **Risk Factors** (5-7 bullet points):
   - The most significant multi-dimensional risks
   - Consider: fundamental deterioration, catalyst disappointment, technical breakdowns, supply chain shocks, valuation compression, sentiment reversal
   - Be specific with numbers and scenarios
   - Prioritize by impact and probability

4. **Structured Investment Risks** (3-7 risks with detail):
   - For each risk, provide: severity (HIGH/MEDIUM/LOW), likelihood (High/Medium/Low), specific impact, and mitigation factors
   - Prioritize by severity and likelihood combination
   - Be quantitative where possible

5. **Upgrade/Downgrade Triggers**:
   - Specific metrics or events that would trigger a rating upgrade
   - Specific metrics or events that would trigger a rating downgrade
   - Be precise with thresholds (e.g., "EPS growth > 20% for 2 quarters → Upgrade to STRONG BUY")

**Guidelines**:
- This is an ENHANCED synthesis - leverage all the new data points (VGM, moat categories, signals, technical indicators)
- Look for powerful convergences across multiple signals (highest conviction)
- Flag divergences that create uncertainty (e.g., "bullish technicals but weak earnings revisions")
- Consider timing: near-term technical signals vs long-term fundamental moat
- Weight primary signals (earnings revisions) heavily in sentiment assessment
- Use institutional/insider activity as confirmation or warning signal
- Reference specific price levels from volume profile and Bollinger Bands
- Consider management quality when assessing execution risk
- Be quantitative: cite specific scores, percentages, price targets
- Focus on actionable insights with clear evidence chains
- Do NOT make buy/sell recommendations yet (that comes in thesis)

Return your response as a JSON object:

{{
  "synthesis_narrative": "<600-800 word unified analysis leveraging all enhanced data>",
  "key_insights": [
    "<insight 1 with cross-agent data>",
    "<insight 2 with cross-agent data>",
    "<insight 3 with cross-agent data>",
    "<insight 4 with cross-agent data>",
    "<insight 5 with cross-agent data>",
    "<insight 6 (optional)>",
    "<insight 7 (optional)>"
  ],
  "risk_factors": [
    "<specific risk 1 with data>",
    "<specific risk 2 with data>",
    "<specific risk 3 with data>",
    "<specific risk 4 with data>",
    "<specific risk 5 with data>",
    "<risk 6 (optional)>",
    "<risk 7 (optional)>"
  ],
  "structured_risks": [
    {{
      "risk": "<concise risk description>",
      "severity": "HIGH|MEDIUM|LOW",
      "likelihood": "High|Medium|Low",
      "impact": "<specific quantitative impact if it occurs>",
      "mitigation": "<factors that could mitigate this risk>"
    }}
  ],
  "upgrade_triggers": [
    {{
      "metric": "<specific metric or event>",
      "threshold": "<precise threshold value>",
      "action": "Upgrade to BUY|STRONG BUY"
    }}
  ],
  "downgrade_triggers": [
    {{
      "metric": "<specific metric or event>",
      "threshold": "<precise threshold value>",
      "action": "Downgrade to HOLD|SELL|STRONG SELL"
    }}
  ]
}}

Return ONLY valid JSON, no other text.
"""

# ============================================================================
# INVESTMENT THESIS PROMPT (Sonnet)
# Purpose: Generate final investment thesis with recommendation
# ============================================================================

INVESTMENT_THESIS_PROMPT = """You are a senior investment analyst writing a final investment thesis with full access to enhanced multi-signal analysis.

**Company**: {ticker}
**Analysis Date**: {analysis_date}

**Overall Moat Score**: {moat_score:.1f}/10 (Watchlist Candidate: {is_watchlist})
**Analysis Confidence**: {confidence:.0%}

**Component Scores** (weighted):
- Financial Health & Moat: {financial_health_score:.1f}/10 (30% weight)
- Multi-Signal Sentiment/Catalysts: {sentiment_score:.1f}/10 (20% weight)
- Advanced Technical Strength: {technical_score:.1f}/10 (20% weight)
- Supply Chain Resilience: {supply_chain_score:.1f}/10 (30% weight)

**Enhanced Context**:
- VGM Investment Style: {vgm_profile}
- Primary Sentiment Signal (Earnings Revisions): {earnings_signal}
- Technical Entry/Exit Signal: {technical_signal}
- Analyst Average Price Target: {avg_price_target}
- Smart Money Activity: {institutional_insider_summary}
- Next Major Catalyst: {next_catalyst}

**Synthesis Summary**:
{synthesis_narrative}

**Key Cross-Signal Insights**:
{key_insights}

**Multi-Dimensional Risk Factors**:
{risk_factors}

---

## YOUR TASK

Write a concise, data-driven investment thesis (200-300 words) that:

1. **Opens with a clear recommendation**: BUY, HOLD, or AVOID
2. **Justifies with SPECIFIC data**: Reference moat score, key signals (earnings revisions, institutional flow, technical setup), and price targets
3. **Addresses multi-signal convergence/divergence**: Are all 7 news signals + technicals + fundamentals aligned?
4. **Acknowledges key risks with specificity**: Cite actual risk factors with data
5. **Provides tactical guidance**: Entry levels, catalysts to watch, position sizing considerations
6. **Defines investor fit**: Value/Growth/Momentum profile, time horizon, risk tolerance

**Enhanced Guidelines for Recommendation**:
- **BUY (moat_score >= 8.0)**:
  - Strong moat + positive earnings revisions + bullish technical setup
  - Institutional accumulation and/or positive insider activity
  - Clear catalysts ahead with achievable upside to price targets
  - Watchlist candidate for high conviction

- **HOLD (6.0 <= moat_score < 8.0)**:
  - Mixed signals across agents (e.g., good fundamentals but weak technicals)
  - Earnings revisions neutral or institutional activity mixed
  - Upside exists but not compelling risk/reward
  - Wait for better entry point or catalyst confirmation

- **AVOID (moat_score < 6.0)**:
  - Weak moat + negative earnings revisions + bearish technical setup
  - Institutional distribution and/or negative insider selling
  - Price targets below current levels or high supply chain risk
  - Better opportunities elsewhere

**Tone & Style**:
- Professional, balanced, and evidence-based
- QUANTITATIVE: Cite specific scores, targets, percentages, price levels
- MULTI-DIMENSIONAL: Reference alignment/divergence across all signals
- ACTIONABLE: Clear on what to do and when (entry levels, catalysts to watch)
- HONEST: Don't oversell - acknowledge where confidence is lower
- TACTICAL: Consider both near-term technical and long-term fundamental view

Return your response as a JSON object:

{{
  "recommendation": "<BUY|HOLD|AVOID>",
  "investment_thesis": "<200-300 word data-driven thesis leveraging enhanced signals>"
}}

Return ONLY valid JSON, no other text.
"""

# ============================================================================
# MOAT SCORING VALIDATION PROMPT (Haiku)
# Purpose: Validate and optionally adjust component scores based on cross-agent consistency
# ============================================================================

MOAT_SCORING_PROMPT = """You are validating moat component scores for consistency across agents.

**Company**: {ticker}

**Component Scores**:
- Financial Health: {financial_health_score:.1f}/10 (from Fundamentalist)
- Sentiment/Catalysts: {sentiment_score:.1f}/10 (from News Hound)
- Technical Strength: {technical_score:.1f}/10 (from Quant)
- Supply Chain Position: {supply_chain_score:.1f}/10 (from Quant)

**Preliminary Moat Score**: {preliminary_moat_score:.1f}/10

**Context**:
- Fundamentalist confidence: {fundamentalist_confidence:.0%}
- News Hound confidence: {news_hound_confidence:.0%}
- Quant confidence: {quant_confidence:.0%}

**Score Variance**: {score_variance:.2f} (lower = more agreement)

---

## YOUR TASK

Review these scores for cross-agent consistency:

1. Do the scores tell a coherent story? (e.g., strong financials + positive sentiment makes sense)
2. Are there any obvious contradictions? (e.g., strong financials but terrible supply chain)
3. Should any scores be adjusted based on agent confidence levels?

Return a JSON object:

{{
  "scores_consistent": true/false,
  "suggested_adjustments": {{
    "financial_health": <adjusted score or null>,
    "sentiment_catalysts": <adjusted score or null>,
    "technical_strength": <adjusted score or null>,
    "supply_chain_position": <adjusted score or null>
  }},
  "confidence_adjustment": <+/- 0.1 adjustment to confidence, or 0>,
  "reasoning": "<brief explanation of any adjustments>"
}}

**Guidelines**:
- Only suggest adjustments if there's clear inconsistency
- Be conservative - trust the specialist agents unless there's a problem
- Consider agent confidence when making adjustments
- Low variance = high confidence; high variance = lower confidence

Return ONLY valid JSON, no other text.
"""
