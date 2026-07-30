# 13F Study — Compounding Method Rulebook (Phase B2) — Design Spec

**Date:** 2026-07-29
**Status:** Approved direction (owner ruling in conversation); spec pending owner review
**Extends:** §5 of `docs/superpowers/specs/2026-07-27-thesis-first-entry-redesign-design.md`
(the quarterly 13F study pass, shipped as Phase B / PR #29). Nothing in the
entry, exit, sizing, or Sleeve B paths changes.

## 1. Why — Phase B writes notes, not knowledge

Phase B as shipped studies one quarter's filing and writes a `study_digest`
row. The weekly memo reads the **newest** digest only. So each quarter's
lessons *replace* the last quarter's rather than building on them: the
system re-derives judgment from scratch every three months and never gets
faster at recognizing a setup it has already seen.

Owner ruling (2026-07-29): the point is for the engine to **think like SALP
going forward** — to look at a name like T1 Energy, reconstruct why it fits,
and carry that reasoning into future picks. That requires the curriculum to
**compound**. A system that only re-reads last quarter's notes is, in the
owner's words, behind the move.

## 2. The evidence that killed the mechanical fix (record this)

During the design conversation three mechanical entry filters were proposed
(a hard `dist_200wma` ceiling, a `dist_200wma` sizing penalty, and an
enforcement gate on the un-repriced preference). **All three were wrong**,
and the measured data is recorded here so no future pass re-proposes them.

Legacy RS-era entries (placed 2026-07-10), measured at entry:

| entry | vs 200-week MA at entry | % of ATH | P&L now |
|---|---|---|---|
| MU @ 991.64 | **+510.6%** | 81.7% | **−25.5%** |
| LRCX @ 353.17 | **+241.7%** | 81.5% | **−28.5%** |
| NVDA @ 202.78 | +93.8% | 86.1% | −6.3% |

All three were bought within ~19% of all-time highs set two to four weeks
earlier. LRCX's highest close *since entry* was its entry day.

The memo's first five entries (2026-07-28), by contrast, came in at −29%
(MARA), +25% (HUBB), +26% (CEG), +79% (ASML), +96% (AVGO) over the 200-week
MA, all with daily RSI 34–47, three of five *below* their 200-day MA.

**But the anchor does not discriminate.** Bloom Energy — the founding
premise's own calibration example, bought by the owner under $100 and by
SALP around $105 — first crossed $100 on 2025-10-13 at **+236% over its
200-day MA and +448% over its 200-week MA**. Its last 200-day touch was
May 2025 at ~$18.47. It is +63.7% from $100 today and was +245% at the June
2026 peak.

> MU entered at +511% over the 200-week and lost 25%.
> BE entered at +448% over the 200-week and made 60%+.

Any sizing penalty or ceiling built on distance-from-anchor would have
crushed the single best idea in the book while doing nothing about MU. The
anchor is noise for selection. It stays **visible and never voting**, exactly
as §3.1.4 of the parent spec already specifies.

**What actually discriminated:** BE at $100 had already repriced 6× but the
binding constraint was still tightening and data-center power was not yet
the story everyone was telling. MU at $991 *was* the story. The variable is
**where the thesis sits against consensus** — which the engine already
models as `stage`, and which already worked: the memo staged memory-hbm
`crowded` and refused to add to MU and LRCX. Those losses belong to the
retired RS system, which had no stage concept.

So the gap is not a missing filter. It is **judging stage accurately and
early**, and that is a judgment problem — the thing a compounding rulebook
improves and a threshold cannot.

## 3. The rulebook

A single living document, versioned quarterly. Not an accumulating pile of
digests (unbounded, unsynthesized, and it just makes the memo re-derive the
pattern every week) — a **revised** artifact.

```json
{
  "version": 3,
  "as_of": "2026-06-30",
  "rules": [{
    "id": "compute-priced-when-capex-is-consensus",
    "rule": "<one transferable decision rule>",
    "rationale": "<why it holds>",
    "evidence_quarters": ["2025-12-31", "2026-03-31"],
    "confirmations": 2,
    "first_seen": "2025-12-31",
    "last_reviewed": "2026-06-30",
    "status": "active"
  }],
  "retired": [{"id": "...", "rule": "...", "retired_because": "...",
               "retired_at": "2026-06-30"}],
  "calibration": {
    "typical_lead_quarters": 2.5,
    "lead_indicator_classes": ["interconnect queue data", "PPA filings"],
    "notes": "<how early they were, measured — see §4>"
  },
  "summary": "<3-6 sentences: how this fund thinks, current best synthesis>"
}
```

- Stored as `ThesisEvidence` with `kind="method_rulebook"`. Append-only, so
  every version survives — the row history **is** the audit trail of how the
  engine's thinking evolved, which is itself the thing the owner wants to be
  able to read back.
- **Bounded:** `RULEBOOK_MAX_RULES` (25). The revise step must retire to stay
  under the cap; it may not silently truncate.
- A rule's `confirmations` count rises only when a *later* quarter's evidence
  independently supports it. Rules that never get re-confirmed and never get
  contradicted stay `active` but visibly stale via `last_reviewed`.

## 4. Earliness calibration — the forward-looking measurement

Phase B already reconstructs `first_period` (the first quarter each position
appears) and per-quarter implied prices. That is the raw material for the
question that actually matters: **how far ahead of the headline were they, and
what tipped them off?**

For each material winner, the study asks (web search, pointed at the window
and the period *after* it):

1. When did this name become a mainstream story — the quarter the thesis
   became a consensus headline?
2. How many quarters before that does the position first appear?
3. What was observable in the earlier window that the headline later
   confirmed?

Aggregate answers land in the rulebook's `calibration` block. This is the
compounding quantity the owner asked for: not "how extended was it" but
"how early were they, and on what evidence."

## 5. The quarterly pass becomes study → revise

The Phase B cron gains one step. Both LLM calls are paid and each gets its
own memoized Inngest step, per the standing discipline.

```
fetch + diff + windows → study (PAID) → parse
                                      → revise rulebook (PAID) → parse
                                      → persist digest + new rulebook version
```

- **Study** (unchanged from Phase B, plus §4's earliness questions): what
  happened this quarter and what was knowable during each window.
- **Revise** (new): input = current rulebook + this quarter's digest. Every
  existing rule gets a verdict — `confirmed` / `sharpened` (restated more
  precisely, same id) / `unchanged` (not tested this quarter) / `retired`
  (contradicted, or revealed as quarter-specific noise). New rules are added
  from the digest. Output = the next rulebook version.
- The revise prompt is told explicitly that a rule surviving on narrative
  alone is weaker than one a later quarter independently confirmed, and that
  **retiring a rule is a first-class outcome** — a rulebook that only grows
  is a rulebook nobody edited.

## 6. What the weekly memo reads changes

The memo's `study_digest` prompt slot (§3.1.6 of the parent spec) carries the
**rulebook** instead of the raw quarterly digest. The digest becomes an input
to the revise step only.

This also closes the leak fixed late in Phase B by a different means: the
rulebook contains no issuer names, cusips, weights, or position values at
all, so the fund's book structurally cannot reach the prompt that authorizes
buys. Tickers keep **zero order authority** (unchanged, guard-tested).

## 7. Failure posture

Unchanged contract — the cron never raises, every step journals and degrades.
One new invariant, and it is the important one:

- **A failed or drifted revise leaves the PRIOR rulebook authoritative.**
  Compounding state must never be lost to a bad LLM response: journal
  `engine_failure`, persist the digest (the study was paid for and is
  useful), and write no new rulebook version.
- No rulebook yet (first ever run) → revise builds version 1 from the digest
  alone.
- Rulebook read failure → the memo runs with no rulebook and a journaled
  warning, exactly as it degrades today.

## 8. Testing

- Pure: rulebook parser (loud on drift), rule-merge semantics
  (confirmed/sharpened/unchanged/retired), cap enforcement with forced
  retirement, version increment, earliness aggregation.
- Replay: the revise step memoized independently of the study step — a
  persist retry must re-bill neither.
- Guards, extending Phase B's: the rulebook payload contains no issuer/cusip/
  weight/value fields; a drifted revise cannot blank an existing rulebook.

## 9. Considered and rejected

- **Any `dist_200wma` ceiling, sizing penalty, or entry gate** — §2. The
  measured evidence says the anchor does not discriminate.
- **Accumulating all quarterly digests into the memo prompt** — unbounded,
  and it pushes pattern synthesis into the weekly call every single week
  instead of doing it once per quarter.
- **Requiring the memo to name the cheaper same-theme alternative it passed
  over** — redundant with `passed_on`, which the memo already records, and it
  is the same mechanical instinct in a thinner disguise.

## 10. Non-goals

- Copy-trading, or any order authority for filing tickers (unchanged).
- Options/short expression of theses (still parked).
- Changes to stage semantics, the review triggers, sizing, or Sleeve B.
- Backtesting the rulebook's judgment — the paper account remains the test.
