"""AnalysisReport builder (Phase C).

Maps a completed analysis (`full_output` with write-time decision
intelligence) onto the AnalysisReport contract — the object that is
persisted verbatim, served verbatim, and used to generate the frontend
types. Pure function over dicts: no fetching, no LLM, no re-derivation —
every judgment value (rating, targets, sizing) is READ from where it was
computed once, never recomputed here.

Returns None (with a log line) when the output is too incomplete to build
a report; callers treat that as "no report available", never as an error.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from research_swarm.logger import logger
from research_swarm.contracts.report import (
    AnalysisReport,
    Catalyst,
    Decision,
    Direction,
    MacroContext,
    MacroTheme,
    PriceTargets,
    QAFlag,
    Rating,
    Risk,
    RiskLevel,
    RunMeta,
    ScoreComponent,
    Scores,
    Signal,
    TargetCase,
    Thesis,
    TrancheStage,
    Divergence,
)

# Mirrors QualityScoreBreakdown.weighted_average (manager/models.py) — the
# weights are recorded on the report so the formula is auditable from the
# payload itself.
# Mirrors QualityScoreBreakdown.quality_score(). Valuation and sentiment are
# deliberately absent: v4.0 reports quality and valuation as separate axes, so
# listing valuation as a "component" of quality would contradict the split.
_WEIGHTS_V3 = {
    "roic_wacc_spread": 0.35,
    "financial_health": 0.35,
    "earnings_momentum": 0.30,
}
_WEIGHTS_FALLBACK = {
    "financial_health": 0.55,
    "earnings_momentum": 0.45,
}

_RISK_LEVEL_MAP = {"low": RiskLevel.LOW, "medium": RiskLevel.MEDIUM, "high": RiskLevel.HIGH}
_DIRECTION_MAP = {
    "positive": Direction.BULLISH,
    "bullish": Direction.BULLISH,
    "negative": Direction.BEARISH,
    "bearish": Direction.BEARISH,
}


def _risk_level(value: Any, default: RiskLevel = RiskLevel.MEDIUM) -> RiskLevel:
    return _RISK_LEVEL_MAP.get(str(value or "").strip().lower(), default)


def _direction(value: Any) -> Direction:
    return _DIRECTION_MAP.get(str(value or "").strip().lower(), Direction.NEUTRAL)


def _build_scores(full_output: Dict[str, Any]) -> Scores:
    breakdown = full_output.get("moat_breakdown") or {}
    weights = _WEIGHTS_V3 if breakdown.get("roic_wacc_spread") is not None else _WEIGHTS_FALLBACK
    components = [
        ScoreComponent(name=name, score=float(breakdown[name]), weight=weight)
        for name, weight in weights.items()
        if breakdown.get(name) is not None
    ]
    from research_swarm.agents.manager.scorer import ManagerScorer

    quality = float(full_output.get("moat_score") or 0.0)
    valuation = full_output.get("normalized_valuation_score")

    return Scores(
        quality_score=quality,
        valuation_score=valuation,
        quality_tier=ManagerScorer._quality_tier(quality),
        valuation_tier=(
            ManagerScorer._valuation_tier(valuation) if valuation is not None else None
        ),
        components=components,
        technical_score=breakdown.get("technical_strength"),
        confidence=float(full_output.get("confidence") or 0.0),
    )


def _build_signals(full_output: Dict[str, Any]) -> List[Signal]:
    news = full_output.get("news_hound_output") or {}
    quant = full_output.get("quant_output") or {}
    signals: List[Signal] = []

    sentiment_score = news.get("sentiment_score")
    if sentiment_score is not None:
        signals.append(Signal(
            name="news_sentiment",
            direction=Direction.BULLISH if sentiment_score >= 6.5
            else (Direction.BEARISH if sentiment_score <= 4.0 else Direction.NEUTRAL),
            score=sentiment_score,
        ))

    est = news.get("earnings_estimates") or {}
    if est.get("net_revision_direction"):
        raw = str(est["net_revision_direction"]).lower()
        signals.append(Signal(
            name="earnings_revisions",
            direction=Direction.BULLISH if "positive" in raw
            else (Direction.BEARISH if "negative" in raw else Direction.NEUTRAL),
            evidence=f"{est.get('upward_revisions', 0)} up / {est.get('downward_revisions', 0)} down (90d)",
        ))

    consensus = news.get("analyst_consensus") or {}
    if consensus.get("consensus_rating"):
        raw = str(consensus["consensus_rating"]).lower()
        evidence = (
            f"consensus {consensus['consensus_rating']}; "
            f"{consensus.get('upgrades', 0)} up / {consensus.get('downgrades', 0)} down"
            f" / {consensus.get('new_coverage', 0)} init (90d)"
        )
        target_trend = str(consensus.get("target_trend") or "").lower()
        if target_trend and target_trend != "stable":
            evidence += f"; targets {target_trend}"
        signals.append(Signal(
            name="analyst_consensus",
            direction=Direction.BULLISH if "buy" in raw
            else (Direction.BEARISH if "sell" in raw else Direction.NEUTRAL),
            evidence=evidence,
        ))

    institutional = news.get("institutional_activity") or {}
    if institutional.get("trend"):
        raw = str(institutional["trend"]).lower()
        signals.append(Signal(
            name="institutional_flow",
            direction=Direction.BULLISH if "accumulation" in raw
            else (Direction.BEARISH if "distribution" in raw else Direction.NEUTRAL),
            evidence=f"trend {institutional['trend']}",
        ))

    insider = news.get("insider_activity") or {}
    if insider.get("insider_score") is not None:
        signals.append(Signal(
            name="insider_activity",
            direction=_direction(insider.get("insider_sentiment")),
            score=insider.get("insider_score"),
            evidence=f"{insider.get('buy_transactions', 0)} buys / {insider.get('sell_transactions', 0)} sells",
        ))

    short = news.get("short_interest") or {}
    if short.get("short_interest_pct") is not None:
        signals.append(Signal(
            name="short_interest",
            direction=_direction(short.get("short_sentiment")),
            evidence=f"{short['short_interest_pct']:.1f}% of float, squeeze risk {short.get('squeeze_risk', 'low')}",
        ))

    dark_pool = news.get("dark_pool_activity") or {}
    if dark_pool.get("avg_ats_pct") is not None:
        signals.append(Signal(
            name="dark_pool",
            direction=_direction(dark_pool.get("dark_pool_sentiment")),
            evidence=f"{dark_pool['avg_ats_pct']:.1f}% ATS (trend {dark_pool.get('trend', 'stable')})",
        ))

    technical_score = quant.get("technical_score")
    if technical_score is not None:
        entry_exit = ((quant.get("technical_indicators") or {}).get("entry_exit_signals") or {})
        signals.append(Signal(
            name="technicals",
            direction=_direction(entry_exit.get("overall_signal")),
            score=technical_score,
        ))

    return signals


def _build_targets(full_output: Dict[str, Any], di: Dict[str, Any]) -> Optional[PriceTargets]:
    manager_targets = full_output.get("price_targets") or {}
    fund_targets = (full_output.get("fundamentalist_output") or {}).get("price_targets") or {}
    current_price = di.get("current_price")
    if not current_price or not manager_targets.get("base_target"):
        return None

    def _case(prefix: str) -> Optional[TargetCase]:
        target = manager_targets.get(f"{prefix}_target")
        if target is None:
            return None
        return TargetCase(
            target=float(target),
            probability=float(manager_targets.get(f"{prefix}_probability") or 0.0),
            assumptions=str(manager_targets.get(f"{prefix}_assumptions") or ""),
        )

    bull, base, bear = _case("bull"), _case("base"), _case("bear")

    # probability-weighted EV — computed HERE, once; the UI reads it.
    weighted = [
        c.target * c.probability for c in (bull, base, bear) if c is not None
    ]
    probability_weighted_ev = round(sum(weighted), 2) if weighted else None

    methodology = str(manager_targets.get("methodology") or fund_targets.get("methodology") or "Blended")
    confidence_score = int(fund_targets.get("confidence_score") or 50)
    is_heuristic = (
        "fallback" in methodology.lower()
        or "percentage-based" in methodology.lower()
        or "heuristic" in methodology.lower()
        or confidence_score <= 25
    )

    return PriceTargets(
        current_price=float(current_price),
        fair_value_low=fund_targets.get("fair_value_low"),
        fair_value_mid=fund_targets.get("fair_value_mid"),
        fair_value_high=fund_targets.get("fair_value_high"),
        bull=bull,
        base=base,
        bear=bear,
        probability_weighted_ev=probability_weighted_ev,
        methodology=methodology,
        confidence_score=max(0, min(100, confidence_score)),
        is_heuristic=is_heuristic,
        persistence_probability=manager_targets.get("persistence_probability"),
        reversion_anchor=manager_targets.get("reversion_anchor"),
        persistence_anchor=manager_targets.get("persistence_anchor"),
        basis_note=manager_targets.get("basis_note"),
    )


def _build_macro(full_output: Dict[str, Any]) -> Optional[MacroContext]:
    """Map the resolved macro exposure onto the report contract.

    Reads what the manager already resolved at run time — nothing is
    recomputed here, so the report shows exactly the macro picture the
    synthesis was written against.
    """
    exposure = full_output.get("macro_exposure") or {}
    if not exposure:
        return None

    market = exposure.get("market") or {}
    spy = (market.get("indices") or {}).get("SPY") or {}
    vix = (market.get("risk") or {}).get("^VIX") or {}

    themes = []
    for t in exposure.get("themes") or []:
        try:
            themes.append(MacroTheme(
                name=str(t["name"]),
                summary=t.get("summary"),
                status=str(t.get("status") or "stable"),
                direction=str(t.get("direction") or "mixed"),
                transmission=str(t.get("transmission") or ""),
                why_relevant=str(t.get("why_relevant") or ""),
                relevance=str(t.get("relevance") or "moderate"),
                confidence=str(t.get("confidence") or "low"),
                evidence=t.get("evidence"),
                company_impact=t.get("company_impact"),
                materiality=t.get("materiality"),
                already_visible=t.get("already_visible"),
            ))
        except Exception:
            continue

    return MacroContext(
        regime=market.get("regime"),
        regime_rationale=market.get("regime_rationale"),
        backdrop=exposure.get("backdrop"),
        themes=themes,
        themes_considered=int(exposure.get("themes_considered") or 0),
        market_return_1m=spy.get("return_1m"),
        market_return_3m=spy.get("return_3m"),
        vix_level=vix.get("last"),
        yield_curve_slope=market.get("yield_curve_slope"),
        sector_leaders=list(market.get("sector_leaders") or []),
        sector_laggards=list(market.get("sector_laggards") or []),
        as_of=market.get("as_of"),
    )


def _trigger_text(trigger: Any) -> str:
    if isinstance(trigger, dict):
        metric = trigger.get("metric", "")
        threshold = trigger.get("threshold", "")
        action = trigger.get("action", "")
        return f"{metric}: {threshold} → {action}".strip(" :→")
    return str(trigger)


def _build_decision(full_output: Dict[str, Any], di: Dict[str, Any]) -> Decision:
    rating_raw = str(full_output.get("rating") or di.get("rating") or "HOLD").upper()
    try:
        rating = Rating(rating_raw)
    except ValueError:
        rating = Rating.HOLD

    moat_score = full_output.get("moat_score")
    recommendation = full_output.get("recommendation")
    valuation_axis = full_output.get("normalized_valuation_score")
    # State BOTH axes: the whole point of the v4.0 split is that the reader can
    # see whether a HOLD is "mediocre business" or "good business, wrong price".
    if moat_score is not None and valuation_axis is not None:
        rating_basis = (
            f"Quality {moat_score:.1f}/10 x Valuation {valuation_axis:.1f}/10 → {rating.value}"
        )
    elif moat_score is not None:
        rating_basis = f"Quality score {moat_score:.1f}/10 → {rating.value}"
    else:
        rating_basis = f"Rating {rating.value}"
    if recommendation and str(recommendation).upper() != rating.value:
        rating_basis += f" (LLM recommendation: {recommendation}; write-time reconciliation applied)"

    conviction_position = di.get("conviction_position") or {}
    initiation = di.get("initiation_decision") or {}
    strategy = di.get("recommended_strategy") or {}
    tranche = di.get("tranche_plan") or {}

    entry_zone = initiation.get("required_entry_zone") or []
    stop_loss = (strategy.get("exit") or {}).get("stop_loss")

    tranche_stages: List[TrancheStage] = []
    starter_pct = initiation.get("starter_allocation_percent")
    if starter_pct is not None:
        tranche_stages.append(TrancheStage(
            stage=1,
            allocation_pct=float(starter_pct),
            trigger="Initiation: price inside required entry zone with quality gates met",
        ))

    return Decision(
        rating=rating,
        rating_basis=rating_basis,
        risk_level=_risk_level(full_output.get("risk_level") or di.get("risk_level")),
        conviction=str(conviction_position.get("conviction_level") or "Medium"),
        is_watchlist_candidate=bool(full_output.get("is_watchlist_candidate")),
        entry_zone_low=entry_zone[0] if len(entry_zone) > 0 else None,
        entry_zone_high=entry_zone[1] if len(entry_zone) > 1 else None,
        stop_loss=stop_loss,
        starter_allocation_pct=starter_pct,
        max_allocation_pct=conviction_position.get("max_pct"),
        tranche_plan=tranche_stages,
        upgrade_triggers=[_trigger_text(t) for t in (full_output.get("upgrade_triggers") or [])],
        downgrade_triggers=[_trigger_text(t) for t in (full_output.get("downgrade_triggers") or [])],
        thesis_break_conditions=[str(c) for c in (tranche.get("thesis_break_conditions") or [])],
    )


def build_analysis_report(
    full_output: Dict[str, Any],
    analysis_id: str,
    created_at: Optional[datetime] = None,
    tokens_used: int = 0,
    cost_usd: float = 0.0,
    duration_seconds: float = 0.0,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    company_name: Optional[str] = None,
) -> Optional[AnalysisReport]:
    """Assemble the persisted AnalysisReport from a completed analysis."""
    try:
        di = full_output.get("decision_intelligence") or {}
        fund = full_output.get("fundamentalist_output") or {}
        thesis_struct = full_output.get("investment_thesis") or {}
        peer = fund.get("peer_comparison") or {}

        thesis = Thesis(
            headline=str(thesis_struct.get("recommendation_summary") or ""),
            narrative=str(full_output.get("synthesis_narrative") or ""),
            key_insights=[str(i) for i in (full_output.get("key_insights") or [])],
            bull_case="\n".join(str(h) for h in (thesis_struct.get("investment_highlights") or [])),
            bear_case="\n".join(str(r) for r in (thesis_struct.get("key_risks") or [])),
            what_would_change_our_mind=[
                _trigger_text(t) for t in (full_output.get("downgrade_triggers") or [])
            ],
        )

        risks = []
        for entry in full_output.get("structured_risks") or []:
            if not isinstance(entry, dict) or not entry.get("risk"):
                continue
            risks.append(Risk(
                description=str(entry["risk"]),
                severity=_risk_level(entry.get("severity")),
                likelihood=_risk_level(entry.get("likelihood")),
                mitigation=entry.get("mitigation"),
            ))

        catalysts = []
        for entry in full_output.get("strategic_catalysts") or []:
            if isinstance(entry, dict) and entry.get("title"):
                catalysts.append(Catalyst(
                    description=f"{entry['title']}: {entry.get('description', '')}".strip(": "),
                    expected_date=entry.get("timeframe"),
                ))
        upcoming = ((full_output.get("news_hound_output") or {}).get("upcoming_catalysts") or {})
        for entry in upcoming.get("catalysts") or []:
            if isinstance(entry, dict) and entry.get("description"):
                catalysts.append(Catalyst(
                    description=str(entry["description"]),
                    expected_date=entry.get("event_date"),
                    direction=_direction(entry.get("impact_direction")),
                ))

        overlay = di.get("divergence_overlay") or {}
        divergence = None
        if overlay:
            divergence = Divergence(
                detected=str(overlay.get("divergence_phase") or "").lower() not in ("", "none", "weak"),
                kind=overlay.get("divergence_type"),
                score=overlay.get("divergence_score"),
                summary=(full_output.get("signal_breakdown") or {}).get("divergence_explanation"),
            )

        # Flags arrive as plain strings (decision intelligence) or dicts with a
        # human-readable "message" (manager calibration flags) — never render a
        # raw dict dump to the reader.
        qa_flags = []
        for flag in (di.get("report_qa_flags") or full_output.get("report_qa_flags") or []):
            if isinstance(flag, dict):
                qa_flags.append(QAFlag(
                    code=str(flag.get("type") or "qa"),
                    message=str(flag.get("message") or flag.get("display_label") or flag.get("type") or "QA review warranted"),
                ))
            else:
                qa_flags.append(QAFlag(code="qa", message=str(flag)))

        targets = _build_targets(full_output, di)
        decision = _build_decision(full_output, di)
        macro = _build_macro(full_output)

        # Honesty check: a bullish rating whose base target sits meaningfully
        # below the current price (or the inverse for bearish ratings) is
        # surfaced to the reader instead of silently rendered.
        if targets and targets.base and targets.current_price and decision:
            gap_pct = (targets.base.target - targets.current_price) / targets.current_price * 100
            rating = str(decision.rating.value if hasattr(decision.rating, "value") else decision.rating).upper()
            if rating in ("BUY", "STRONG BUY") and gap_pct < -5:
                qa_flags.append(QAFlag(
                    code="rating_target_divergence",
                    message=(
                        f"Rating is {rating} (quality-driven) but the base target "
                        f"${targets.base.target:,.2f} sits {abs(gap_pct):.0f}% below the "
                        f"current price ${targets.current_price:,.2f}"
                    ),
                ))
            elif rating in ("SELL", "STRONG SELL") and gap_pct > 5:
                qa_flags.append(QAFlag(
                    code="rating_target_divergence",
                    message=(
                        f"Rating is {rating} but the base target ${targets.base.target:,.2f} "
                        f"sits {gap_pct:.0f}% above the current price ${targets.current_price:,.2f}"
                    ),
                ))
            elif rating == "HOLD" and abs(gap_pct) > 10:
                qa_flags.append(QAFlag(
                    code="rating_target_divergence",
                    message=(
                        f"Rating is HOLD but the base target ${targets.base.target:,.2f} sits "
                        f"{abs(gap_pct):.0f}% {'below' if gap_pct < 0 else 'above'} the "
                        f"current price ${targets.current_price:,.2f}"
                    ),
                ))

        return AnalysisReport(
            ticker=str(full_output.get("ticker") or "").upper(),
            company_name=company_name or fund.get("company_name"),
            sector=sector or peer.get("sector"),
            industry=industry or peer.get("industry"),
            as_of=created_at or datetime.now(),
            scores=_build_scores(full_output),
            signals=_build_signals(full_output),
            divergence=divergence,
            targets=targets,
            thesis=thesis,
            risks=risks,
            catalysts=catalysts,
            decision=decision,
            macro=macro,
            meta=RunMeta(
                analysis_id=analysis_id,
                created_at=created_at or datetime.now(),
                models_used={
                    "news_interpretation": "claude-sonnet-4-6",
                    "synthesis_thesis": "claude-sonnet-5",
                    "extraction": "claude-haiku-4-5",
                },
                tokens_total=tokens_used,
                cost_usd=cost_usd,
                duration_seconds=duration_seconds,
                qa_flags=qa_flags,
            ),
        )
    except Exception:
        logger.exception("AnalysisReport build failed — report omitted for this result")
        return None
