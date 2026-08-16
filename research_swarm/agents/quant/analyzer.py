"""
LLM Analysis Module for Quant agent.

Generates qualitative narratives for technical and supply chain analysis.
"""
import json
from typing import Dict, Any, List
from langchain_anthropic import ChatAnthropic
from loguru import logger
from research_swarm.utils import extract_token_usage

from .models import TechnicalIndicators, SupplyChainGraph, NodeType
from .prompts import (
    SUPPLY_CHAIN_ANALYSIS_PROMPT,
)

try:
    from research_swarm.config import settings
    ANTHROPIC_API_KEY = settings.anthropic_api_key
except ImportError:
    import os
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def build_technical_digest(indicators: TechnicalIndicators) -> str:
    """Deterministic technical summary assembled from the indicator models'
    own interpretation strings (Phase B3). Replaces the Sonnet narrative call —
    every sentence here is grounded in a computed value, and the Manager's
    synthesis writes the actual interpretation with full cross-signal context.
    """
    ma = indicators.moving_averages
    signals = indicators.entry_exit_signals

    def fmt(value, decimals=2):
        return f"{value:.{decimals}f}" if value is not None else "N/A"

    lines = [
        f"Overall technical signal: {signals.overall_signal.value.upper()} "
        f"(confidence {signals.confidence:.0%}; {len(signals.bullish_factors)} bullish vs "
        f"{len(signals.bearish_factors)} bearish factors).",
        signals.interpretation,
        "",
        f"Price ${fmt(ma.current_price)} vs SMA50 ${fmt(ma.sma_50)} / SMA200 ${fmt(ma.sma_200)} "
        f"({ma.crossover_signal.value}).",
        f"RSI: {indicators.rsi.interpretation}",
        f"MACD: {indicators.macd.interpretation}",
        f"Bollinger Bands: {indicators.bollinger_bands.interpretation}",
        f"Stochastic: {indicators.stochastic.interpretation}",
        f"Volume profile: {indicators.volume_profile.interpretation}",
    ]
    if signals.bullish_factors:
        lines.append("Bullish factors: " + "; ".join(signals.bullish_factors))
    if signals.bearish_factors:
        lines.append("Bearish factors: " + "; ".join(signals.bearish_factors))

    rs = indicators.relative_strength
    if rs.vs_market_3m is not None or rs.vs_sector_3m is not None:
        lines.append(
            f"Relative strength (3m): {fmt(rs.vs_sector_3m, 1)}% vs sector, "
            f"{fmt(rs.vs_market_3m, 1)}% vs market."
        )

    return "\n".join(line for line in lines if line is not None)


class QuantAnalyzer:
    """Generates qualitative analysis narratives using LLMs."""

    def __init__(self):
        """Initialize analyzer with LLM models."""
        # Sonnet for deeper qualitative analysis
        # max_tokens must be set explicitly — LangChain defaults to 1024 and
        # silently truncates the narrative output.
        self.sonnet = ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=ANTHROPIC_API_KEY,
            temperature=0.3,
            max_tokens=8192,
        )

        logger.info("QuantAnalyzer initialized")

    def generate_supply_chain_analysis(
        self,
        ticker: str,
        analysis_date: str,
        supply_chain_graph: SupplyChainGraph
    ) -> tuple[str, int]:
        """
        Generate supply chain analysis narrative.

        Args:
            ticker: Stock ticker
            analysis_date: Analysis date
            supply_chain_graph: SupplyChainGraph model

        Returns:
            Tuple of (analysis_text, tokens_used)
        """
        logger.info(f"Generating supply chain analysis for {ticker}")

        # Count nodes by type
        tier1_suppliers = [n for n in supply_chain_graph.nodes if n.node_type == NodeType.SUPPLIER]
        tier2_suppliers = [n for n in supply_chain_graph.nodes if n.node_type == NodeType.SUPPLIER_T2]
        customers = [n for n in supply_chain_graph.nodes if n.node_type == NodeType.CUSTOMER]

        # Format supplier lists
        supplier_list = "\n".join([f"- {s.name}" + (f" ({s.ticker})" if s.ticker else "") for s in tier1_suppliers]) or "None identified"
        tier2_list = "\n".join([f"- {s.name}" + (f" ({s.ticker})" if s.ticker else "") for s in tier2_suppliers]) or "None identified"

        # Format hidden dependencies
        hidden_deps_text = "\n".join([f"- {dep}" for dep in supply_chain_graph.hidden_dependencies]) or "None identified"

        # Format critical paths
        critical_paths_text = ""
        for i, path in enumerate(supply_chain_graph.critical_paths[:3], 1):
            path_str = " → ".join(path)
            critical_paths_text += f"{i}. {path_str}\n"
        if not critical_paths_text:
            critical_paths_text = "None identified"

        prompt = SUPPLY_CHAIN_ANALYSIS_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            total_nodes=len(supply_chain_graph.nodes),
            total_edges=len(supply_chain_graph.edges),
            max_depth=supply_chain_graph.max_depth,
            tier1_suppliers=len(tier1_suppliers),
            tier2_suppliers=len(tier2_suppliers),
            major_customers=len(customers),
            supplier_list=supplier_list,
            tier2_list=tier2_list,
            hidden_dependencies=hidden_deps_text,
            critical_paths=critical_paths_text,
        )

        try:
            response = self.sonnet.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            logger.success(f"✓ Generated supply chain analysis for {ticker}")
            return response_text, tokens_used

        except Exception as e:
            logger.error(f"Error generating supply chain analysis: {e}")
            return f"Error generating supply chain analysis: {str(e)}", 0

    def _format_supply_chain_summary(self, graph: SupplyChainGraph) -> str:
        """
        Format supply chain graph for LLM prompt.

        Args:
            graph: SupplyChainGraph model

        Returns:
            Formatted text summary
        """
        lines = []
        lines.append(f"Root Company: {graph.root_ticker}")
        lines.append(f"Total Nodes: {len(graph.nodes)}")
        lines.append(f"Total Edges: {len(graph.edges)}")
        lines.append(f"Max Depth: {graph.max_depth} tiers")
        lines.append("")

        # Nodes by type
        for node_type in [NodeType.CUSTOMER, NodeType.SUPPLIER, NodeType.SUPPLIER_T2]:
            nodes_of_type = [n for n in graph.nodes if n.node_type == node_type]
            if nodes_of_type:
                lines.append(f"\n{node_type.value.upper()}S:")
                for node in nodes_of_type:
                    ticker_str = f" ({node.ticker})" if node.ticker else ""
                    lines.append(f"  - {node.name}{ticker_str}")

        # Edges
        lines.append("\nRELATIONSHIPS:")
        for edge in graph.edges[:20]:  # Limit to first 20 edges
            lines.append(f"  - {edge.source} → {edge.target} [{edge.relation_type.value}]")

        if len(graph.edges) > 20:
            lines.append(f"  ... and {len(graph.edges) - 20} more relationships")

        return "\n".join(lines)

    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from LLM response (handles markdown code blocks or preamble text).

        Args:
            text: Response text

        Returns:
            Clean JSON string
        """
        text = text.strip()

        # Try markdown code blocks first
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # Fallback: find JSON object boundaries (handles preamble text before JSON)
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            return text[first_brace:last_brace + 1]

        # Last resort: return as-is and let json.loads fail with useful error
        return text
