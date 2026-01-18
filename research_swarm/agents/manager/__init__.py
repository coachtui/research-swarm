"""
Manager Agent - Orchestrates all research agents and calculates moat scores.

The Manager agent is the top-level coordinator that:
1. Calls Fundamentalist, News Hound, and Quant agents
2. Synthesizes their findings into unified analysis
3. Calculates moat scores using weighted formula
4. Generates investment theses
5. Identifies watchlist candidates (moat_score >= 8)
"""
from .graph import analyze_swarm
from .models import ManagerOutput, MoatScoreBreakdown

__all__ = [
    "analyze_swarm",
    "ManagerOutput",
    "MoatScoreBreakdown",
]
