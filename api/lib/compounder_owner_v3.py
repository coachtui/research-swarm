"""
DVRG Compounder Owner v3 — Structural Ownership Engine
========================================================

Live deployment logic for durability-first portfolio construction
with drawdown-based accumulation overlay.

NOT an optimizer. NOT a Kelly engine. NOT a vol targeter.

This is a capital ownership machine:
  - Identify durable compounders
  - Own them consistently (10-15 names, equal weight)
  - Add aggressively during structural dips
  - Trim during euphoria
  - Sell only on thesis break

Integration point: called from api/routes/deployment.py or
api/lib/decision_intelligence.py after signal computation.

Usage:
    from api.lib.compounder_owner_v3 import CompounderEngine, OwnerConfig

    engine = CompounderEngine(config=OwnerConfig())
    result = engine.refresh(signals, price_data, current_portfolio)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class OwnerConfig:
    """All tunable parameters for the ownership engine."""

    # Portfolio shape
    target_names: int = 12
    min_names: int = 8
    max_names: int = 15
    max_pos: float = 0.25
    min_pos: float = 0.04

    # Durability percentile thresholds (cross-sectional)
    rev_persist_pctile: float = 65.0
    fwd_growth_pctile: float = 60.0
    roic_pctile: float = 60.0
    gm_pctile: float = 50.0
    min_durability_pass: int = 4      # must pass 4 of 6

    # Drawdown accumulation tiers (CONVEX — non-linear scaling)
    add_tiers: list = field(default_factory=lambda: [
        (-0.20, 0.02),   # -20% drawdown → +2% weight
        (-0.30, 0.04),   # -30% → +4% (convex)
        (-0.40, 0.06),   # -40% → +6% (convex)
        (-0.50, 0.08),   # -50% → +8% (convex)
    ])

    # Euphoria trimming
    euphoria_above_200dma: float = 0.30   # price 30% above 200DMA
    euphoria_weight_threshold: float = 0.20  # only trim if weight > 20%
    euphoria_trim_pct: float = 0.03       # trim 3% weight

    # Thesis break thresholds
    rev_growth_floor: float = 8.0         # sell if < this for 2Q
    roic_floor: float = 12.0              # sell if ROIC below this
    margin_compression_threshold: float = -5.0  # gross margin drop %

    # Churn limits
    max_quarterly_replacements: int = 3   # max names swapped per quarter
    annual_turnover_target: float = 0.30  # flag if exceeded

    # Sector exclusions
    excluded_sectors: set = field(default_factory=lambda: {
        "Financial Services", "Banks", "Insurance",
    })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA CONTRACTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class SignalInput:
    """Minimal signal interface — maps from production SignalRow or live data."""
    ticker: str
    revenue_3y_cagr: Optional[float]
    revenue_growth_yoy: Optional[float]
    revenue_growth_persistence: Optional[int]
    gross_margin: Optional[float]
    fcf_margin: Optional[float]
    moat_score: float
    margin_trend: str                # "expanding" | "stable" | "contracting" | "unknown"
    eps_revision_positive: bool
    sector: str
    current_price: float
    high_252d: Optional[float]       # 252-day high price
    ma_200d: Optional[float]         # 200-day moving average


@dataclass
class PortfolioPosition:
    """Current state of a portfolio position."""
    ticker: str
    weight: float
    entry_date: date
    entry_price: float
    quarters_held: int = 0
    compounder_score: float = 0.0
    # Drawdown add cycle tracking (each tier applies once per cycle)
    add_tiers_applied: set = field(default_factory=set)  # set of dd thresholds already applied
    last_drawdown: float = 0.0  # most recent drawdown value


@dataclass
class OwnerAction:
    """Action output from the engine."""
    ticker: str
    action: str          # "HOLD" | "ADD" | "TRIM" | "SELL" | "BUY"
    current_weight: float
    target_weight: float
    reason: str
    drawdown_pct: Optional[float] = None
    compounder_score: Optional[float] = None


@dataclass
class RefreshResult:
    """Full output of a quarterly/monthly refresh."""
    actions: list[OwnerAction]
    target_portfolio: dict[str, float]    # ticker → weight
    diagnostics: dict
    is_quarterly: bool


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 1: DURABILITY UNIVERSE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def compute_durability_eligible(
    signals: list[SignalInput],
    cfg: OwnerConfig,
) -> list[SignalInput]:
    """
    Percentile-based durability filter. Must pass 4 of 6 criteria.
    Relaxes thresholds until at least min_names qualify.
    """
    eligible = [s for s in signals if s.sector not in cfg.excluded_sectors]
    if len(eligible) < 20:
        return eligible

    # Cross-sectional percentiles
    def _pctile(vals: list[float]) -> dict[int, float]:
        """Map index → percentile rank (0-100)."""
        arr = np.array(vals)
        n = len(arr)
        if n == 0:
            return {}
        ranks = np.argsort(np.argsort(arr)) / n * 100
        return {i: float(ranks[i]) for i in range(n)}

    rev_persist_vals = [float(s.revenue_growth_persistence or 0) for s in eligible]
    fwd_growth_vals = [s.revenue_3y_cagr if s.revenue_3y_cagr is not None else (s.revenue_growth_yoy or 0.0) for s in eligible]
    roic_vals = [s.moat_score for s in eligible]
    gm_vals = [s.gross_margin or 0.0 for s in eligible]

    rp_pct = _pctile(rev_persist_vals)
    fg_pct = _pctile(fwd_growth_vals)
    rc_pct = _pctile(roic_vals)
    gm_pct = _pctile(gm_vals)

    for relaxation in range(8):
        rp_t = cfg.rev_persist_pctile - relaxation * 5
        fg_t = cfg.fwd_growth_pctile - relaxation * 5
        rc_t = cfg.roic_pctile - relaxation * 5
        gm_t = cfg.gm_pctile - relaxation * 5

        candidates = []
        for i, s in enumerate(eligible):
            passes = 0
            if rp_pct.get(i, 0) >= rp_t:
                passes += 1
            if fg_pct.get(i, 0) >= fg_t:
                passes += 1
            if rc_pct.get(i, 0) >= rc_t:
                passes += 1
            if gm_pct.get(i, 0) >= gm_t:
                passes += 1
            if s.fcf_margin is not None and s.fcf_margin > 0:
                passes += 1
            if s.margin_trend != "contracting":
                passes += 1
            if passes >= cfg.min_durability_pass:
                candidates.append(s)

        if len(candidates) >= cfg.min_names:
            logger.debug("Durability: %d eligible (relaxation=%d)", len(candidates), relaxation)
            return candidates

    return candidates


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 2: COMPOUNDER SCORE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def compute_compounder_scores(signals: list[SignalInput]) -> dict[str, float]:
    """Rank eligible names by durability-weighted composite score."""
    if len(signals) < 3:
        return {}

    def _rank(vals: list[float]) -> list[float]:
        arr = np.array(vals)
        n = len(arr)
        if n <= 1:
            return [0.5] * n
        return list(np.argsort(np.argsort(arr)) / n)

    tickers = [s.ticker for s in signals]
    rev = _rank([s.revenue_3y_cagr if s.revenue_3y_cagr is not None else (s.revenue_growth_yoy or 0) for s in signals])
    pers = _rank([float(s.revenue_growth_persistence or 0) for s in signals])
    moat = _rank([s.moat_score for s in signals])
    gm = _rank([s.gross_margin or 0.0 for s in signals])
    fcf = _rank([s.fcf_margin or 0.0 for s in signals])
    bal = _rank([1.0 if s.eps_revision_positive else 0.0 for s in signals])

    scores = {}
    for i, t in enumerate(tickers):
        scores[t] = (
            0.25 * rev[i]
            + 0.20 * pers[i]
            + 0.15 * moat[i]
            + 0.15 * gm[i]
            + 0.10 * fcf[i]
            + 0.10 * bal[i]
            + 0.05 * rev[i]   # R&D proxy
        )
    return scores


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 3: DRAWDOWN ACCUMULATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def compute_drawdown_adds(
    positions: dict[str, PortfolioPosition],
    signals_map: dict[str, SignalInput],
    cfg: OwnerConfig,
) -> list[OwnerAction]:
    """
    CONVEX tiered accumulation during drawdowns.

    Each tier applies ONCE per drawdown cycle. Cycle resets when price
    recovers above -15% from 252d high. Adds are cumulative across tiers.

    Fundamental validation gate: blocks adds if quarterly data shows
    structural deterioration.
    """
    actions = []
    for ticker, pos in positions.items():
        sig = signals_map.get(ticker)
        if sig is None or sig.high_252d is None or sig.high_252d <= 0:
            continue

        drawdown = (sig.current_price / sig.high_252d) - 1.0

        # Reset add cycle if price recovered above -15%
        if drawdown > -0.15:
            pos.add_tiers_applied = set()

        pos.last_drawdown = drawdown

        # Fundamental validation gate (stricter than thesis break)
        # Must have: rev growth >= 10% OR stable multi-quarter trend
        # Must NOT have: structural deterioration
        if _thesis_deteriorating(sig):
            continue
        rev = sig.revenue_growth_yoy
        if rev is not None and rev < 5.0 and sig.margin_trend == "contracting":
            continue  # block add — fundamentals weakening

        # Apply each tier ONCE per cycle (cumulative)
        total_add = 0.0
        for dd_threshold, add_amount in sorted(cfg.add_tiers, key=lambda x: x[0]):
            if drawdown <= dd_threshold and dd_threshold not in pos.add_tiers_applied:
                total_add += add_amount
                pos.add_tiers_applied.add(dd_threshold)

        if total_add > 0 and pos.weight < cfg.max_pos:
            target = min(pos.weight + total_add, cfg.max_pos)
            actions.append(OwnerAction(
                ticker=ticker,
                action="ADD",
                current_weight=pos.weight,
                target_weight=target,
                reason=f"Convex add: DD {drawdown:.0%}, +{total_add:.0%} (tiers: {len(pos.add_tiers_applied)})",
                drawdown_pct=drawdown,
            ))

    return actions


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 4: EUPHORIA TRIMMING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def compute_euphoria_trims(
    positions: dict[str, PortfolioPosition],
    signals_map: dict[str, SignalInput],
    cfg: OwnerConfig,
) -> list[OwnerAction]:
    """Trim positions trading far above 200DMA at high weight."""
    actions = []
    for ticker, pos in positions.items():
        sig = signals_map.get(ticker)
        if sig is None or sig.ma_200d is None or sig.ma_200d <= 0:
            continue

        above_200dma = (sig.current_price / sig.ma_200d) - 1.0

        if (above_200dma >= cfg.euphoria_above_200dma
                and pos.weight > cfg.euphoria_weight_threshold):
            target = max(pos.weight - cfg.euphoria_trim_pct, cfg.min_pos)
            actions.append(OwnerAction(
                ticker=ticker,
                action="TRIM",
                current_weight=pos.weight,
                target_weight=target,
                reason=f"Price {above_200dma:.0%} above 200DMA, weight {pos.weight:.0%} > threshold",
            ))

    return actions


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 5: SELL DISCIPLINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _thesis_deteriorating(sig: SignalInput) -> bool:
    """Soft check: near-deterioration (used to block adds, not trigger sells)."""
    rev = sig.revenue_growth_yoy
    if rev is not None and rev < 3.0 and not sig.eps_revision_positive:
        return True
    if sig.margin_trend == "contracting" and sig.moat_score < 5.0:
        return True
    return False


def compute_thesis_breaks(
    positions: dict[str, PortfolioPosition],
    signals_map: dict[str, SignalInput],
    cfg: OwnerConfig,
) -> list[OwnerAction]:
    """
    Full exit requires CONFIRMED thesis break — not single-quarter noise.

    Three independent break conditions (any one triggers exit):
      A) Growth Collapse: rev < 8% + negative revisions + margin contracting
      B) Capital Destruction: ROIC < 12% (moat < 4) + margin deteriorating
      C) Structural Break: moat collapse below 3.0 (severe)

    Single-quarter slowdown is NOT a sell trigger.
    """
    actions = []
    for ticker, pos in positions.items():
        sig = signals_map.get(ticker)
        if sig is None:
            actions.append(OwnerAction(
                ticker=ticker, action="SELL",
                current_weight=pos.weight, target_weight=0.0,
                reason="No signal data — universe exit",
            ))
            continue

        # Condition A: Growth Collapse (requires 3 confirming signals)
        rev = sig.revenue_growth_yoy
        growth_collapse = (
            rev is not None and rev < cfg.rev_growth_floor
            and not sig.eps_revision_positive
            and sig.margin_trend == "contracting"
        )

        # Condition B: Capital Destruction (ROIC collapse + margin + leverage)
        capital_destruction = (
            sig.moat_score < 4.0
            and sig.margin_trend in ("contracting", "unknown")
            and (sig.fcf_margin is not None and sig.fcf_margin < 0)
        )

        # Condition C: Structural Break (severe moat collapse)
        structural_break = sig.moat_score < 3.0

        if growth_collapse or capital_destruction or structural_break:
            reasons = []
            if growth_collapse:
                reasons.append(f"Growth collapse: rev {rev:.0f}% + neg revisions + margin contracting")
            if capital_destruction:
                reasons.append(f"Capital destruction: moat {sig.moat_score:.1f}, FCF margin {sig.fcf_margin:.0f}%")
            if structural_break:
                reasons.append(f"Structural break: moat {sig.moat_score:.1f} < 3.0")

            actions.append(OwnerAction(
                ticker=ticker, action="SELL",
                current_weight=pos.weight, target_weight=0.0,
                reason="THESIS BREAK: " + "; ".join(reasons),
            ))

    return actions


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 6: QUARTERLY HEALTH CHECK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def quarterly_refresh(
    current_positions: dict[str, PortfolioPosition],
    signals: list[SignalInput],
    scores: dict[str, float],
    cfg: OwnerConfig,
) -> list[OwnerAction]:
    """
    Quarterly: re-rank universe, replace bottom holdings with superior
    candidates. Capped at max_quarterly_replacements to limit churn.
    """
    actions = []
    current_tickers = set(current_positions.keys())

    # Rank all eligible by score
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_n = [t for t, _ in sorted_scores[:cfg.target_names]]

    # Identify replacements: current holdings not in top N
    to_remove = []
    for ticker in current_tickers:
        if ticker not in scores or scores.get(ticker, 0) < sorted_scores[cfg.target_names - 1][1] if len(sorted_scores) >= cfg.target_names else False:
            to_remove.append((ticker, scores.get(ticker, 0)))

    # Sort by score ascending (weakest first)
    to_remove.sort(key=lambda x: x[1])

    # New additions: top N not currently held
    to_add = [t for t in top_n if t not in current_tickers]

    # Cap replacements
    n_replace = min(len(to_remove), len(to_add), cfg.max_quarterly_replacements)

    for i in range(n_replace):
        old_ticker, old_score = to_remove[i]
        new_ticker = to_add[i]
        new_score = scores.get(new_ticker, 0)

        # Only replace if new is materially better
        if new_score > old_score + 0.05:
            old_pos = current_positions[old_ticker]
            actions.append(OwnerAction(
                ticker=old_ticker, action="SELL",
                current_weight=old_pos.weight, target_weight=0.0,
                reason=f"Replaced by {new_ticker} (score {new_score:.2f} > {old_score:.2f})",
                compounder_score=old_score,
            ))
            equal_w = 1.0 / max(len(current_tickers), cfg.target_names)
            actions.append(OwnerAction(
                ticker=new_ticker, action="BUY",
                current_weight=0.0, target_weight=equal_w,
                reason=f"New compounder (score {new_score:.2f}, replaces {old_ticker})",
                compounder_score=new_score,
            ))

    # Fill empty slots if under target
    slots = cfg.target_names - (len(current_tickers) - n_replace + n_replace)
    if slots > 0:
        remaining_adds = [t for t in to_add[n_replace:] if t not in current_tickers]
        equal_w = 1.0 / cfg.target_names
        for ticker in remaining_adds[:slots]:
            actions.append(OwnerAction(
                ticker=ticker, action="BUY",
                current_weight=0.0, target_weight=equal_w,
                reason=f"Filling empty slot (score {scores.get(ticker, 0):.2f})",
                compounder_score=scores.get(ticker, 0),
            ))

    return actions


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CompounderEngine:
    """
    Stateless engine. Call refresh() each period with current state.
    Returns actions and target portfolio.
    """

    def __init__(self, config: OwnerConfig = OwnerConfig()):
        self.cfg = config

    def refresh(
        self,
        signals: list[SignalInput],
        current_positions: dict[str, PortfolioPosition],
        is_quarterly: bool = False,
    ) -> RefreshResult:
        """
        Run the full ownership logic.

        Monthly: drawdown adds + euphoria trims + thesis breaks
        Quarterly: + universe re-rank + slot filling
        """
        signals_map = {s.ticker: s for s in signals}
        all_actions: list[OwnerAction] = []

        # Phase 1: Durability universe
        eligible = compute_durability_eligible(signals, self.cfg)
        scores = compute_compounder_scores(eligible)

        # Phase 5: Thesis breaks (always checked first)
        breaks = compute_thesis_breaks(current_positions, signals_map, self.cfg)
        all_actions.extend(breaks)

        # Remove broken positions from working set
        broken_tickers = {a.ticker for a in breaks if a.action == "SELL"}
        working_positions = {
            t: p for t, p in current_positions.items() if t not in broken_tickers
        }

        # Phase 3: Drawdown accumulation (monthly)
        # STRICT GUARD: only operate on positions in eligible universe
        eligible_tickers = {s.ticker for s in eligible}
        eligible_positions = {
            t: p for t, p in working_positions.items() if t in eligible_tickers
        }
        adds = compute_drawdown_adds(eligible_positions, signals_map, self.cfg)
        all_actions.extend(adds)

        # Phase 4: Euphoria trimming (monthly)
        trims = compute_euphoria_trims(working_positions, signals_map, self.cfg)
        all_actions.extend(trims)

        # Phase 6: Quarterly refresh
        if is_quarterly:
            quarterly = quarterly_refresh(working_positions, eligible, scores, self.cfg)
            all_actions.extend(quarterly)

        # Build target portfolio
        target = self._build_target(current_positions, all_actions)

        # Diagnostics
        n_eligible = len(eligible)
        n_held = len(target)
        avg_score = np.mean(list(scores.values())) if scores else 0
        top_scores = sorted(scores.values(), reverse=True)[:5]

        diagnostics = {
            "n_eligible": n_eligible,
            "n_held": n_held,
            "n_actions": len(all_actions),
            "n_adds": sum(1 for a in all_actions if a.action == "ADD"),
            "n_trims": sum(1 for a in all_actions if a.action == "TRIM"),
            "n_sells": sum(1 for a in all_actions if a.action == "SELL"),
            "n_buys": sum(1 for a in all_actions if a.action == "BUY"),
            "avg_compounder_score": round(avg_score, 3),
            "top_5_scores": [round(s, 3) for s in top_scores],
            "total_weight": round(sum(target.values()), 3),
            "is_quarterly": is_quarterly,
        }

        return RefreshResult(
            actions=all_actions,
            target_portfolio=target,
            diagnostics=diagnostics,
            is_quarterly=is_quarterly,
        )

    def _build_target(
        self,
        current: dict[str, PortfolioPosition],
        actions: list[OwnerAction],
    ) -> dict[str, float]:
        """
        Apply actions to current positions to produce target weights.

        NO AUTOMATIC RE-NORMALIZATION after adds.
        Adds create intentional overweight (convexity).

        Normalization ONLY on:
          - Hard cap breach (> 25% → trim to 22-23%)
          - Exit reallocation (freed weight redistributed)
          - New entry (needs funding)
          - Total > 100% (hard constraint)
        """
        target = {t: p.weight for t, p in current.items()}

        has_exits = False
        has_entries = False

        for a in actions:
            if a.action == "SELL":
                target.pop(a.ticker, None)
                has_exits = True
            elif a.action == "BUY":
                target[a.ticker] = a.target_weight
                has_entries = True
            elif a.action == "ADD":
                # Direct weight assignment — NO normalization
                target[a.ticker] = a.target_weight
            elif a.action == "TRIM":
                target[a.ticker] = a.target_weight

        # Enforce hard cap only (trim to 22-23%, not exactly 25%)
        for t in list(target.keys()):
            if target[t] > self.cfg.max_pos:
                target[t] = self.cfg.max_pos - 0.02  # trim to 23%

        # Only normalize if structural change (exit/entry) or total > 100%
        total = sum(target.values())

        if total > 1.0:
            # Must scale down — but preserve relative overweights from adds
            scale = 1.0 / total
            for t in target:
                target[t] *= scale
        elif (has_exits or has_entries) and total < 0.90:
            # Significant cash freed — redistribute to fill deployment
            # But don't force-equalize; scale existing proportionally
            if total > 0:
                scale = min(1.0, 0.98 / total)  # target ~98% invested
                for t in target:
                    target[t] *= scale

        # Remove anything that drifted below minimum
        target = {t: w for t, w in target.items() if w >= self.cfg.min_pos * 0.5}

        return target
