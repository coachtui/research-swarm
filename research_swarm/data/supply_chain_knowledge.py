"""
Supply Chain Knowledge Base.

Curated database of known supply chain relationships for bottleneck identification.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from research_swarm.logger import logger


@dataclass
class SupplierRelationship:
    """Represents a supplier relationship."""
    name: str
    ticker: Optional[str]
    category: str
    criticality: str  # critical, major, moderate
    description: str
    dependency_level: str  # sole_source, major, secondary
    revenue_exposure: str
    bottleneck_risk: str  # extreme, high, medium, low
    source: str


@dataclass
class CustomerRelationship:
    """Represents a customer relationship."""
    name: str
    ticker: Optional[str]
    category: str
    criticality: str
    revenue_exposure: str
    description: str
    source: str


@dataclass
class BottleneckAnalysis:
    """Bottleneck analysis for a supplier."""
    tier: int  # 0 = absolute monopoly, 1 = critical, 2 = major, 3 = moderate
    tier_name: str
    is_bottleneck: bool
    bottleneck_score: float  # 0-10, higher = more critical bottleneck
    characteristics: List[str]
    investment_thesis: str
    customers_exposed: List[str]  # List of major customers dependent on this supplier


class SupplyChainKnowledgeBase:
    """Manages curated supply chain relationship data."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize knowledge base.

        Args:
            db_path: Path to supply chain database JSON file
        """
        if db_path is None:
            db_path = Path(__file__).parent / "supply_chain_db.json"

        self.db_path = db_path
        self.data = self._load_database()
        logger.info(f"Loaded supply chain knowledge base with {len(self.data['relationships'])} companies")

    def _load_database(self) -> Dict:
        """Load supply chain database from JSON."""
        try:
            with open(self.db_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Supply chain database not found at {self.db_path}")
            return {"relationships": {}, "bottleneck_tiers": {}}

    def get_suppliers(self, ticker: str) -> List[SupplierRelationship]:
        """Get known suppliers for a company.

        Args:
            ticker: Stock ticker

        Returns:
            List of supplier relationships
        """
        company_data = self.data.get("relationships", {}).get(ticker, {})
        suppliers = company_data.get("suppliers", [])

        return [
            SupplierRelationship(
                name=s.get("name"),
                ticker=s.get("ticker"),
                category=s.get("category"),
                criticality=s.get("criticality"),
                description=s.get("description"),
                dependency_level=s.get("dependency_level"),
                revenue_exposure=s.get("revenue_exposure", "Unknown"),
                bottleneck_risk=s.get("bottleneck_risk", "unknown"),
                source=s.get("source", "Curated database")
            )
            for s in suppliers
        ]

    def get_customers(self, ticker: str) -> List[CustomerRelationship]:
        """Get known customers for a company.

        Args:
            ticker: Stock ticker

        Returns:
            List of customer relationships
        """
        company_data = self.data.get("relationships", {}).get(ticker, {})
        customers = company_data.get("customers", [])

        return [
            CustomerRelationship(
                name=c.get("name"),
                ticker=c.get("ticker"),
                category=c.get("category"),
                criticality=c.get("criticality"),
                revenue_exposure=c.get("revenue_exposure", "Unknown"),
                description=c.get("description"),
                source=c.get("source", "Curated database")
            )
            for c in customers
        ]

    def identify_bottlenecks(self, ticker: str) -> List[SupplierRelationship]:
        """Identify bottleneck suppliers for a company.

        Args:
            ticker: Stock ticker

        Returns:
            List of bottleneck suppliers (high or extreme risk)
        """
        suppliers = self.get_suppliers(ticker)
        bottlenecks = [
            s for s in suppliers
            if s.bottleneck_risk in ["extreme", "high"]
        ]

        # Sort by criticality
        criticality_order = {"critical": 0, "major": 1, "moderate": 2}
        bottlenecks.sort(key=lambda s: criticality_order.get(s.criticality, 3))

        return bottlenecks

    def analyze_as_supplier(self, ticker: str) -> BottleneckAnalysis:
        """Analyze if this company is a bottleneck supplier to others.

        Args:
            ticker: Stock ticker

        Returns:
            Bottleneck analysis showing criticality to customers
        """
        customers = self.get_customers(ticker)

        # Calculate bottleneck score based on:
        # 1. Number of customers
        # 2. Customer concentration
        # 3. Criticality to customers

        if not customers:
            return BottleneckAnalysis(
                tier=3,
                tier_name="Not identified as bottleneck",
                is_bottleneck=False,
                bottleneck_score=0.0,
                characteristics=[],
                investment_thesis="No known customer dependencies",
                customers_exposed=[]
            )

        # Check if listed in bottleneck tiers
        bottleneck_tiers = self.data.get("bottleneck_tiers", {})
        for tier_key, tier_data in bottleneck_tiers.items():
            tier_companies = tier_data.get("companies", [])
            # Check if ticker matches (case-insensitive, partial match)
            for company_str in tier_companies:
                if ticker.upper() in company_str.upper():
                    tier_num = int(tier_key.split("_")[1])
                    score = 10.0 - (tier_num * 2.5)  # tier 0 = 10.0, tier 1 = 7.5, etc.

                    return BottleneckAnalysis(
                        tier=tier_num,
                        tier_name=tier_data.get("description", ""),
                        is_bottleneck=tier_num <= 1,
                        bottleneck_score=score,
                        characteristics=tier_data.get("characteristics", []),
                        investment_thesis=tier_data.get("investment_thesis", ""),
                        customers_exposed=[c.name for c in customers if c.ticker]
                    )

        # Not in explicit bottleneck tier, but has customers
        # Calculate score based on criticality
        critical_count = sum(1 for c in customers if c.criticality == "critical")
        major_count = sum(1 for c in customers if c.criticality == "major")

        score = min(10.0, (critical_count * 3.0) + (major_count * 1.5))
        is_bottleneck = score >= 5.0
        tier = 2 if is_bottleneck else 3

        return BottleneckAnalysis(
            tier=tier,
            tier_name="Major supplier" if is_bottleneck else "Moderate supplier",
            is_bottleneck=is_bottleneck,
            bottleneck_score=score,
            characteristics=[
                f"{critical_count} critical customers",
                f"{major_count} major customers",
                f"{len(customers)} total customers"
            ],
            investment_thesis="Supplier with multiple dependencies" if is_bottleneck else "Non-critical supplier",
            customers_exposed=[c.name for c in customers if c.ticker]
        )

    def get_supply_chain_depth(self, ticker: str, depth: int = 2) -> Dict:
        """Get supply chain to specified depth.

        Args:
            ticker: Stock ticker to start from
            depth: How many levels to traverse (1 = direct suppliers, 2 = suppliers of suppliers)

        Returns:
            Nested dict of supply chain relationships
        """
        if depth <= 0:
            return {}

        result = {
            "ticker": ticker,
            "suppliers": [],
            "customers": []
        }

        # Get direct suppliers
        suppliers = self.get_suppliers(ticker)
        for supplier in suppliers:
            supplier_data = {
                "name": supplier.name,
                "ticker": supplier.ticker,
                "criticality": supplier.criticality,
                "bottleneck_risk": supplier.bottleneck_risk,
                "description": supplier.description
            }

            # Recursively get supplier's suppliers
            if depth > 1 and supplier.ticker:
                supplier_data["suppliers"] = self.get_supply_chain_depth(
                    supplier.ticker, depth - 1
                ).get("suppliers", [])

            result["suppliers"].append(supplier_data)

        # Get direct customers
        customers = self.get_customers(ticker)
        for customer in customers:
            customer_data = {
                "name": customer.name,
                "ticker": customer.ticker,
                "criticality": customer.criticality,
                "revenue_exposure": customer.revenue_exposure,
                "description": customer.description
            }
            result["customers"].append(customer_data)

        return result


# Global instance
supply_chain_kb = SupplyChainKnowledgeBase()
