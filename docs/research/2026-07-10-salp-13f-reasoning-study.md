# SALP 13F Reasoning Study — six quarters of revealed thesis behavior

**Date:** 2026-07-10
**Source:** SEC EDGAR, Situational Awareness LP, CIK 0002045724, all six
13F-HR filings (periods 2024-12-31 → 2026-03-31), parsed from the raw
infotables (values, adds/drops, put/call).
**Purpose (owner-directed):** extract HOW this fund reasons — constraint
identification, timing, cap-size expression, lifecycle management — and
encode it into the theme-discovery reasoning layer. NOT copy-trading:
filings arrive 45 days stale; the value is the pattern, not the tickers.
**Caveat:** 13Fs show long US equity/options only (no shorts of record
beyond puts, no private book, no cost basis, no intra-quarter trades).
Inference below is exactly that — inference.

## The arc, quarter by quarter

**Q4-2024 ($255M, 6 names).** MRVL 34%, VST 23%, VRT 20%, TLN 11%, CEG 8%,
MOD 3%. Before "power is the bottleneck" was a consensus phrase, ~65% of
the book was power generation and thermal (IPPs, nuclear-adjacent, cooling).
The conspicuous absence: NVDA and every consensus AI megacap. They bought
what the buildout could not proceed without, not who sells the buildout.

**Q1-2025 ($1.0B, 12 names).** INTC 46% (a conviction-max contrarian bet on
US foundry when the name was left for dead), AVGO 12%, ONTO 7%; first
bitcoin-miner conversions appear small (IREN, APLD, CORZ, CRWV 5%) — the
"powered-shell" insight: miners own energized datacenter sites, repriceable
as AI capacity years before consensus; EQT 5% (natural gas feeds the power
constraint upstream).

**Q2-2025 ($2.1B, 9 names).** Consolidation: SMH 27% (broad-semis beta
while picking spots), INTC 21%, AVGO 15%, VST 12%; miners kept.

**Q3-2025 ($4.1B, 25 names).** CRWV 26%, INTC 16%, miners pressed
(CORZ 9%, IREN 8%), NVDA appears — small, 7%, late, never the bet. New
complexes: memory/storage (MU, SNDK, WDC, STX), optics (COHR, LITE), TSM,
and **BE (Bloom Energy)** — fuel cells as *fast-deployable* power, bought
before its late-2025 repricing. The constraint had migrated: compute
capacity was getting built, so what binds next is memory/storage and
interconnect — and power *on short time frames*.

**Q4-2025 ($5.5B, 25 names).** BE pressed to 17% (≈4× weight — press the
confirmed winner), CRWV 22%, LITE 9%; megacaps DROPPED entirely (NVDA,
AVGO, TSM, MU, WDC, STX, VST, SMH) after the run — asymmetry spent; and
the power thesis goes further down-cap and behind-the-meter: Babcock &
Wilcox (nuclear services), Power Solutions Intl (gensets), ProPetro and
Liberty Energy (frac fleets converted to power generation), CleanSpark,
Bitfarms, WhiteFiber. Grid power exhausted → bridge power binds.

**Q1-2026 ($13.7B, 29 names).** Megacaps re-enter (NVDA 11%, ORCL 8%,
AVGO 7%, AMD 7%, MU 7%, TSM, ASML) but **hedged**: puts of $1.57B NVDA,
$2.04B SMH, $1.0B AVGO, $969M AMD, $1.07B ORCL against the longs, calls
kept on MU/TSM/SNDK/CRWV. New smalls keep coming (HIVE, T1 Energy,
SharonAI); GLW (optical fiber — the interconnect constraint moving into
physical fiber); INFY puts (second-order: AI disrupts labor-arbitrage IT
services). Insurance is bought with options, not achieved by selling the
thesis.

## Extracted principles (the reasoning to encode)

1. **Buy the binding constraint, not the beneficiary.** Consensus buys
   who sells the theme; they buy what the theme cannot proceed without
   (power → cooling → shells → memory/storage → optics → fiber → bridge
   power). Pricing power and multi-year re-ratings live at the
   constraint.
2. **The constraint migrates — always ask "what binds NEXT."** Each
   quarter's book answers next quarter's bottleneck, not last year's.
   When a constraint becomes a consensus phrase, it is priced; rotate to
   the successor constraint.
3. **Time-to-solve is a stock-selection criterion.** Demand on short
   time frames accrues to whoever can deliver NOW: fuel cells, gensets,
   frac-fleet conversions, energized miner shells (months) — over
   elegant solutions (new nuclear, a decade). Bloom before repricing is
   this principle in one trade.
4. **Express one theme across the whole cap spectrum.** Megacap anchors
   for durability; small/mid pure-plays for asymmetry. The small caps
   inside a *confirmed* theme are where seeing-it-early pays multiples —
   surfaced precisely because cap-weighted consensus ignores them.
5. **Concentrate at peak conviction and press confirmed winners.**
   MRVL 34%, INTC 46%, CRWV 26%, BE 4×-pressed to 17%. Position size is
   an output of conviction, not a fixed band.
6. **Reduce via rotation or hedges, not thesis abandonment.** Exit when
   asymmetry is spent (megacaps after the run) or re-enter hedged with
   puts. Two valid ways down from a winner; "stop-loss" is neither.
7. **Trade the second-order effects too.** AI disrupts as well as
   demands (INFY puts). A theme's losers are part of the theme.

## Where this lands in the system

- Principles 1–4 and 7 → the monthly theme-discovery reasoning prompt
  (`execution/themes/prompts.py`), as a revealed-behavior block beside
  the SA method — wired via the thesis-hold redesign PR.
- Principle 5 (conviction-sized concentration) → the concentration-band
  experiment (own harness run, still out of scope).
- Principle 6 → already partially landed (thesis-hold redesign kills
  price exits); the hedge leg belongs to the future options sleeve.
- The future quarterly *13F study pass* (auto-fetch new filings, re-run
  this analysis, propose discovery adjustments) remains a separate spec;
  this document is its manual prototype and template.
