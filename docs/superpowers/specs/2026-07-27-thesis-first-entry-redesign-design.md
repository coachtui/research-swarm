# Thesis-First Entry Redesign — Design Spec

**Date:** 2026-07-27
**Status:** Approved direction (owner ruling); spec pending owner review
**Supersedes:** the entry-selection half of the Phase 3C funnel design
(docs/superpowers/specs/2026-07-09-phase3c-sleeve-a-funnel-design.md). The
exit side (thesis-hold redesign, PR #12) is unchanged and this spec makes
entries symmetric with it.

## 1. Why (founding-premise ruling, 2026-07-27)

The Autopilot exists to look at markets the way Situational Awareness LP
does: form a forward thesis about where the binding constraint in the AI
buildout sits, enter **before the news catches on**, and hold until the
thesis is priced or broken. The owner's Bloom Energy entry (<$100, before
SALP's ~$105, long before the hype) is the calibration example.

The 2026-07-27 audit showed the shipped engine inverted this premise:

- All 9 consecutive Sleeve A entries came from the industry-RS channel
  (XOP/KRE/ITA top holdings); zero came from theme baskets.
- The candidate universe is seeded by `rank_1m` — the most recency-biased
  window computed anywhere in the codebase.
- `SCREEN_WEIGHTS` are ~60–70% trailing price; there is no valuation input
  at selection time and no conviction floor at entry (GD entered at 43.8).
- Entries fired at +43% to +151% above the 200-week MA. `dist_200wma`,
  `rsi14`, `detect_rotations`, and `next_constraints` are all computed and
  then never read by any decision.
- SALP's actual Q1-26 13F (CIK 0002045724) put ~62% of the book in puts on
  the semis complex while staying long power/storage/neocloud — the exact
  inverse of what an RS-ranked engine buys in that tape.

Owner ruling: buying strength and averaging down is "lose money investing."
Entries must flow from thesis and evidence. Momentum may inform sizing and
timing; it must never pick the direction. See memory
`autopilot-thesis-first-founding-premise`.

**Backtesting is a non-goal.** The Alpaca paper account is the test bed;
the engine is graded by auditing its written reasoning and its P&L there.

## 2. Architecture

The Monday funnel cron keeps its skeleton — cron slot, journal, broker
client, caps, cash ledger, failure posture — and its **entry side is
replaced** by a weekly thesis pass:

```
gather context → LLM thesis memo (Sonnet + web search) → parse + validate
→ diligence (paid full run, veto-only) → size → place limit orders
```

- The weekly memo is the **only buy authority**, symmetric with the
  LLM-review-only sell authority from the thesis-hold redesign.
- Deleted from the entry path (not down-weighted — deleted, so no formula
  in the codebase can pick a stock): the `plan_decisions` entry queue and
  challenger logic, the screen-score selector, the conviction-formula gate,
  and the industry-ETF top-holdings universe channel as an entry source.
- Every active theme gains a `stage` the memo must assign weekly:
  `pre_consensus → catching_on → crowded → priced`.
  Entries are legal only in `pre_consensus` and `catching_on`. A move to
  `crowded`/`priced` fires the existing thesis review (which already owns
  sell authority) for every holding sourced from that theme — this is the
  SALP-exits-optics behavior. Stage never auto-sells.
- Sleeve B (control) reads none of this. `REGIME_INVESTED_FRACTION` is
  never touched.

## 3. The weekly thesis memo

One Sonnet call with server-side web search (budget ~15 uses), Monday
before order placement. Journaled verbatim to EngineReport.

### 3.1 Inputs (the packet)

1. **Active theses** — slug, thesis, binding constraint, leading
   indicators, current stage, constituents, and each thesis's
   **evidence ledger**: what prior memos observed, predicted, and decided
   (last ~8 weeks). The memo must reconcile prior predictions with what
   happened before it may act.
2. **`next_constraints` hypotheses** from the same ledger, each with
   indicator status. The memo may graduate a hypothesis to a proposed
   theme when its indicators confirm (routed through the existing monthly
   apply/validation machinery).
3. **Current book** — every position with entry basis, thesis linkage,
   stage of its sourcing theme, unrealized P&L.
4. **Crowdedness gauges, explicitly inverted** — theme/sector/industry RS
   rankings framed as "what is already priced"; per-candidate
   `dist_200wma` and `rsi14` framed as "how much repricing already
   happened." Hot = late = entries close and exits open. Weak RS on a
   thesis whose evidence is confirming is the highest-priority setup (the
   BE anatomy, stated in the prompt).
5. **Numbers packet per candidate** — light-runner outputs (fair-value
   gap, valuation score, insider, dark pool, short % float), visible but
   never voting.
6. **Latest 13F study digest** (§5) — method rules, not tickers.
7. **Regime/breadth context** from the weekly outlook (information only).

### 3.2 Output schema (JSON, parsed with the loud-on-drift posture)

```json
{
  "theses": [{
    "slug": "dc-energy",
    "evidence_this_week": ["<observation with source>", "..."],
    "stage": "pre_consensus | catching_on | crowded | priced",
    "stage_rationale": "<1-2 sentences citing evidence>",
    "actions": [{
      "action": "enter | add | review | hold",
      "ticker": "BE",
      "role": "anchor | pure_play | catalyst",
      "why_now": "<1 falsifiable sentence>",
      "why_this_expression": "<1 sentence — why this name and not the obvious one>",
      "conviction": 0.0,
      "entry_style": "at_market | on_pullback"
    }]
  }],
  "hypothesis_updates": [{
    "hypothesis": "<existing or new>",
    "indicator_observations": ["..."],
    "verdict": "confirming | unclear | disconfirmed | graduate_to_theme"
  }],
  "market_view": "<3-6 sentences: where we are in the buildout, what binds next>"
}
```

"No action" everywhere is a first-class, expected answer. Web search is
pointed at the theses' **specific leading indicators** (power contracts,
lead times, capex, physical commitments), not generic news.

## 4. From memo to orders — what mechanics keep

For each `enter`/`add`, in order:

1. **Validation floors (non-negotiable):** Alpaca-tradable universe gate,
   ADV/mcap/price floors, ticker↔company cross-check. Unchanged.
2. **Diligence, not gatekeeping:** the paid full analysis still runs
   (FULL_RUNS_PER_WEEK budget stays, memoized-step billing discipline
   stays). Its only powers are veto on SELL verdict or unusable data. It
   cannot rank the memo's picks.
3. **Sizing:** memo conviction × role maps into the 3–12% band (anchors
   top of band, catalysts bottom); vol ceiling, 1%-of-ADV cap,
   theme/sector aggregate caps, cash ledger, exposure floors — all keep
   full authority. Mechanics size; they never select.
4. **Entry price:** `at_market` → limit at last close (current behavior);
   `on_pullback` → the existing patient-limit machinery
   (max(sma20, price − ATR), 2-week TTL). The memo chooses per entry; it
   has `dist_200wma` and ATR in hand when it does.

DCA ladder, earnings-divergence adds, all five review triggers, exposure
floors, duplicate-order guard, coid idempotency: unchanged — now pointed
at thesis-selected names, which is what they were designed for.

Light runs shrink to the shortlist the memo is actually weighing
(holdings + active-theme constituents + hypothesis candidates), not a
191-name screen.

## 5. Quarterly 13F study pass

New cron (quarterly, ~1 week after the 45-day 13F deadline). Trusted-fund
list starts with SALP (CIK 0002045724; also Situational Awareness
Partners LP, CIK 0002038540) and is extensible.

**Explicitly NOT thesis adoption or copy-trading.** By filing time the
positions are ~7 weeks stale — acting on them is already late. The filing
is an **answer key for a test the market already gave**:

1. Pull current + prior 13F info tables from EDGAR; diff positions
   (new/exited/resized, including puts/calls).
2. For each material move, reconstruct the **entry/exit window**: first
   quarter the position appears, share-count deltas, position value vs.
   that quarter's price range → estimate roughly when and where they
   acted.
3. LLM reconstructs **what was publicly knowable during that window** —
   before the hype — that justified the move (web search over
   that-period news: contracts, lead times, capex announcements).
4. Deliverable: **method rules**, e.g. "when compute capex accelerates
   and grid lead times blow out, the deliver-now power name reprices;
   indicator pattern that preceded it was X" / "they treated compute as
   priced when Y became a consensus headline."
5. Digest lands in the evidence ledger; feeds every weekly memo (§3.1.6)
   and the monthly discovery prompt. Tickers from filings get **zero
   direct authority** over orders.

## 6. Storage

- **New table `ThesisEvidence`** (append-only ledger):
  `id, createdAt, kind (weekly_memo | hypothesis | study_digest),
  themeSlug?, hypothesisKey?, week, stage?, body Json`. Indexed on
  (themeSlug, createdAt) and (kind, createdAt).
- **`stage` column on ThemeBasket** (nullable string; null = not yet
  assigned).
- Weekly memos and study digests also journal to EngineReport (types
  `thesis_memo`, `study_digest`) for the existing admin surface.
- Migration via hand-written SQL + `prisma migrate deploy` (see memory
  `prisma-migrate-dev-broken`).

## 7. Failure posture

Unchanged from the funnel contract: the cron never raises; every step
catches, journals `engine_failure`, and degrades. Specifics:

- Memo parse failure or schema drift → loud `engine_failure` + **no-op
  week** (no orders). Never guess.
- Web search unavailable → memo still runs; must mark evidence as
  "unverified this week"; entries in `pre_consensus` stage are deferred
  (evidence-gated entries need evidence).
- Ledger read failure → memo runs stateless with a journaled warning.
- Every entry order journals the memo excerpt that authorized it
  (why_now, stage, evidence) — the after-the-fact audit trail ruling.

## 8. Testing

- Pure functions unit-tested as today: memo parser (loud on drift), stage
  transition rules, ledger assembly/truncation, sizing mapping,
  entry-style routing, 13F diff + entry-window estimation.
- Inngest wiring gets replay-simulation tests (lesson from PR #12: inline
  step harnesses hide replay bugs; paid steps memoized).
- Strategy-level grading happens on the **paper account**: every order
  carries its written thesis, so the owner audits reasoning + P&L weekly
  the same way SALP's filings were audited by hand on 2026-07-27.

## 9. Build order (one spec, phased plan)

1. **Phase A — memo engine + entry rewire** (the fix): ThesisEvidence
   table, stage column, memo prompt/parser/planner, order pipeline rewire,
   deletion of the RS entry channel, funnel cron surgery.
2. **Phase B — quarterly 13F study pass**: EDGAR fetch, diff, window
   reconstruction, digest into ledger.
3. **Phase C — admin surfacing**: memo trail UI on the Outlook/audit tab
   (rides the existing after-the-fact audit-trail design when it lands).

## 10. Non-goals

- Backtesting the LLM's judgment (paper account is the test).
- Options/short expression of theses (SALP's put book is out of scope;
  parked as a separate founding-premise conversation).
- Copy-trading any filing.
- Any change to Sleeve B, the shared regime constants, or the
  user-facing research flow.
