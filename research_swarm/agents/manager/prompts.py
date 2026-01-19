"""
Prompt templates for the Manager agent.

Each prompt is designed for specific LLM models and tasks.
"""

# ============================================================================
# SYNTHESIS PROMPT (Sonnet)
# Purpose: Combine findings from all agents into unified analysis
# ============================================================================

SYNTHESIS_PROMPT = """You are an investment analyst synthesizing research from multiple specialized teams.

**Company**: {ticker}
**Analysis Date**: {analysis_date}
**Analysis Period**: {analysis_period}

You have received reports from three specialized research teams:

---

## 1. FUNDAMENTALIST ANALYSIS

**Financial Health Score**: {financial_health_score:.1f}/10

**Key Metrics**:
{fundamentalist_summary}

**Analysis**: {fundamentalist_narrative}

---

## 2. NEWS & SENTIMENT ANALYSIS

**Sentiment Score**: {sentiment_score:.1f}/10

**Recent Catalysts**:
{news_catalysts}

**Analysis**: {news_narrative}

---

## 3. QUANTITATIVE ANALYSIS

**Technical Score**: {technical_score:.1f}/10
**Supply Chain Score**: {supply_chain_score:.1f}/10

**Technical Indicators**: {technical_summary}

**Supply Chain Resilience**: {supply_chain_summary}

---

## YOUR TASK

Synthesize these three perspectives into a unified investment analysis. Generate:

1. **Synthesis Narrative** (400-600 words):
   - Integrate findings across all three dimensions (fundamental, sentiment, technical/supply chain)
   - Identify themes that appear across multiple analyses (e.g., "strong fundamentals confirmed by positive sentiment")
   - Note any contradictions or divergences between the analyses
   - Assess the overall investment opportunity holistically

2. **Key Insights** (3-5 bullet points):
   - The most important takeaways for an investor
   - Each insight should synthesize information from multiple sources
   - Focus on actionable insights (e.g., "Strong moat from supply chain dominance + positive AI tailwinds")

3. **Risk Factors** (3-5 bullet points):
   - The most significant risks to this investment
   - Consider fundamental, technical, and market/sentiment risks
   - Be specific and balanced (not overly pessimistic or optimistic)

**Guidelines**:
- Be objective and balanced - acknowledge both strengths and weaknesses
- Look for confirmation or divergence across analyses
- Consider how different factors interact (e.g., strong fundamentals but negative sentiment might indicate opportunity)
- Use professional investment analysis language
- Do NOT make explicit buy/sell recommendations yet (that comes in the thesis)
- Focus on synthesis, not just summarization

Return your response as a JSON object:

{{
  "synthesis_narrative": "<400-600 word unified analysis>",
  "key_insights": [
    "<insight 1>",
    "<insight 2>",
    "<insight 3>",
    "<insight 4 (optional)>",
    "<insight 5 (optional)>"
  ],
  "risk_factors": [
    "<risk 1>",
    "<risk 2>",
    "<risk 3>",
    "<risk 4 (optional)>",
    "<risk 5 (optional)>"
  ]
}}

Return ONLY valid JSON, no other text.
"""

# ============================================================================
# INVESTMENT THESIS PROMPT (Sonnet)
# Purpose: Generate final investment thesis with recommendation
# ============================================================================

INVESTMENT_THESIS_PROMPT = """You are an investment analyst writing a final investment thesis.

**Company**: {ticker}
**Analysis Date**: {analysis_date}

**Moat Score**: {moat_score:.1f}/10 (Watchlist: {is_watchlist})
**Confidence**: {confidence:.0%}

**Component Scores**:
- Financial Health: {financial_health_score:.1f}/10 (30% weight)
- Sentiment/Catalysts: {sentiment_score:.1f}/10 (20% weight)
- Technical Strength: {technical_score:.1f}/10 (20% weight)
- Supply Chain Position: {supply_chain_score:.1f}/10 (30% weight)

**Synthesis Summary**:
{synthesis_narrative}

**Key Insights**:
{key_insights}

**Risk Factors**:
{risk_factors}

---

## YOUR TASK

Write a concise investment thesis (150-250 words) that:

1. **Opens with a clear recommendation**: BUY, HOLD, or AVOID
2. **Justifies the recommendation**: Reference the moat score and key supporting factors
3. **Acknowledges the main risks**: Don't oversell - be balanced
4. **Provides context**: How does this fit in a portfolio? What type of investor is this for?

**Guidelines for Recommendation**:
- **BUY (moat_score >= 8.0)**: Strong fundamentals, positive catalysts, technical strength, and/or supply chain advantages. Watchlist candidate.
- **HOLD (6.0 <= moat_score < 8.0)**: Decent opportunity but not compelling. Missing one or more key factors.
- **AVOID (moat_score < 6.0)**: Weak fundamentals, negative catalysts, technical weakness, and/or supply chain vulnerabilities.

**Tone**:
- Professional and balanced
- Specific (reference actual scores and factors)
- Actionable (clear on what an investor should do)
- Honest about risks and limitations

Return your response as a JSON object:

{{
  "recommendation": "<BUY|HOLD|AVOID>",
  "investment_thesis": "<150-250 word thesis>"
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
