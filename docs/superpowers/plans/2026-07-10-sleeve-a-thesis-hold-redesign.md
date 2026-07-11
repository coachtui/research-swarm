# Sleeve A Thesis-Hold Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Sleeve A's exit authority from price mechanics (stops, evictions, weight trims) to LLM thesis reviews with four triggers (staleness, earnings-divergence, ladder rungs, concentration) and three new outcomes (ADD / TRIM / SELL-via-verdict), raise exposure floors Sleeve-A-only, and add the 200-week-MA input and the SALP revealed-behavior reasoning block.

**Architecture:** All decision changes live in the weekly funnel cron and pure funnel modules; the daily cron keeps ratcheting `highWaterClose` (the ladder anchor) but never sells; `plan_decisions` grows opt-out parameters so the Tier 2 backtest harness keeps its old-mechanics fidelity; one additive Json column (`EnginePosition.dcaState`) persists rung state.

**Tech Stack:** Python 3.9 (`python3`, not `python`), prisma-client-py (0.15 — NO Json path filters), Inngest SDK 0.5.x, yfinance, pytest with the complete prisma stub in `tests/conftest.py`.

## Global Constraints

- **Sleeve B is a frozen control group.** `REGIME_INVESTED_FRACTION` in `execution/constants.py:68` is read by `execution/engine/sleeve_b.py:82` — it must NOT be edited. Sleeve A gets its own constant.
- **Backtest harness fidelity:** `execution/backtest/` models the OLD mechanics and must be behaviorally unchanged (its suites `tests/test_backtest_*.py` pass untouched). `plan_decisions` keeps eviction/trim behavior by default; only the live funnel opts out.
- **Review-only sells invariant:** after this plan, no price or weight level sells a Sleeve A share of any size; delisting/corporate action is the sole exception. Rungs and concentration only *trigger reviews*.
- **Paper only.** No real-money paths. Sleeve A `SleeveState.mode` stays as-is.
- Journal/report types are additive only; existing `REPORT_TYPES` strings unchanged.
- Migrations: hand-write SQL + `python3 -m prisma migrate deploy` (NEVER `migrate dev` — shadow-DB baseline always fails; see project memory).
- Run tests with `python3 -m pytest <paths> -q --no-cov` (the repo-wide coverage gate fails any subset run).
- Baseline test debt: the full suite has ~75 pre-existing failures/20 errors on main (legacy, unrelated). The gate for this plan: every `tests/test_funnel_*.py`, `tests/test_backtest_*.py`, `tests/test_execution_*.py`, `tests/test_theme_*.py`, and every NEW test passes.
- Branch: create `sleeve-a-thesis-hold` off `main` AFTER `phase3d-tier2-backtest` merges (the spec's evidence chain should be in history first).
- Spec: `docs/superpowers/specs/2026-07-10-sleeve-a-thesis-hold-redesign-design.md`.

---

### Task 1: Spec amendments forced by code exploration

**Files:**
- Modify: `docs/superpowers/specs/2026-07-10-sleeve-a-thesis-hold-redesign-design.md`

Exploration found four facts the spec didn't know. Amend it first so the spec stays the source of truth:

- [ ] **Step 1: Edit the spec** — make these four wording changes:

1. Mechanical change 1 (exposure floors): replace "`REGIME_INVESTED_FRACTION` becomes …" with: "a new Sleeve-A-only constant `SLEEVE_A_INVESTED_FRACTION = {"risk_on": 1.0, "neutral": 0.9, "risk_off": 0.75}` is added and read solely by the Sleeve A funnel; `REGIME_INVESTED_FRACTION` is untouched because `execution/engine/sleeve_b.py` (the frozen control) reads it."
2. Mechanical change 2 (evictions): replace "the eviction branch is removed from `plan_decisions` … `OUTCOMPETE_MARGIN` is deleted" with: "`plan_decisions` gains `evictions: bool = True` and `trim_ceiling: Optional[float] = RISK_TRIM_CEILING` parameters; the live funnel calls it with `evictions=False, trim_ceiling=None`. Defaults preserve the Tier 2 backtest harness's old-mechanics fidelity; `OUTCOMPETE_MARGIN` survives for the harness only."
3. LLM-layer item 11 (reasoning block): replace "Prompt-only change; parser/schema untouched." with: "Prompt change plus a minimal parser passthrough: an optional top-level `next_constraints` array in the monthly response is journaled as `theme_proposal` EngineReports (no lifecycle effect, no DB schema change); absent key ⇒ old behavior."
4. LLM-layer item 12 (200-week MA): replace "surfaced to the LLM in light/full run context and in reports" with: "computed for holdings + ranked candidates from a dedicated 5-year weekly fetch, attached to screen rows as `dist_200wma` (null when <4y history), and surfaced in engine journals (entry orders, review triggers, funnel summary). Threading it into the paid swarm prompt is an explicit rider for a later PR."

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-07-10-sleeve-a-thesis-hold-redesign-design.md
git commit -m "docs(funnel): spec amendments from code exploration — Sleeve-A-only exposure constant, parameterized plan_decisions, parser passthrough, 200wMA scope"
```

---

### Task 2: Sleeve-A-only exposure floors

**Files:**
- Modify: `execution/constants.py` (near line 68)
- Modify: `inngest_app/functions/sleeve_a_funnel.py:36` (import) and `:1168` (read)
- Test: `tests/test_funnel_exposure.py` (create)

**Interfaces:**
- Produces: `SLEEVE_A_INVESTED_FRACTION: Dict[str, float]` in `execution/constants.py`.

- [ ] **Step 1: Write the failing test** — create `tests/test_funnel_exposure.py`:

```python
"""Exposure floors: Sleeve A gets its own dict; the control group's
constant is frozen at its Phase 2 values."""
from execution.constants import REGIME_INVESTED_FRACTION, SLEEVE_A_INVESTED_FRACTION


def test_sleeve_b_control_constant_is_frozen():
    assert REGIME_INVESTED_FRACTION == {"risk_on": 1.0, "neutral": 0.7, "risk_off": 0.4}


def test_sleeve_a_floors_match_owner_ruling():
    # owner 2026-07-10: "90% invested at least; at most 25% cash"
    assert SLEEVE_A_INVESTED_FRACTION == {"risk_on": 1.0, "neutral": 0.9, "risk_off": 0.75}


def test_funnel_reads_sleeve_a_dict_not_the_shared_one():
    import inspect

    import inngest_app.functions.sleeve_a_funnel as funnel
    src = inspect.getsource(funnel)
    assert "SLEEVE_A_INVESTED_FRACTION" in src
    assert "REGIME_INVESTED_FRACTION" not in src
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest tests/test_funnel_exposure.py -q --no-cov` → ImportError (`SLEEVE_A_INVESTED_FRACTION`).

- [ ] **Step 3: Implement** — in `execution/constants.py`, directly below `REGIME_INVESTED_FRACTION` (line 68):

```python
# Sleeve A thesis-hold exposure floors (owner ruling 2026-07-10). Sleeve B
# (control) keeps REGIME_INVESTED_FRACTION above — never merge these.
SLEEVE_A_INVESTED_FRACTION = {"risk_on": 1.0, "neutral": 0.9, "risk_off": 0.75}
```

In `inngest_app/functions/sleeve_a_funnel.py`: change the import at line 36 from `REGIME_INVESTED_FRACTION` to `SLEEVE_A_INVESTED_FRACTION`, and at line 1168 change

```python
    invested_fraction = REGIME_INVESTED_FRACTION.get(regime, 0.7)
```
to
```python
    invested_fraction = SLEEVE_A_INVESTED_FRACTION.get(regime, 0.9)
```

- [ ] **Step 4: Run to verify it passes** — `python3 -m pytest tests/test_funnel_exposure.py tests/test_funnel_*.py -q --no-cov` → green.
- [ ] **Step 5: Commit** — `git add execution/constants.py inngest_app/functions/sleeve_a_funnel.py tests/test_funnel_exposure.py && git commit -m "feat(funnel): Sleeve-A-only exposure floors 1.0/0.9/0.75 — control constant untouched"`

---

### Task 3: Parameterize `plan_decisions` (evictions/trims opt-out)

**Files:**
- Modify: `execution/funnel/decisions.py`
- Modify: `inngest_app/functions/sleeve_a_funnel.py:1149` (call site)
- Test: `tests/test_funnel_decisions.py` (append; read the file's existing fixtures first and reuse them)

**Interfaces:**
- Produces: `plan_decisions(holdings, candidates, sleeve_equity, max_positions, evictions: bool = True, trim_ceiling: Optional[float] = None→default RISK_TRIM_CEILING) -> Dict` — defaults byte-equivalent to today. Signature detail below.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_funnel_decisions.py` (mirror its existing holding/candidate dict shapes — `{"symbol","conviction","market_value"}` / `{"symbol","conviction"}`):

```python
def test_evictions_false_never_outcompetes_full_book():
    holdings = [{"symbol": f"H{i}", "conviction": 50.0, "market_value": 10_000.0}
                for i in range(3)]
    candidates = [{"symbol": "NEW", "conviction": 99.0}]
    plan = plan_decisions(holdings, candidates, 100_000.0, 3, evictions=False)
    assert plan["exits"] == []
    assert plan["entry_queue"] == []          # book full, no eviction allowed


def test_evictions_false_still_fills_empty_slots():
    holdings = [{"symbol": "H0", "conviction": 50.0, "market_value": 10_000.0}]
    candidates = [{"symbol": "NEW", "conviction": 55.0}]
    plan = plan_decisions(holdings, candidates, 100_000.0, 3, evictions=False)
    assert plan["entry_queue"] == ["NEW"]


def test_trim_ceiling_none_disables_mechanical_trims():
    holdings = [{"symbol": "BIG", "conviction": 80.0, "market_value": 30_000.0}]
    plan = plan_decisions(holdings, [], 100_000.0, 15,
                          evictions=False, trim_ceiling=None)
    assert plan["trims"] == []


def test_defaults_keep_old_behavior_for_the_backtest_harness():
    holdings = [{"symbol": "WEAK", "conviction": 40.0, "market_value": 30_000.0}]
    candidates = [{"symbol": "STRONG", "conviction": 60.0}]  # clears margin 10
    plan = plan_decisions(holdings, candidates, 100_000.0, 1)
    assert [e["symbol"] for e in plan["exits"]] == ["WEAK"]   # eviction intact
    assert plan["trims"] and plan["trims"][0]["reason"] == "risk_trim"
```

- [ ] **Step 2: Run to verify the new ones fail** — `python3 -m pytest tests/test_funnel_decisions.py -q --no-cov` → TypeError on `evictions=` kwarg.

- [ ] **Step 3: Implement** — in `execution/funnel/decisions.py`:

Signature (add `Optional` to the typing import; sentinel keeps the default tied to the constant):

```python
_TRIM_DEFAULT = object()


def plan_decisions(
    holdings: List[Dict[str, Any]], candidates: List[Dict[str, Any]],
    sleeve_equity: float, max_positions: int,
    evictions: bool = True, trim_ceiling: Any = _TRIM_DEFAULT,
) -> Dict[str, Any]:
    if trim_ceiling is _TRIM_DEFAULT:
        trim_ceiling = RISK_TRIM_CEILING
```

Wrap the existing eviction block (currently lines 40-51, the `weakest = book[0] …` branch) so it only runs when `evictions` is true; when false, a full book simply stops queueing:

```python
        if not book:
            break
        if not evictions:
            break                     # thesis-hold: challengers never evict
        weakest = book[0]
        ...existing eviction code unchanged...
```

Gate the trim block on the parameter (replace `if weight > RISK_TRIM_CEILING:` with `if trim_ceiling is not None and weight > trim_ceiling:` and guard the whole `trims` loop with `if sleeve_equity > 0 and trim_ceiling is not None:`).

Call site `inngest_app/functions/sleeve_a_funnel.py:1149`:

```python
    decisions = plan_decisions(holdings, candidates, sleeve_equity, max_positions,
                               evictions=False, trim_ceiling=None)
```

- [ ] **Step 4: Verify old behavior is untouched** — `python3 -m pytest tests/test_funnel_decisions.py tests/test_backtest_*.py -q --no-cov` → all green (backtest suites prove default-path fidelity).
- [ ] **Step 5: Commit** — `git add execution/funnel/decisions.py inngest_app/functions/sleeve_a_funnel.py tests/test_funnel_decisions.py && git commit -m "feat(funnel): plan_decisions opts out of evictions/trims for thesis-hold; harness defaults unchanged"`

---

### Task 4: Daily cron — high-water ratchet only, no stop sells

**Files:**
- Modify: `inngest_app/functions/execution_daily.py` (step `sleeve-a-stops`, lines ~497-611)
- Test: append to the existing daily-cron test file (find it: `grep -l "sleeve_a_stops\|sleeve-a-stops" tests/` — expected `tests/test_execution_daily*.py`); reuse its fixtures/stubs.

**Interfaces:**
- Consumes: `stop_levels(high_water, today_close, atr)` (unchanged — the backtest imports it).
- Produces: the step renamed in behavior (id can stay) — it ratchets `highWaterClose`, writes `stopPrice: None`, and NEVER calls `broker.submit_sell`.

- [ ] **Step 1: Write the failing test** — append to the daily-cron test file, following its existing stub pattern (the repo conftest ships a full prisma stub; the existing stop tests show how positions/ohlcv/broker are faked):

```python
async def test_sleeve_a_step_ratchets_high_water_but_never_sells(daily_env):
    """Thesis-hold: price never sells. The old stop condition is engineered
    to fire (close far below high-water) — the step must still not sell."""
    env = daily_env(positions=[fake_position("NVDA", qty=10, avg=100.0,
                                             high_water=200.0)],
                    bars={"NVDA": fake_bar(open=100.0, low=95.0, close=96.0)})
    out = await run_sleeve_a_stops_step(env)
    assert env.broker.sells == []                       # never traded
    pos = env.db.positions[("A", "NVDA")]
    assert pos["highWaterClose"] == 200.0               # ratchet persisted
    assert pos["stopPrice"] is None                     # stop retired
    assert out["stops_fired"] == 0
```

Adapt fixture names (`daily_env`, `fake_position`, `fake_bar`, `run_sleeve_a_stops_step`) to the file's actual helpers — the assertion set is the contract: **no sell call, ratchet persisted, stopPrice None**.

- [ ] **Step 2: Run to verify it fails** — the current code sells when `today_low <= stop`.

- [ ] **Step 3: Implement** — in `sleeve_a_stops_step`, keep everything through the ratchet persist, then delete the firing branch:

```python
            hw_in = pos.highWaterClose if pos.highWaterClose is not None else pos.avgEntryPrice
            new_hw, _stop = stop_levels(hw_in, today_close, atr)
            await db.engineposition.update(
                where={"sleeve_symbol": {"sleeve": SLEEVE_A, "symbol": pos.symbol}},
                data={"highWaterClose": new_hw, "stopPrice": None},
            )
            # Thesis-hold (spec 2026-07-10): price levels never sell. The
            # high-water ratchet stays — it anchors the DCA ladder.
```

Remove the now-dead `stop_fill_price` call, `broker.submit_sell`, cash-credit, and `exit_stop` report from this step (leave `stop_fill_price` itself in the module — delete it only if nothing else imports it; `grep -rn stop_fill_price` first). Update the step's summary payload (`stops_fired: 0` or drop the key — match what the existing tests assert).

- [ ] **Step 4: Run** — `python3 -m pytest tests/test_execution_daily*.py tests/test_backtest_fills.py -q --no-cov` → green (backtest `check_stop` still imports `stop_levels`).
- [ ] **Step 5: Commit** — `git add inngest_app/functions/execution_daily.py tests/ && git commit -m "feat(funnel): daily cron ratchets high-water only — trailing stops retired for Sleeve A"`

---

### Task 5: Market-buy support on the funnel brokers

**Files:**
- Modify: `execution/broker/alpaca_funnel_client.py` (class `AlpacaFunnelBroker`, line 29)
- Modify: `execution/broker/shadow_client.py` (class `ShadowBrokerClient`)
- Test: append to the existing broker tests (`grep -l AlpacaFunnelBroker tests/`)

**Interfaces:**
- Consumes: `AlpacaClient.submit_market_buy_notional(symbol, notional)` (`execution/broker/alpaca_client.py:52`, already exists); `_book_fill`/`_increase_position` privates.
- Produces: `submit_market_buy(self, symbol: str, qty: float, price_hint: float, journal: dict, client_order_id: str) -> BrokerOrderResult` on BOTH broker classes (same shape as `submit_sell` — whole-share qty for Alpaca, `notional = qty * price_hint` passed to the SDK).

- [ ] **Step 1: Write the failing tests** — append to the broker test file, mirroring its existing fake-Alpaca pattern:

```python
async def test_submit_market_buy_books_fill_and_position(broker_env):
    broker, alpaca, db = broker_env()
    alpaca.next_fill = {"status": "filled", "filled_qty": 5, "filled_avg_price": 101.0}
    res = await broker.submit_market_buy(
        symbol="MU", qty=5, price_hint=100.0,
        journal={"reason": "dca_add", "rung": 0.2},
        client_order_id="paper-A-MU-20260713-dca")
    assert res.status == "filled"
    assert alpaca.market_buys == [("MU", 500.0)]        # notional = qty*hint
    pos = db.positions[("A", "MU")]
    assert pos["qty"] == 5
    trade = db.trades[-1]
    assert trade["side"] == "buy" and trade["journal"]["reason"] == "dca_add"


async def test_submit_market_buy_is_idempotent_on_client_order_id(broker_env):
    broker, alpaca, db = broker_env()
    alpaca.next_fill = {"status": "filled", "filled_qty": 5, "filled_avg_price": 101.0}
    await broker.submit_market_buy("MU", 5, 100.0, {"reason": "dca_add"}, "coid-1")
    res2 = await broker.submit_market_buy("MU", 5, 100.0, {"reason": "dca_add"}, "coid-1")
    assert len(alpaca.market_buys) == 1                 # second call found the trade row
```

Plus one shadow test: `ShadowBrokerClient.submit_market_buy` fills immediately at `price_hint` and books the position (mirror how its `submit_sell` fills).

- [ ] **Step 2: Run to verify failure** — AttributeError: no `submit_market_buy`.

- [ ] **Step 3: Implement** — `AlpacaFunnelBroker.submit_market_buy`, structured exactly like `submit_sell` (line 107): idempotency check via `_find_by_client_order_id` first; floor qty to whole shares (Alpaca GTC constraint doesn't apply to market-day orders, but stay whole-share for ledger consistency); call `self._alpaca.submit_market_buy_notional(symbol, qty * price_hint)`; on fill `_book_fill` + `_increase_position` (seed `highWaterClose` only if the position is new — an ADD must NOT reset an existing high-water: pass through `_increase_position`, which already preserves position fields, and only the *create* path writes `highWaterClose: price`); write the EngineTrade row with `side="buy"`, `status` from the fill, `journal=journal`. `ShadowBrokerClient.submit_market_buy`: immediate fill at `price_hint`, same booking as its `submit_sell` inverse.

- [ ] **Step 4: Run** — broker tests green.
- [ ] **Step 5: Commit** — `git add execution/broker/ tests/ && git commit -m "feat(broker): market-buy method on funnel brokers for thesis-hold ADD tranches"`

---

### Task 6: `dcaState` column (additive migration)

**Files:**
- Modify: `db/schema.prisma` (EnginePosition, line ~1014)
- Create: `db/migrations/<timestamp>_engine_position_dca_state/migration.sql`

- [ ] **Step 1: Confirm the physical table name** — `grep -A2 '@@map' db/schema.prisma | grep -B1 -A1 engine` (EnginePosition's `@@map`). Use it in the SQL below (shown as `engine_positions`; substitute what the grep says).
- [ ] **Step 2: Add the field** to EnginePosition in `db/schema.prisma`, after `reportRef`:

```prisma
  dcaState        Json?     // thesis-hold ladder: {"armed_high": float, "used": [0.2,...]}
```

- [ ] **Step 3: Hand-write the migration** (`migrate dev` is broken in this repo — always hand-write + deploy):

```sql
-- engine_position dcaState: thesis-hold ladder rung memory (additive, nullable)
ALTER TABLE "engine_positions" ADD COLUMN "dcaState" JSONB;
```

- [ ] **Step 4: Regenerate the client** — `python3 -m prisma generate` (do NOT deploy to Neon from a feature branch; deploy is an operator step in the PR body, BEFORE merge, same as 3A/3C).
- [ ] **Step 5: Verify** — `python3 -m pytest tests/test_execution_sleeve_service.py -q --no-cov` (or nearest engine-position test) still green; conftest prisma stub may need the field added — if its model dicts enumerate fields, add `dcaState: None`.
- [ ] **Step 6: Commit** — `git add db/ tests/conftest.py && git commit -m "feat(db): EnginePosition.dcaState — ladder rung memory (additive migration)"`

---

### Task 7: Pure trigger predicates (`execution/funnel/review_triggers.py`)

**Files:**
- Create: `execution/funnel/review_triggers.py`
- Modify: `execution/constants.py` (new block)
- Test: `tests/test_funnel_review_triggers.py` (create)

**Interfaces:**
- Produces (all pure, consumed by Task 8):
  - `drawdown(price: float, high_water: Optional[float]) -> float`
  - `ladder_rung(dd: float, state: Optional[dict], high_water: float) -> Tuple[Optional[float], dict]` — returns `(rung_crossed_or_None, new_state)`; state shape `{"armed_high": float, "used": List[float]}`, re-arms when `high_water > armed_high`
  - `earnings_divergence(days_since_earnings: Optional[float], dd: float) -> bool`
  - `staleness(report_age_days: Optional[float]) -> bool`
  - `concentration(weight: float) -> bool`
  - `collect_triggers(*, dd, days_since_earnings, report_age_days, weight, dca_state, high_water) -> Tuple[List[str], dict]` — ordered trigger names + updated dca state
- Constants produced: `DCA_RUNGS = (0.20, 0.30, 0.40)`, `DCA_TRANCHE_FRACTION = 0.5`, `EARNINGS_DIVERGENCE_DD = 0.15`, `EARNINGS_DIVERGENCE_MAX_DAYS = 14` (calendar ≈ two weekly passes), `CONCENTRATION_REVIEW_WEIGHT = 0.20`, `TRIM_FALLBACK_TARGET = 0.12`.

- [ ] **Step 1: Write the failing tests** — `tests/test_funnel_review_triggers.py`:

```python
"""Thesis-hold review triggers — pure predicates, spec 2026-07-10."""
from execution.funnel.review_triggers import (
    collect_triggers, concentration, drawdown, earnings_divergence,
    ladder_rung, staleness,
)


def test_drawdown_from_high_water():
    assert drawdown(80.0, 100.0) == 0.2
    assert drawdown(100.0, None) == 0.0          # no anchor yet → no drawdown
    assert drawdown(120.0, 100.0) == 0.0         # above high → clamped


def test_ladder_rungs_fire_once_and_rearm_on_new_high():
    rung, st = ladder_rung(0.22, None, high_water=100.0)
    assert rung == 0.20 and st == {"armed_high": 100.0, "used": [0.20]}
    rung, st = ladder_rung(0.24, st, high_water=100.0)
    assert rung is None                           # 20 used, 30 not reached
    rung, st = ladder_rung(0.31, st, high_water=100.0)
    assert rung == 0.30
    rung, st = ladder_rung(0.05, st, high_water=140.0)   # new high re-arms
    assert rung is None and st == {"armed_high": 140.0, "used": []}


def test_earnings_divergence_window_and_floor():
    assert earnings_divergence(days_since_earnings=3, dd=0.16)
    assert earnings_divergence(days_since_earnings=13, dd=0.15)
    assert not earnings_divergence(days_since_earnings=15, dd=0.30)  # window
    assert not earnings_divergence(days_since_earnings=3, dd=0.14)   # floor
    assert not earnings_divergence(None, 0.30)                       # unknown date


def test_staleness_and_concentration():
    assert staleness(43)            # > HOLDING_STALE_WEEKS(6)*7
    assert not staleness(41)
    assert staleness(None)          # never reviewed → stale
    assert concentration(0.21) and not concentration(0.20)


def test_collect_triggers_orders_and_updates_state():
    names, st = collect_triggers(dd=0.22, days_since_earnings=4,
                                 report_age_days=50, weight=0.25,
                                 dca_state=None, high_water=100.0)
    assert names == ["staleness", "earnings_divergence", "ladder_rung",
                     "concentration"]
    assert st["used"] == [0.20]
```

- [ ] **Step 2: Run to verify it fails** — ModuleNotFoundError.
- [ ] **Step 3: Implement** — constants block in `execution/constants.py` (after the Phase 3C funnel block, ~line 123):

```python
# Thesis-hold review triggers (spec 2026-07-10-sleeve-a-thesis-hold-redesign)
DCA_RUNGS = (0.20, 0.30, 0.40)       # drawdown-from-high add/review levels
DCA_TRANCHE_FRACTION = 0.5           # ADD buys half a fresh entry's notional
EARNINGS_DIVERGENCE_DD = 0.15        # drawdown floor for the "MU signal"
EARNINGS_DIVERGENCE_MAX_DAYS = 14    # two weekly passes wide (Mon-cutoff leak)
CONCENTRATION_REVIEW_WEIGHT = 0.20   # weight that TRIGGERS a review (never sells)
TRIM_FALLBACK_TARGET = 0.12          # TRIM target if the review states none
```

`execution/funnel/review_triggers.py`:

```python
"""Thesis-hold review triggers (pure). A trigger NEVER trades — it earns a
holding a thesis review; the review's verdict is the only sell authority."""
from typing import Dict, List, Optional, Tuple

from execution.constants import (
    CONCENTRATION_REVIEW_WEIGHT, DCA_RUNGS, EARNINGS_DIVERGENCE_DD,
    EARNINGS_DIVERGENCE_MAX_DAYS, HOLDING_STALE_WEEKS,
)


def drawdown(price: float, high_water: Optional[float]) -> float:
    if not high_water or high_water <= 0:
        return 0.0
    return max(0.0, 1.0 - price / high_water)


def ladder_rung(dd: float, state: Optional[dict],
                high_water: float) -> Tuple[Optional[float], dict]:
    st = dict(state or {"armed_high": high_water, "used": []})
    st["used"] = list(st.get("used") or [])
    if high_water > float(st.get("armed_high") or 0.0):
        st = {"armed_high": high_water, "used": []}
    rung = next((r for r in DCA_RUNGS if dd >= r and r not in st["used"]), None)
    if rung is not None:
        st["used"].append(rung)
    return rung, st


def earnings_divergence(days_since_earnings: Optional[float], dd: float) -> bool:
    return (days_since_earnings is not None
            and days_since_earnings <= EARNINGS_DIVERGENCE_MAX_DAYS
            and dd >= EARNINGS_DIVERGENCE_DD)


def staleness(report_age_days: Optional[float]) -> bool:
    return report_age_days is None or report_age_days > HOLDING_STALE_WEEKS * 7


def concentration(weight: float) -> bool:
    return weight > CONCENTRATION_REVIEW_WEIGHT


def collect_triggers(*, dd: float, days_since_earnings: Optional[float],
                     report_age_days: Optional[float], weight: float,
                     dca_state: Optional[dict],
                     high_water: float) -> Tuple[List[str], dict]:
    names: List[str] = []
    if staleness(report_age_days):
        names.append("staleness")
    if earnings_divergence(days_since_earnings, dd):
        names.append("earnings_divergence")
    rung, st = ladder_rung(dd, dca_state, high_water)
    if rung is not None:
        names.append("ladder_rung")
    if concentration(weight):
        names.append("concentration")
    return names, st
```

- [ ] **Step 4: Run** — green.
- [ ] **Step 5: Commit** — `git add execution/funnel/review_triggers.py execution/constants.py tests/test_funnel_review_triggers.py && git commit -m "feat(funnel): pure thesis-review trigger predicates + ladder state"`

---

### Task 8: Weekly cron wiring — triggered reviews, ADD/TRIM/SELL outcomes

This is the seam task. Everything lands in `_decide_and_execute` (`inngest_app/functions/sleeve_a_funnel.py:1049`), between holdings-building and `plan_decisions`, plus a post-plan ADD/TRIM stage.

**Files:**
- Modify: `inngest_app/functions/sleeve_a_funnel.py`
- Modify: `execution/reporting.py:13-21` (REPORT_TYPES: add `"dca_add", "review_trigger"`)
- Test: append to the funnel cron test file (`grep -l "_decide_and_execute" tests/`) using its existing env/stub fixtures.

**Interfaces:**
- Consumes: `collect_triggers` (Task 7), `submit_market_buy` (Task 5), `plan_decisions(..., evictions=False, trim_ceiling=None)` (Task 3), existing `reuse_or_budget`/`run_paid_analysis`/`persist_full`, `size_entry`, `_load_latest_signals`, `write_report`.
- Produces: journal types `review_trigger` (info, one per triggered holding: `{symbol, triggers, dd, weight, report_age_days}`) and `dca_add` (info: `{symbol, rung_or_trigger, qty, notional, conviction}`); TRIM sells journaled as existing `risk_trim` with `body.origin = "llm_trim"`.

Flow to implement (order matters — reviews refresh verdicts BEFORE the plan, so a SELL verdict exits through the existing `sell_verdict` path):

- [ ] **Step 1: Write the failing tests** — append to the funnel cron test file (reuse its fixtures; the contracts to pin):

```python
async def test_triggered_holding_gets_review_before_plan(funnel_env):
    """A stale holding consumes a full-run budget slot ahead of new entries,
    and a SELL verdict from that review exits via the sell_verdict path."""
    env = funnel_env(holdings={"OLDN": dict(qty=10, report_age_days=60)},
                     review_results={"OLDN": {"verdict": "avoid"}})
    out = await run_decide_and_execute(env)
    assert env.reports.count("review_trigger") == 1
    assert env.broker.sells and env.broker.sells[0].symbol == "OLDN"
    assert env.reports.count("exit_sell_verdict") == 1


async def test_rung_trigger_with_buy_verdict_adds_half_tranche(funnel_env):
    env = funnel_env(holdings={"DIPN": dict(qty=10, high_water=100.0,
                                            close=75.0, report_age_days=2,
                                            verdict="buy")})
    out = await run_decide_and_execute(env)
    add = [b for b in env.broker.market_buys if b.symbol == "DIPN"]
    assert len(add) == 1
    assert env.reports.count("dca_add") == 1
    st = env.db.positions[("A", "DIPN")]["dcaState"]
    assert 0.20 in st["used"]


async def test_concentration_trigger_trims_only_via_review(funnel_env):
    env = funnel_env(holdings={"BIGW": dict(qty=100, close=300.0,
                                            weight=0.30, verdict="hold",
                                            report_age_days=2)},
                     sleeve_equity=100_000.0)
    out = await run_decide_and_execute(env)
    trims = [s for s in env.broker.sells if s.journal["reason"] == "risk_trim"]
    assert len(trims) == 1
    # target = TRIM_FALLBACK_TARGET when the review states no percent
    assert abs(trims[0].qty * 300.0 - (0.30 - 0.12) * 100_000.0) < 300.0


async def test_no_trigger_no_spend_no_trade(funnel_env):
    env = funnel_env(holdings={"CALM": dict(qty=10, report_age_days=2,
                                            verdict="buy", close=100.0,
                                            high_water=105.0)})
    out = await run_decide_and_execute(env)
    assert env.reports.count("review_trigger") == 0
    assert env.broker.sells == [] and env.broker.market_buys == []
```

Adapt fixture plumbing to the real test file's helpers; the four contracts above are the deliverable.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement — stage A (trigger computation).** In `_decide_and_execute`, after `sleeve_equity` (line ~1096) and the holdings loop, load position rows and earnings recency, then compute triggers:

```python
    pos_rows = {p.symbol: p for p in await get_engine_positions(db, SLEEVE_A)}

    async def _days_since_earnings(sym: str) -> Optional[float]:
        try:
            edf = await asyncio.to_thread(market_client.get_earnings_dates, sym)
            past = [d for d in edf.index if d <= now] if edf is not None else []
            return (now - max(past)).days if past else None
        except Exception:                                    # noqa: BLE001
            return None

    triggered: Dict[str, dict] = {}
    for h in holdings:
        sym = h["symbol"]
        pos = pos_rows.get(sym)
        close = close_by_symbol.get(sym, 0.0)
        hw = (pos.highWaterClose if pos and pos.highWaterClose else None) or close
        dd = drawdown(close, hw)
        weight = (h["market_value"] / sleeve_equity) if sleeve_equity > 0 else 0.0
        dse = await _days_since_earnings(sym) if dd >= EARNINGS_DIVERGENCE_DD else None
        names, new_state = collect_triggers(
            dd=dd, days_since_earnings=dse,
            report_age_days=latest.get(sym, {}).get("report_age_days"),
            weight=weight, dca_state=(pos.dcaState if pos else None), high_water=hw)
        if not names:
            continue
        triggered[sym] = {"triggers": names, "dd": dd, "weight": weight,
                          "dca_state": new_state}
        await _journal(db, "review_trigger", "info",
                       f"{sym}: review triggered — {', '.join(names)}",
                       {"symbol": sym, "triggers": names, "dd": round(dd, 4),
                        "weight": round(weight, 4)})
```

Persist `dcaState` for rung-triggered names immediately (the rung is consumed by being *reviewed*, whatever the outcome — spec: once per episode):

```python
        if "ladder_rung" in names and pos is not None:
            await db.engineposition.update(
                where={"sleeve_symbol": {"sleeve": SLEEVE_A, "symbol": sym}},
                data={"dcaState": Json(new_state)})
```

- [ ] **Step 4: Implement — stage B (budget-prioritized reviews).** Before the entry handshakes, run reviews for triggered holdings through the SAME budget machinery (per-symbol `step.run` at top level, exactly like `_handshake_and_enter`'s `handshake-analyze-{sym}` steps — nested `step.run` is a non-retriable SDK error):

```python
    for sym in sorted(triggered, key=lambda s: -(latest.get(s, {})
                                                 .get("report_age_days") or 999)):
        gate = await reuse_or_budget(db, sym, run_date)
        if gate["action"] == "skip":
            await _journal(db, "theme_review", "info",
                           f"{sym}: review deferred — {gate.get('reason')}",
                           {"symbol": sym, "stage": "thesis_review"})
            triggered[sym]["deferred"] = True
            continue
        if gate["action"] == "analyze":
            result = await step.run(f"thesis-review-{sym}",
                                    run_paid_analysis, sym)
            await persist_full(db, sym, run_date, result,
                               marker="sleeve_a_funnel")
    latest = await _load_latest_signals(db, symbols)   # refresh verdicts
```

Then REBUILD the `holdings` list (rerun the existing holdings loop) so fresh verdicts feed `vetoed`/conviction → `plan_decisions` → the existing `_execute_sells` path handles SELL exits with zero new sell code. (Extract the existing holdings loop lines 1098-1113 into a local closure `def _build_holdings() -> list` and call it twice.)

- [ ] **Step 5: Implement — stage C (ADD/TRIM after the plan, before entry handshakes).** ADD (cash priority over new entries — this stage runs before `_handshake_and_enter` and decrements `deployable`/`cash_available`):

```python
    for sym, t in triggered.items():
        if t.get("deferred") or sym in {e["symbol"] for e in decisions["exits"]}:
            continue
        meta = latest.get(sym) or {}
        row = by_symbol.get(sym) or {}
        if {"ladder_rung", "earnings_divergence"} & set(t["triggers"]) \
                and meta.get("verdict") == "buy":
            conv = next(h["conviction"] for h in holdings if h["symbol"] == sym)
            notional = DCA_TRANCHE_FRACTION * size_entry(
                conv, sleeve_equity, float(row.get("liquidity_adv_usd") or 0.0),
                float(row.get("atr_pct") or 0.0), deployable, cash_available)
            close = close_by_symbol.get(sym, 0.0)
            qty = int(notional // close) if close > 0 else 0
            if qty >= 1 and qty * close >= MIN_TRADE_NOTIONAL:
                res = await client.submit_market_buy(
                    symbol=sym, qty=qty, price_hint=close,
                    journal={"reason": "dca_add", "triggers": t["triggers"]},
                    client_order_id=f"paper-A-{sym}-{run_date:%Y%m%d}-dca")
                await _journal(db, "dca_add", "info",
                               f"{sym}: ladder add {qty} @ ~{close:.2f}",
                               {"symbol": sym, "qty": qty,
                                "notional": round(qty * close, 2),
                                "triggers": t["triggers"]})
                deployable = max(0.0, deployable - qty * close)
                cash_available = max(0.0, cash_available - qty * close)
        elif "concentration" in t["triggers"] and meta.get("verdict") in ("buy", "hold"):
            target = _parse_trim_target(meta) or TRIM_FALLBACK_TARGET
            excess = t["weight"] - target
            close = close_by_symbol.get(sym, 0.0)
            if excess > 0 and close > 0:
                qty = round(excess * sleeve_equity / close, 4)
                decisions["trims"].append({"symbol": sym, "reason": "risk_trim",
                                           "sell_notional": round(qty * close, 2),
                                           "origin": "llm_trim"})
```

`_parse_trim_target(meta)`: regex a percent out of the review's `positionSizeRec` string (`re.search(r"(\d+(?:\.\d+)?)\s*%", ...)` → `float/100` if `0 < x < CONCENTRATION_REVIEW_WEIGHT`), else None. TRIM rows flow through the existing `_execute_sells` trim branch unchanged.

- [ ] **Step 6: REPORT_TYPES** — in `execution/reporting.py`, add `"dca_add", "review_trigger"` to the frozenset. Check the vocab test (`grep -rn "REPORT_TYPES" tests/`) — it pins the count (18 types after 3C); update to 20 with the two new names.
- [ ] **Step 7: Run the full funnel + backtest suites** — `python3 -m pytest tests/test_funnel_*.py tests/test_backtest_*.py tests/test_execution_*.py tests/test_theme_*.py -q --no-cov` → green.
- [ ] **Step 8: Commit** — `git add inngest_app/functions/sleeve_a_funnel.py execution/reporting.py tests/ && git commit -m "feat(funnel): thesis reviews with ADD/TRIM/SELL outcomes wired into the weekly pass"`

---

### Task 9: 200-week MA distance

**Files:**
- Modify: `execution/market_data.py` (new helper)
- Modify: `inngest_app/functions/sleeve_a_funnel.py` (`_screen`, line ~882-919)
- Test: `tests/test_funnel_200wma.py` (create)

**Interfaces:**
- Produces: `fetch_weekly_closes(tickers: List[str], period: str = "5y") -> Dict[str, pd.Series]` in `execution/market_data.py`; screen rows for holdings + top-`CANDIDATE_POOL` candidates gain `"dist_200wma": Optional[float]` (`price / 200w-SMA − 1`, `None` when < 200 weekly bars).

- [ ] **Step 1: Write the failing tests** — `tests/test_funnel_200wma.py`:

```python
import numpy as np
import pandas as pd

from execution.market_data import dist_200wma


def _weekly(n, p0=100.0, rate=1.002):
    idx = pd.date_range("2019-01-04", periods=n, freq="W-FRI")
    return pd.Series(p0 * rate ** np.arange(n), index=idx)


def test_dist_200wma_computes_distance():
    closes = _weekly(260)
    d = dist_200wma(closes)
    sma = closes.rolling(200).mean().iloc[-1]
    assert abs(d - (closes.iloc[-1] / sma - 1.0)) < 1e-9


def test_dist_200wma_none_under_200_weeks():
    assert dist_200wma(_weekly(150)) is None
    assert dist_200wma(None) is None
```

- [ ] **Step 2: Run to verify failure** — ImportError.
- [ ] **Step 3: Implement** — in `execution/market_data.py`:

```python
def fetch_weekly_closes(tickers: List[str], period: str = "5y") -> Dict[str, pd.Series]:
    """Weekly closes for the 200-week MA input. Small symbol sets only
    (holdings + ranked candidates) — never the full screening universe."""
    raw = yf.download(tickers=" ".join(tickers), period=period, interval="1wk",
                      group_by="ticker", auto_adjust=True, progress=False,
                      threads=True)
    out: Dict[str, pd.Series] = {}
    for t in tickers:
        try:
            s = (raw[t]["Close"] if len(tickers) > 1 else raw["Close"]).dropna()
            if not s.empty:
                out[t] = s
        except (KeyError, TypeError):
            continue
    return out


def dist_200wma(weekly_closes: Optional[pd.Series]) -> Optional[float]:
    if weekly_closes is None or len(weekly_closes) < 200:
        return None
    sma = float(weekly_closes.rolling(200).mean().iloc[-1])
    return float(weekly_closes.iloc[-1] / sma - 1.0) if sma > 0 else None
```

In `_screen` (sleeve_a_funnel.py), after ranking: one `fetch_weekly_closes` call for `holdings ∪ ranked[:CANDIDATE_POOL]` symbols via `asyncio.to_thread`, then `row["dist_200wma"] = dist_200wma(weekly.get(sym))` on those rows (guard the whole block in try/except → journal `engine_failure` warning and continue with `None`s — degrade, never block, same posture as 3A). Include `dist_200wma` in the `entry_order` journal body (in `_handshake_and_enter` where the order journal is built) and in the `review_trigger` body (Task 8 — add `"dist_200wma": row.get("dist_200wma")`).

- [ ] **Step 4: Run** — new tests + `tests/test_funnel_screen.py` green.
- [ ] **Step 5: Commit** — `git add execution/market_data.py inngest_app/functions/sleeve_a_funnel.py tests/test_funnel_200wma.py && git commit -m "feat(funnel): 200-week MA distance input for holdings and ranked candidates"`

---

### Task 10: Theme prompts — revealed-behavior block + forward hypotheses

**Files:**
- Modify: `execution/themes/prompts.py`
- Modify: `execution/themes/parser.py` (optional `next_constraints` passthrough)
- Modify: the discovery cron that consumes the parse (find: `grep -rn "next_constraints\|build_monthly_prompt" execution/themes/ inngest_app/` → the monthly discovery function) — journal hypotheses.
- Test: `tests/test_theme_prompts.py` (append), `tests/test_theme_parser.py` (append)

**Interfaces:**
- Produces: `_REVEALED_BEHAVIOR` block inside `build_monthly_prompt`; parser returns `{"themes": [...], "next_constraints": [...]}` (empty list when absent).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_theme_prompts.py`:

```python
def test_monthly_prompt_demands_forward_hypotheses_and_roles():
    md = build_monthly_prompt({})
    for phrase in ("what binds NEXT", "next_constraints", "time-to-solve",
                   "anchor", "pure-play", "catalyst", "time-to-survive",
                   "second-order losers"):
        assert phrase in md, phrase
```

Append to `tests/test_theme_parser.py` (mirror its existing parse-call pattern):

```python
def test_parser_passes_next_constraints_through():
    raw = json.dumps({"themes": [], "next_constraints": [
        {"hypothesis": "grid labor binds", "candidates": ["MYRG"],
         "leading_indicators": ["backlogs"], "falsification": "wages flat"}]})
    out = parse_monthly_response(raw)
    assert out["next_constraints"][0]["hypothesis"] == "grid labor binds"


def test_parser_tolerates_missing_next_constraints():
    out = parse_monthly_response(json.dumps({"themes": []}))
    assert out["next_constraints"] == []
```

(Adapt `parse_monthly_response` to the parser's real function name — read `execution/themes/parser.py` first.)

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement the prompt block** — in `execution/themes/prompts.py`, add after `_SA_METHOD` and interpolate into `build_monthly_prompt` directly below `{_SA_METHOD}`:

```python
_REVEALED_BEHAVIOR = """## Revealed behavior of the best thematic investors (13F study, 2026-07-10)
- Buy the BINDING CONSTRAINT, not the beneficiary. Consensus buys who
  sells the theme; the re-rating lives in what the theme cannot proceed
  without (power -> cooling -> energized shells -> memory/storage ->
  optics -> fiber -> bridge power).
- The constraint MIGRATES. Your primary deliverable each month is FORWARD:
  answer "what binds NEXT once today's constraints are priced?" A
  constraint that has become a consensus headline is priced — rotate the
  reasoning to its successor.
- Time-to-solve is a selection criterion. Short-time-frame demand accrues
  to whoever can deliver NOW (fuel cells, gensets, converted capacity)
  over elegant solutions that take a decade.
- Express every theme across the cap spectrum and by ROLE — state the
  role in each constituent's exposure sentence: anchor
  (contracted/profitable floor with thesis optionality), pure-play
  (asymmetric constraint exposure), or catalyst (identifiable pending
  repricing event). For pure-plays and catalysts also state
  time-to-survive: whether the balance sheet reaches the catalyst.
- Name the theme's second-order losers in metadata (who is disrupted or
  squeezed if the thesis plays out).

In addition to "themes", return a top-level "next_constraints" array with
1-3 FORWARD hypotheses — constraints not yet investable-obvious:
  {"hypothesis": "<one sentence>", "candidates": ["TICK", ...],
   "leading_indicators": ["<2-4 observable signals>", ...],
   "falsification": "<what kills the hypothesis>"}
A hypothesis graduates to a proposed theme in a LATER month only when its
leading indicators confirm."""
```

- [ ] **Step 4: Implement the parser passthrough** — in `execution/themes/parser.py`'s monthly-response parser, after themes are extracted: `out["next_constraints"] = [h for h in (data.get("next_constraints") or []) if isinstance(h, dict) and h.get("hypothesis")]`. In the monthly discovery cron, journal each: `write_report("theme_proposal", "info", "theme_discovery", f"next-constraint hypothesis: {h['hypothesis'][:80]}", h)` — no lifecycle effect.
- [ ] **Step 5: Run** — `python3 -m pytest tests/test_theme_*.py -q --no-cov` → green (existing prompt tests must still pass — the SA-method assertions are untouched).
- [ ] **Step 6: Commit** — `git add execution/themes/ tests/ && git commit -m "feat(themes): revealed-behavior reasoning block + forward next-constraint hypotheses"`

---

### Task 11: Isolation, full sweep, PR

**Files:**
- Modify: the prompt-isolation test (`grep -rln "prompt.isolation\|strategist payload" tests/`) — extend.
- No other source changes.

- [ ] **Step 1: Extend the prompt-isolation test** — assert the Sleeve B strategist payload contains none of: `dist_200wma`, `dca_add`, `review_trigger`, `next_constraints`, `SLEEVE_A_INVESTED_FRACTION` (same contract as the 3A/3B new-signal exclusions; follow the existing test's payload-builder fixture).
- [ ] **Step 2: Review-only-sells invariant test** — add to `tests/test_funnel_exposure.py`:

```python
def test_no_price_level_sell_paths_remain():
    """The daily cron must not reference stop_fill_price for Sleeve A sells,
    and the funnel must not call plan_decisions with mechanical trims."""
    import inspect

    import inngest_app.functions.sleeve_a_funnel as funnel
    src = inspect.getsource(funnel)
    assert "trim_ceiling=None" in src and "evictions=False" in src
```

- [ ] **Step 3: Full sweep** — `python3 -m pytest tests/ -q 2>&1 | tail -5`; compare failures against the pre-existing baseline (`git stash` trick if needed): zero NEW failures.
- [ ] **Step 4: Push branch + open PR.** PR body must carry the operator checklist:
  1. `python3 -m prisma migrate deploy` on Neon (the `dcaState` migration) **BEFORE merge** (same reasoning as 3A: regenerated client SELECTs the new column).
  2. Merge → Railway auto-deploy → re-sync Inngest **only after** "Inngest handler mounted with N function(s)" shows in Railway logs (a sync PUT can hit the old build).
  3. Watch the first Monday 16:00 UTC pass manually: expect `review_trigger` journals for any stale holding, zero `exit_stop` reports ever again, deployable jump from the new floors (neutral 0.7 → 0.9 ≈ +$14k deployable at current equity), and no Sleeve B behavior change at Monday 15:00 UTC (control frozen).
  4. Circuit breaker stays armed (−15pp vs SPY → halt); owner decides its future the first time it trips.
- [ ] **Step 5: Commit + hand off to review** — normal final-review cycle (superpowers:requesting-code-review), riders listed: 200wMA not yet threaded into the paid swarm prompt; `_parse_trim_target` depends on free-text `positionSizeRec`; earnings dates from yfinance (`Ticker.earnings_dates`) can be sparse for small caps — trigger degrades to staleness-only.

---

## Self-Review

- **Spec coverage:** floors → T2; evictions → T3; stops → T4; trims/TRIM → T3+T8; review triggers (staleness/divergence/rung/concentration) → T7+T8; ADD → T5+T8; SELL-via-review → T8 stage B (existing sell_verdict path); 200wMA → T9; reasoning block + forward hypotheses + parser passthrough → T10; circuit breaker retained → no change (T11 operator note); pre-committed evaluation criteria → reporting change is out of code scope (monthly reporting rides existing snapshots; noted in spec, no task needed — the criteria govern how RESULTS are judged, not code); spec amendments → T1.
- **Placeholders:** the cron-level tests in T4/T8 name fixtures generically with explicit instructions to adapt to the real test files' helpers — deliberate: those files' fixtures are the established pattern and must be reused, and the pinned CONTRACTS are stated exactly. No TBDs.
- **Type consistency:** `submit_market_buy(symbol, qty, price_hint, journal, client_order_id)` consistent T5↔T8; `collect_triggers` kwargs consistent T7↔T8; `dcaState` shape `{"armed_high", "used"}` consistent T6↔T7↔T8; `SLEEVE_A_INVESTED_FRACTION` consistent T2↔T11.
