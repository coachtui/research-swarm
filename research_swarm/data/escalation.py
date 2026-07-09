"""Escalation scoring — decides which quant-tier tickers earn paid swarm analysis.

Pure functions only: no I/O, no DB, no LLM. The weekly batch builds
EscalationCandidate objects from screener output + prior WeeklySignal rows and
feeds them here. Spec: docs/superpowers/specs/2026-07-08-tiered-batch-design.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Trigger weights (spec-fixed; tune only with escalationReasons audit data)
W_PRIOR_BUY = 3.0
W_POST_EARNINGS = 2.5
W_OUTLOOK_SECTOR = 2.0
W_DIVERGENCE = 2.0
W_WATCHLIST = 1.5

POST_EARNINGS_MAX_DAYS = 5
DIVERGENCE_MIN_DELTA = 3.0
DEFAULT_THRESHOLD = 2.0
DEFAULT_CAP = 5


@dataclass
class EscalationCandidate:
    ticker: str
    screener_score: float
    sector: Optional[str] = None
    prior_screener_score: Optional[float] = None
    prior_verdict: Optional[str] = None
    days_since_earnings: Optional[int] = None
    on_watchlist: bool = False
    has_fresh_report: bool = False


@dataclass
class EscalationContext:
    favored_sectors: frozenset = field(default_factory=frozenset)


@dataclass
class EscalationDecision:
    ticker: str
    score: float
    reasons: List[str]
    action: str  # "swarm" | "reuse" | "hold"


def escalation_score(
    candidate: EscalationCandidate, context: EscalationContext
) -> Tuple[float, List[str]]:
    """Weighted trigger score and the reasons that fired, in fixed order."""
    score = 0.0
    reasons: List[str] = []

    if candidate.prior_verdict == "buy":
        score += W_PRIOR_BUY
        reasons.append("prior_buy")

    if (
        candidate.days_since_earnings is not None
        and candidate.days_since_earnings <= POST_EARNINGS_MAX_DAYS
    ):
        score += W_POST_EARNINGS
        reasons.append("post_earnings")

    if candidate.sector and candidate.sector in context.favored_sectors:
        score += W_OUTLOOK_SECTOR
        reasons.append("outlook_sector")

    if (
        candidate.prior_screener_score is not None
        and abs(candidate.screener_score - candidate.prior_screener_score)
        >= DIVERGENCE_MIN_DELTA
    ):
        score += W_DIVERGENCE
        reasons.append("score_divergence")

    if candidate.on_watchlist:
        score += W_WATCHLIST
        reasons.append("watchlist")

    return score, reasons


def select_escalations(
    candidates: List[EscalationCandidate],
    context: EscalationContext,
    cap: int = DEFAULT_CAP,
    threshold: float = DEFAULT_THRESHOLD,
) -> List[EscalationDecision]:
    """One decision per candidate (input order preserved).

    Qualified (score >= threshold) candidates with a fresh user report are
    marked "reuse" — free, no cap slot. The remaining qualified candidates
    rank by (score desc, screener_score desc, ticker asc); the top `cap`
    become "swarm". Everything else is "hold".
    """
    by_ticker = {c.ticker: c for c in candidates}
    decisions = []
    for c in candidates:
        score, reasons = escalation_score(c, context)
        action = "hold"
        if score >= threshold and c.has_fresh_report:
            action = "reuse"
        decisions.append(EscalationDecision(c.ticker, score, reasons, action))

    contenders = [d for d in decisions if d.action == "hold" and d.score >= threshold]
    contenders.sort(
        key=lambda d: (-d.score, -by_ticker[d.ticker].screener_score, d.ticker)
    )
    for d in contenders[:cap]:
        d.action = "swarm"

    return decisions
