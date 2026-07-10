# tests/test_sleeve_a_funnel_cron.py
"""Funnel cron: gates, budget discipline, shadow orders, journal."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import inngest_app.functions.sleeve_a_funnel as saf

NOW = datetime(2026, 7, 13, 16, 0, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


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
