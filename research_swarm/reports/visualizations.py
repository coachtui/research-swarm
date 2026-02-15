"""Chart generation for reports using matplotlib and networkx."""

from pathlib import Path
from typing import Dict, List

import matplotlib
import matplotlib.pyplot as plt
import networkx as nx

# Use non-interactive backend for server environments
matplotlib.use("Agg")


class ChartGenerator:
    """Generates charts and visualizations for stock analysis reports."""

    def __init__(self, output_dir: Path):
        """Initialize chart generator.

        Args:
            output_dir: Directory to save chart images
        """
        self.charts_dir = output_dir / "charts"
        self.charts_dir.mkdir(parents=True, exist_ok=True)

        # Set matplotlib style for better-looking charts
        try:
            plt.style.use("seaborn-v0_8-whitegrid")
        except OSError:
            # Fallback if seaborn style not available
            plt.style.use("default")

    def generate_moat_breakdown(
        self, ticker: str, breakdown: Dict[str, float]
    ) -> Path:
        """Generate horizontal bar chart of moat score components.

        Args:
            ticker: Stock ticker symbol
            breakdown: Dictionary with moat component scores

        Returns:
            Path to generated PNG file
        """
        fig, ax = plt.subplots(figsize=(8, 5))

        # Define components (v2.0 moat scoring formula)
        components = [
            "Earnings Momentum",
            "Financial Health",
            "Valuation",
            "Technical/Momentum",
            "Sentiment",
        ]

        # Extract values in the same order
        values = [
            breakdown.get("earnings_momentum", 0.0),
            breakdown.get("financial_health", 0.0),
            breakdown.get("valuation", 0.0),
            breakdown.get("technical_strength", 0.0),
            breakdown.get("sentiment_catalysts", 0.0),
        ]

        # Color code based on score thresholds
        colors = []
        for value in values:
            if value >= 7.0:
                colors.append("#00D9B5")  # Green - Strong
            elif value >= 4.0:
                colors.append("#f39c12")  # Gold - Moderate
            else:
                colors.append("#e74c3c")  # Red - Weak

        # Create horizontal bar chart
        ax.barh(components, values, color=colors, edgecolor="black", linewidth=0.5)

        # Configure axes
        ax.set_xlim(0, 10)
        ax.set_xlabel("Score", fontsize=11, fontweight="bold")
        ax.set_title(f"{ticker} Moat Score Breakdown", fontsize=13, fontweight="bold")

        # Add value labels on bars
        for i, (component, value) in enumerate(zip(components, values)):
            ax.text(
                value + 0.2,
                i,
                f"{value:.1f}",
                va="center",
                fontsize=10,
                fontweight="bold",
            )

        # Add grid for better readability
        ax.grid(axis="x", alpha=0.3, linestyle="--")
        ax.set_axisbelow(True)

        # Save chart
        path = self.charts_dir / f"moat_{ticker}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        return path

    def generate_supply_chain_graph(
        self,
        ticker: str,
        nodes: List[Dict],
        edges: List[Dict],
        hidden_dependencies: List[str],
    ) -> Path:
        """Generate supply chain network visualization using NetworkX.

        Args:
            ticker: Stock ticker symbol
            nodes: List of node dictionaries with 'name', 'ticker', 'node_type'
            edges: List of edge dictionaries with 'source', 'target', 'relationship'
            hidden_dependencies: List of hidden dependency descriptions

        Returns:
            Path to generated PNG file
        """
        # Create directed graph
        G = nx.DiGraph()

        # Node type color mapping
        node_colors_map = {
            "root": "#4361ee",  # Blue - Root company
            "customer": "#00D9B5",  # Green - Customers
            "supplier": "#e67e22",  # Orange - Suppliers
            "supplier_t2": "#f39c12",  # Yellow - Tier 2 suppliers
        }

        # Add nodes to graph
        for node in nodes:
            G.add_node(
                node["name"],
                node_type=node.get("node_type", "supplier"),
                ticker=node.get("ticker", ""),
            )

        # Add edges to graph
        for edge in edges:
            G.add_edge(edge["source"], edge["target"])

        # Skip visualization if graph is empty
        if len(G.nodes()) == 0:
            # Create a placeholder image indicating no supply chain data
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(
                0.5,
                0.5,
                f"No supply chain data available for {ticker}",
                ha="center",
                va="center",
                fontsize=14,
                color="gray",
            )
            ax.axis("off")
            path = self.charts_dir / f"supply_chain_{ticker}.png"
            fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
            plt.close(fig)
            return path

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 8))

        # Use spring layout for better node distribution
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

        # Assign colors based on node types
        node_colors = [
            node_colors_map.get(G.nodes[node].get("node_type", "supplier"), "#95a5a6")
            for node in G.nodes()
        ]

        # Draw the graph
        nx.draw(
            G,
            pos,
            ax=ax,
            node_color=node_colors,
            node_size=2000,
            with_labels=True,
            font_size=8,
            font_weight="bold",
            arrows=True,
            arrowsize=15,
            edge_color="#7f8c8d",
            width=2,
            alpha=0.9,
        )

        # Add title
        ax.set_title(
            f"{ticker} Supply Chain Network", fontsize=14, fontweight="bold", pad=20
        )

        # Add legend
        legend_elements = [
            plt.Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="#4361ee",
                markersize=10,
                label="Root Company",
            ),
            plt.Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="#00D9B5",
                markersize=10,
                label="Customer",
            ),
            plt.Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="#e67e22",
                markersize=10,
                label="Supplier (T1)",
            ),
            plt.Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="#f39c12",
                markersize=10,
                label="Supplier (T2)",
            ),
        ]
        ax.legend(
            handles=legend_elements, loc="upper left", framealpha=0.9, fontsize=9
        )

        # Add hidden dependencies as text annotation if present
        if hidden_dependencies:
            deps_text = "Hidden Dependencies:\n" + "\n".join(
                f"• {dep[:50]}..." if len(dep) > 50 else f"• {dep}"
                for dep in hidden_dependencies[:3]
            )
            ax.text(
                0.02,
                0.02,
                deps_text,
                transform=ax.transAxes,
                fontsize=8,
                verticalalignment="bottom",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
            )

        # Save chart
        path = self.charts_dir / f"supply_chain_{ticker}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        return path

    def generate_portfolio_overview(
        self, tickers: List[str], moat_scores: List[float]
    ) -> Path:
        """Generate bar chart showing moat scores across portfolio.

        Args:
            tickers: List of stock tickers
            moat_scores: List of corresponding moat scores

        Returns:
            Path to generated PNG file
        """
        fig, ax = plt.subplots(figsize=(12, 6))

        # Sort by moat score descending
        sorted_data = sorted(
            zip(tickers, moat_scores), key=lambda x: x[1], reverse=True
        )
        sorted_tickers, sorted_scores = zip(*sorted_data) if sorted_data else ([], [])

        # Color code bars
        colors = []
        for score in sorted_scores:
            if score >= 8.0:
                colors.append("#00D9B5")  # Green - Watchlist
            elif score >= 7.0:
                colors.append("#f39c12")  # Gold - Strong
            elif score >= 5.0:
                colors.append("#3498db")  # Blue - Moderate
            else:
                colors.append("#e74c3c")  # Red - Weak

        # Create bar chart
        bars = ax.bar(
            range(len(sorted_tickers)),
            sorted_scores,
            color=colors,
            edgecolor="black",
            linewidth=0.5,
        )

        # Configure axes
        ax.set_xticks(range(len(sorted_tickers)))
        ax.set_xticklabels(sorted_tickers, rotation=45, ha="right")
        ax.set_ylabel("Moat Score", fontsize=11, fontweight="bold")
        ax.set_ylim(0, 10)
        ax.set_title(
            "Portfolio Moat Score Overview", fontsize=14, fontweight="bold", pad=20
        )

        # Add watchlist threshold line
        ax.axhline(y=8.0, color="#00D9B5", linestyle="--", linewidth=2, alpha=0.5)
        ax.text(
            len(sorted_tickers) - 0.5,
            8.2,
            "Watchlist Threshold",
            ha="right",
            fontsize=9,
            color="#00D9B5",
        )

        # Add value labels on bars
        for i, (ticker, score) in enumerate(zip(sorted_tickers, sorted_scores)):
            ax.text(
                i,
                score + 0.2,
                f"{score:.1f}",
                ha="center",
                fontsize=9,
                fontweight="bold",
            )

        # Add grid
        ax.grid(axis="y", alpha=0.3, linestyle="--")
        ax.set_axisbelow(True)

        # Save chart
        path = self.charts_dir / "portfolio_overview.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        return path
