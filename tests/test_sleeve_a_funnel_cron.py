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
    (b) treats standing shadow-open buy notionals as committed capital,
    subtracting them from BOTH cash_available and deployable."""
    db = MagicMock()
    # One standing shadow buy worth $1,000 from a previous pass.
    db.enginetrade.find_many = AsyncMock(return_value=[
        MagicMock(qty=50.0, limitPrice=20.0, notional=1000.0, side="buy",
                  status="shadow_open"),
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
            db, MagicMock(), NOW, "neutral",
            sleeve_ctx={"cash": 10_000.0, "positions": {},
                        "allow_buys": True, "status": "active"},
            assembled={}, screened={"ranked": [], "close_by_symbol": {},
                                    "sector_by_symbol": {}},
            lights={"light_rows": {}, "spent": 0}, step=None,
        ))

    # Committed $1,000 comes off both spendable envelopes:
    # cash: 10,000 (post-sells ledger) − 1,000 = 9,000
    # deployable: 0.7 (neutral) × 10,000 equity − 0 MV − 1,000 = 6,000
    assert captured["cash_available"] == 9000.0
    assert captured["deployable"] == 6000.0
    # And placing a buy writes NO cash — the daily fill (or expiry) decides.
    cash_write.assert_not_called()
    assert len(out["placed"]) == 1


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

    def capture_plan(holdings, candidates, equity, maxpos):
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

    def capture_plan(holdings, candidates, equity, maxpos):
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
