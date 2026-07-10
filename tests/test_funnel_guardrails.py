"""Aggregate caps: overlapping themes double-count; sector cap spans sleeves."""
from execution.constants import MAX_SECTOR_PCT_OF_ACCOUNT, MAX_THEME_PCT_OF_SLEEVE
from execution.engine.guardrails import enforce_funnel_guardrails

SLEEVE, ACCOUNT = 70_000.0, 100_000.0


def _order(sym, notional, themes=(), sector=None):
    return {"symbol": sym, "side": "buy", "notional": notional,
            "tags": {"themes": list(themes)}, "sector": sector}


def _hold(sym, mv, themes=(), sector=None):
    return {"symbol": sym, "market_value": mv, "tags": {"themes": list(themes)},
            "sector": sector}


def test_theme_cap_counts_existing_exposure():
    cap = MAX_THEME_PCT_OF_SLEEVE * SLEEVE                      # 24,500
    holdings = [_hold("A", 20_000, themes=["photonics"])]
    orders = [_order("B", 8_000, themes=["photonics"])]
    adjusted, notes = enforce_funnel_guardrails(
        orders, SLEEVE, ACCOUNT, cash_available=50_000.0, holdings=holdings,
        other_sleeve_sector_notional={}, allow_buys=True,
    )
    assert adjusted[0]["notional"] == round(cap - 20_000, 2)    # capped to 4,500
    assert any("photonics" in n for n in notes)


def test_overlapping_name_counts_against_every_theme():
    holdings = [_hold("A", 20_000, themes=["photonics", "chips"])]
    orders = [_order("B", 8_000, themes=["chips"])]
    adjusted, _ = enforce_funnel_guardrails(
        orders, SLEEVE, ACCOUNT, 50_000.0, holdings, {}, True,
    )
    cap = MAX_THEME_PCT_OF_SLEEVE * SLEEVE
    assert adjusted[0]["notional"] == round(cap - 20_000, 2)


def test_sector_cap_spans_sleeves():
    cap = MAX_SECTOR_PCT_OF_ACCOUNT * ACCOUNT                   # 35,000
    holdings = [_hold("A", 10_000, sector="Technology")]
    orders = [_order("B", 10_000, sector="Technology")]
    adjusted, notes = enforce_funnel_guardrails(
        orders, SLEEVE, ACCOUNT, 50_000.0, holdings,
        other_sleeve_sector_notional={"Technology": 20_000.0}, allow_buys=True,
    )
    assert adjusted[0]["notional"] == round(cap - 30_000, 2)    # 5,000 left
    assert any("sector" in n.lower() for n in notes)


def test_halted_drops_buys_sells_pass():
    orders = [_order("B", 5_000), {"symbol": "A", "side": "sell",
                                   "est_notional": 3_000.0, "qty": 10}]
    adjusted, notes = enforce_funnel_guardrails(
        orders, SLEEVE, ACCOUNT, 50_000.0, [], {}, allow_buys=False,
    )
    assert [o["side"] for o in adjusted] == ["sell"]
    assert any("halted" in n for n in notes)


def test_cash_includes_sell_proceeds_and_dust_dropped():
    orders = [{"symbol": "A", "side": "sell", "est_notional": 3_000.0, "qty": 10},
              _order("B", 3_500)]
    adjusted, _ = enforce_funnel_guardrails(
        orders, SLEEVE, ACCOUNT, cash_available=1_000.0, holdings=[],
        other_sleeve_sector_notional={}, allow_buys=True,
    )
    buy = [o for o in adjusted if o["side"] == "buy"][0]
    assert buy["notional"] == 3_500.0                            # 1k cash + 3k proceeds
    adjusted2, _ = enforce_funnel_guardrails(
        [_order("C", 3_500)], SLEEVE, ACCOUNT, cash_available=0.5, holdings=[],
        other_sleeve_sector_notional={}, allow_buys=True,
    )
    assert adjusted2 == []                                       # below $1 Alpaca minimum
