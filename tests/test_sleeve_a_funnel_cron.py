# tests/test_sleeve_a_funnel_cron.py
"""Funnel cron: gates, budget discipline, shadow orders, journal."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import inngest_app.functions.sleeve_a_funnel as saf

NOW = datetime(2026, 7, 13, 16, 0, tzinfo=timezone.utc)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_module_imports_without_inngest_sdk():
    assert hasattr(saf, "sleeve_a_funnel")   # None without SDK is fine


def test_stale_outlook_skips_pass_and_journals():
    db = MagicMock()
    stale = MagicMock(runDate=NOW - timedelta(days=10), regime="neutral")
    with patch.object(saf, "get_latest_outlook", new=AsyncMock(return_value=stale)), \
         patch.object(saf, "write_report", new=AsyncMock()) as report:
        out = _run(saf._load_and_gate_outlook(db, now=NOW))
    assert out is None
    kwargs = report.call_args.kwargs if report.call_args.kwargs else {}
    args = report.call_args.args
    assert "engine_failure" in (list(args) + list(kwargs.values()))


def test_entry_requires_full_run_and_respects_budget():
    """The budget gate still owns the handshake: an exhausted weekly full-run
    budget defers the memo's entry rather than placing it un-diligenced."""
    db = MagicMock()
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "skip",
                                                  "reason": "budget_exhausted"})), \
         patch.object(saf, "write_report", new=AsyncMock()) as report:
        placed = _run(saf._handshake_and_enter(
            db, client, planned_entries=[_planned("AEHR")],
            screen_by_symbol={"AEHR": _memo_screen("AEHR")},
            run_date=NOW, sleeve_equity=70_000.0, deployable=49_000.0,
            cash_available=49_000.0, holdings=[], sector_by_symbol={},
            other_sleeve_sector_notional={}, allow_buys=True, step=None,
        ))
    assert placed == []
    client.submit_limit_buy.assert_not_called()
    types = [c.args[0] if c.args else c.kwargs.get("report_type")
             for c in report.call_args_list]
    assert "entry_deferred" in types


def test_full_pass_places_shadow_order_with_deterministic_id():
    """The deterministic client_order_id (the duplicate-order guard) survives
    the memo rewiring; a HOLD verdict is not a veto, so the order places."""
    db = MagicMock()
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    signals = {"verdict": "hold", "fairValue": 26.0, "insiderScore": 7.0,
               "darkPoolScore": None, "sentimentScore": 6.0}
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse", "signals": signals})), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "write_report", new=AsyncMock()):
        placed = _run(saf._handshake_and_enter(
            db, client, planned_entries=[_planned("AEHR", entry_style="at_market")],
            screen_by_symbol={"AEHR": _memo_screen("AEHR", price=20.0, sma20=19.0,
                                                   atr=1.0, atr_pct=0.05,
                                                   liquidity_adv_usd=5e6)},
            run_date=NOW, sleeve_equity=70_000.0, deployable=49_000.0,
            cash_available=49_000.0, holdings=[], sector_by_symbol={},
            other_sleeve_sector_notional={}, allow_buys=True, step=None,
        ))
    assert len(placed) == 1
    kwargs = client.submit_limit_buy.call_args.kwargs
    assert kwargs["client_order_id"] == "shadow-A-AEHR-20260713"
    assert kwargs["limit_price"] == 20.0          # at_market → limit at close


def test_outlook_rankings_dicts_unwrap_and_reach_consumers():
    """MarketOutlook.industryRankings/themeRankings are DICTS shaped
    {"rankings": [...], "rotations": [...], "missing": [...]} (see
    execution/indicators/industry_strength.py). Lock the shape: the unwrapped
    rankings LIST must reach the top-industries / top-themes scoring slices
    in _screen. (There is no industry-RS universe channel — _assemble draws
    only on theme members, watchlist, and holdings.)"""
    import pandas as pd

    industry_rankings = [{"etf": "SMH", "industry": "Semiconductors", "rank_1m": 1}]
    theme_rankings = [{"slug": "photonics", "rank_1m": 1}]
    sector_rankings = [{"etf": "XLE", "sector": "Energy", "rank_1m": 1}]
    outlook_row = MagicMock(
        regime="neutral",
        industryRankings={"rankings": industry_rankings, "rotations": [],
                          "missing": []},
        themeRankings={"rankings": theme_rankings, "rotations": [],
                       "missing": []},
        sectorRankings=sector_rankings,
    )
    ctx = saf._outlook_context(outlook_row)
    assert ctx["industryRankings"] == industry_rankings
    assert ctx["themeRankings"] == theme_rankings
    # sectorRankings is a plain list on the row — passed through, not unwrapped.
    assert ctx["sectorRankings"] == sector_rankings

    # _assemble: theme members reach the tagged universe (no industry channel).
    db = MagicMock()
    with patch("execution.funnel.universe.load_theme_members",
               new=AsyncMock(return_value={"photonics": ["AEHR"]})), \
         patch("execution.research_feed.get_research_context",
               new=AsyncMock(return_value={"watchlist": []})):
        assembled = _run(saf._assemble(db, ctx, holdings=[]))
    assert "AEHR" in assembled["tagged"]

    # _screen: the [:5] slices over the unwrapped lists reach screen_row.
    df = pd.DataFrame({"Close": [50.0] * 60, "Volume": [1_000_000] * 60})
    captured = {}

    def fake_screen_row(symbol, frame, spy_closes, tags, top_themes,
                        top_industries, quality):
        captured["top_themes"] = top_themes
        captured["top_industries"] = top_industries
        return {"symbol": symbol, "screen_score": 5.0, "price": 50.0,
                "sma20": 49.0, "atr": 1.0, "atr_pct": 0.02, "ext_atr": 0.5,
                "momentum": 5.0, "hunting_bonus": 5.0,
                "liquidity_adv_usd": 5e7, "tags": tags}

    async def _identity_rerank(rows):
        return rows

    with patch("execution.market_data.fetch_ohlcv_batch",
               new=MagicMock(return_value={"AEHR": df, "SPY": df})), \
         patch("execution.funnel.screen.screen_row", new=fake_screen_row), \
         patch.object(saf, "_quality_rerank", new=_identity_rerank), \
         patch.object(saf, "_sectors_for", new=AsyncMock(return_value={})):
        screened = _run(saf._screen(assembled, ctx, {"positions": {}}))
    assert captured["top_industries"] == ["SMH"]
    assert captured["top_themes"] == ["photonics"]
    assert [r["symbol"] for r in screened["ranked"]] == ["AEHR"]


def test_assemble_has_no_industry_channel():
    """Founding-premise regression guard: no formula-picked universe source.
    The industry-ETF top-holdings channel is DELETED (spec Section 2) — a
    symbol may enter the universe only via themes, watchlist, or being
    held."""
    import execution.funnel.universe as universe

    assert not hasattr(universe, "fetch_industry_holdings")

    db = MagicMock()
    ctx = {"regime": "neutral", "industryRankings": [], "themeRankings": []}
    with patch("execution.funnel.universe.load_theme_members",
               new=AsyncMock(return_value={"photonics": ["AEHR"]})), \
         patch("execution.research_feed.get_research_context",
               new=AsyncMock(return_value={"watchlist": []})):
        assembled = _run(saf._assemble(db, ctx, holdings=[]))

    assert "industry_holdings" not in assembled["counts"]
    assert "AEHR" in assembled["tagged"]
    assert assembled["tagged"]["AEHR"]["themes"] == ["photonics"]
    assert assembled["tagged"]["AEHR"]["industries"] == []


# NOTE: test_full_run_sell_verdict_vetoes_entry lived here. It is subsumed by
# test_sell_verdict_is_the_only_diligence_veto (bottom of file), which asserts
# the same SELL veto PLUS the exit_sell_verdict journal and the None-verdict
# counterpart that the veto-only rule turns on.


def test_open_shadow_buys_reduce_spend_and_no_cash_write_at_buy_submit():
    """F1 (Task 13 review): the daily fills step is the SOLE cash mover for
    buys. The weekly pass (a) never writes the cash ledger at buy submit and
    (b) treats standing open buy notionals as committed capital, subtracting
    them from BOTH cash_available and deployable — sourced from the broker's
    OWN get_open_orders() (live "open" or shadow "shadow_open" rows alike),
    not a hardcoded shadow-only DB query."""
    db = MagicMock()
    client = MagicMock()
    # One standing (live) open buy worth $1,000 from a previous pass.
    client.get_open_orders = AsyncMock(return_value=[
        MagicMock(qty=50.0, limitPrice=20.0, notional=1000.0, side="buy",
                  status="open"),
    ])
    captured = {}

    async def fake_handshake(db_, client, entry_queue, cands, run_date,
                             sleeve_equity, deployable, cash_available,
                             holdings, sector_by_symbol, other, allow_buys, step):
        captured["deployable"] = deployable
        captured["cash_available"] = cash_available
        return [{"symbol": "AEHR", "qty": 100.0, "limit_price": 20.0,
                 "notional": 2000.0, "client_order_id": "shadow-A-AEHR-20260713",
                 "expires_at": NOW.isoformat()}]

    with patch.object(saf, "_theme_review", new=AsyncMock()), \
         patch.object(saf, "plan_decisions",
                      return_value={"exits": [], "trims": [],
                                    "entry_queue": ["AEHR"], "notes": []}), \
         patch.object(saf, "_execute_sells",
                      new=AsyncMock(return_value={"cash": 10_000.0,
                                                  "proceeds": 0.0, "sold": []})), \
         patch.object(saf, "_sleeve_b_sector_notional", new=AsyncMock(return_value={})), \
         patch.object(saf, "_handshake_and_enter", new=fake_handshake), \
         patch.object(saf, "write_report", new=AsyncMock()), \
         patch("execution.sleeve_service.update_sleeve_cash",
               new=AsyncMock()) as cash_write:
        out = _run(saf._decide_and_execute(
            db, client, NOW, "neutral",
            sleeve_ctx={"cash": 10_000.0, "positions": {},
                        "allow_buys": True, "status": "active"},
            assembled={}, screened={"ranked": [], "close_by_symbol": {},
                                    "sector_by_symbol": {}},
            lights={"light_rows": {}, "spent": 0}, step=None,
        ))

    # Committed $1,000 comes off both spendable envelopes:
    # cash: 10,000 (post-sells ledger) − 1,000 = 9,000
    # deployable: 0.9 (Sleeve A neutral floor) × 10,000 equity − 0 MV − 1,000 = 8,000
    assert captured["cash_available"] == 9000.0
    assert captured["deployable"] == 8000.0
    # And placing a buy writes NO cash — the daily fill (or expiry) decides.
    cash_write.assert_not_called()
    assert len(out["placed"]) == 1


def test_open_shadow_buys_sees_live_open_orders_not_just_shadow():
    """Regression: _open_shadow_buys previously hand-rolled a DB query
    hardcoded to status="shadow_open", which only ShadowBrokerClient writes.
    AlpacaFunnelBroker (the LIVE paper broker Sleeve A actually trades through
    per the 2026-07-10 owner ruling) writes status="open" — the hardcoded
    query went permanently blind to real outstanding orders, so a symbol with
    a standing live limit buy was never excluded from next week's candidates
    and could be bought again (the NVDA/HOOD duplicate-order bug). Now it
    must go through client.get_open_orders(), whatever the broker actually is."""
    client = MagicMock()
    client.get_open_orders = AsyncMock(return_value=[
        MagicMock(symbol="NVDA", side="buy", qty=2.0, limitPrice=900.0, notional=None),
        MagicMock(symbol="HOOD", side="buy", qty=10.0, limitPrice=45.0, notional=450.0),
        MagicMock(symbol="AEHR", side="sell", qty=5.0, limitPrice=None, notional=None),
    ])

    out = _run(saf._open_shadow_buys(client))

    assert out["symbols"] == {"NVDA", "HOOD"}
    assert out["count"] == 2
    assert out["notional"] == 2250.0  # 2*900 (reconstructed) + 450 (stated)


# ── Final whole-branch review pins (Phase 3C) ────────────────────────────────

def _screen_row(sym, **over):
    row = {"symbol": sym, "price": 20.0, "sma20": 19.0, "atr": 1.0,
           "atr_pct": 0.02, "ext_atr": 0.5, "momentum": 5.0, "hunting_bonus": 5.0,
           "liquidity_adv_usd": 5e6, "screen_score": 6.0, "tags": {}}
    row.update(over)
    return row


def test_c2_holding_verdict_and_staleness_reach_conviction():
    """C2: the most-recent full-run SELL verdict vetoes a holding into
    plan_decisions (and it exits), and a 60-day-old report decays its
    staleness multiplier below 1.0 — both were dead before the fix."""
    import inngest_app.functions.sleeve_a_funnel as saf
    from execution.funnel.conviction import compute_conviction
    from execution.funnel.decisions import plan_decisions as real_plan

    captured = {}

    def capture_plan(holdings, equity, maxpos, **kwargs):
        captured["holdings"] = holdings
        captured["max_positions"] = maxpos
        return real_plan(holdings, equity, maxpos)

    screened = {
        "ranked": [_screen_row("OLD"), _screen_row("STALE")],
        "close_by_symbol": {"OLD": 20.0, "STALE": 20.0},
        "sector_by_symbol": {},
    }
    latest = {"OLD": {"verdict": "sell", "report_age_days": 0.0},
              "STALE": {"verdict": None, "report_age_days": 60.0}}
    sells = {}

    async def fake_sells(db, client, decisions, *a, **k):
        sells["decisions"] = decisions
        return {"cash": 5000.0, "proceeds": 0.0, "sold": []}

    with patch.object(saf, "_load_latest_signals", new=AsyncMock(return_value=latest)), \
         patch.object(saf, "_load_position_source_tags", new=AsyncMock(return_value={})), \
         patch.object(saf, "_open_shadow_buys",
                      new=AsyncMock(return_value={"notional": 0.0, "symbols": set(), "count": 0})), \
         patch.object(saf, "_theme_review", new=AsyncMock()), \
         patch.object(saf, "_execute_sells", new=fake_sells), \
         patch.object(saf, "_sleeve_b_sector_notional", new=AsyncMock(return_value={})), \
         patch.object(saf, "_handshake_and_enter", new=AsyncMock(return_value=[])), \
         patch.object(saf, "full_runs_used", new=AsyncMock(return_value=1)), \
         patch.object(saf, "plan_decisions", new=capture_plan), \
         patch.object(saf, "write_report", new=AsyncMock()):
        _run(saf._decide_and_execute(
            MagicMock(), MagicMock(), NOW, "neutral",
            sleeve_ctx={"cash": 10_000.0, "positions": {"OLD": 10.0, "STALE": 10.0},
                        "allow_buys": True, "status": "active"},
            assembled={"active_themes": []}, screened=screened,
            lights={"light_rows": {}, "spent": 0}, step=None,
        ))

    holds = {h["symbol"]: h for h in captured["holdings"]}
    # SELL verdict → vetoed=True into plan_decisions → exits.
    assert holds["OLD"]["vetoed"] is True
    assert {"symbol": "OLD", "reason": "sell_verdict"} in sells["decisions"]["exits"]
    # 60-day report → staleness multiplier < 1.0 (score below the age-0 control).
    control = compute_conviction(saf._conviction_input_from_light(
        {}, _screen_row("STALE"), report_age_days=0.0, verdict=None))["score"]
    assert holds["STALE"]["conviction"] < control


def test_c1_industry_only_holding_not_theme_reviewed():
    """C1a: an industry-sourced holding (industries rotate out weekly BY
    DESIGN) with no theme tags is never flagged — no phantom paid review."""
    import inngest_app.functions.sleeve_a_funnel as saf

    holdings = [{"symbol": "IND", "source_tags": {"industries": ["semis"]}}]
    reuse = AsyncMock()
    with patch.object(saf, "reuse_or_budget", new=reuse), \
         patch.object(saf, "write_report", new=AsyncMock()):
        _run(saf._theme_review(MagicMock(), NOW, holdings, {},
                               active_themes={"ai"}, step=None))
    reuse.assert_not_called()
    assert "theme_review_failed" not in holdings[0]


def test_c1_deferred_review_never_exits():
    """C1b: budget-exhausted review returns no signals → deferred, holding
    stays (theme_review_failed never set). Degradation must not force a trade."""
    import inngest_app.functions.sleeve_a_funnel as saf

    holdings = [{"symbol": "DEF", "source_tags": {"themes": ["dead"]}}]
    report = AsyncMock()
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "skip",
                                                  "reason": "budget_exhausted"})), \
         patch.object(saf, "write_report", new=report):
        _run(saf._theme_review(MagicMock(), NOW, holdings, {},
                               active_themes=set(), step=None))
    assert holdings[0].get("theme_review_failed") in (None, False)
    bodies = [c.args[4] if len(c.args) > 4 else c.kwargs.get("body")
              for c in report.call_args_list]
    assert any(isinstance(b, dict) and b.get("status") == "deferred" for b in bodies)


def test_c1_completed_review_below_floor_exits():
    """C1b: a COMPLETED review whose re-score is below the retirement floor
    fails the holding."""
    import inngest_app.functions.sleeve_a_funnel as saf

    holdings = [{"symbol": "GONE", "source_tags": {"themes": ["dead"]}}]
    signals = {"verdict": "hold", "insiderScore": 0.0, "darkPoolScore": 0.0,
               "sentimentScore": 0.0}
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse", "signals": signals})), \
         patch.object(saf, "write_report", new=AsyncMock()):
        _run(saf._theme_review(MagicMock(), NOW, holdings, {},
                               active_themes=set(), step=None))
    assert holdings[0]["theme_review_failed"] is True


def test_i1_handshake_recompute_applies_small_cap_haircut():
    """I1: full signals overlaid ONTO the light/screen base preserve market_cap,
    so the small-cap haircut still bites at the entry recompute."""
    import inngest_app.functions.sleeve_a_funnel as saf
    from execution.funnel.conviction import compute_conviction

    screen = {"price": 20.0, "momentum": 8.0, "hunting_bonus": 8.0}
    signals = {"verdict": "hold", "insiderScore": 8.0, "darkPoolScore": 6.0,
               "sentimentScore": 6.0}
    base_small = saf._conviction_input_from_light(
        {"market_cap": 4e8, "valuation_score": 7.0}, screen)
    base_big = saf._conviction_input_from_light(
        {"market_cap": 5e9, "valuation_score": 7.0}, screen)
    merged_small = saf._conviction_input_from_signals(signals, screen, base=base_small)
    merged_big = saf._conviction_input_from_signals(signals, screen, base=base_big)
    assert merged_small["market_cap"] == 4e8   # phantom key gone; light value survives
    out_small = compute_conviction(merged_small)
    out_big = compute_conviction(merged_big)
    assert out_small["multipliers"]["haircut"] < 1.0
    assert out_small["score"] < out_big["score"]


def test_i2_quality_rerank_reblends_screen_score():
    """I2: calculate_valuation_score's tuple is unpacked and the screen_score
    is re-blended, so a high-quality name outranks an identical low-quality one."""
    import inngest_app.functions.sleeve_a_funnel as saf

    rows = [{"symbol": "HI", "screen_score": 5.0, "quality": 5.0},
            {"symbol": "LO", "screen_score": 5.0, "quality": 5.0}]
    scorer = MagicMock()
    scorer.calculate_valuation_score.side_effect = \
        lambda m: ({"HI": 9.0, "LO": 1.0}[m["sym"]], {})
    provider = MagicMock()
    provider.get_valuation_metrics.side_effect = lambda s: {"sym": s}
    with patch("research_swarm.agents.fundamentalist.scorer.HealthScorer",
               return_value=scorer), \
         patch("research_swarm.data.data_provider_hybrid.HybridDataProvider",
               return_value=provider):
        out = _run(saf._quality_rerank(rows))
    hi = next(r for r in out if r["symbol"] == "HI")
    lo = next(r for r in out if r["symbol"] == "LO")
    assert hi["screen_score"] > lo["screen_score"]


def test_i3_standing_order_excluded_and_counts_to_cap():
    """I3a: a symbol with a standing shadow-open buy is absent from the
    challengers AND reserves a slot against the max-positions cap."""
    import inngest_app.functions.sleeve_a_funnel as saf
    from execution.constants import SLEEVE_A_MAX_POSITIONS

    captured = {}

    def capture_plan(holdings, equity, maxpos, **kwargs):
        captured["max_positions"] = maxpos
        return {"exits": [], "trims": [], "notes": []}

    # Task 10: entries come from the MEMO, so the standing-order exclusion is
    # asserted where it now bites — the planned-entry list handed to the entry
    # handshake, filtered BEFORE any paid run (see
    # test_open_symbol_memo_entry_skips_before_paid_run for the billing half).
    async def capture_handshake(db_, client, planned, screens, *a, **k):
        captured["symbols"] = sorted(e["ticker"] for e in planned)
        return []

    plan = {"entries": [_planned("PENDING"), _planned("NEW")], "adds": [],
            "reviews": [], "stage_updates": {}, "rejected": [], "prior_stages": {}}
    screened = {"ranked": [_screen_row("PENDING"), _screen_row("NEW")],
                "close_by_symbol": {}, "sector_by_symbol": {}}
    with patch.object(saf, "_load_latest_signals", new=AsyncMock(return_value={})), \
         patch.object(saf, "_load_position_source_tags", new=AsyncMock(return_value={})), \
         patch.object(saf, "_memo_pipeline", new=AsyncMock(return_value=plan)), \
         patch.object(saf, "_open_shadow_buys",
                      new=AsyncMock(return_value={"notional": 1000.0,
                                                  "symbols": {"PENDING"}, "count": 1})), \
         patch.object(saf, "_theme_review", new=AsyncMock()), \
         patch.object(saf, "_execute_sells",
                      new=AsyncMock(return_value={"cash": 5000.0, "proceeds": 0.0, "sold": []})), \
         patch.object(saf, "_sleeve_b_sector_notional", new=AsyncMock(return_value={})), \
         patch.object(saf, "_handshake_and_enter", new=capture_handshake), \
         patch.object(saf, "full_runs_used", new=AsyncMock(return_value=0)), \
         patch.object(saf, "plan_decisions", new=capture_plan), \
         patch.object(saf, "write_report", new=AsyncMock()):
        _run(saf._decide_and_execute(
            MagicMock(), MagicMock(), NOW, "neutral",
            sleeve_ctx={"cash": 10_000.0, "positions": {}, "allow_buys": True,
                        "status": "active"},
            assembled={"active_themes": []}, screened=screened,
            lights={"light_rows": {}, "spent": 0}, step=None,
        ))
    assert "PENDING" not in captured["symbols"]
    assert "NEW" in captured["symbols"]
    assert captured["max_positions"] == SLEEVE_A_MAX_POSITIONS - 1


def test_i4_light_slot_policy_fresh_rides_free_stale_claims_slot():
    """I4: a 3-day-old holding rides free; a 7-week-old holding claims a slot."""
    import inngest_app.functions.sleeve_a_funnel as saf

    ranked = [{"symbol": "FRESH"}]
    positions = {"FRESH": 1.0, "OLD": 1.0, "NOROW": 1.0}
    latest = {"FRESH": {"report_age_days": 3.0}, "OLD": {"report_age_days": 49.0}}
    fresh, stale = saf._light_slot_policy(ranked, positions, latest)
    assert "FRESH" in fresh and "FRESH" not in stale
    assert "OLD" in stale and "NOROW" in stale   # 49d and no-row both claim a slot


def test_i5_two_same_theme_entries_jointly_capped():
    """I5: enforce_funnel_guardrails accumulates across placed orders in a pass,
    so three same-theme entries are jointly capped at MAX_THEME_PCT_OF_SLEEVE."""
    import inngest_app.functions.sleeve_a_funnel as saf
    from execution.constants import MAX_THEME_PCT_OF_SLEEVE

    sleeve_equity = 100_000.0
    screen = {"price": 20.0, "sma20": 19.0, "atr": 1.0, "atr_pct": 0.02,
              "liquidity_adv_usd": 1e9, "screen_score": 6.0,
              "tags": {"themes": ["t"]}}
    screens = {s: dict(screen, symbol=s) for s in ("N1", "N2", "N3")}
    # Three anchors at full memo conviction want 12% each — 36% of the sleeve.
    planned = [_planned(s, role="anchor", conviction=1.0, entry_style="at_market")
               for s in ("N1", "N2", "N3")]
    signals = {"verdict": "buy", "insiderScore": 10.0, "darkPoolScore": 10.0,
               "sentimentScore": 10.0, "fairValue": 40.0}
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse", "signals": signals})), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "write_report", new=AsyncMock()):
        placed = _run(saf._handshake_and_enter(
            MagicMock(), client, planned_entries=planned,
            screen_by_symbol=screens, run_date=NOW, sleeve_equity=sleeve_equity,
            deployable=sleeve_equity, cash_available=sleeve_equity, holdings=[],
            sector_by_symbol={}, other_sleeve_sector_notional={}, allow_buys=True,
            step=None,
        ))
    theme_total = sum(p["notional"] for p in placed)
    assert theme_total <= MAX_THEME_PCT_OF_SLEEVE * sleeve_equity + 0.01
    assert theme_total > 0.30 * sleeve_equity   # cap actually bound (3×12% wanted 36%)


def test_alpaca_tradable_symbols_returns_broker_set():
    import execution.broker.alpaca_client as alpaca_mod
    import execution.broker.credentials as creds_mod

    client = MagicMock()
    client.list_tradable_us_equities = MagicMock(return_value={"AEHR", "NVDA"})
    with patch.object(creds_mod, "get_active_alpaca_account",
                      new=AsyncMock(return_value=MagicMock())), \
         patch.object(alpaca_mod, "client_from_account", new=MagicMock(return_value=client)):
        out = _run(saf._alpaca_tradable_symbols(MagicMock()))
    assert out == {"AEHR", "NVDA"}


def test_alpaca_tradable_symbols_degrades_to_none_on_no_account():
    import execution.broker.credentials as creds_mod

    with patch.object(creds_mod, "get_active_alpaca_account",
                      new=AsyncMock(return_value=None)):
        out = _run(saf._alpaca_tradable_symbols(MagicMock()))
    assert out is None


def test_alpaca_tradable_symbols_degrades_to_none_on_failure():
    import execution.broker.credentials as creds_mod

    with patch.object(creds_mod, "get_active_alpaca_account",
                      new=AsyncMock(side_effect=RuntimeError("db down"))):
        out = _run(saf._alpaca_tradable_symbols(MagicMock()))
    assert out is None


def test_bootstrap_refuses_when_spy_close_unavailable():
    """Operational: a missing previous SPY close must NOT seed
    inceptionSpyClose=0.0 (that silently disables the breaker forever)."""
    import inngest_app.functions.sleeve_a_funnel as saf
    import execution.broker.alpaca_client as alpaca_mod
    import execution.broker.credentials as creds_mod
    import execution.sleeve_service as sleeve_mod

    client = MagicMock()
    client.get_account_summary = MagicMock(return_value={"equity": 100_000.0})
    init = AsyncMock()
    with patch.object(sleeve_mod, "get_sleeve_state", new=AsyncMock(return_value=None)), \
         patch.object(creds_mod, "get_active_alpaca_account",
                      new=AsyncMock(return_value=MagicMock())), \
         patch.object(alpaca_mod, "client_from_account", new=MagicMock(return_value=client)), \
         patch.object(sleeve_mod, "init_sleeve_state", new=init), \
         patch.object(saf, "_previous_spy_close", new=AsyncMock(return_value=0.0)), \
         patch.object(saf, "write_report", new=AsyncMock()):
        out = _run(saf._ensure_sleeve_a(MagicMock(), NOW))
    assert out is None
    init.assert_not_called()


def test_theme_review_skipped_when_theme_membership_unavailable():
    """Outage guard (same class as C1): empty theme_members/active_themes means
    a theme-source outage, not mass retirement — the ENTIRE theme-review stage
    is skipped (journaled), no holding is flagged, no research is commissioned."""
    import inngest_app.functions.sleeve_a_funnel as saf

    captured = {}

    def capture_plan(holdings, equity, maxpos, **kwargs):
        captured["holdings"] = holdings
        return {"exits": [], "trims": [], "notes": []}

    screened = {"ranked": [_screen_row("THM")],
                "close_by_symbol": {"THM": 20.0}, "sector_by_symbol": {}}
    reuse = AsyncMock()
    report = AsyncMock()
    with patch.object(saf, "_load_latest_signals", new=AsyncMock(return_value={})), \
         patch.object(saf, "_load_position_source_tags",
                      new=AsyncMock(return_value={"THM": {"themes": ["dead"]}})), \
         patch.object(saf, "_open_shadow_buys",
                      new=AsyncMock(return_value={"notional": 0.0, "symbols": set(),
                                                  "count": 0})), \
         patch.object(saf, "reuse_or_budget", new=reuse), \
         patch.object(saf, "_execute_sells",
                      new=AsyncMock(return_value={"cash": 5000.0, "proceeds": 0.0,
                                                  "sold": []})), \
         patch.object(saf, "_sleeve_b_sector_notional", new=AsyncMock(return_value={})), \
         patch.object(saf, "_handshake_and_enter", new=AsyncMock(return_value=[])), \
         patch.object(saf, "full_runs_used", new=AsyncMock(return_value=0)), \
         patch.object(saf, "plan_decisions", new=capture_plan), \
         patch.object(saf, "write_report", new=report):
        _run(saf._decide_and_execute(
            MagicMock(), MagicMock(), NOW, "neutral",
            sleeve_ctx={"cash": 10_000.0, "positions": {"THM": 10.0},
                        "allow_buys": True, "status": "active"},
            assembled={"active_themes": []},   # theme-source outage
            screened=screened, lights={"light_rows": {}, "spent": 0}, step=None,
        ))

    # No holding flagged; no research handshake commissioned.
    reuse.assert_not_called()
    assert all(not h.get("theme_review_failed") for h in captured["holdings"])
    # The skip is journaled: theme_review row, status "skipped".
    skip_calls = [c for c in report.call_args_list
                  if (c.args[0] if c.args else c.kwargs.get("report_type")) == "theme_review"]
    assert skip_calls, "expected a theme_review skip journal row"
    body = (skip_calls[0].args[4] if len(skip_calls[0].args) > 4
            else skip_calls[0].kwargs.get("body"))
    assert body.get("status") == "skipped"
    assert body.get("reason") == "theme membership unavailable"


def test_execute_sells_credits_actual_fill_not_hint():
    """I1: a live broker fills the market sell at the REAL price — cash and
    proceeds must credit res.filled_qty * res.filled_avg_price, not the close
    hint. (Shadow returns hint values, so shadow behavior is unchanged.)"""
    from execution.broker.base import BrokerOrderResult
    import execution.sleeve_service as sleeve_mod

    db = MagicMock()
    client = MagicMock()
    client.submit_sell = AsyncMock(return_value=BrokerOrderResult(
        order_id="alp-1", symbol="AEHR", side="sell", status="filled",
        filled_qty=100.0, filled_avg_price=19.5,   # hint below is 20.0
    ))
    cash_writes = []

    async def fake_update_sleeve_cash(db_, sleeve, cash):
        cash_writes.append(cash)

    with patch.object(sleeve_mod, "update_sleeve_cash", new=fake_update_sleeve_cash), \
         patch.object(saf, "_journal", new=AsyncMock()) as journal:
        out = _run(saf._execute_sells(
            db, client,
            {"exits": [{"symbol": "AEHR", "reason": "sell_verdict"}], "trims": []},
            {"AEHR": 20.0}, {"AEHR": 100.0}, NOW, 1000.0,
        ))

    assert out["proceeds"] == 1950.0                     # 100 * 19.5, NOT 2000
    assert out["cash"] == 1000.0 + 1950.0
    assert out["sold"] == ["AEHR"]
    # journal logs the ACTUAL fill price
    exit_bodies = [c.args[4] for c in journal.call_args_list
                   if c.args[1] == "exit_sell_verdict"]
    assert exit_bodies and exit_bodies[0]["fill_price"] == 19.5


def test_execute_sells_zero_fill_credits_nothing_and_journals_failure():
    """I1: a timed-out live sell (no fill) must credit NO cash, not count the
    exit, and journal an engine_failure warning — the position row already
    reflects reality via position_after_fill inside the broker."""
    from execution.broker.base import BrokerOrderResult
    import execution.sleeve_service as sleeve_mod

    db = MagicMock()
    client = MagicMock()
    client.submit_sell = AsyncMock(return_value=BrokerOrderResult(
        order_id="alp-1", symbol="AEHR", side="sell", status="timeout",
        filled_qty=0.0, filled_avg_price=None,
    ))
    cash_writes = []

    async def fake_update_sleeve_cash(db_, sleeve, cash):
        cash_writes.append(cash)

    with patch.object(sleeve_mod, "update_sleeve_cash", new=fake_update_sleeve_cash), \
         patch.object(saf, "_journal", new=AsyncMock()) as journal:
        out = _run(saf._execute_sells(
            db, client,
            {"exits": [{"symbol": "AEHR", "reason": "sell_verdict"}],
             "trims": [{"symbol": "NVDA", "sell_notional": 2000.0}]},
            {"AEHR": 20.0, "NVDA": 100.0}, {"AEHR": 100.0, "NVDA": 50.0},
            NOW, 1000.0,
        ))

    assert out["proceeds"] == 0.0
    assert out["cash"] == 1000.0                        # nothing credited
    assert out["sold"] == []
    kinds = [c.args[1] for c in journal.call_args_list]
    assert kinds.count("engine_failure") == 2           # exit AND trim no-fill
    assert "exit_sell_verdict" not in kinds and "risk_trim" not in kinds


# ── Task 8: thesis-hold review triggers → ADD / TRIM / REDUCE / SELL ─────────
# The five contracts wire pure triggers (Task 7) + market-buy (Task 5) into the
# weekly pass. A trigger NEVER trades — it earns a review; the review's verdict
# (or an outcome built from it) is the only authority to buy/sell.
import contextlib
from types import SimpleNamespace

from execution.broker.base import BrokerOrderResult


class _ReportSink:
    """Async stand-in for write_report that records every journalled type."""
    def __init__(self):
        self.types = []
        self.titles = []

    async def __call__(self, report_type, severity, source, title, body, db=None):
        self.types.append(report_type)
        self.titles.append(title)
        return "rep"

    def count(self, t):
        return self.types.count(t)


class _ThDB:
    """Minimal fake db: engineposition.update records dcaState (unwrapping the
    prisma Json wrapper); the broker mutates a shared (sleeve, symbol) qty map."""
    def __init__(self, positions):
        self.positions = {("A", s): {"qty": float(v["qty"]),
                                      "dcaState": v.get("dcaState")}
                          for s, v in positions.items()}
        self.engineposition = SimpleNamespace(update=self._update)
        # (ticker, runDate) -> row; the R1 stage-B short-circuit reads its own
        # (ticker, run_date) full-tier row via weeklysignal.find_unique.
        self._ws_rows = {}
        self.weeklysignal = SimpleNamespace(find_unique=self._ws_find_unique)

    async def _ws_find_unique(self, where):
        key = where["ticker_runDate"]
        return self._ws_rows.get((key["ticker"], key["runDate"]))

    async def _update(self, where, data):
        key = ("A", where["sleeve_symbol"]["symbol"])
        rec = self.positions.setdefault(key, {})
        val = data.get("dcaState")
        rec["dcaState"] = getattr(val, "data", val)

    def _increase(self, symbol, qty):
        self.positions[("A", symbol)]["qty"] += qty

    def _reduce(self, symbol, qty):
        self.positions[("A", symbol)]["qty"] -= qty


class _ThBroker:
    """Records market buys / sells and reflects them onto the fake db."""
    def __init__(self, db):
        self._db = db
        self.market_buys = []
        self.sells = []

    async def submit_market_buy(self, symbol, qty, price_hint, journal, client_order_id):
        self.market_buys.append(SimpleNamespace(
            symbol=symbol, qty=qty, price_hint=price_hint, journal=journal,
            client_order_id=client_order_id))
        self._db._increase(symbol, qty)
        return BrokerOrderResult(order_id=client_order_id, symbol=symbol, side="buy",
                                 status="shadow_filled", filled_qty=qty,
                                 filled_avg_price=price_hint)

    async def submit_sell(self, symbol, qty, price_hint, journal, client_order_id):
        self.sells.append(SimpleNamespace(
            symbol=symbol, qty=qty, price_hint=price_hint, journal=journal,
            client_order_id=client_order_id))
        self._db._reduce(symbol, qty)
        return BrokerOrderResult(order_id=client_order_id, symbol=symbol, side="sell",
                                 status="shadow_filled", filled_qty=qty,
                                 filled_avg_price=price_hint)


def _th_pos_row(symbol, qty, high_water=None, dca_state=None):
    return SimpleNamespace(symbol=symbol, qty=float(qty),
                           highWaterClose=high_water, dcaState=dca_state)


@contextlib.contextmanager
def _thesis_ctx(pos_rows, latest, reuse_action, sink, memo_plan=None):
    """Patch every collaborator so the REAL _decide_and_execute + _execute_sells
    run end to end while stage A/B inputs are controlled. `latest` may be a list
    (side_effect: initial then post-review refresh) or a single dict.

    `memo_plan` stands in for the whole thesis-memo pipeline (Task 9): None is a
    no-op memo week, which is what these trigger/outcome tests want — they pin
    the review path, not the memo path."""
    import importlib
    # NB: `research_swarm.data` re-exports a lowercase singleton that shadows the
    # submodule under attribute access, so `import ... as` binds the instance.
    # import_module returns the real module object from sys.modules.
    mdc_mod = importlib.import_module("research_swarm.data.market_data_client")
    mc = MagicMock()
    mc.get_earnings_dates.return_value = None
    latest_mock = (AsyncMock(side_effect=latest) if isinstance(latest, list)
                   else AsyncMock(return_value=latest))
    with patch.object(saf, "_load_latest_signals", new=latest_mock), \
         patch.object(saf, "_load_position_source_tags", new=AsyncMock(return_value={})), \
         patch.object(saf, "_memo_pipeline", new=AsyncMock(return_value=memo_plan)), \
         patch.object(saf, "_open_shadow_buys",
                      new=AsyncMock(return_value={"notional": 0.0, "symbols": set(),
                                                 "count": 0})), \
         patch.object(saf, "_sleeve_b_sector_notional", new=AsyncMock(return_value={})), \
         patch.object(saf, "_handshake_and_enter", new=AsyncMock(return_value=[])), \
         patch.object(saf, "full_runs_used", new=AsyncMock(return_value=0)), \
         patch.object(saf, "reuse_or_budget", new=AsyncMock(return_value=reuse_action)), \
         patch.object(saf, "run_paid_analysis", new=AsyncMock(return_value={})), \
         patch.object(saf, "persist_full",
                      new=AsyncMock(return_value={"status": "upgraded", "signals": {}})), \
         patch.object(saf, "write_report", new=sink), \
         patch("execution.sleeve_service.get_engine_positions",
               new=AsyncMock(return_value=pos_rows)), \
         patch("execution.sleeve_service.update_sleeve_cash", new=AsyncMock()), \
         patch.object(mdc_mod, "MarketDataClient", return_value=mc):
        yield


def _th_meta(verdict, age, prior=None, last_price=None, rec=None):
    return {"verdict": verdict, "report_age_days": age, "prior_verdict": prior,
            "last_review_price": last_price, "position_size_rec": rec}


def _run_decide(db, broker, sleeve_ctx, screened):
    return _run(saf._decide_and_execute(
        db, broker, NOW, "neutral", sleeve_ctx=sleeve_ctx,
        assembled={"active_themes": []}, screened=screened,
        lights={"light_rows": {}, "spent": 0}, step=None,
    ))


def test_triggered_holding_gets_review_before_plan():
    """A stale holding claims a full-run slot ahead of new entries; the review's
    AVOID verdict exits it through the existing sell_verdict path."""
    db = _ThDB({"OLDN": {"qty": 10.0}})
    broker = _ThBroker(db)
    screened = {"ranked": [_screen_row("OLDN", price=20.0)],
                "close_by_symbol": {"OLDN": 20.0}, "sector_by_symbol": {}}
    latest = [{"OLDN": _th_meta("buy", 60.0)},          # stale → review triggered
              {"OLDN": _th_meta("avoid", 0.0, prior="buy")}]   # review → AVOID
    sink = _ReportSink()
    with _thesis_ctx([_th_pos_row("OLDN", 10.0)], latest, {"action": "analyze"}, sink):
        _run_decide(db, broker,
                    {"cash": 5000.0, "positions": {"OLDN": 10.0},
                     "allow_buys": True, "status": "active"}, screened)
    assert sink.count("review_trigger") == 1
    assert broker.sells and broker.sells[0].symbol == "OLDN"
    assert sink.count("exit_sell_verdict") == 1
    assert broker.market_buys == []


def test_rung_trigger_with_buy_verdict_adds_half_tranche():
    """A 25% drawdown fires the 0.20 ladder rung; a still-buy verdict adds half a
    tranche and the consumed rung is persisted to dcaState."""
    db = _ThDB({"DIPN": {"qty": 10.0}})
    broker = _ThBroker(db)
    screened = {"ranked": [_screen_row("DIPN", price=75.0, liquidity_adv_usd=1e7,
                                       atr_pct=0.05)],
                "close_by_symbol": {"DIPN": 75.0}, "sector_by_symbol": {}}
    latest = {"DIPN": _th_meta("buy", 2.0)}
    sink = _ReportSink()
    with _thesis_ctx([_th_pos_row("DIPN", 10.0, high_water=100.0)], latest,
                     {"action": "reuse", "signals": {"verdict": "buy"}}, sink):
        _run_decide(db, broker,
                    {"cash": 10_000.0, "positions": {"DIPN": 10.0},
                     "allow_buys": True, "status": "active"}, screened)
    add = [b for b in broker.market_buys if b.symbol == "DIPN"]
    assert len(add) == 1
    assert sink.count("dca_add") == 1
    st = db.positions[("A", "DIPN")]["dcaState"]
    assert 0.20 in st["used"]
    assert broker.sells == []


def test_concentration_trigger_trims_only_via_review():
    """A 30% weight triggers a review; the still-hold verdict shaves the excess
    back to TRIM_FALLBACK_TARGET (0.15) via decisions['trims'] → risk_trim."""
    db = _ThDB({"BIGW": {"qty": 100.0}})
    broker = _ThBroker(db)
    screened = {"ranked": [_screen_row("BIGW", price=300.0)],
                "close_by_symbol": {"BIGW": 300.0}, "sector_by_symbol": {}}
    latest = {"BIGW": _th_meta("hold", 2.0)}
    sink = _ReportSink()
    with _thesis_ctx([_th_pos_row("BIGW", 100.0)], latest,
                     {"action": "reuse", "signals": {"verdict": "hold"}}, sink):
        _run_decide(db, broker,
                    {"cash": 70_000.0, "positions": {"BIGW": 100.0},
                     "allow_buys": True, "status": "active"}, screened)
    trims = [s for s in broker.sells if s.journal["reason"] == "risk_trim"]
    assert len(trims) == 1
    assert abs(trims[0].qty * 300.0 - (0.30 - 0.15) * 100_000.0) < 300.0
    assert broker.market_buys == []


def test_no_trigger_no_spend_no_trade():
    """A fresh, in-band, low-drawdown holding fires no trigger: no review, no
    ADD, no TRIM, no sell."""
    db = _ThDB({"CALM": {"qty": 10.0}})
    broker = _ThBroker(db)
    screened = {"ranked": [_screen_row("CALM", price=100.0)],
                "close_by_symbol": {"CALM": 100.0}, "sector_by_symbol": {}}
    latest = {"CALM": _th_meta("buy", 2.0)}
    sink = _ReportSink()
    with _thesis_ctx([_th_pos_row("CALM", 10.0, high_water=105.0)], latest,
                     {"action": "reuse", "signals": {"verdict": "buy"}}, sink):
        _run_decide(db, broker,
                    {"cash": 5000.0, "positions": {"CALM": 10.0},
                     "allow_buys": True, "status": "active"}, screened)
    assert sink.count("review_trigger") == 0
    assert broker.sells == [] and broker.market_buys == []


def test_verdict_downgrade_releases_a_tranche_not_the_position():
    """A fresh review that downgrades buy→hold releases one 25% tranche (the DCA
    ladder's mirror) — the position is reduced, not exited."""
    db = _ThDB({"MU": {"qty": 100.0}})
    broker = _ThBroker(db)
    screened = {"ranked": [_screen_row("MU", price=300.0)],
                "close_by_symbol": {"MU": 300.0}, "sector_by_symbol": {}}
    latest = [{"MU": _th_meta("buy", 60.0)},                    # stale → review
              {"MU": _th_meta("hold", 0.0, prior="buy")}]       # buy→hold downgrade
    sink = _ReportSink()
    # cash large enough that MU's 30k position is < CONCENTRATION_REVIEW_WEIGHT
    # of equity — isolates the buy→hold REDUCE from the concentration TRIM.
    with _thesis_ctx([_th_pos_row("MU", 100.0)], latest, {"action": "analyze"}, sink):
        _run_decide(db, broker,
                    {"cash": 200_000.0, "positions": {"MU": 100.0},
                     "allow_buys": True, "status": "active"}, screened)
    sells = [s for s in broker.sells if s.symbol == "MU"]
    assert len(sells) == 1 and abs(sells[0].qty - 25.0) < 1e-6
    assert sink.count("thesis_reduce") == 1
    assert db.positions[("A", "MU")]["qty"] == 75


# ── C2 replay-model / C2b rung durability / I1 fill-accurate ADD ─────────────
# The failure class the review surfaced was invisible to inline (step=None)
# tests: production runs under the Inngest replay model, where the function body
# re-executes on every step boundary and only step.run results are memoized.


class _MemoStep:
    """Simulates the Inngest replay model: step.run memoizes by id across the
    (re-executing) function body AND across explicit re-invocations, and return
    values round-trip through JSON to mirror the durable-log serialization."""

    def __init__(self):
        self._log = {}

    async def run(self, step_id, fn):
        import json
        if step_id in self._log:
            return json.loads(self._log[step_id])
        val = await fn()
        self._log[step_id] = json.dumps(val)
        return json.loads(self._log[step_id])


class _RejectBroker(_ThBroker):
    """submit_market_buy that the broker REJECTS (zero fill) — the market never
    accepted the order, so nothing may be debited from the sleeve."""

    async def submit_market_buy(self, symbol, qty, price_hint, journal, client_order_id):
        self.market_buys.append(SimpleNamespace(
            symbol=symbol, qty=qty, price_hint=price_hint, journal=journal,
            client_order_id=client_order_id))
        return BrokerOrderResult(order_id="", symbol=symbol, side="buy",
                                 status="rejected", filled_qty=0.0,
                                 filled_avg_price=None)


def _rung_screened():
    return {"ranked": [_screen_row("DIPN", price=75.0, liquidity_adv_usd=1e7,
                                   atr_pct=0.05)],
            "close_by_symbol": {"DIPN": 75.0}, "sector_by_symbol": {}}


def test_replay_memoized_triggers_single_add_and_journal():
    """C2/I4: two _decide_and_execute runs under a memoizing step fake (first
    executes, replay returns cached) must yield IDENTICAL triggers, exactly one
    review_trigger journal, exactly one dca_add order+journal, and the ladder
    ADD must actually execute on the PAID review path — the end-to-end scenario
    C2 broke (a rung consumed on exec 1 vanished before the post-review replay)."""
    db = _ThDB({"DIPN": {"qty": 10.0}})
    broker = _ThBroker(db)
    latest = {"DIPN": _th_meta("buy", 2.0)}     # fresh (no staleness) → rung only
    sink = _ReportSink()
    step = _MemoStep()

    def _decide():
        return _run(saf._decide_and_execute(
            db, broker, NOW, "neutral",
            sleeve_ctx={"cash": 10_000.0, "positions": {"DIPN": 10.0},
                        "allow_buys": True, "status": "active"},
            assembled={"active_themes": []}, screened=_rung_screened(),
            lights={"light_rows": {}, "spent": 0}, step=step))

    with _thesis_ctx([_th_pos_row("DIPN", 10.0, high_water=100.0)], latest,
                     {"action": "analyze"}, sink):
        out1 = _decide()
        out2 = _decide()                         # the replay

    assert out1["reviews"]["triggered"] == {"DIPN": ["ladder_rung"]}
    assert out1["reviews"]["triggered"] == out2["reviews"]["triggered"]
    assert sink.count("review_trigger") == 1     # journalled exactly once
    assert sink.count("dca_add") == 1            # journalled exactly once
    add = [b for b in broker.market_buys if b.symbol == "DIPN"]
    assert len(add) == 1                         # ONE ADD order on the paid path
    st = db.positions[("A", "DIPN")]["dcaState"]
    assert 0.20 in st["used"]                    # rung durably consumed


def test_i1_rejected_dca_add_debits_nothing():
    """I1: a rejected market buy (zero fill) must debit NOTHING from the ADD
    ledger and journal an engine_failure — not a phantom dca_add at the hint."""
    db = _ThDB({"DIPN": {"qty": 10.0}})
    broker = _RejectBroker(db)
    latest = {"DIPN": _th_meta("buy", 2.0)}
    sink = _ReportSink()
    with _thesis_ctx([_th_pos_row("DIPN", 10.0, high_water=100.0)], latest,
                     {"action": "reuse", "signals": {"verdict": "buy"}}, sink):
        out = _run_decide(db, broker,
                          {"cash": 10_000.0, "positions": {"DIPN": 10.0},
                           "allow_buys": True, "status": "active"}, _rung_screened())
    assert len(broker.market_buys) == 1          # order attempted
    assert db.positions[("A", "DIPN")]["qty"] == 10.0   # rejected → no shares
    assert sink.count("dca_add") == 0            # nothing filled → not journalled
    assert sink.count("engine_failure") >= 1     # no-fill journalled
    assert out["reviews"]["add_notional"] == 0.0  # ledger debited nothing


def test_c2b_deferred_review_leaves_rung_for_next_week():
    """C2b: a budget-deferred review must NOT durably consume the ladder rung —
    the rung fires again the following week when budget frees up."""
    db = _ThDB({"DIPN": {"qty": 10.0}})
    broker = _ThBroker(db)
    screened = _rung_screened()

    # Week 1: budget exhausted → review deferred; rung must NOT be consumed.
    sink1 = _ReportSink()
    with _thesis_ctx([_th_pos_row("DIPN", 10.0, high_water=100.0)],
                     {"DIPN": _th_meta("buy", 2.0)},
                     {"action": "skip", "reason": "budget_exhausted"}, sink1):
        _run_decide(db, broker,
                    {"cash": 10_000.0, "positions": {"DIPN": 10.0},
                     "allow_buys": True, "status": "active"}, screened)
    assert sink1.count("review_trigger") == 1
    assert broker.market_buys == []                       # deferred → no ADD
    assert db.positions[("A", "DIPN")].get("dcaState") is None  # rung intact

    # Week 2: budget available (reuse) → rung fires AGAIN and is consumed now.
    sink2 = _ReportSink()
    pos2 = _th_pos_row("DIPN", db.positions[("A", "DIPN")]["qty"],
                       high_water=100.0,
                       dca_state=db.positions[("A", "DIPN")].get("dcaState"))
    with _thesis_ctx([pos2], {"DIPN": _th_meta("buy", 2.0)},
                     {"action": "reuse", "signals": {"verdict": "buy"}}, sink2):
        _run_decide(db, broker,
                    {"cash": 10_000.0, "positions": {"DIPN": 10.0},
                     "allow_buys": True, "status": "active"}, screened)
    assert sink2.count("review_trigger") == 1
    add = [b for b in broker.market_buys if b.symbol == "DIPN"]
    assert len(add) == 1                                  # rung re-fired → ADD
    st = db.positions[("A", "DIPN")]["dcaState"]
    assert 0.20 in st["used"]                             # now consumed


# ── R1: budget-gate re-evaluation must not flip a completed review to deferred
# on the exec AFTER this pass's own persist_full created the full-tier row ─────


class _StepInterrupt(BaseException):
    """A BaseException (like an Inngest step suspension) — escapes the funnel's
    `except Exception` guards so exec 1 stops AT the interrupt step, mirroring a
    real replay boundary rather than the local degrade path."""


class _InterruptStep(_MemoStep):
    """Memoizing step fake that raises a suspension the FIRST time it reaches
    `interrupt_at` (after earlier steps have already run + persisted), then
    executes that step normally on the replay."""

    def __init__(self, interrupt_at):
        super().__init__()
        self._interrupt_at = interrupt_at
        self._fired = False

    async def run(self, step_id, fn):
        if step_id == self._interrupt_at and not self._fired:
            self._fired = True
            raise _StepInterrupt(step_id)
        return await super().run(step_id, fn)


async def _ws_writing_persist(db, ticker, run_date, result, current_price, screen_score):
    """persist_full stand-in that actually writes the full-tier funnel row the
    stage-B short-circuit reads back on the replay exec."""
    db._ws_rows[(ticker, run_date)] = SimpleNamespace(
        tier="full", escalationReasons=["sleeve_a_funnel"])
    return {"status": "upgraded", "signals": {}}


def test_r1_gate_flip_replay_keeps_review_not_deferred():
    """R1: exec 1 persists a paid review then interrupts at the dca-add step;
    on exec 2 the budget gate would return skip (the just-created full row
    saturates the cap), but the stage-B short-circuit must classify the symbol
    as reviewed — identical add_spend/trims to a no-interrupt run, and NO
    spurious budget_exhausted deferral journal."""
    analyze = {"action": "analyze"}
    skip = {"action": "skip", "reason": "budget_exhausted"}
    ctx = {"cash": 10_000.0, "positions": {"DIPN": 10.0},
           "allow_buys": True, "status": "active"}

    # Reference: one clean no-interrupt run (gate stays analyze throughout).
    ref_db = _ThDB({"DIPN": {"qty": 10.0}})
    ref_broker = _ThBroker(ref_db)
    ref_sink = _ReportSink()
    with _thesis_ctx([_th_pos_row("DIPN", 10.0, high_water=100.0)],
                     {"DIPN": _th_meta("buy", 2.0)}, analyze, ref_sink), \
         patch.object(saf, "persist_full", new=_ws_writing_persist):
        ref = _run_decide(ref_db, ref_broker, ctx, _rung_screened())
    assert ref["reviews"]["add_notional"] > 0             # baseline ADD fired

    # Interrupt-after-persist replay: gate flips analyze→skip; the fix must
    # never consult it on exec 2 (short-circuit fires first).
    db = _ThDB({"DIPN": {"qty": 10.0}})
    broker = _ThBroker(db)
    sink = _ReportSink()
    step = _InterruptStep(interrupt_at="dca-add-dipn")
    gate = AsyncMock(side_effect=[analyze, skip, skip, skip])

    def _decide():
        return _run(saf._decide_and_execute(
            db, broker, NOW, "neutral", sleeve_ctx=ctx,
            assembled={"active_themes": []}, screened=_rung_screened(),
            lights={"light_rows": {}, "spent": 0}, step=step))

    with _thesis_ctx([_th_pos_row("DIPN", 10.0, high_water=100.0)],
                     {"DIPN": _th_meta("buy", 2.0)}, analyze, sink), \
         patch.object(saf, "reuse_or_budget", new=gate), \
         patch.object(saf, "persist_full", new=_ws_writing_persist):
        interrupted = False
        try:
            _decide()                    # exec 1: persists, interrupts at dca-add
        except _StepInterrupt:
            interrupted = True
        assert interrupted               # exec 1 suspended AFTER persist
        out2 = _decide()                 # exec 2: the replay

    # (a) reviewed, not deferred
    assert out2["reviews"]["reviewed"] == ["DIPN"]
    assert out2["reviews"]["deferred"] == []
    # (b) identical add_spend / trims to the no-interrupt reference
    assert out2["reviews"]["add_notional"] == ref["reviews"]["add_notional"]
    assert (out2["decisions"].get("trims", [])
            == ref["decisions"].get("trims", []))
    # (c) no spurious "review deferred — budget_exhausted" journal
    assert not any("deferred" in t for t in sink.titles)


# ── Task 9: thesis-memo pipeline wiring ──────────────────────────────────────
# The memo is the ONLY buy authority (spec §3). An unusable memo is a NO-OP
# WEEK, not a quiet zero: nothing is bought, everything else (fills, exits,
# already-earned reviews) still runs, and the cron never raises.


class _MemoDB:
    """Fake db exposing only what the memo pipeline touches: the ThemeBasket
    stage write. Reuses the file's SimpleNamespace fake-db idiom."""

    def __init__(self):
        self.stage_writes = []
        self.themebasket = SimpleNamespace(update=self._update)

    async def _update(self, where, data):
        self.stage_writes.append((where["slug"], data["stage"]))


def test_memo_pipeline_parse_failure_is_noop_week(monkeypatch):
    """MemoParseError → engine_failure journal + None (no orders), never a raise."""
    async def fake_gather(db, outlook, book, candidates):
        return {"theses": []}

    monkeypatch.setattr(saf, "gather_memo_packet", fake_gather)
    monkeypatch.setattr(saf, "reason_memo", lambda packet: "NOT JSON")
    journaled = []

    async def fake_journal(db, rtype, sev, title, body):
        journaled.append((rtype, sev))

    monkeypatch.setattr(saf, "_journal", fake_journal)

    out = _run(saf._memo_pipeline(None, {}, [], {}, NOW, step=None))
    assert out is None
    assert ("engine_failure", "critical") in journaled


def test_memo_pipeline_persists_stages_and_returns_plan(monkeypatch):
    import json

    raw = json.dumps({"theses": [{"slug": "dc-energy", "stage": "crowded",
                                  "stage_rationale": "r", "evidence_this_week": [],
                                  "actions": [{"action": "review", "ticker": "MU"}]}],
                      "hypothesis_updates": [], "market_view": "v"})
    persisted = []

    async def fake_gather(db, outlook, book, candidates):
        return {"theses": []}

    async def fake_persist(db, week, raw_memo, memo):
        persisted.append((week, raw_memo, memo))

    monkeypatch.setattr(saf, "gather_memo_packet", fake_gather)
    monkeypatch.setattr(saf, "reason_memo", lambda packet: raw)
    monkeypatch.setattr(saf, "persist_memo", fake_persist)
    monkeypatch.setattr(saf, "write_report", AsyncMock())

    db = _MemoDB()
    plan = _run(saf._memo_pipeline(
        db, {}, [{"symbol": "MU", "qty": 10.0, "market_value": 1000.0}], {},
        NOW, step=None))

    assert plan["reviews"] == ["MU"]
    assert ("dc-energy", "crowded") in db.stage_writes
    assert persisted and persisted[0][0] == NOW.date().isoformat()
    assert persisted[0][1] == raw


def test_memo_pipeline_paid_call_is_its_own_memoized_step(monkeypatch):
    """The PAID reason_memo call lives in step "thesis-memo", persist in
    "memo-persist" — a persist retry must never re-bill (the $3.50 lesson).

    Gather is memoized INSIDE the paid step too: the function body re-executes
    at every step boundary, so an unmemoized gather re-queries theme state on
    each replay and a transient blip there would throw away an already-paid,
    already-persisted memo."""
    import json

    raw = json.dumps({"theses": [], "hypothesis_updates": [], "market_view": "v"})
    calls = {"paid": 0, "gather": 0}

    async def fake_gather(db, outlook, book, candidates):
        calls["gather"] += 1
        return {"theses": []}

    async def fake_persist(db, week, raw_memo, memo):
        pass

    def paid(packet):
        calls["paid"] += 1
        return raw

    monkeypatch.setattr(saf, "gather_memo_packet", fake_gather)
    monkeypatch.setattr(saf, "reason_memo", paid)
    monkeypatch.setattr(saf, "persist_memo", fake_persist)
    monkeypatch.setattr(saf, "write_report", AsyncMock())

    step = _MemoStep()
    _run(saf._memo_pipeline(_MemoDB(), {}, [], {}, NOW, step=step))
    _run(saf._memo_pipeline(_MemoDB(), {}, [], {}, NOW, step=step))   # replay

    assert calls["paid"] == 1                      # billed exactly once
    assert calls["gather"] == 1                    # and gathered exactly once
    assert set(step._log) == {"thesis-memo", "memo-persist"}


def test_memo_pipeline_gather_failure_is_noop_week(monkeypatch):
    """A gather failure inside the paid step is a no-op week, not a raise."""
    async def boom_gather(db, outlook, book, candidates):
        raise RuntimeError("theme state unavailable")

    monkeypatch.setattr(saf, "gather_memo_packet", boom_gather)
    monkeypatch.setattr(saf, "reason_memo", lambda packet: "unreached")
    journaled = []

    async def fake_journal(db, rtype, sev, title, body):
        journaled.append((rtype, sev))

    monkeypatch.setattr(saf, "_journal", fake_journal)

    assert _run(saf._memo_pipeline(None, {}, [], {}, NOW, step=None)) is None
    assert ("engine_failure", "critical") in journaled


def test_memo_pipeline_reports_prior_stage_for_transition_detection(monkeypatch):
    """The plan carries each thesis's PRE-memo stage so the caller can trigger
    on the transition into crowded/priced rather than on the stage state."""
    import json

    raw = json.dumps({"theses": [{"slug": "dc-energy", "stage": "crowded",
                                  "stage_rationale": "r", "evidence_this_week": [],
                                  "actions": []},
                                 {"slug": "robotics", "stage": "crowded",
                                  "stage_rationale": "r", "evidence_this_week": [],
                                  "actions": []}],
                      "hypothesis_updates": [], "market_view": "v"})

    async def fake_gather(db, outlook, book, candidates):
        # dc-energy was ALREADY crowded last week; robotics is moving into it.
        return {"theses": [{"slug": "dc-energy", "stage": "crowded"},
                           {"slug": "robotics", "stage": "catching_on"}]}

    async def fake_persist(db, week, raw_memo, memo):
        pass

    monkeypatch.setattr(saf, "gather_memo_packet", fake_gather)
    monkeypatch.setattr(saf, "reason_memo", lambda packet: raw)
    monkeypatch.setattr(saf, "persist_memo", fake_persist)
    monkeypatch.setattr(saf, "write_report", AsyncMock())

    plan = _run(saf._memo_pipeline(_MemoDB(), {}, [], {}, NOW, step=None))
    assert plan["prior_stages"] == {"dc-energy": "crowded",
                                    "robotics": "catching_on"}
    # Both stages still PERSIST — stage_updates is the persistence contract.
    assert plan["stage_updates"] == {"dc-energy": "crowded", "robotics": "crowded"}


def test_outlook_context_feeds_all_three_memo_crowdedness_inputs():
    """Spec §3.1 requires theme, sector AND industry RS as crowdedness inputs.
    _outlook_context is what the cron hands the memo, so its output must make
    all three non-None in the packet — sector RS was silently missing."""
    from execution.thesis import memo as memo_mod

    outlook_row = MagicMock(
        regime="neutral",
        industryRankings={"rankings": [{"etf": "SMH"}]},
        themeRankings={"rankings": [{"slug": "photonics"}]},
        sectorRankings=[{"etf": "XLE", "sector": "Energy"}],
    )

    async def fake_state(db, include_retired=True):
        return []

    async def fake_ledger(db, slugs):
        return {"by_theme": {}, "hypotheses": [], "study_digest": []}

    with patch.object(memo_mod, "_current_theme_state", new=fake_state), \
         patch.object(memo_mod, "load_ledger_context", new=fake_ledger):
        packet = _run(memo_mod.gather_memo_packet(
            MagicMock(), saf._outlook_context(outlook_row), [], {}))

    crowd = packet["crowdedness"]
    assert crowd["theme_rankings"] == [{"slug": "photonics"}]
    assert crowd["industry_rankings"] == [{"etf": "SMH"}]
    assert crowd["sector_rankings"] == [{"etf": "XLE", "sector": "Energy"}]
    assert packet["regime"] == "neutral"


def test_memo_reviews_and_crowded_stage_earn_reviews_not_trades():
    """Stage A union: a memo `review` action on a held name AND every holding
    whose sourcing theme just went crowded/priced earn a review under the
    trigger name "memo_stage" — a stage change NEVER trades by itself."""
    db = _ThDB({"MU": {"qty": 10.0}, "THM": {"qty": 10.0}})
    broker = _ThBroker(db)
    screened = {"ranked": [_screen_row("MU", price=100.0),
                           _screen_row("THM", price=100.0)],
                "close_by_symbol": {"MU": 100.0, "THM": 100.0},
                "sector_by_symbol": {}}
    latest = {"MU": _th_meta("buy", 2.0), "THM": _th_meta("buy", 2.0)}
    sink = _ReportSink()
    plan = {"entries": [], "adds": [], "reviews": ["MU"],
            "stage_updates": {"dc-energy": "crowded", "robotics": "catching_on"},
            "prior_stages": {"dc-energy": "catching_on", "robotics": "catching_on"},
            "rejected": []}

    with _thesis_ctx([_th_pos_row("MU", 10.0, high_water=101.0),
                      _th_pos_row("THM", 10.0, high_water=101.0)],
                     latest, {"action": "reuse", "signals": {"verdict": "buy"}},
                     sink, memo_plan=plan), \
         patch.object(saf, "_load_position_source_tags",
                      new=AsyncMock(return_value={
                          "THM": {"themes": ["dc-energy"]},
                          "MU": {"themes": ["robotics"]}})):
        out = _run_decide(db, broker,
                          {"cash": 500_000.0, "positions": {"MU": 10.0, "THM": 10.0},
                           "allow_buys": True, "status": "active"}, screened)

    trig = out["reviews"]["triggered"]
    assert sorted(trig) == ["MU", "THM"]
    assert trig["MU"] == ["memo_stage"]        # memo review action
    assert trig["THM"] == ["memo_stage"]       # sourcing theme went crowded
    assert sink.count("review_trigger") == 2
    # A stage change earns a review, never a trade.
    assert broker.sells == [] and broker.market_buys == []


def test_sticky_crowded_theme_does_not_retrigger_every_week():
    """memo_stage fires on the TRANSITION into crowded/priced, not on the
    state. stage_updates records every thesis's stage unconditionally, so a
    state filter would re-flag a sticky crowded theme's holdings EVERY week and
    burn the full-run budget forever. Same plan as the test above, except
    dc-energy was ALREADY crowded last week — THM must stay silent while the
    explicit `review` action on MU still fires."""
    db = _ThDB({"MU": {"qty": 10.0}, "THM": {"qty": 10.0}})
    broker = _ThBroker(db)
    screened = {"ranked": [_screen_row("MU", price=100.0),
                           _screen_row("THM", price=100.0)],
                "close_by_symbol": {"MU": 100.0, "THM": 100.0},
                "sector_by_symbol": {}}
    latest = {"MU": _th_meta("buy", 2.0), "THM": _th_meta("buy", 2.0)}
    sink = _ReportSink()
    plan = {"entries": [], "adds": [], "reviews": ["MU"],
            "stage_updates": {"dc-energy": "crowded"},
            "prior_stages": {"dc-energy": "crowded"},   # unchanged since last week
            "rejected": []}

    with _thesis_ctx([_th_pos_row("MU", 10.0, high_water=101.0),
                      _th_pos_row("THM", 10.0, high_water=101.0)],
                     latest, {"action": "reuse", "signals": {"verdict": "buy"}},
                     sink, memo_plan=plan), \
         patch.object(saf, "_load_position_source_tags",
                      new=AsyncMock(return_value={"THM": {"themes": ["dc-energy"]}})):
        out = _run_decide(db, broker,
                          {"cash": 500_000.0, "positions": {"MU": 10.0, "THM": 10.0},
                           "allow_buys": True, "status": "active"}, screened)

    assert sorted(out["reviews"]["triggered"]) == ["MU"]   # THM NOT re-flagged
    assert sink.count("review_trigger") == 1
    assert broker.sells == [] and broker.market_buys == []


def test_stage_deepening_crowded_to_priced_does_retrigger():
    """A theme moving crowded → priced IS a fresh move into a review stage."""
    db = _ThDB({"THM": {"qty": 10.0}})
    broker = _ThBroker(db)
    screened = {"ranked": [_screen_row("THM", price=100.0)],
                "close_by_symbol": {"THM": 100.0}, "sector_by_symbol": {}}
    sink = _ReportSink()
    plan = {"entries": [], "adds": [], "reviews": [],
            "stage_updates": {"dc-energy": "priced"},
            "prior_stages": {"dc-energy": "crowded"},
            "rejected": []}

    with _thesis_ctx([_th_pos_row("THM", 10.0, high_water=101.0)],
                     {"THM": _th_meta("buy", 2.0)},
                     {"action": "reuse", "signals": {"verdict": "buy"}},
                     sink, memo_plan=plan), \
         patch.object(saf, "_load_position_source_tags",
                      new=AsyncMock(return_value={"THM": {"themes": ["dc-energy"]}})):
        out = _run_decide(db, broker,
                          {"cash": 500_000.0, "positions": {"THM": 10.0},
                           "allow_buys": True, "status": "active"}, screened)

    assert out["reviews"]["triggered"] == {"THM": ["memo_stage"]}


def test_noop_memo_week_places_no_entries_but_still_runs_sells():
    """memo_plan None ⇒ the entry queue is EMPTY (no buy authority this week)
    while exits/trims still execute; the summary records status "noop"."""
    captured = {}

    async def fake_handshake(db_, client, entry_queue, cands, *a, **k):
        captured["entry_queue"] = list(entry_queue)
        return []

    sells = AsyncMock(return_value={"cash": 5000.0, "proceeds": 0.0, "sold": []})

    with patch.object(saf, "_load_latest_signals", new=AsyncMock(return_value={})), \
         patch.object(saf, "_load_position_source_tags", new=AsyncMock(return_value={})), \
         patch.object(saf, "_open_shadow_buys",
                      new=AsyncMock(return_value={"notional": 0.0, "symbols": set(),
                                                  "count": 0})), \
         patch.object(saf, "_theme_review", new=AsyncMock()), \
         patch.object(saf, "_memo_pipeline", new=AsyncMock(return_value=None)), \
         patch.object(saf, "_execute_sells", new=sells), \
         patch.object(saf, "_sleeve_b_sector_notional", new=AsyncMock(return_value={})), \
         patch.object(saf, "_handshake_and_enter", new=fake_handshake), \
         patch.object(saf, "full_runs_used", new=AsyncMock(return_value=0)), \
         patch.object(saf, "write_report", new=AsyncMock()):
        out = _run(saf._decide_and_execute(
            MagicMock(), MagicMock(), NOW, "neutral",
            sleeve_ctx={"cash": 10_000.0, "positions": {}, "allow_buys": True,
                        "status": "active"},
            assembled={"active_themes": []},
            screened={"ranked": [_screen_row("NEW")], "close_by_symbol": {},
                      "sector_by_symbol": {}},
            lights={"light_rows": {}, "spent": 0}, step=None,
        ))

    assert captured["entry_queue"] == []
    # ...but the sells stage still ran: a no-op memo blocks BUYS only.
    assert sells.await_count == 1
    assert out["sells"] == {"cash": 5000.0, "proceeds": 0.0, "sold": []}
    assert out["memo"] == {"status": "noop", "entries_planned": 0, "rejected": 0}


def test_memo_entries_and_adds_become_the_entry_queue():
    """The memo — not the screen ranking — is the buy authority: planned
    entries + adds ARE the entry queue, and plan_decisions gets no candidates."""
    captured = {}

    def capture_plan(holdings, equity, maxpos, **kwargs):
        return {"exits": [], "trims": [], "notes": []}

    async def fake_handshake(db_, client, planned, screens, *a, **k):
        # Task 10: the handshake receives the planner's entry DICTS (carrying
        # role/conviction/entry_style/why_now), not bare symbols.
        captured["entry_queue"] = [e["ticker"] for e in planned]
        captured["planned"] = list(planned)
        captured["screen_keys"] = sorted(screens)
        return []

    plan = {"entries": [_planned("NEW")], "adds": [_planned("HELD", action="add")],
            "reviews": [], "stage_updates": {}, "rejected": [{"ticker": "BAD"}]}

    with patch.object(saf, "_load_latest_signals", new=AsyncMock(return_value={})), \
         patch.object(saf, "_load_position_source_tags", new=AsyncMock(return_value={})), \
         patch.object(saf, "_open_shadow_buys",
                      new=AsyncMock(return_value={"notional": 0.0, "symbols": set(),
                                                  "count": 0})), \
         patch.object(saf, "_theme_review", new=AsyncMock()), \
         patch.object(saf, "_memo_pipeline", new=AsyncMock(return_value=plan)), \
         patch.object(saf, "plan_decisions", new=capture_plan), \
         patch.object(saf, "_execute_sells",
                      new=AsyncMock(return_value={"cash": 5000.0, "proceeds": 0.0,
                                                  "sold": []})), \
         patch.object(saf, "_sleeve_b_sector_notional", new=AsyncMock(return_value={})), \
         patch.object(saf, "_handshake_and_enter", new=fake_handshake), \
         patch.object(saf, "full_runs_used", new=AsyncMock(return_value=0)), \
         patch.object(saf, "write_report", new=AsyncMock()):
        out = _run(saf._decide_and_execute(
            MagicMock(), MagicMock(), NOW, "neutral",
            sleeve_ctx={"cash": 10_000.0, "positions": {}, "allow_buys": True,
                        "status": "active"},
            assembled={"active_themes": []},
            screened={"ranked": [_screen_row("SCREENPICK")], "close_by_symbol": {},
                      "sector_by_symbol": {}},
            lights={"light_rows": {}, "spent": 0}, step=None,
        ))

    # plan_decisions keeps its exits/trims job but has NO entry authority —
    # its signature no longer even accepts candidates (Task 11 founding-
    # premise guard, see tests/test_funnel_decisions.py).
    assert captured["entry_queue"] == ["NEW", "HELD"]
    assert "SCREENPICK" not in captured["entry_queue"]
    # ...and the memo's own reasoning rides along to the handshake.
    assert captured["planned"][0]["role"] == "anchor"
    assert captured["planned"][0]["why_now"] == "w"
    # screen_by_symbol is the raw screen map (sizing inputs), not a candidate table.
    assert captured["screen_keys"] == ["SCREENPICK"]
    assert out["memo"] == {"status": "ok", "entries_planned": 2, "rejected": 1}


# ── Task 10: entries come from the memo plan; diligence is VETO-ONLY ─────────
# The handshake no longer re-scores conviction: the memo already decided WHAT
# and HOW BIG (role × conviction). The paid full run is a veto (SELL/AVOID or
# unusable data), never a selector — and every placed order carries the memo's
# own words into the journal so the trade can be audited after the fact.

def _planned(sym="BE", **over):
    """A planner entry item (execution/thesis/planner.py) as the cron sees it."""
    item = {"slug": "dc-energy", "stage": "catching_on", "action": "enter",
            "ticker": sym, "role": "anchor", "conviction": 0.8,
            "entry_style": "on_pullback", "why_now": "w",
            "why_this_expression": "e"}
    item.update(over)
    return item


def _memo_screen(sym="BE", **over):
    row = {"symbol": sym, "price": 100.0, "sma20": 95.0, "atr": 4.0,
           "atr_pct": 0.04, "liquidity_adv_usd": 5e7, "screen_score": 6.0,
           "tags": {"themes": ["dc-energy"]}, "dist_200wma": 0.2}
    row.update(over)
    return row


def _handshake(planned, screens, **over):
    """Run the REAL _handshake_and_enter over a memo plan."""
    kwargs = {"run_date": NOW, "sleeve_equity": 100_000.0,
              "deployable": 100_000.0, "cash_available": 100_000.0,
              "holdings": [], "sector_by_symbol": {},
              "other_sleeve_sector_notional": {}, "allow_buys": True,
              "step": None}
    kwargs.update(over)
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    placed = _run(saf._handshake_and_enter(
        MagicMock(), client, planned_entries=planned,
        screen_by_symbol=screens, **kwargs))
    return placed, client


def test_entry_carries_memo_provenance_and_pullback_pricing():
    """A planned on_pullback entry submits at max(sma20, price - ATR) with the
    2-week patient TTL, and journals why_now/role/stage — the after-the-fact
    audit trail the memo is accountable to."""
    sink = _ReportSink()
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse",
                                                  "signals": {"verdict": "buy"}})), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "write_report", new=sink):
        placed, client = _handshake([_planned()], {"BE": _memo_screen()})

    assert len(placed) == 1
    kwargs = client.submit_limit_buy.call_args.kwargs
    assert kwargs["limit_price"] == 96.0                    # max(95, 100 - 4)
    assert (kwargs["expires_at"] - NOW).days == 14          # PATIENT_LIMIT_TTL_WEEKS
    j = kwargs["journal"]
    assert j["why_now"] == "w"
    assert j["why_this_expression"] == "e"
    assert j["role"] == "anchor"
    assert j["stage"] == "catching_on"
    assert j["slug"] == "dc-energy"
    assert j["entry_style"] == "on_pullback"
    assert j["memo_conviction"] == 0.8
    # convictionScore stays the daily-fills provenance key (now the 0-1 memo
    # conviction, not the old 0-100 formula score).
    assert j["convictionScore"] == 0.8
    assert j["ttl_days"] == 14
    # anchor band 0.08..0.12 → 0.8 conviction ⇒ 11.2% of a 100k sleeve.
    assert abs(placed[0]["notional"] - 11_200.0) < 1.0
    assert sink.count("entry_order") == 1


def test_at_market_entry_prices_at_last_close_with_one_week_ttl():
    """The other half of entry_price_and_ttl: at_market is a limit at the last
    close with a 1-week TTL."""
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse",
                                                  "signals": {"verdict": "buy"}})), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "write_report", new=AsyncMock()):
        placed, client = _handshake([_planned(entry_style="at_market")],
                                    {"BE": _memo_screen()})
    assert len(placed) == 1
    kwargs = client.submit_limit_buy.call_args.kwargs
    assert kwargs["limit_price"] == 100.0
    assert (kwargs["expires_at"] - NOW).days == 7


def test_sell_verdict_is_the_only_diligence_veto():
    """VETO-ONLY: a SELL verdict blocks the memo's entry and journals
    exit_sell_verdict; an ABSENT verdict (hold / no opinion) does NOT — the
    diligence run may only say no, it may never select."""
    sink = _ReportSink()
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse",
                                                  "signals": {"verdict": "sell"}})), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "write_report", new=sink):
        placed, client = _handshake([_planned()], {"BE": _memo_screen()})
    assert placed == []
    client.submit_limit_buy.assert_not_called()
    assert sink.count("exit_sell_verdict") == 1

    # ...and a None verdict still places: no conviction formula stands between
    # the memo and the order.
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse",
                                                  "signals": {"verdict": None}})), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "write_report", new=AsyncMock()):
        placed, client = _handshake([_planned()], {"BE": _memo_screen()})
    assert len(placed) == 1
    client.submit_limit_buy.assert_called_once()


def test_avoid_verdict_also_vetoes_the_memo_entry():
    sink = _ReportSink()
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse",
                                                  "signals": {"verdict": "AVOID"}})), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "write_report", new=sink):
        placed, client = _handshake([_planned()], {"BE": _memo_screen()})
    assert placed == []
    client.submit_limit_buy.assert_not_called()
    assert sink.count("exit_sell_verdict") == 1


def test_role_band_sizes_the_entry_not_a_conviction_formula():
    """Two identical screens, different memo roles ⇒ different notionals. The
    size comes from ROLE_BANDS × the memo's conviction, nothing else."""
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse",
                                                  "signals": {"verdict": "buy"}})), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "write_report", new=AsyncMock()):
        anchor, _ = _handshake([_planned("AN", role="anchor")],
                               {"AN": _memo_screen("AN")})
        catalyst, _ = _handshake([_planned("CA", role="catalyst")],
                                 {"CA": _memo_screen("CA")})
    assert anchor[0]["notional"] > catalyst[0]["notional"]


def test_incomplete_screen_row_journals_failure_not_an_order():
    sink = _ReportSink()
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse",
                                                  "signals": {"verdict": "buy"}})), \
         patch.object(saf, "write_report", new=sink):
        placed, client = _handshake([_planned()], {"BE": {"price": 100.0}})
    assert placed == []
    client.submit_limit_buy.assert_not_called()
    assert sink.count("engine_failure") == 1


def _decide_with_memo(plan, screened, open_buys, sleeve_ctx, sink,
                      gate=None, handshake=None, db=None, client=None):
    """_decide_and_execute with the memo pipeline stubbed and (by default) the
    REAL _handshake_and_enter."""
    patches = [
        patch.object(saf, "_load_latest_signals", new=AsyncMock(return_value={})),
        patch.object(saf, "_load_position_source_tags", new=AsyncMock(return_value={})),
        patch.object(saf, "_open_shadow_buys", new=AsyncMock(return_value=open_buys)),
        patch.object(saf, "_theme_review", new=AsyncMock()),
        patch.object(saf, "_memo_pipeline", new=AsyncMock(return_value=plan)),
        patch.object(saf, "_execute_sells",
                     new=AsyncMock(return_value={"cash": sleeve_ctx["cash"],
                                                 "proceeds": 0.0, "sold": []})),
        patch.object(saf, "_sleeve_b_sector_notional", new=AsyncMock(return_value={})),
        patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)),
        patch.object(saf, "full_runs_used", new=AsyncMock(return_value=0)),
        patch.object(saf, "reuse_or_budget",
                     new=gate or AsyncMock(return_value={"action": "reuse",
                                                         "signals": {"verdict": "buy"}})),
        patch.object(saf, "write_report", new=sink),
    ]
    if handshake is not None:
        patches.append(patch.object(saf, "_handshake_and_enter", new=handshake))
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        return _run(saf._decide_and_execute(
            db or MagicMock(), client or MagicMock(), NOW, "neutral",
            sleeve_ctx=sleeve_ctx, assembled={"active_themes": []},
            screened=screened, lights={"light_rows": {}, "spent": 0}, step=None,
        ))


def test_open_symbol_memo_entry_skips_before_paid_run():
    """Carry-over from Task 9: a symbol with a STANDING open buy is dropped
    from the memo's entry list BEFORE the handshake, so reuse_or_budget is
    never consulted for it and no paid full run is burned on an order the
    duplicate guard would have to throw away."""
    gate_calls = []

    async def counting_gate(db_, sym, run_date):
        gate_calls.append(sym)
        return {"action": "reuse", "signals": {"verdict": "buy"}}

    sink = _ReportSink()
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    plan = {"entries": [_planned("PENDING"), _planned("NEW")], "adds": [],
            "reviews": [], "stage_updates": {}, "rejected": [], "prior_stages": {}}
    screened = {"ranked": [_memo_screen("PENDING"), _memo_screen("NEW")],
                "close_by_symbol": {}, "sector_by_symbol": {}}

    out = _decide_with_memo(
        plan, screened,
        {"notional": 0.0, "symbols": {"PENDING"}, "count": 1},
        {"cash": 200_000.0, "positions": {}, "allow_buys": True,
         "status": "active"},
        sink, gate=counting_gate, client=client)

    assert gate_calls == ["NEW"]                       # PENDING never billed
    assert [p["symbol"] for p in out["placed"]] == ["NEW"]
    assert sink.count("entry_deferred") == 1


def test_memo_add_deduped_when_ladder_add_already_executed_this_pass():
    """A same-pass collision: the review-outcome DCA ladder ADD and the memo's
    `add` are the SAME intent. The executed ladder add wins; the memo add is
    dropped with an entry_deferred journal before any paid handshake."""
    db = _ThDB({"DIPN": {"qty": 10.0}})
    broker = _ThBroker(db)
    broker.submit_limit_buy = AsyncMock()
    sink = _ReportSink()
    plan = {"entries": [], "adds": [_planned("DIPN", action="add")],
            "reviews": [], "stage_updates": {}, "rejected": [], "prior_stages": {}}
    gate_calls = []
    captured = {}
    real_handshake = saf._handshake_and_enter

    async def counting_gate(db_, sym, run_date):
        gate_calls.append(sym)
        return {"action": "reuse", "signals": {"verdict": "buy"}}

    async def spy_handshake(*a, **k):
        captured["planned"] = list(a[2])
        return await real_handshake(*a, **k)

    with _thesis_ctx([_th_pos_row("DIPN", 10.0, high_water=100.0)],
                     {"DIPN": _th_meta("buy", 2.0)},
                     {"action": "reuse", "signals": {"verdict": "buy"}},
                     sink, memo_plan=plan), \
         patch.object(saf, "reuse_or_budget", new=counting_gate), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "_handshake_and_enter", new=spy_handshake):
        _run_decide(db, broker,
                    {"cash": 10_000.0, "positions": {"DIPN": 10.0},
                     "allow_buys": True, "status": "active"}, _rung_screened())

    assert [b.symbol for b in broker.market_buys] == ["DIPN"]   # ladder add ran
    assert sink.count("dca_add") == 1
    assert captured["planned"] == []                            # memo add dropped
    assert sink.count("entry_deferred") == 1
    # ...and dropped BEFORE any paid work: the ONE gate call is stage B's
    # review. A memo add that reached the handshake would gate DIPN twice.
    assert gate_calls == ["DIPN"]
    broker.submit_limit_buy.assert_not_called()


def test_rejected_ladder_add_leaves_the_memo_add_standing():
    """The dedupe keys off an ADD that actually EXECUTED. A rejected (zero-fill)
    ladder add bought nothing, so the memo's add must still reach the
    handshake — otherwise a broker rejection silently cancels the memo."""
    db = _ThDB({"DIPN": {"qty": 10.0}})
    broker = _RejectBroker(db)
    sink = _ReportSink()
    handshake = AsyncMock(return_value=[])
    plan = {"entries": [], "adds": [_planned("DIPN", action="add")],
            "reviews": [], "stage_updates": {}, "rejected": [], "prior_stages": {}}

    with _thesis_ctx([_th_pos_row("DIPN", 10.0, high_water=100.0)],
                     {"DIPN": _th_meta("buy", 2.0)},
                     {"action": "reuse", "signals": {"verdict": "buy"}},
                     sink, memo_plan=plan), \
         patch.object(saf, "_handshake_and_enter", new=handshake):
        _run_decide(db, broker,
                    {"cash": 10_000.0, "positions": {"DIPN": 10.0},
                     "allow_buys": True, "status": "active"}, _rung_screened())

    assert [e["ticker"] for e in handshake.await_args.args[2]] == ["DIPN"]


def test_replay_shrunken_envelope_cannot_double_order_via_memo_add():
    """D1 (Task 10 review): the duplicate-order failure class.

    `_open_shadow_buys` is a LIVE, unmemoized broker query, so a replay's
    deployable/cash envelope is smaller than the first execution's. When the
    ladder ADD's integer-qty gate lived OUTSIDE the memoized step, exec 2's
    shrunken envelope could push the halved rung under the gate — the step was
    never reached, `ladder_added` came back empty, and the memo's `add` sailed
    through the dedupe and placed a SECOND order for the same name under a
    different client_order_id (shadow-A-… vs paper-A-…-dca), which the broker's
    coid guard cannot catch.

    With sizing + gate INSIDE the step, the replay returns exec 1's recorded
    fill and the memo add is deferred.
    """
    db = _ThDB({"DIPN": {"qty": 10.0}})
    broker = _ThBroker(db)
    broker.submit_limit_buy = AsyncMock()
    sink = _ReportSink()
    step = _MemoStep()
    real_handshake = saf._handshake_and_enter
    plan = {"entries": [], "adds": [_planned("DIPN", action="add")],
            "reviews": [], "stage_updates": {}, "rejected": [], "prior_stages": {}}

    def _decide():
        return _run(saf._decide_and_execute(
            db, broker, NOW, "neutral",
            sleeve_ctx={"cash": 10_000.0, "positions": {"DIPN": 10.0},
                        "allow_buys": True, "status": "active"},
            assembled={"active_themes": []}, screened=_rung_screened(),
            lights={"light_rows": {}, "spent": 0}, step=step))

    # exec 1: nothing committed. exec 2 (the replay): the pass's own capital is
    # now standing at the broker, so deployable collapses to ~130 — enough for
    # the memo's fractional-qty add, NOT enough for the rung's integer-qty gate
    # at a $75 close. `symbols` stays empty so the standing-open-order dedupe
    # cannot mask the bug: `ladder_added` is the only thing holding the line.
    open_buys = AsyncMock(side_effect=[
        {"notional": 0.0, "symbols": set(), "count": 0},
        {"notional": 8_795.0, "symbols": set(), "count": 0},
    ])

    with _thesis_ctx([_th_pos_row("DIPN", 10.0, high_water=100.0)],
                     {"DIPN": _th_meta("buy", 2.0)},
                     {"action": "reuse", "signals": {"verdict": "buy"}},
                     sink, memo_plan=plan), \
         patch.object(saf, "_open_shadow_buys", new=open_buys), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "_handshake_and_enter", new=real_handshake):
        _decide()
        _decide()                                    # the replay

    # Exactly ONE ladder add, and NO shadow limit buy from the memo path.
    assert [b.symbol for b in broker.market_buys] == ["DIPN"]
    assert sink.count("dca_add") == 1
    broker.submit_limit_buy.assert_not_called()
    # The book moved exactly once, by exec 1's rung — the replay bought nothing.
    assert db.positions[("A", "DIPN")]["qty"] == 10.0 + broker.market_buys[0].qty


def test_memo_add_is_half_a_fresh_entry():
    """Owner ruling (DCA_TRANCHE_FRACTION): an ADD buys HALF a fresh entry's
    notional. Same role, same conviction, same screen — only `action` differs."""
    from execution.constants import DCA_TRANCHE_FRACTION

    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse",
                                                  "signals": {"verdict": "buy"}})), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "write_report", new=AsyncMock()):
        enter, _ = _handshake([_planned("EN", action="enter")],
                              {"EN": _memo_screen("EN")})
        add, add_client = _handshake([_planned("AD", action="add")],
                                     {"AD": _memo_screen("AD")})

    assert enter[0]["notional"] == 11_200.0                     # full anchor band
    assert add[0]["notional"] == enter[0]["notional"] * DCA_TRANCHE_FRACTION
    # ...and the journal says WHY it is half.
    j = add_client.submit_limit_buy.call_args.kwargs["journal"]
    assert j["add_tranche_fraction"] == DCA_TRANCHE_FRACTION
    assert j["action"] == "add"


def test_same_ticker_planned_twice_places_one_order():
    """Two theses naming the same expression must not stack two orders (and
    must not burn two paid full runs on it)."""
    gate_calls = []

    async def counting_gate(db_, sym, run_date):
        gate_calls.append(sym)
        return {"action": "reuse", "signals": {"verdict": "buy"}}

    sink = _ReportSink()
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    plan = {"entries": [_planned("DUP", slug="dc-energy"),
                        _planned("DUP", slug="grid-buildout")],
            "adds": [], "reviews": [], "stage_updates": {}, "rejected": [],
            "prior_stages": {}}
    screened = {"ranked": [_memo_screen("DUP")], "close_by_symbol": {},
                "sector_by_symbol": {}}

    out = _decide_with_memo(
        plan, screened, {"notional": 0.0, "symbols": set(), "count": 0},
        {"cash": 200_000.0, "positions": {}, "allow_buys": True,
         "status": "active"},
        sink, gate=counting_gate, client=client)

    assert gate_calls == ["DUP"]                     # billed once, not twice
    assert [p["symbol"] for p in out["placed"]] == ["DUP"]
    assert client.submit_limit_buy.await_count == 1
    assert sink.count("entry_deferred") == 1


# ── Task 12: end-to-end pass — REAL memo pipeline + REAL handshake ──────────
# Every test above stubs one side of the seam: either _memo_pipeline (so the
# trigger/outcome tests can pin a plan) or _handshake_and_enter (so the memo
# tests can read the entry queue). These three run BOTH for real inside
# _decide_and_execute — the pass as production runs it, with only the memo's
# two external edges faked (the theme-state gather and the PAID LLM call).
# _decide_and_execute is the most end-to-end seam the harness has: the
# registered Inngest function is None without the pip SDK (see
# test_module_imports_without_inngest_sdk), and its body is a thin step
# wrapper whose funnel_summary "memo" field is outcome["memo"] verbatim.


class _E2EDB(_ThDB):
    """_ThDB plus the two tables the REAL memo pipeline writes: the append-only
    evidence ledger and the ThemeBasket stage column."""

    def __init__(self, positions):
        super().__init__(positions)
        self.evidence = []
        self.stage_writes = []
        self.thesisevidence = SimpleNamespace(create=self._ev_create)
        self.themebasket = SimpleNamespace(update=self._tb_update)

    async def _ev_create(self, data):
        body = data.get("body")
        self.evidence.append({**data, "body": getattr(body, "data", body)})

    async def _tb_update(self, where, data):
        self.stage_writes.append((where["slug"], data["stage"]))

    def ledger_slugs(self, kind="weekly_memo"):
        return [e["themeSlug"] for e in self.evidence if e["kind"] == kind]


class _CoidBroker(_ThBroker):
    """Shadow-broker stand-in carrying the REAL duplicate guard: a
    client_order_id already booked is a no-op that returns the existing order
    (execution/broker/shadow_client.py). `attempts` records every submit the
    cron made, `limit_buys` only the ones that actually became orders — the
    gap between them is what a replay costs."""

    def __init__(self, db):
        super().__init__(db)
        self.limit_buys = []
        self.attempts = []
        self._booked = set()

    async def submit_limit_buy(self, symbol, qty, limit_price, expires_at,
                               journal, client_order_id):
        self.attempts.append(client_order_id)
        if client_order_id not in self._booked:
            self._booked.add(client_order_id)
            self.limit_buys.append(SimpleNamespace(
                symbol=symbol, qty=qty, limit_price=limit_price,
                expires_at=expires_at, journal=journal,
                client_order_id=client_order_id))
        return BrokerOrderResult(order_id=client_order_id, symbol=symbol,
                                 side="buy", status="shadow_open",
                                 filled_qty=0.0, filled_avg_price=None)


def _memo_raw(theses, hypotheses=(), market_view="mixed tape, capex intact"):
    """The verbatim JSON body the paid memo call returns."""
    import json
    return json.dumps({"theses": list(theses),
                       "hypothesis_updates": list(hypotheses),
                       "market_view": market_view})


def _thesis(slug, stage="catching_on", actions=(), evidence=("e",)):
    return {"slug": slug, "stage": stage, "stage_rationale": f"{slug} rationale",
            "evidence_this_week": list(evidence), "actions": list(actions)}


def _enter_action(ticker, **over):
    a = {"action": "enter", "ticker": ticker, "role": "anchor",
         "conviction": 0.8, "entry_style": "at_market",
         "why_now": "grid interconnect queue cleared",
         "why_this_expression": "the only pure-play on the bottleneck"}
    a.update(over)
    return a


@contextlib.contextmanager
def _e2e_ctx(pos_rows, sink, raw, prior_stages, calls, open_buys=None):
    """Everything _thesis_ctx patches EXCEPT the two seams under test:
    _memo_pipeline and _handshake_and_enter run FOR REAL, and so do
    persist_memo / append_evidence / plan_from_memo / _execute_sells. Only
    gather_memo_packet (theme state) and reason_memo (the PAID call) are
    faked — the memo's two external edges."""
    import importlib
    from execution.thesis import memo as memo_mod

    mdc_mod = importlib.import_module("research_swarm.data.market_data_client")
    mc = MagicMock()
    mc.get_earnings_dates.return_value = None

    async def fake_gather(db, outlook, book, candidates):
        calls["gather"] += 1
        calls.setdefault("packets", []).append(
            {"regime": (outlook or {}).get("regime"),
             "book": [b["symbol"] for b in book],
             "candidates": sorted(candidates)})
        # The pre-memo theme state: gather is what carries prior stages.
        return {"theses": [{"slug": s, "stage": st}
                           for s, st in prior_stages.items()]}

    def fake_reason(packet):
        calls["paid"] += 1
        return raw

    with patch.object(saf, "gather_memo_packet", new=fake_gather), \
         patch.object(saf, "reason_memo", new=fake_reason), \
         patch.object(memo_mod, "write_report", new=sink), \
         patch.object(saf, "_load_latest_signals", new=AsyncMock(return_value={})), \
         patch.object(saf, "_load_position_source_tags", new=AsyncMock(return_value={})), \
         patch.object(saf, "_open_shadow_buys",
                      new=AsyncMock(return_value=open_buys or
                                    {"notional": 0.0, "symbols": set(), "count": 0})), \
         patch.object(saf, "_sleeve_b_sector_notional", new=AsyncMock(return_value={})), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "full_runs_used", new=AsyncMock(return_value=0)), \
         patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse",
                                                  "signals": {"verdict": "buy"}})), \
         patch.object(saf, "run_paid_analysis", new=AsyncMock(return_value={})), \
         patch.object(saf, "persist_full",
                      new=AsyncMock(return_value={"status": "upgraded", "signals": {}})), \
         patch.object(saf, "write_report", new=sink), \
         patch("execution.sleeve_service.get_engine_positions",
               new=AsyncMock(return_value=pos_rows)), \
         patch("execution.sleeve_service.update_sleeve_cash", new=AsyncMock()), \
         patch.object(mdc_mod, "MarketDataClient", return_value=mc):
        yield


def _e2e_pass(db, broker, screened, cash=100_000.0, positions=None, step=None):
    return _run(saf._decide_and_execute(
        db, broker, NOW, "neutral",
        sleeve_ctx={"cash": cash, "positions": dict(positions or {}),
                    "allow_buys": True, "status": "active"},
        assembled={"active_themes": ["dc-energy", "robotics"]},
        screened=screened, lights={"light_rows": {}, "spent": 0}, step=step,
        outlook={"regime": "neutral"},
    ))


def test_full_pass_no_op_memo_places_nothing():
    """An all-HOLD memo is a healthy week, not a failure: the pass places
    NOTHING, journals the memo verbatim exactly once, reports memo.status "ok"
    (not "noop" — the memo was usable, it just said hold), and still appends
    one evidence-ledger row per thesis so next week's memo has this week's
    reasoning to reconcile against."""
    db = _E2EDB({})
    broker = _CoidBroker(db)
    sink = _ReportSink()
    calls = {"gather": 0, "paid": 0}
    raw = _memo_raw([
        _thesis("dc-energy", "catching_on",
                [{"action": "hold", "ticker": "BE"}]),
        _thesis("robotics", "pre_consensus",
                [{"action": "hold", "ticker": "ABB"}]),
    ])
    screened = {"ranked": [_memo_screen("BE"), _memo_screen("ABB")],
                "close_by_symbol": {}, "sector_by_symbol": {}}

    with _e2e_ctx([], sink, raw, {"dc-energy": "catching_on",
                                  "robotics": "pre_consensus"}, calls):
        out = _e2e_pass(db, broker, screened)

    # (1) zero submits of any kind — a hold memo buys nothing and sells nothing.
    assert broker.limit_buys == [] and broker.attempts == []
    assert broker.market_buys == [] and broker.sells == []
    assert out["placed"] == []
    # (2) the memo is journalled verbatim exactly once.
    assert sink.count("thesis_memo") == 1
    # (3) the funnel_summary "memo" fragment (outcome["memo"] verbatim).
    assert out["memo"] == {"status": "ok", "entries_planned": 0, "rejected": 0}
    # (4) one append-only ledger row per thesis, carrying the stage it was
    #     written at, plus the ThemeBasket stage persist.
    assert db.ledger_slugs() == ["dc-energy", "robotics"]
    assert [e["stage"] for e in db.evidence] == ["catching_on", "pre_consensus"]
    assert [e["week"] for e in db.evidence] == [NOW.date().isoformat()] * 2
    assert db.evidence[0]["body"]["stage_rationale"] == "dc-energy rationale"
    assert sorted(db.stage_writes) == [("dc-energy", "catching_on"),
                                       ("robotics", "pre_consensus")]
    # ...and the paid call ran exactly once for the pass, over the screened
    # universe (the memo may only name validated symbols).
    assert calls["gather"] == 1 and calls["paid"] == 1
    assert calls["packets"] == [{"regime": "neutral", "book": [],
                                 "candidates": ["ABB", "BE"]}]


def test_full_pass_memo_entry_places_order_with_provenance():
    """One catching_on `enter` at_market walks the whole pass: parse → plan →
    stage persist → dedupe → veto-only handshake → shadow limit buy at
    round(price, 2) under the deterministic client_order_id, with the memo's
    own words on the order. The spend envelope handed to the handshake is
    DECREMENTED by the standing-order commitment on both legs."""
    db = _E2EDB({})
    broker = _CoidBroker(db)
    sink = _ReportSink()
    calls = {"gather": 0, "paid": 0}
    raw = _memo_raw([_thesis("dc-energy", "catching_on", [_enter_action("BE")])])
    # 101.237 is deliberately un-round: at_market must submit at round(p, 2).
    screened = {"ranked": [_memo_screen("BE", price=101.237)],
                "close_by_symbol": {}, "sector_by_symbol": {}}
    captured = {}
    real_handshake = saf._handshake_and_enter

    async def spy_handshake(*a, **k):
        captured["planned"] = list(a[2])
        captured["sleeve_equity"], captured["deployable"] = a[5], a[6]
        captured["cash_available"] = a[7]
        return await real_handshake(*a, **k)

    with _e2e_ctx([], sink, raw, {"dc-energy": "catching_on"}, calls,
                  open_buys={"notional": 20_000.0, "symbols": set(), "count": 1}), \
         patch.object(saf, "_handshake_and_enter", new=spy_handshake):
        out = _e2e_pass(db, broker, screened)

    # (1) exactly ONE limit buy, priced at the rounded last close.
    assert len(broker.limit_buys) == 1
    order = broker.limit_buys[0]
    assert order.symbol == "BE"
    assert order.limit_price == 101.24                # round(101.237, 2)
    assert (order.expires_at - NOW).days == 7         # at_market TTL
    # (2) the deterministic coid — the duplicate-order guard's key.
    assert order.client_order_id == "shadow-A-BE-20260713"
    # (3) the memo's reasoning rides on the order, so the trade can be graded
    #     after the fact on WHY, not on a score.
    j = order.journal
    assert j["why_now"] == "grid interconnect queue cleared"
    assert j["why_this_expression"] == "the only pure-play on the bottleneck"
    assert j["stage"] == "catching_on"
    assert j["slug"] == "dc-energy"
    assert j["role"] == "anchor" and j["memo_conviction"] == 0.8
    assert j["entry_style"] == "at_market"
    # (4) deployable/cash are DECREMENTED by the standing-order commitment:
    #     0.9 (neutral) x 100k equity - 0 position MV - 20k committed, and the
    #     cash ledger less the same 20k. Both, not just one.
    assert captured["sleeve_equity"] == 100_000.0
    assert captured["deployable"] == 70_000.0
    assert captured["cash_available"] == 80_000.0
    # ...and the order was sized inside that envelope (anchor band x 0.8).
    assert out["placed"] == [{
        "symbol": "BE", "qty": order.qty, "limit_price": 101.24,
        "notional": 11_200.0, "client_order_id": "shadow-A-BE-20260713",
        "expires_at": order.expires_at.isoformat()}]
    assert out["memo"] == {"status": "ok", "entries_planned": 1, "rejected": 0}
    assert sink.count("entry_order") == 1
    assert sink.count("thesis_memo") == 1
    assert db.ledger_slugs() == ["dc-energy"]
    # The planner's dict — not a bare symbol — is what reached the handshake.
    assert [e["ticker"] for e in captured["planned"]] == ["BE"]


def test_replay_does_not_rebill_memo():
    """The $3.50 guarantee under the Inngest replay model: two executions of
    the pass sharing ONE step log bill the paid memo call exactly ONCE, persist
    it once, and — because the handshake is NOT memoized and re-submits on the
    replay — leave exactly ONE order standing, caught by the deterministic
    client_order_id the broker dedupes on."""
    db = _E2EDB({})
    broker = _CoidBroker(db)
    sink = _ReportSink()
    calls = {"gather": 0, "paid": 0}
    raw = _memo_raw([_thesis("dc-energy", "catching_on", [_enter_action("BE")])])
    screened = {"ranked": [_memo_screen("BE", price=101.237)],
                "close_by_symbol": {}, "sector_by_symbol": {}}
    step = _MemoStep()

    with _e2e_ctx([], sink, raw, {"dc-energy": "catching_on"}, calls):
        out1 = _e2e_pass(db, broker, screened, step=step)
        out2 = _e2e_pass(db, broker, screened, step=step)   # the replay

    # (1) billed once — and gathered once, since gather lives INSIDE the paid
    #     step (a re-gather on replay can discard an already-paid memo).
    assert calls["paid"] == 1
    assert calls["gather"] == 1
    assert set(step._log) >= {"thesis-memo", "memo-persist"}
    # (2) persisted once: one journal row, one ledger row, one stage write.
    assert sink.count("thesis_memo") == 1
    assert db.ledger_slugs() == ["dc-energy"]
    assert db.stage_writes == [("dc-energy", "catching_on")]
    # (3) the plan is identical across the replay (parse/plan re-derived from
    #     the memoized raw), so the replay re-submits...
    assert out1["memo"] == out2["memo"] == {"status": "ok", "entries_planned": 1,
                                            "rejected": 0}
    assert broker.attempts == ["shadow-A-BE-20260713"] * 2
    # (4) ...but ONE order exists: the coid guard collapsed the duplicate.
    assert len(broker.limit_buys) == 1
    assert broker.limit_buys[0].limit_price == 101.24
