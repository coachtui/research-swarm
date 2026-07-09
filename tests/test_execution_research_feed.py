"""research_feed: defensive, read-only, schema-drift-proof."""
import pytest

from execution.research_feed import _collect_names_by_keys, get_research_context


def test_collector_finds_nested_supply_chain_keys():
    blob = {"agents": {"fundamentalist": {
        "customers": ["NVDA", "Super Micro"], "suppliers": ["TSMC"],
        "other": {"key_suppliers": ["SK Hynix"]},
    }}}
    out: list = []
    _collect_names_by_keys(blob, ("customers", "suppliers", "key_customers", "key_suppliers"), out)
    assert set(out) == {"NVDA", "Super Micro", "TSMC", "SK Hynix"}


def test_collector_ignores_non_list_and_non_str_values():
    out: list = []
    _collect_names_by_keys({"customers": "NVDA", "suppliers": [1, {"x": 1}, "AMD"]},
                           ("customers", "suppliers"), out)
    assert out == ["AMD"]


class _Table:
    def __init__(self, rows=None, fail=False):
        self._rows, self._fail = rows or [], fail

    async def find_many(self, **kwargs):
        if self._fail:
            raise RuntimeError("db down")
        return self._rows


class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.mark.asyncio
async def test_context_is_all_empty_on_db_failure():
    class Db:
        watchlist = _Table(fail=True)
        stockresult = _Table(fail=True)
    ctx = await get_research_context(Db())
    assert ctx == {"watchlist": [], "supply_chain": [], "news_entities": []}


@pytest.mark.asyncio
async def test_context_dedupes_and_uppercases_watchlist():
    class Db:
        watchlist = _Table(rows=[_Row(ticker="aehr"), _Row(ticker="AEHR"), _Row(ticker="VIAV")])
        stockresult = _Table(rows=[_Row(fullOutput=None)])
    ctx = await get_research_context(Db())
    assert ctx["watchlist"] == ["AEHR", "VIAV"]


@pytest.mark.asyncio
async def test_context_wires_supply_chain_and_news_keys_to_output_fields():
    blob = {"agents": {
        "fundamentalist": {"customers": ["NVDA"], "suppliers": ["TSMC"]},
        "news_hound": {"entities": ["CoreWeave"]},
    }}

    class Db:
        watchlist = _Table(rows=[])
        stockresult = _Table(rows=[_Row(fullOutput=blob)])

    ctx = await get_research_context(Db())
    assert ctx["supply_chain"] == ["NVDA", "TSMC"]
    assert ctx["news_entities"] == ["CoreWeave"]


@pytest.mark.asyncio
async def test_context_partial_failure_watchlist_down_stockresult_up():
    blob = {"agents": {"fundamentalist": {"suppliers": ["TSMC"]}}}

    class Db:
        watchlist = _Table(fail=True)
        stockresult = _Table(rows=[_Row(fullOutput=blob)])

    ctx = await get_research_context(Db())
    assert ctx["watchlist"] == []
    assert ctx["supply_chain"] == ["TSMC"]
