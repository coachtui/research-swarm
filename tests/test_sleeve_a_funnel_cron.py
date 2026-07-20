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
    db = MagicMock()
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "skip",
                                                  "reason": "budget_exhausted"})), \
         patch.object(saf, "write_report", new=AsyncMock()) as report:
        placed = _run(saf._handshake_and_enter(
            db, client, entry_queue=["AEHR"],
            candidates_by_symbol={"AEHR": {"conviction": 80.0, "screen": {
                "price": 20.0, "sma20": 19.0, "atr": 1.0, "atr_pct": 0.05,
                "ext_atr": 0.5, "liquidity_adv_usd": 5e6,
                "tags": {"themes": ["photonics"]}, "screen_score": 6.0}}},
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
    db = MagicMock()
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    signals = {"verdict": "hold", "fairValue": 26.0, "insiderScore": 7.0,
               "darkPoolScore": None, "sentimentScore": 6.0}
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse", "signals": signals})), \
         patch.object(saf, "write_report", new=AsyncMock()):
        placed = _run(saf._handshake_and_enter(
            db, client, entry_queue=["AEHR"],
            candidates_by_symbol={"AEHR": {"conviction": 80.0, "screen": {
                "price": 20.0, "sma20": 19.0, "atr": 1.0, "atr_pct": 0.05,
                "ext_atr": 0.5, "liquidity_adv_usd": 5e6,
                "tags": {"themes": ["photonics"]}, "screen_score": 6.0}}},
            run_date=NOW, sleeve_equity=70_000.0, deployable=49_000.0,
            cash_available=49_000.0, holdings=[], sector_by_symbol={},
            other_sleeve_sector_notional={}, allow_buys=True, step=None,
        ))
    assert len(placed) == 1
    kwargs = client.submit_limit_buy.call_args.kwargs
    assert kwargs["client_order_id"] == "shadow-A-AEHR-20260713"
    assert kwargs["limit_price"] == 20.0          # not extended → limit at close


def test_outlook_rankings_dicts_unwrap_and_reach_consumers():
    """MarketOutlook.industryRankings/themeRankings are DICTS shaped
    {"rankings": [...], "rotations": [...], "missing": [...]} (see
    execution/indicators/industry_strength.py). Lock the shape: the unwrapped
    rankings LIST must reach fetch_industry_holdings and the top-industries /
    top-themes slices in _screen."""
    import pandas as pd

    industry_rankings = [{"etf": "SMH", "industry": "Semiconductors", "rank_1m": 1}]
    theme_rankings = [{"slug": "photonics", "rank_1m": 1}]
    outlook_row = MagicMock(
        regime="neutral",
        industryRankings={"rankings": industry_rankings, "rotations": [],
                          "missing": []},
        themeRankings={"rankings": theme_rankings, "rotations": [],
                       "missing": []},
    )
    ctx = saf._outlook_context(outlook_row)
    assert ctx["industryRankings"] == industry_rankings
    assert ctx["themeRankings"] == theme_rankings

    # _assemble: the unwrapped LIST reaches fetch_industry_holdings verbatim.
    db = MagicMock()
    fih = MagicMock(return_value={"SMH": ["AEHR"]})
    with patch("execution.funnel.universe.load_theme_members",
               new=AsyncMock(return_value={"photonics": ["AEHR"]})), \
         patch("execution.funnel.universe.fetch_industry_holdings", new=fih), \
         patch("execution.research_feed.get_research_context",
               new=AsyncMock(return_value={"watchlist": []})):
        assembled = _run(saf._assemble(db, ctx, holdings=[]))
    fih.assert_called_once_with(industry_rankings)
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


def test_full_run_sell_verdict_vetoes_entry():
    db = MagicMock()
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse",
                                                  "signals": {"verdict": "sell"}})), \
         patch.object(saf, "write_report", new=AsyncMock()):
        placed = _run(saf._handshake_and_enter(
            db, client, entry_queue=["BAD"],
            candidates_by_symbol={"BAD": {"conviction": 80.0, "screen": {
                "price": 20.0, "sma20": 19.0, "atr": 1.0, "atr_pct": 0.05,
                "ext_atr": 0.5, "liquidity_adv_usd": 5e6, "tags": {"themes": []},
                "screen_score": 6.0}}},
            run_date=NOW, sleeve_equity=70_000.0, deployable=49_000.0,
            cash_available=49_000.0, holdings=[], sector_by_symbol={},
            other_sleeve_sector_notional={}, allow_buys=True, step=None,
        ))
    assert placed == []
    client.submit_limit_buy.assert_not_called()


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

    def capture_plan(holdings, candidates, equity, maxpos, **kwargs):
        captured["holdings"] = holdings
        captured["max_positions"] = maxpos
        return real_plan(holdings, candidates, equity, maxpos)

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

    def capture_plan(holdings, candidates, equity, maxpos, **kwargs):
        captured["symbols"] = [c["symbol"] for c in candidates]
        captured["max_positions"] = maxpos
        return {"exits": [], "trims": [], "entry_queue": [], "notes": []}

    screened = {"ranked": [_screen_row("PENDING"), _screen_row("NEW")],
                "close_by_symbol": {}, "sector_by_symbol": {}}
    with patch.object(saf, "_load_latest_signals", new=AsyncMock(return_value={})), \
         patch.object(saf, "_load_position_source_tags", new=AsyncMock(return_value={})), \
         patch.object(saf, "_open_shadow_buys",
                      new=AsyncMock(return_value={"notional": 1000.0,
                                                  "symbols": {"PENDING"}, "count": 1})), \
         patch.object(saf, "_theme_review", new=AsyncMock()), \
         patch.object(saf, "_execute_sells",
                      new=AsyncMock(return_value={"cash": 5000.0, "proceeds": 0.0, "sold": []})), \
         patch.object(saf, "_sleeve_b_sector_notional", new=AsyncMock(return_value={})), \
         patch.object(saf, "_handshake_and_enter", new=AsyncMock(return_value=[])), \
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
    base = {"momentum": 10.0, "hunting_bonus": 10.0, "market_cap": 5e10,
            "valuation_score": 10.0}
    screen = {"price": 20.0, "sma20": 19.0, "atr": 1.0, "atr_pct": 0.02,
              "ext_atr": 0.5, "liquidity_adv_usd": 1e9, "screen_score": 6.0,
              "tags": {"themes": ["t"]}}
    cands = {s: {"screen": dict(screen), "conv_input": dict(base)}
             for s in ("N1", "N2", "N3")}
    signals = {"verdict": "buy", "insiderScore": 10.0, "darkPoolScore": 10.0,
               "sentimentScore": 10.0, "fairValue": 40.0}
    client = MagicMock()
    client.submit_limit_buy = AsyncMock()
    with patch.object(saf, "reuse_or_budget",
                      new=AsyncMock(return_value={"action": "reuse", "signals": signals})), \
         patch.object(saf, "_latest_full_signal_id", new=AsyncMock(return_value=None)), \
         patch.object(saf, "write_report", new=AsyncMock()):
        placed = _run(saf._handshake_and_enter(
            MagicMock(), client, entry_queue=["N1", "N2", "N3"],
            candidates_by_symbol=cands, run_date=NOW, sleeve_equity=sleeve_equity,
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

    def capture_plan(holdings, candidates, equity, maxpos, **kwargs):
        captured["holdings"] = holdings
        return {"exits": [], "trims": [], "entry_queue": [], "notes": []}

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
def _thesis_ctx(pos_rows, latest, reuse_action, sink):
    """Patch every collaborator so the REAL _decide_and_execute + _execute_sells
    run end to end while stage A/B inputs are controlled. `latest` may be a list
    (side_effect: initial then post-review refresh) or a single dict."""
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
