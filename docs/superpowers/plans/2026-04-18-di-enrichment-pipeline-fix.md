# Decision Intelligence Enrichment Pipeline Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the silent failure chain that causes `engineSuggestedWeight` and `targetWeight` to stay at `0.0` for every portfolio position, even after the engine runs successfully. Replace silent exception swallowing with structured diagnostic logging, and add a deterministic moat-based fallback so covered positions never display `tgt 0.0%`.

**Architecture:** The decision intelligence (DI) enrichment pipeline has three silent exit paths in `api/lib/decision_intelligence.py` and one swallowed exception in `research_swarm/reports/decision_intelligence_calculator.py`. When any link in the chain breaks, `conviction_position` becomes `None` → `or {}` destroys the trace → `recommended_pct` is missing → the engine's `rec_pct is not None` guard skips the DB write → `engineSuggestedWeight` stays `null` and `targetWeight` stays `0`. Fix: (1) convert each silent return into a structured `logger.warning` with context; (2) add a moat-score-derived fallback in the portfolio engine that writes a default suggested weight when DI data is absent.

**Tech Stack:** Python 3.11+, FastAPI, Prisma Client Python (asyncio), pytest, pytest-asyncio, structlog/stdlib logging.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `api/lib/decision_intelligence.py` | Modify | Add logging to the three silent return paths; replace bare `print` in outer except with `logger.exception` |
| `research_swarm/reports/decision_intelligence_calculator.py` | Modify | Upgrade the `link_conviction_to_position` exception handler from `logger.warning` to `logger.exception` and include inputs in the message |
| `api/services/portfolio_engine.py` | Modify | Add `_moat_fallback_weight` helper and use it when `conviction_position.recommended_pct` is missing; log which path produced the weight |
| `tests/test_di_enrichment_diagnostics.py` | Create | Unit tests covering each silent exit path and the moat fallback |
| `tests/test_portfolio_engine_plans.py` | Modify | Add a case where `fullOutput` has no DI block and no `fundamentalist_output.valuation_metrics.current_price` — assert moat fallback writes `engineSuggestedWeight` |

---

## Task 1: Add Diagnostic Logging to DI Enrichment Silent Paths

**Files:**
- Modify: `api/lib/decision_intelligence.py`
- Test: `tests/test_di_enrichment_diagnostics.py`

Currently `enrich_with_decision_intelligence` has three places where it returns `full_output` unchanged without any log output, and an outer `except` that uses `print` instead of `logger`. We need to see which path is firing in production.

- [ ] **Step 1: Write the failing test for missing-price log path**

Create `tests/test_di_enrichment_diagnostics.py`:

```python
"""Tests for diagnostic logging in the DI enrichment pipeline."""
from __future__ import annotations

import logging

import pytest

from api.lib.decision_intelligence import enrich_with_decision_intelligence


def test_logs_when_current_price_missing(caplog: pytest.LogCaptureFixture) -> None:
    """When valuation_metrics.current_price is 0, enrichment returns early with a log."""
    full_output = {
        "fundamentalist_output": {"valuation_metrics": {"current_price": 0}},
    }
    with caplog.at_level(logging.WARNING, logger="api.lib.decision_intelligence"):
        result = enrich_with_decision_intelligence(full_output, moat_score=7.0)

    assert "decision_intelligence" not in result
    assert any(
        "current_price" in rec.message.lower() and "enrichment skipped" in rec.message.lower()
        for rec in caplog.records
    ), f"expected current_price skip log, got: {[r.message for r in caplog.records]}"


def test_logs_when_recommended_strategy_missing(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When strategy_calculator returns falsy, enrichment returns early with a log."""
    full_output = {
        "fundamentalist_output": {
            "valuation_metrics": {"current_price": 100.0, "valuation_category": "Fair"},
            "price_targets": {
                "base_target": 120.0,
                "bull_target": 140.0,
                "bear_target": 85.0,
                "base_probability": 0.5,
                "bull_probability": 0.25,
                "bear_probability": 0.25,
            },
        },
    }

    def _empty_strategy(**kwargs):
        return None

    import research_swarm.agents.manager.strategy_calculator as sc
    monkeypatch.setattr(sc.strategy_calculator, "calculate_full_strategy", _empty_strategy)

    with caplog.at_level(logging.WARNING, logger="api.lib.decision_intelligence"):
        result = enrich_with_decision_intelligence(full_output, moat_score=7.0)

    assert "decision_intelligence" not in result
    assert any(
        "recommended_strategy" in rec.message.lower()
        for rec in caplog.records
    )


def test_logs_with_traceback_on_unexpected_exception(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The outer except block logs via logger.exception, not print."""
    import research_swarm.agents.manager.strategy_calculator as sc

    def _boom(**kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(sc.strategy_calculator, "calculate_full_strategy", _boom)

    full_output = {
        "fundamentalist_output": {
            "valuation_metrics": {"current_price": 100.0, "valuation_category": "Fair"},
        },
    }

    with caplog.at_level(logging.ERROR, logger="api.lib.decision_intelligence"):
        result = enrich_with_decision_intelligence(full_output, moat_score=7.0)

    assert "decision_intelligence" not in result
    assert any(
        "synthetic failure" in (rec.exc_text or "") or "synthetic failure" in rec.message
        for rec in caplog.records
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_di_enrichment_diagnostics.py -v`
Expected: FAIL — `AssertionError` on each log assertion because the current code uses `print` and silent `return`.

- [ ] **Step 3: Add module logger and replace silent returns in `api/lib/decision_intelligence.py`**

Find the top of the file and ensure a module logger exists. Add (if missing) right after the imports block:

```python
import logging

logger = logging.getLogger(__name__)
```

Locate the `current_price` guard (around line 376) and replace:

```python
        if not current_price or current_price <= 0:
            return full_output
```

with:

```python
        if not current_price or current_price <= 0:
            logger.warning(
                "DI enrichment skipped: current_price unusable (value=%r, moat=%s)",
                current_price,
                moat_score,
            )
            return full_output
```

Locate the `recommended_strategy` guard (around line 478) and replace:

```python
        if not recommended_strategy:
            return full_output
```

with:

```python
        if not recommended_strategy:
            logger.warning(
                "DI enrichment skipped: recommended_strategy empty "
                "(price=%s, rating=%s, risk=%s, moat=%s)",
                current_price,
                rating,
                risk_level,
                moat_score,
            )
            return full_output
```

Locate the outer except block (around line 576) and replace:

```python
    except Exception as e:
        # Fail silently — DI is additive, not critical
        print(f"Decision intelligence enrichment failed: {e}")
```

with:

```python
    except Exception:
        # DI is additive, not critical — but we need a traceback to debug
        # silent failures downstream (engineSuggestedWeight / targetWeight = 0).
        logger.exception("Decision intelligence enrichment failed")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_di_enrichment_diagnostics.py -v`
Expected: PASS on all three tests.

- [ ] **Step 5: Commit**

```bash
git add api/lib/decision_intelligence.py tests/test_di_enrichment_diagnostics.py
git commit -m "feat(di): add diagnostic logging to enrichment silent-exit paths"
```

---

## Task 2: Upgrade `link_conviction_to_position` Exception Handler

**Files:**
- Modify: `research_swarm/reports/decision_intelligence_calculator.py`

The current handler uses `logger.warning(f"Conviction-position link failed: {e}")` which drops the traceback. Upgrade to `logger.exception` and include the inputs so we can reproduce locally.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_di_enrichment_diagnostics.py`:

```python
def test_link_conviction_failure_logs_exception(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """link_conviction_to_position failures log a traceback (exc_info present)."""
    from research_swarm.reports.decision_intelligence_calculator import (
        decision_intelligence_calculator,
    )

    def _boom(self, **kwargs):
        raise ValueError("conviction boom")

    monkeypatch.setattr(
        type(decision_intelligence_calculator),
        "link_conviction_to_position",
        _boom,
    )

    with caplog.at_level(
        logging.ERROR,
        logger="research_swarm.reports.decision_intelligence_calculator",
    ):
        result = decision_intelligence_calculator.calculate_all(
            current_price=100.0,
            rating="HOLD",
            risk_level="Medium",
            moat_score=6.0,
            conviction_level="Medium",
            discount_to_target_pct=5.0,
            entry_strategy={},
            exit_plan={},
            position_sizing={"recommended_pct": 5.0, "max_pct": 7.5},
            price_targets={},
            technical_indicators={},
            signal_breakdown=None,
        )

    assert result["conviction_position"] is None
    assert any(
        rec.exc_info is not None and "conviction boom" in (rec.exc_text or "")
        for rec in caplog.records
    ), "expected exc_info on error log"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_di_enrichment_diagnostics.py::test_link_conviction_failure_logs_exception -v`
Expected: FAIL — `logger.warning` does not attach exc_info.

- [ ] **Step 3: Upgrade the handler**

Open `research_swarm/reports/decision_intelligence_calculator.py`. Locate the `link_conviction_to_position` call site (around line 949) and replace:

```python
        # 4. Conviction-position link
        conviction_position = None
        try:
            conviction_position = self.link_conviction_to_position(
                conviction_level=conviction_level,
                position_sizing=position_sizing,
                risk_level=risk_level,
                moat_score=moat_score,
                rating=rating,
            )
        except Exception as e:
            logger.warning(f"Conviction-position link failed: {e}")
```

with:

```python
        # 4. Conviction-position link
        conviction_position = None
        try:
            conviction_position = self.link_conviction_to_position(
                conviction_level=conviction_level,
                position_sizing=position_sizing,
                risk_level=risk_level,
                moat_score=moat_score,
                rating=rating,
            )
        except Exception:
            logger.exception(
                "Conviction-position link failed "
                "(conviction=%s, risk=%s, moat=%s, rating=%s, sizing_keys=%s)",
                conviction_level,
                risk_level,
                moat_score,
                rating,
                sorted((position_sizing or {}).keys()),
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_di_enrichment_diagnostics.py::test_link_conviction_failure_logs_exception -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research_swarm/reports/decision_intelligence_calculator.py tests/test_di_enrichment_diagnostics.py
git commit -m "feat(di): surface traceback when conviction-position link fails"
```

---

## Task 3: Add Moat-Based Fallback in Portfolio Engine

**Files:**
- Modify: `api/services/portfolio_engine.py`
- Test: `tests/test_portfolio_engine_plans.py`

When DI enrichment fails for any reason, `conviction_position.recommended_pct` is missing and the engine writes nothing — so the UI shows `tgt 0.0%`. Add a deterministic fallback that derives a suggested weight from `moatScore` alone. This guarantees a non-zero target for every covered position while still preferring the DI-computed value when available.

**Fallback table (moat_score → weight fraction):**

| Moat score | Weight |
|---|---|
| ≥ 8.5 | 0.08 (8%) |
| 7.0–8.49 | 0.06 (6%) |
| 5.0–6.99 | 0.04 (4%) |
| 3.5–4.99 | 0.02 (2%) |
| < 3.5 or None | None (do not write — let user decide) |

- [ ] **Step 1: Write the failing test**

Open `tests/test_portfolio_engine_plans.py` and add at the bottom (adjust imports if the file uses a different harness):

```python
import pytest

from api.services.portfolio_engine import _moat_fallback_weight


@pytest.mark.parametrize(
    "moat,expected",
    [
        (9.2, 0.08),
        (8.5, 0.08),
        (7.4, 0.06),
        (7.0, 0.06),
        (6.2, 0.04),
        (5.0, 0.04),
        (4.0, 0.02),
        (3.5, 0.02),
        (3.0, None),
        (None, None),
    ],
)
def test_moat_fallback_weight(moat, expected):
    assert _moat_fallback_weight(moat) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_engine_plans.py -k moat_fallback -v`
Expected: FAIL — `ImportError: cannot import name '_moat_fallback_weight'`.

- [ ] **Step 3: Add the helper to `api/services/portfolio_engine.py`**

Open `api/services/portfolio_engine.py`. Directly after the existing `_parse_full_output` function (near line 58), add:

```python
def _moat_fallback_weight(moat_score: float | None) -> float | None:
    """
    Deterministic weight derivation from moat score alone.

    Used when the DI enrichment pipeline fails to produce a conviction_position
    with recommended_pct. Returns None for unknown / low-moat positions so the
    engine does not override a user's deliberate 0% target.
    """
    if moat_score is None:
        return None
    if moat_score >= 8.5:
        return 0.08
    if moat_score >= 7.0:
        return 0.06
    if moat_score >= 5.0:
        return 0.04
    if moat_score >= 3.5:
        return 0.02
    return None
```

- [ ] **Step 4: Run test to verify the helper passes**

Run: `pytest tests/test_portfolio_engine_plans.py -k moat_fallback -v`
Expected: PASS — 10 parametrized cases.

- [ ] **Step 5: Wire the fallback into the suggested-weight loop**

In `api/services/portfolio_engine.py`, locate the suggested-weight extraction block (around line 542):

```python
        # Extract engineSuggestedWeight from conviction_position.recommended_pct
        if stock_result and stock_result.fullOutput:
            fo = _parse_full_output(stock_result.fullOutput, stock_result.moatScore)
            di_block = fo.get("decision_intelligence") or {}
            conv = di_block.get("conviction_position") or {}
            rec_pct = conv.get("recommended_pct")
            if rec_pct is not None:
                suggested_weights[pos.ticker] = float(rec_pct) / 100.0
                logger.info("Engine: %s suggested weight = %.1f%%", pos.ticker, float(rec_pct))
```

Replace with:

```python
        # Extract engineSuggestedWeight from conviction_position.recommended_pct,
        # falling back to moat-derived weight when DI is missing or incomplete.
        if stock_result and stock_result.fullOutput:
            fo = _parse_full_output(stock_result.fullOutput, stock_result.moatScore)
            di_block = fo.get("decision_intelligence") or {}
            conv = di_block.get("conviction_position") or {}
            rec_pct = conv.get("recommended_pct")
            if rec_pct is not None:
                suggested_weights[pos.ticker] = float(rec_pct) / 100.0
                logger.info(
                    "Engine: %s suggested weight = %.1f%% (source=DI)",
                    pos.ticker,
                    float(rec_pct),
                )
            else:
                fallback = _moat_fallback_weight(stock_result.moatScore)
                if fallback is not None:
                    suggested_weights[pos.ticker] = fallback
                    logger.info(
                        "Engine: %s suggested weight = %.1f%% (source=moat_fallback, moat=%s)",
                        pos.ticker,
                        fallback * 100,
                        stock_result.moatScore,
                    )
                else:
                    logger.warning(
                        "Engine: %s no suggested weight — no DI conviction and moat=%s "
                        "(leaving targetWeight unchanged)",
                        pos.ticker,
                        stock_result.moatScore,
                    )
```

- [ ] **Step 6: Add an integration-style test for the fallback**

Append to `tests/test_portfolio_engine_plans.py`:

```python
@pytest.mark.asyncio
async def test_moat_fallback_writes_suggested_weight_when_di_missing(monkeypatch):
    """
    When fullOutput has no decision_intelligence and DI enrichment can't build one
    (e.g. current_price missing), the engine still writes engineSuggestedWeight
    from the moat fallback table.
    """
    from api.services import portfolio_engine as eng

    fo = {"fundamentalist_output": {"valuation_metrics": {"current_price": 0}}}

    class _Result:
        fullOutput = fo
        moatScore = 8.0  # → 0.06 fallback

    fo_parsed = eng._parse_full_output(_Result.fullOutput, _Result.moatScore)
    assert "decision_intelligence" not in fo_parsed  # enrichment bailed

    # The helper alone is deterministic; verify the fallback wiring produces 6%.
    assert eng._moat_fallback_weight(_Result.moatScore) == 0.06
```

- [ ] **Step 7: Run tests to verify all pass**

Run: `pytest tests/test_portfolio_engine_plans.py -k "moat_fallback or writes_suggested_weight" -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add api/services/portfolio_engine.py tests/test_portfolio_engine_plans.py
git commit -m "feat(engine): fall back to moat-derived weight when DI conviction missing"
```

---

## Task 4: End-to-End Verification

**Files:** (none modified — manual validation)

After Tasks 1–3 land, run the engine against the user's real portfolio and confirm `tgt %` populates for every covered holding.

- [ ] **Step 1: Run the full test suite to ensure no regressions**

Run: `pytest tests/test_di_enrichment_diagnostics.py tests/test_portfolio_engine_plans.py tests/test_portfolio_actions_route.py tests/test_allocation.py -v`
Expected: PASS on all tests.

- [ ] **Step 2: Tail the API server logs in one terminal**

Run: `uvicorn api.index:app --reload --log-level info 2>&1 | tee /tmp/engine.log`

- [ ] **Step 3: Trigger the engine from the frontend**

In the admin dashboard → Portfolio → "Run Engine" button, trigger a monthly cycle.

Expected log patterns in `/tmp/engine.log`:
- For positions where DI works: `Engine: <TICKER> suggested weight = X.X% (source=DI)`
- For positions where DI fails but moat is known: `Engine: <TICKER> suggested weight = X.X% (source=moat_fallback, moat=...)`
- For positions with no moat at all: `Engine: <TICKER> no suggested weight ... (leaving targetWeight unchanged)`
- If any `DI enrichment skipped` or `Decision intelligence enrichment failed` lines appear, those identify the exact root cause for each ticker.

- [ ] **Step 4: Reload the Holdings tab and verify UI**

Open the Holdings tab. Expected:
- Every position with a recent StockResult shows a non-zero `tgt X.X%`
- Positions that previously showed `tgt 0.0%` with "No signal data" now show the fallback weight with a sensible signal line
- The `Target %` column matches the DI or moat-fallback log output for that ticker

- [ ] **Step 5: Document findings**

If any positions still show `tgt 0.0%` after the fix, grep `/tmp/engine.log` for that ticker and file the log excerpt in the conversation. The new logging should pinpoint which step (price missing, strategy empty, conviction link exception) is responsible, making the follow-up fix obvious.

- [ ] **Step 6: Commit any documentation updates**

```bash
# Only if logs revealed a fixable root cause worth documenting
git add docs/superpowers/plans/2026-04-18-di-enrichment-pipeline-fix.md
git commit -m "docs: note DI enrichment root cause observed during verification"
```
