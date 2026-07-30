# Phase C — The Audit Surface (This Week Extension) — Design Spec

**Date:** 2026-07-30
**Status:** Approved direction (owner, 2026-07-30 conversation); spec pending owner review
**Parent:** `docs/superpowers/specs/2026-07-27-thesis-first-entry-redesign-design.md` §9
(Phase C). Supersedes the one-line "memo trail UI" description there and absorbs
the after-the-fact audit-trail design parked at approaches stage on 2026-07-20.

## 1. Why

The founding premise grades the engine by the owner auditing **reasoning +
P&L weekly, the way SALP's filings were audited by hand**. The data for that
audit is already written — every order journals its why, every memo records
its passes, every plan is validated — but almost none of it renders, and the
most important artifact is being thrown away:

- **Position plans are parsed, validated, and dropped.** Since PR #27 the memo
  writes a `position_plan` with every entry (absolute ladder rungs each with a
  why, a mandatory `thesis_break` condition, an exit posture with reasoning).
  Nothing persists it. The crowded-winner review's "what was our plan
  entering?" question reads back nothing.
- **The engine's "no" is invisible.** The memo records `passed_on` with
  reasons and stages themes `crowded` with rationale — its first act was
  refusing to add MU — but a week of disciplined passing renders identically
  to a week where nothing ran.
- **"Why that price" is half-recorded.** Each order journals its limit and
  entry style, but the derivation (`max(sma20, price − ATR)`) computes and
  discards its inputs. "Why $382.31" is unanswerable from the record.

Owner rulings that bind this design: engine visibility is an **after-the-fact
audit trail, never an approval gate** (2026-07-20 — "what's missing is the
WHY — trigger, gate values, verdict, sizing math next to each action"); the
owner's stated reading is *"whatever the picks are, I want the why, why that
price, and the plan if we enter"* with the null case — "nothing attractive at
these prices" — surfaced as a first-class outcome (2026-07-30).

## 2. Shape

Extend the existing **This Week** admin tab (the page that already joins live
broker positions to the memo's reasoning) into the audit surface. No new tab,
no new endpoint. Three small write-side additions give the glass something to
show; the read side is one endpoint extension and one component split.

Everything in this phase **records more and shows more, and decides
nothing** — no change to entries, exits, sizing, stages, or Sleeve B.

## 3. Write side

### 3.1 Persist the position plan

- New nullable column on `EnginePosition`: `positionPlan Json?`. Hand-written
  SQL + `prisma migrate deploy` (see memory `prisma-migrate-dev-broken`);
  deploy before merge, per standing rule.
- The validated plan (output of `execution/thesis/position_plan.validate_plan`
  — rungs with levels and whys, `thesis_break`, `exit_plan` posture +
  reasoning) rides the order's journal dict at submit — the same vehicle that
  already carries `why_now` / `why_this_expression` / `stage` from
  `inngest_app/functions/sleeve_a_funnel.py` into `apply_fill` → the
  position row.
- On fill, the plan lands in `positionPlan`. An `add` whose memo action
  carries a new plan **overwrites** — latest plan wins. An entry without a
  plan (the memo dropped a malformed one — loud, per PR #27's posture) leaves
  the column null.
- Existing positions predate persistence and stay null until the memo next
  touches them.

### 3.2 Journal the price math

The `entry_order` journal dict gains the derivation inputs alongside the
limit they produced: `price` (last close at decision), `sma20`, `atr`.
`entry_style` and `dist_200wma` are already journaled. This makes every
future order's price self-explaining: *pullback limit = max(sma20, price −
ATR)*, at-market limit = last close.

### 3.3 Price-conditional passes

`passed_on` entries (`execution/thesis/parser.py::_passed_on`) gain an
optional `reconsider_if` string — the memo's own statement of what would
change its mind: a price ("below ~$700"), evidence ("interconnect lead times
blowing out"), or both. One prompt line teaches it; the parser accepts and
passes it through; the ledger rows the week endpoint already reads carry it
with no storage change. Absent → omitted, never fabricated.

## 4. Read side

### 4.1 API — extend `GET /autopilot/week`

(`api/routes/autopilot.py::get_week`; no new endpoint.)

- **Positions** gain:
  - `plan`: the persisted `positionPlan` verbatim (rungs, `thesis_break`,
    exit posture + why), or null.
  - `entry_forensics`: joined from the symbol's latest `entry_order`
    EngineReport row — `limit_price`, `entry_style`, `price`, `sma20`, `atr`,
    `dist_200wma`, `add_tranche_fraction`. Null when no journal row exists
    (pre-journal entries).
- **Response** gains `market_view`: the memo's 3–6-sentence read on where we
  are in the buildout (already stored verbatim in the `thesis_memo` journal
  row / memo body — surfaced, not recomputed).
- **`actions`** (the decided-but-not-held list) gains `reconsider_if`.
- Degrade posture unchanged: broker down → reasoning still renders
  (`broker_ok=False`); missing journal row → `entry_forensics` null; null
  plan → null, labeled by the UI, never invented.

### 4.2 UI — WeekPanel splits into subcomponents

(`frontend/components/autopilot/WeekPanel.tsx`, currently ~254 lines, grows
past comfort — split by responsibility:)

- **`PositionCard`** — each holding, expandable into its dossier:
  - the ladder drawn with the current price marked against it; each rung
    shows level, size fraction, and its why. **No hit/pending attribution in
    v1** — that requires fills history and can lie; a rung is a stated
    intention, not a claimed fill.
  - exit posture with its reasoning, and the `thesis_break` condition
    verbatim — the line the owner reads during a drawdown week.
  - entry why (`why_now`, `why_this_expression`, role, stage at entry) and
    the price math, rendered as a sentence: *"pullback limit $382.31 = price
    $391.00 − ATR $8.70, floored at SMA20 $380.10."*
  - positions with no plan on file show **"no plan recorded (pre-Phase-C
    entry)"** — an explicit label, not an empty box.
- **`DecisionsSection`** — everything decided this week: entries (with price
  math), passes (reason + `reconsider_if`), exits (their written arguments).
- **`NoBuyBanner`** — a week whose memo placed zero buys renders
  `market_view` as a headline: *"Nothing at attractive prices this week —
  here's what we saw."* Deliberate decision, visually distinct from an empty
  page and from a failed run.

## 5. Explicitly deferred (not lost — listed so they aren't re-litigated)

- **Placing ladder rungs as live resting orders** — execution behavior with
  real order-management risk (duplicate-guard, TTL, replace semantics);
  deserves its own pass after the owner has watched plans render for a few
  weeks.
- **Rung fill-attribution** (hit/pending) — needs fills history; v2.
- **Theme trail over weeks** (evidence → prediction → outcome per theme) and
  **position dossier pages** — natural v2 once plan data has history.
- **Rulebook UI** — cheap but different reading; separate small feature.

## 6. Failure posture

Unchanged contracts everywhere. The write-side additions live inside paths
that already never raise (order journal, memo parse-and-skip, fill
persistence); a malformed plan still costs the ladder loudly and never the
entry (PR #27 rule). The week endpoint keeps its degrade guarantees (§4.1).
The UI renders every absence as a labeled absence.

## 7. Testing

- Backend TDD: journal additions, `_passed_on` field pass-through, plan
  persistence through the fill path **with a replay-simulation test** (the
  fill path is Inngest; inline-step harnesses hide replay bugs — PR #12
  lesson), week-response assembly helpers (plan join, forensics join,
  market_view, no-buy detection) as pure functions.
- Frontend: `tsc --noEmit` + build, consistent with how the This Week tab
  shipped (no frontend test infra exists; not introduced here).
- Migration deployed to Neon before merge.

## 8. Non-goals

- Any change to entry/exit/sizing behavior, stage semantics, or Sleeve B.
- Approval gates of any kind (standing owner ruling).
- Backfilling plans or forensics for pre-Phase-C positions.
