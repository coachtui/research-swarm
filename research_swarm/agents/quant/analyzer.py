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
    HIDDEN_DEPENDENCY_PROMPT,
    TECHNICAL_ANALYSIS_PROMPT,
    SUPPLY_CHAIN_ANALYSIS_PROMPT,
)

try:
    from research_swarm.config import settings
    ANTHROPIC_API_KEY = settings.anthropic_api_key
except ImportError:
    import os
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


class QuantAnalyzer:
    """Generates qualitative analysis narratives using LLMs."""

    def __init__(self):
        """Initialize analyzer with LLM models."""
        # Haiku for cost-effective hidden dependency analysis
        self.haiku = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=ANTHROPIC_API_KEY,
            temperature=0.0,
            max_tokens=4096,
        )

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

    def analyze_hidden_dependencies(
        self,
        ticker: str,
        analysis_date: str,
        supply_chain_graph: SupplyChainGraph
    ) -> tuple[Dict[str, Any], int]:
        """
        Analyze hidden dependencies using LLM.

        Args:
            ticker: Stock ticker
            analysis_date: Analysis date
            supply_chain_graph: Supply chain graph

        Returns:
            Tuple of (hidden_dependencies_dict, tokens_used)
        """
        logger.info(f"Analyzing hidden dependencies for {ticker}")

        # Format supply chain graph for prompt
        graph_summary = self._format_supply_chain_summary(supply_chain_graph)

        prompt = HIDDEN_DEPENDENCY_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            supply_chain_summary=graph_summary,
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            hidden_deps = json.loads(json_text)

            logger.success(f"✓ Analyzed hidden dependencies for {ticker}")
            return hidden_deps, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse hidden dependencies JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # Return default data but track tokens used (API was called)
            return {"hidden_dependencies": [], "overall_risk_level": "medium", "summary": "Error parsing analysis"}, tokens_used

        except Exception as e:
            logger.error(f"Error analyzing hidden dependencies: {e}")
            # Return 0 tokens for general errors (API call may not have completed)
            return {"hidden_dependencies": [], "overall_risk_level": "medium", "summary": "Error in analysis"}, 0

    def generate_technical_analysis(
        self,
        ticker: str,
        analysis_date: str,
        indicators: TechnicalIndicators
    ) -> tuple[str, int]:
        """
        Generate technical analysis narrative.

        Args:
            ticker: Stock ticker
            analysis_date: Analysis date
            indicators: TechnicalIndicators model

        Returns:
            Tuple of (analysis_text, tokens_used)
        """
        logger.info(f"Generating technical analysis for {ticker}")

        # Extract indicator values for prompt
        ma = indicators.moving_averages
        rsi = indicators.rsi
        macd = indicators.macd
        bb = indicators.bollinger_bands
        stoch = indicators.stochastic
        vol = indicators.volume
        vp = indicators.volume_profile
        rs = indicators.relative_strength
        signals = indicators.entry_exit_signals

        # Format values, handling None
        def fmt_float(val, decimals=2):
            return f"{val:.{decimals}f}" if val is not None else "N/A"

        def fmt_pct(val):
            return f"{val:+.1f}" if val is not None else "N/A"

        prompt = TECHNICAL_ANALYSIS_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            # Moving Averages
            sma_50=ma.sma_50 or 0,
            sma_200=ma.sma_200 or 0,
            current_price=ma.current_price or 0,
            crossover_signal=ma.crossover_signal.value,
            days_since_crossover=ma.days_since_crossover or "N/A",
            # RSI
            rsi_value=rsi.rsi_14 or 50,
            rsi_signal=rsi.rsi_signal.value,
            rsi_interpretation=rsi.interpretation,
            # MACD
            macd_line=macd.macd_line or 0,
            signal_line=macd.signal_line or 0,
            histogram=macd.histogram or 0,
            macd_signal=macd.macd_signal.value,
            macd_interpretation=macd.interpretation,
            # Bollinger Bands
            upper_band=bb.upper_band or 0,
            middle_band=bb.middle_band or 0,
            lower_band=bb.lower_band or 0,
            bb_current_price=bb.current_price or 0,
            bb_position=bb.position.value,
            bandwidth=bb.bandwidth or 0,
            bb_interpretation=bb.interpretation,
            # Stochastic
            k_value=stoch.k_value or 50,
            d_value=stoch.d_value or 50,
            stoch_signal=stoch.stochastic_signal.value,
            stoch_interpretation=stoch.interpretation,
            # Volume
            avg_volume=vol.avg_volume_20d or 0,
            current_volume=vol.current_volume or 0,
            volume_ratio=vol.volume_ratio or 1.0,
            volume_trend=vol.volume_trend.value,
            # Volume Profile
            poc=vp.poc or 0,
            value_area_high=vp.value_area_high or 0,
            value_area_low=vp.value_area_low or 0,
            volume_profile_interpretation=vp.interpretation,
            # Relative Strength
            ticker_return_1m=fmt_pct(rs.ticker_return_1m),
            vs_sector_1m=fmt_pct(rs.vs_sector_1m),
            vs_market_1m=fmt_pct(rs.vs_market_1m),
            ticker_return_3m=fmt_pct(rs.ticker_return_3m),
            vs_sector_3m=fmt_pct(rs.vs_sector_3m),
            vs_market_3m=fmt_pct(rs.vs_market_3m),
            # Entry/Exit Signals
            overall_signal=signals.overall_signal.value,
            signal_confidence=signals.confidence,
            bullish_count=len(signals.bullish_factors),
            bearish_count=len(signals.bearish_factors),
        )

        try:
            response = self.sonnet.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            logger.success(f"✓ Generated technical analysis for {ticker}")
            return response_text, tokens_used

        except Exception as e:
            logger.error(f"Error generating technical analysis: {e}")
            return f"Error generating technical analysis: {str(e)}", 0

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
