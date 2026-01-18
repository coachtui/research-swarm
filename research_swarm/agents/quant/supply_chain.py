"""
Supply chain graph builder for the Quant agent.

Builds NetworkX graphs from supply chain data, identifies hidden dependencies,
and maps tier-2/3 suppliers.
"""
from typing import List, Optional, Dict, Set, Tuple
import networkx as nx
from loguru import logger

from research_swarm.agents.fundamentalist.models import SupplyChainOutput
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

    # Tier-2 Suppliers (suppliers to TSMC, ASML, etc.)
    "Nittobo Glass": None,  # Private company
    "Zeiss": None,  # Private (Carl Zeiss AG)
    "Trumpf": None,  # Private
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
    "Advanced Micro Devices": "AMD",
    "Qualcomm": "QCOM",
    "Apple": "AAPL",
    "Broadcom": "AVGO",
}


class SupplyChainGraphBuilder:
    """
    Builds supply chain graphs from fundamentalist data.

    Supports multi-tier analysis and hidden dependency detection.
    """

    def __init__(self):
        """Initialize the graph builder."""
        self.ticker_cache: Dict[str, Optional[str]] = {}

    def build_from_fundamentalist_data(
        self,
        root_ticker: str,
        supply_chain_data: SupplyChainOutput,
        max_depth: int = 2
    ) -> SupplyChainGraph:
        """
        Build supply chain graph from Fundamentalist agent output.

        Args:
            root_ticker: The root company ticker
            supply_chain_data: SupplyChainOutput from Fundamentalist
            max_depth: Maximum tier depth to explore (1=tier-1, 2=tier-2, etc.)

        Returns:
            SupplyChainGraph with nodes, edges, and analysis
        """
        logger.info(f"Building supply chain graph for {root_ticker} (max_depth={max_depth})")

        nodes: List[SupplyChainNode] = []
        edges: List[SupplyChainEdge] = []

        # Create root node
        root_node = SupplyChainNode(
            id=root_ticker,
            name=root_ticker,
            node_type=NodeType.ROOT,
            ticker=root_ticker,
            description="Root company being analyzed",
        )
        nodes.append(root_node)

        # Add customers (tier-1)
        for customer in supply_chain_data.major_customers:
            customer_ticker = self._resolve_ticker(customer)
            customer_id = customer_ticker if customer_ticker else f"customer_{customer.replace(' ', '_')}"

            customer_node = SupplyChainNode(
                id=customer_id,
                name=customer,
                node_type=NodeType.CUSTOMER,
                ticker=customer_ticker,
                description=f"Major customer of {root_ticker}",
            )
            nodes.append(customer_node)

            # Edge: root supplies to customer
            edge = SupplyChainEdge(
                source=root_ticker,
                target=customer_id,
                relation_type=RelationType.SUPPLIES_TO,
                weight=0.8,  # Customers are important but not critical path
                description=f"{root_ticker} supplies products/services to {customer}",
            )
            edges.append(edge)

        # Add suppliers (tier-1)
        tier1_suppliers = []
        for supplier in supply_chain_data.major_suppliers:
            supplier_ticker = self._resolve_ticker(supplier)
            supplier_id = supplier_ticker if supplier_ticker else f"supplier_{supplier.replace(' ', '_')}"

            supplier_node = SupplyChainNode(
                id=supplier_id,
                name=supplier,
                node_type=NodeType.SUPPLIER,
                ticker=supplier_ticker,
                description=f"Major supplier to {root_ticker}",
            )
            nodes.append(supplier_node)
            tier1_suppliers.append((supplier_id, supplier))

            # Edge: supplier supplies to root
            edge = SupplyChainEdge(
                source=supplier_id,
                target=root_ticker,
                relation_type=RelationType.SUPPLIES_TO,
                weight=1.0,  # Suppliers are critical path
                description=f"{supplier} supplies components/materials to {root_ticker}",
            )
            edges.append(edge)

        # Extend to tier-2 if max_depth >= 2
        if max_depth >= 2:
            tier2_nodes, tier2_edges = self._extend_graph_tier2(tier1_suppliers, nodes)
            nodes.extend(tier2_nodes)
            edges.extend(tier2_edges)

        # Build NetworkX graph for analysis
        G = self._to_networkx(nodes, edges)

        # Find critical paths
        critical_paths = self._find_critical_paths(G, root_ticker)

        # Identify hidden dependencies
        hidden_dependencies = self._identify_hidden_dependencies(G, root_ticker, nodes, edges)

        return SupplyChainGraph(
            root_ticker=root_ticker,
            nodes=nodes,
            edges=edges,
            max_depth=max_depth,
            hidden_dependencies=hidden_dependencies,
            critical_paths=critical_paths,
        )

    def _extend_graph_tier2(
        self,
        tier1_suppliers: List[Tuple[str, str]],
        existing_nodes: List[SupplyChainNode]
    ) -> Tuple[List[SupplyChainNode], List[SupplyChainEdge]]:
        """
        Extend graph with tier-2 suppliers (suppliers of suppliers).

        Args:
            tier1_suppliers: List of (supplier_id, supplier_name) tuples
            existing_nodes: Existing nodes in the graph

        Returns:
            Tuple of (new_nodes, new_edges)
        """
        logger.info(f"Extending graph with tier-2 suppliers")

        tier2_nodes: List[SupplyChainNode] = []
        tier2_edges: List[SupplyChainEdge] = []

        # Hardcoded tier-2 relationships (based on semiconductor industry knowledge)
        tier2_relationships = {
            "TSM": ["ASML", "Tokyo Electron", "Applied Materials", "Shin-Etsu Chemical"],
            "ASML": ["Zeiss", "Trumpf", "Nittobo Glass"],
            "INTC": ["ASML", "Applied Materials", "Lam Research"],
            "AMAT": ["Applied Materials"],  # AMAT supplies to itself (different divisions)
            "LRCX": ["Lam Research"],
        }

        existing_ids = {node.id for node in existing_nodes}

        for supplier_id, supplier_name in tier1_suppliers:
            # Check if we have known tier-2 suppliers for this tier-1 supplier
            if supplier_id in tier2_relationships:
                for tier2_name in tier2_relationships[supplier_id]:
                    tier2_ticker = self._resolve_ticker(tier2_name)
                    tier2_id = tier2_ticker if tier2_ticker else f"supplier_t2_{tier2_name.replace(' ', '_')}"

                    # Skip if node already exists
                    if tier2_id in existing_ids or any(n.id == tier2_id for n in tier2_nodes):
                        # Add edge to existing node
                        edge = SupplyChainEdge(
                            source=tier2_id,
                            target=supplier_id,
                            relation_type=RelationType.SUPPLIES_TO,
                            weight=0.9,
                            description=f"{tier2_name} supplies to {supplier_name}",
                        )
                        tier2_edges.append(edge)
                        continue

                    # Create tier-2 node
                    tier2_node = SupplyChainNode(
                        id=tier2_id,
                        name=tier2_name,
                        node_type=NodeType.SUPPLIER_T2,
                        ticker=tier2_ticker,
                        description=f"Tier-2 supplier to {supplier_name}",
                    )
                    tier2_nodes.append(tier2_node)
                    existing_ids.add(tier2_id)

                    # Create edge
                    edge = SupplyChainEdge(
                        source=tier2_id,
                        target=supplier_id,
                        relation_type=RelationType.SUPPLIES_TO,
                        weight=0.9,
                        description=f"{tier2_name} supplies to {supplier_name}",
                    )
                    tier2_edges.append(edge)

        logger.info(f"Added {len(tier2_nodes)} tier-2 nodes and {len(tier2_edges)} tier-2 edges")
        return tier2_nodes, tier2_edges

    def _to_networkx(
        self,
        nodes: List[SupplyChainNode],
        edges: List[SupplyChainEdge]
    ) -> nx.DiGraph:
        """
        Convert to NetworkX directed graph.

        Args:
            nodes: List of supply chain nodes
            edges: List of supply chain edges

        Returns:
            NetworkX DiGraph
        """
        G = nx.DiGraph()

        # Add nodes with attributes
        for node in nodes:
            G.add_node(
                node.id,
                name=node.name,
                node_type=node.node_type.value,
                ticker=node.ticker,
                description=node.description,
            )

        # Add edges with attributes
        for edge in edges:
            G.add_edge(
                edge.source,
                edge.target,
                relation_type=edge.relation_type.value,
                weight=edge.weight,
                description=edge.description,
            )

        return G

    def _find_critical_paths(
        self,
        G: nx.DiGraph,
        root_ticker: str
    ) -> List[List[str]]:
        """
        Find critical paths in the supply chain.

        Critical paths are the longest paths from tier-2/3 suppliers to the root.

        Args:
            G: NetworkX directed graph
            root_ticker: Root company ticker

        Returns:
            List of critical paths (each path is a list of node IDs)
        """
        critical_paths = []

        # Find all nodes with no incoming edges (tier-2/3 suppliers or leaf nodes)
        leaf_nodes = [node for node in G.nodes() if G.in_degree(node) == 0]

        # Find all simple paths from leaf nodes to root
        for leaf in leaf_nodes:
            try:
                paths = list(nx.all_simple_paths(G, leaf, root_ticker))
                critical_paths.extend(paths)
            except nx.NetworkXNoPath:
                continue

        # Sort by path length (longest first) and take top 5
        critical_paths.sort(key=len, reverse=True)
        return critical_paths[:5]

    def _identify_hidden_dependencies(
        self,
        G: nx.DiGraph,
        root_ticker: str,
        nodes: List[SupplyChainNode],
        edges: List[SupplyChainEdge]
    ) -> List[str]:
        """
        Identify hidden dependencies (tier-2/3 suppliers shared by multiple tier-1 suppliers).

        These are critical bottlenecks in the supply chain.

        Args:
            G: NetworkX directed graph
            root_ticker: Root company ticker
            nodes: List of all nodes
            edges: List of all edges

        Returns:
            List of hidden dependency node names
        """
        hidden_deps: Set[str] = set()

        # Find tier-2 and tier-3 suppliers
        tier2_plus_nodes = [
            node for node in nodes
            if node.node_type in [NodeType.SUPPLIER_T2, NodeType.SUPPLIER_T3]
        ]

        # For each tier-2+ supplier, check if it supplies to multiple tier-1 suppliers
        for tier2_node in tier2_plus_nodes:
            # Get all direct successors (nodes this supplies to)
            successors = list(G.successors(tier2_node.id))

            # Count how many are tier-1 suppliers or root
            tier1_customers = []
            for successor in successors:
                successor_node = next((n for n in nodes if n.id == successor), None)
                if successor_node and successor_node.node_type in [NodeType.SUPPLIER, NodeType.ROOT]:
                    tier1_customers.append(successor)

            # If supplies to multiple tier-1 suppliers, it's a hidden dependency
            if len(tier1_customers) >= 2:
                hidden_deps.add(tier2_node.name)
                logger.info(
                    f"Hidden dependency identified: {tier2_node.name} "
                    f"supplies to {len(tier1_customers)} tier-1 suppliers"
                )

        return sorted(list(hidden_deps))

    def _resolve_ticker(self, company_name: str) -> Optional[str]:
        """
        Resolve company name to stock ticker.

        Args:
            company_name: Company name

        Returns:
            Stock ticker or None if not found/not public
        """
        # Check cache
        if company_name in self.ticker_cache:
            return self.ticker_cache[company_name]

        # Check known mappings
        for key, ticker in TICKER_MAPPINGS.items():
            if key.lower() in company_name.lower() or company_name.lower() in key.lower():
                self.ticker_cache[company_name] = ticker
                return ticker

        # Not found
        self.ticker_cache[company_name] = None
        return None
