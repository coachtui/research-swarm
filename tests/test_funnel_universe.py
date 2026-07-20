"""Universe assembly: merge/tag/dedupe/floors. Pure functions — no network."""
from execution.funnel.universe import apply_floors, merge_sources


def _tags(**over):
    base = {"themes": [], "industries": [], "watchlist": False, "holding": False}
    base.update(over)
    return base


def test_merge_tags_and_dedupes_across_sources():
    tagged = merge_sources(
        theme_members={"photonics": ["aehr", "LASR"], "memory-hbm": ["RMBS", "AEHR"]},
        industry_holdings={"SMH": ["NVDA", "RMBS"]},
        watchlist=["nvda", "VIAV"],
        holdings=["LASR"],
    )
    assert tagged["AEHR"] == _tags(themes=["memory-hbm", "photonics"])
    assert tagged["RMBS"] == _tags(themes=["memory-hbm"], industries=["SMH"])
    assert tagged["NVDA"] == _tags(industries=["SMH"], watchlist=True)
    assert tagged["LASR"] == _tags(themes=["photonics"], holding=True)
    assert tagged["VIAV"] == _tags(watchlist=True)


def test_merge_excludes_signal_instruments():
    tagged = merge_sources(
        theme_members={}, industry_holdings={"SMH": ["SMH", "SPY", "XLK", "IWM", "NVDA"]},
        watchlist=["RSP"], holdings=[],
    )
    assert set(tagged) == {"NVDA"}


def test_floors_exclude_and_journal_reasons():
    tagged = {
        "OK": _tags(), "THIN": _tags(), "TINY": _tags(), "PENNY": _tags(), "DARK": _tags(),
        "NOCAP": _tags(),
    }
    metrics = {
        "OK":    {"adv_usd": 5e6, "market_cap": 5e8, "price": 20.0},
        "THIN":  {"adv_usd": 5e5, "market_cap": 5e8, "price": 20.0},
        "TINY":  {"adv_usd": 5e6, "market_cap": 9e7, "price": 20.0},
        "PENNY": {"adv_usd": 5e6, "market_cap": 5e8, "price": 1.5},
        "DARK":  {"adv_usd": None, "market_cap": 5e8, "price": None},
        "NOCAP": {"adv_usd": 5e6, "market_cap": None, "price": 20.0},
    }
    kept, excluded = apply_floors(tagged, metrics)
    assert set(kept) == {"OK", "NOCAP"}          # unknown mcap passes (sanity net)
    reasons = {e["symbol"]: e["reason"] for e in excluded}
    assert reasons == {
        "THIN": "adv_below_floor", "TINY": "mcap_below_floor",
        "PENNY": "price_below_floor", "DARK": "no_price_data",
    }


def test_floors_exclude_non_alpaca_tradable_symbols():
    """A foreign listing surfaced by an ETF's top-holdings feed (Air Canada
    as "AC.TO" via the JETS airline ETF) or a delisted/acquired ticker a data
    vendor hasn't dropped (e.g. JNPR post-HPE-acquisition) must never reach
    screening/entry just because it still prices — Alpaca can't trade it."""
    tagged = {"OK": _tags(), "AC.TO": _tags(), "JNPR": _tags()}
    metrics = {
        "OK":    {"adv_usd": 5e6, "market_cap": 5e8, "price": 20.0},
        "AC.TO": {"adv_usd": 5e6, "market_cap": 5e9, "price": 18.0},
        "JNPR":  {"adv_usd": 5e6, "market_cap": 5e9, "price": 40.0},
    }
    kept, excluded = apply_floors(tagged, metrics, tradable_symbols={"OK"})
    assert set(kept) == {"OK"}
    reasons = {e["symbol"]: e["reason"] for e in excluded}
    assert reasons == {"AC.TO": "not_alpaca_tradable", "JNPR": "not_alpaca_tradable"}


def test_floors_skip_tradability_gate_when_lookup_unavailable():
    """tradable_symbols=None (the default) means the Alpaca lookup failed or
    wasn't attempted — degrade to no gate rather than freezing the screen."""
    tagged = {"OK": _tags()}
    metrics = {"OK": {"adv_usd": 5e6, "market_cap": 5e8, "price": 20.0}}
    kept, excluded = apply_floors(tagged, metrics, tradable_symbols=None)
    assert set(kept) == {"OK"}
    assert excluded == []
