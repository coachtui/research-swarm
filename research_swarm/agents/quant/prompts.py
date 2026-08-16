"""
Prompt templates for the Quant agent.

Each prompt is designed for specific LLM models and tasks.
"""

# ============================================================================
# HIDDEN DEPENDENCY PROMPT (Haiku)
# Purpose: Identify hidden dependencies in supply chain graph
# ============================================================================

HIDDEN_DEPENDENCY_PROMPT = """You are analyzing a supply chain graph to identify hidden dependencies.

**Company**: {ticker}
**Analysis Date**: {analysis_date}

**Supply Chain Graph**:
{supply_chain_summary}

---

**Task**: Identify hidden dependencies - tier-2 or tier-3 suppliers that are shared by multiple tier-1 suppliers. These represent critical bottlenecks in the supply chain.

For example, if both TSMC and Intel rely on ASML for lithography equipment, ASML is a hidden dependency that affects multiple paths to {ticker}.

**Instructions**:
1. Analyze the graph structure and identify tier-2/3 nodes that supply to multiple tier-1 suppliers
2. Assess the criticality of each hidden dependency (can it be substituted? is it a monopoly?)
3. Evaluate the risk level (high/medium/low)

Return your analysis as a JSON object:

{{
  "hidden_dependencies": [
    {{
      "name": "<supplier name>",
      "tier": <2 or 3>,
      "supplies_to": ["<tier-1 supplier 1>", "<tier-1 supplier 2>", ...],
      "criticality": "<high|medium|low>",
      "risk_description": "<why this is a bottleneck>",
      "substitutability": "<easy|difficult|impossible>"
    }}
  ],
  "overall_risk_level": "<high|medium|low>",
  "summary": "<brief summary of key findings>"
}}

**Instructions**:
- Focus on tier-2 and tier-3 suppliers
- Consider industry knowledge (e.g., ASML's monopoly on EUV lithography)
- Return ONLY valid JSON, no other text
"""

# ============================================================================
# TECHNICAL ANALYSIS PROMPT (Sonnet)
# Purpose: Generate qualitative technical analysis narrative
# ============================================================================

# ============================================================================
# SUPPLY CHAIN ANALYSIS PROMPT (Sonnet)
# Purpose: Generate qualitative supply chain resilience narrative
# ============================================================================

SUPPLY_CHAIN_ANALYSIS_PROMPT = """You are a supply chain analyst writing a resilience assessment report.

**Company**: {ticker}
**Analysis Date**: {analysis_date}

**Supply Chain Graph Summary**:
- Total Nodes: {total_nodes}
- Total Edges: {total_edges}
- Max Depth: {max_depth} tiers
- Number of Tier-1 Suppliers: {tier1_suppliers}
- Number of Tier-2 Suppliers: {tier2_suppliers}
- Number of Major Customers: {major_customers}

**Suppliers** (Tier-1):
{supplier_list}

**Tier-2 Suppliers**:
{tier2_list}

**Hidden Dependencies**:
{hidden_dependencies}

**Critical Paths** (longest supply chains):
{critical_paths}

---

**Task**: Write a comprehensive supply chain resilience analysis (400-600 words) covering:

1. **Supplier Diversification**: Evaluate the breadth and diversity of the supplier base. Is the company dependent on a few critical suppliers or well-diversified?

2. **Tier Depth Analysis**: Assess the visibility into tier-2 and tier-3 suppliers. What does the tier depth tell us about supply chain complexity and risk?

3. **Hidden Dependencies**: Analyze the identified hidden dependencies. Which tier-2/3 suppliers create bottlenecks? How critical are they? Can they be substituted?

4. **Critical Path Analysis**: Examine the longest supply chains. Where are the potential points of failure? What happens if a critical path node fails?

5. **Geographic and Geopolitical Risk**: Consider geographic concentration (e.g., Taiwan for semiconductors, China for rare earths). What geopolitical risks exist?

6. **Overall Supply Chain Resilience**: Synthesize findings into an assessment of supply chain strength and vulnerability. What are the biggest risks? What are the strengths?

**Guidelines**:
- Be objective and risk-focused
- Use specific examples from the graph
- Consider industry context (e.g., semiconductor supply chains are inherently concentrated)
- Highlight both strengths and vulnerabilities
- Discuss potential mitigation strategies where relevant
- Use professional supply chain analysis language
- Note: Focus on structural resilience, not financial health of suppliers
"""

# ============================================================================
# COMBINED SCORING PROMPT (Optional, for LLM-assisted scoring)
# Purpose: Help validate or adjust automated scores
# ============================================================================

SCORING_VALIDATION_PROMPT = """You are validating quantitative scores for a stock analysis.

**Company**: {ticker}

**Technical Score**: {technical_score:.1f}/10
**Breakdown**: Trend={trend_score:.1f}, Momentum={momentum_score:.1f}, Volume={volume_score:.1f}, RelStrength={rs_score:.1f}

**Supply Chain Score**: {supply_chain_score:.1f}/10
**Breakdown**: Diversification={div_score:.1f}, TierDepth={tier_score:.1f}, CriticalPath={path_score:.1f}, HiddenDep={hidden_score:.1f}

**Combined Quant Score**: {quant_score:.1f}/10

---

**Task**: Review these scores for reasonableness. Do they align with the technical and supply chain analyses? Are there any scores that seem too high or too low given the data?

Return a JSON object:

{{
  "scores_reasonable": true/false,
  "suggested_adjustments": {{
    "technical_score": <adjusted score or null>,
    "supply_chain_score": <adjusted score or null>
  }},
  "reasoning": "<brief explanation of any suggested adjustments>"
}}

**Instructions**:
- Only suggest adjustments if scores are clearly inconsistent with the data
- Be conservative - trust the automated scoring unless there's a clear issue
- Return ONLY valid JSON, no other text
"""
