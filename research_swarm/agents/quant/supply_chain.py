"""
Supply chain graph builder for the Quant agent.

Builds NetworkX graphs from supply chain data, identifies hidden dependencies,
and maps tier-2/3 suppliers. Enhanced with curated knowledge base for bottleneck identification.
"""
from typing import List, Optional, Dict, Set, Tuple
import networkx as nx
from loguru import logger

from research_swarm.agents.fundamentalist.models import SupplyChainOutput
from research_swarm.data.supply_chain_knowledge import supply_chain_kb
from .models import (
    SupplyChainNode,
    SupplyChainEdge,
    SupplyChainGraph,
    NodeType,
    RelationType,
)


# Known ticker mappings for semiconductor supply chain
TICKER_MAPPINGS = {
    # Tier-1 Suppliers
    "TSMC": "TSM",
    "Taiwan Semiconductor": "TSM",
    "Taiwan Semiconductor Manufacturing": "TSM",
    "ASML": "ASML",
    "ASML Holding": "ASML",
    "Intel": "INTC",
    "Samsung": "SSNLF",
    "Applied Materials": "AMAT",
    "Lam Research": "LRCX",
    "KLA Corporation": "KLAC",
    "Synopsys": "SNPS",
    "Cadence": "CDNS",

    # Tier-2 Suppliers
    "Shin-Etsu Chemical": "4063.T",
    "Tokyo Electron": "8035.T",
    "Advantest": "6857.T",
    "Nikon": "NINOY",
    "Canon": "CAJ",
    "SUMCO": "3436.T",

    # Common customers
    "NVIDIA": "NVDA",
    "Nvidia": "NVDA",
    "AMD": "AMD",
    "Qualcomm": "QCOM",
    "Apple": "AAPL",
    "Broadcom": "AVGO",
}


class SupplyChainGraphBuilder:
    """Builds supply chain graphs from multiple data sources."""

    def __init__(self):
        """Initialize graph builder."""
        logger.info("SupplyChainGraphBuilder initialized with knowledge base integration")

    def build_from_fundamentalist_data(
        self,
        root_ticker: str,
        supply_chain_data: SupplyChainOutput,
        max_depth: int = 2
    ) -> SupplyChainGraph:
        """
        Build supply chain graph from fundamentalist data + knowledge base.

        Args:
            root_ticker: Root company ticker
            supply_chain_data: Supply chain data from fundamentalist agent
            max_depth: Maximum graph depth

        Returns:
            SupplyChainGraph with nodes and edges
        """
        logger.info(f"Building supply chain graph for {root_ticker}")

        # Initialize graph
        G = nx.DiGraph()
        nodes = []
        edges = []

        # Add root node
        root_node = SupplyChainNode(
            id=root_ticker,
            name=root_ticker,
            ticker=root_ticker,
            node_type=NodeType.ROOT,
            description="Root company being analyzed"
        )
        nodes.append(root_node)
        G.add_node(root_ticker, **root_node.dict())

        # 1. Add suppliers from 10-K extraction
        for supplier_name in supply_chain_data.major_suppliers or []:
            supplier_id = self._normalize_name(supplier_name)
            ticker = self._get_ticker(supplier_name)

            supplier_node = SupplyChainNode(
                id=supplier_id,
                name=supplier_name,
                ticker=ticker,
                node_type=NodeType.SUPPLIER,
                description=f"Supplier identified from 10-K filing"
            )
            nodes.append(supplier_node)
            G.add_node(supplier_id, **supplier_node.dict())

            # Add edge
            edge = SupplyChainEdge(
                source=supplier_id,
                target=root_ticker,
                relation_type=RelationType.SUPPLIES_TO,
                description="Supply relationship"
            )
            edges.append(edge)
            G.add_edge(supplier_id, root_ticker)

        # 2. Enrich with knowledge base data
        kb_suppliers = supply_chain_kb.get_suppliers(root_ticker)
        for kb_supplier in kb_suppliers:
            supplier_id = kb_supplier.ticker or self._normalize_name(kb_supplier.name)

            # Check if already added from 10-K
            if supplier_id not in G.nodes:
                supplier_node = SupplyChainNode(
                    id=supplier_id,
                    name=kb_supplier.name,
                    ticker=kb_supplier.ticker,
                    node_type=NodeType.SUPPLIER,
                    description=f"{kb_supplier.description} [KB: {kb_supplier.criticality}, Bottleneck: {kb_supplier.bottleneck_risk}]"
                )
                nodes.append(supplier_node)
                G.add_node(supplier_id, **supplier_node.dict())

                edge = SupplyChainEdge(
                    source=supplier_id,
                    target=root_ticker,
                    relation_type=RelationType.SUPPLIES_TO,
                    description=f"Critical dependency: {kb_supplier.dependency_level}"
                )
                edges.append(edge)
                G.add_edge(supplier_id, root_ticker)

            # Add metadata about bottleneck risk
            G.nodes[supplier_id]['bottleneck_risk'] = kb_supplier.bottleneck_risk
            G.nodes[supplier_id]['criticality'] = kb_supplier.criticality
            G.nodes[supplier_id]['dependency_level'] = kb_supplier.dependency_level

        # 3. Add customers from knowledge base
        kb_customers = supply_chain_kb.get_customers(root_ticker)
        for kb_customer in kb_customers:
            customer_id = kb_customer.ticker or self._normalize_name(kb_customer.name)

            customer_node = SupplyChainNode(
                id=customer_id,
                name=kb_customer.name,
                ticker=kb_customer.ticker,
                node_type=NodeType.CUSTOMER,
                description=f"{kb_customer.description} [Revenue exposure: {kb_customer.revenue_exposure}]"
            )
            nodes.append(customer_node)
            G.add_node(customer_id, **customer_node.dict())

            edge = SupplyChainEdge(
                source=root_ticker,
                target=customer_id,
                relation_type=RelationType.SUPPLIES_TO,
                description=f"Customer relationship: {kb_customer.criticality}"
            )
            edges.append(edge)
            G.add_edge(root_ticker, customer_id)

        # 4. Add tier-2 suppliers (suppliers of suppliers) if depth allows
        if max_depth >= 2:
            for supplier in kb_suppliers:
                if supplier.ticker:
                    tier2_suppliers = supply_chain_kb.get_suppliers(supplier.ticker)
                    for tier2_supplier in tier2_suppliers[:3]:  # Limit to top 3
                        tier2_id = tier2_supplier.ticker or self._normalize_name(tier2_supplier.name)

                        if tier2_id not in G.nodes:
                            tier2_node = SupplyChainNode(
                                id=tier2_id,
                                name=tier2_supplier.name,
                                ticker=tier2_supplier.ticker,
                                node_type=NodeType.SUPPLIER_T2,
                                description=f"Tier-2 supplier: {tier2_supplier.description}"
                            )
                            nodes.append(tier2_node)
                            G.add_node(tier2_id, **tier2_node.dict())

                            # Add edge from tier-2 to tier-1
                            edge = SupplyChainEdge(
                                source=tier2_id,
                                target=supplier.ticker,
                                relation_type=RelationType.SUPPLIES_TO,
                                description=f"Tier-2 supply relationship"
                            )
                            edges.append(edge)
                            G.add_edge(tier2_id, supplier.ticker)

                            # Add metadata
                            G.nodes[tier2_id]['bottleneck_risk'] = tier2_supplier.bottleneck_risk
                            G.nodes[tier2_id]['criticality'] = tier2_supplier.criticality

        # 5. Identify critical paths (paths through bottleneck suppliers)
        critical_paths = self._identify_critical_paths(G, root_ticker)

        # Build final graph object
        supply_chain_graph = SupplyChainGraph(
            root_ticker=root_ticker,
            nodes=nodes,
            edges=edges,
            max_depth=max_depth,
            hidden_dependencies=[],
            critical_paths=critical_paths
        )

        logger.success(
            f"✓ Built enriched supply chain graph: {len(nodes)} nodes, "
            f"{len(edges)} edges, {len(critical_paths)} critical paths"
        )

        return supply_chain_graph

    def _identify_critical_paths(self, G: nx.DiGraph, root: str) -> List[List[str]]:
        """Identify critical paths through bottleneck suppliers."""
        critical_paths = []

        # Find all paths from suppliers to root
        for node in G.nodes:
            if node != root and G.nodes[node].get('bottleneck_risk') in ['extreme', 'high']:
                try:
                    # Find all simple paths from bottleneck to root
                    paths = list(nx.all_simple_paths(G, source=node, target=root, cutoff=3))
                    critical_paths.extend(paths[:2])  # Take top 2 paths per bottleneck
                except nx.NetworkXNoPath:
                    continue

        # Deduplicate
        critical_paths = [list(x) for x in set(tuple(x) for x in critical_paths)]

        return critical_paths[:10]  # Return top 10 critical paths

    def _normalize_name(self, name: str) -> str:
        """Normalize supplier/customer name for node ID."""
        return name.replace(" ", "_").replace("(", "").replace(")", "").upper()

    def _get_ticker(self, name: str) -> Optional[str]:
        """Get ticker symbol from company name if known."""
        return TICKER_MAPPINGS.get(name)


# Global instance
graph_builder = SupplyChainGraphBuilder()
