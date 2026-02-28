'use client'

// Phase 1 — Executive Signal Panel
// Terminal-style capital signal display. Numbers dominate; methodology behind toggle.
// No new model logic — all values derived from existing outputs.

import { useState } from 'react'
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown } from 'lucide-react'
import type { SignalBreakdown, ConvictionPosition, FairValueCalibration } from '@/types/api'
import { deriveStructuralBias } from '@/lib/utils/decisionDimensions'

interface CapitalSignalPanelProps {
  rating: string | null
  ticker: string
  currentPrice: number
  fairValueCalibration?: FairValueCalibration | null
  priceTargets?: {
    bear_target: number
    bear_probability: number
    base_target: number
    base_probability: number
    bull_target: number
    bull_probability: number
  } | null
  expectedReturnAnnualized?: number | null
  signalBreakdown?: SignalBreakdown | null
  conviction?: ConvictionPosition | null
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function ratingColors(rating: string | null): { bg: string; border: string; text: string } {
  if (!rating) return { bg: 'bg-surface-elevated', border: 'border-border', text: 'text-text-secondary' }
  const r = rating.toUpperCase()
  if (['STRONG BUY', 'BUY', 'ACCUMULATE', 'BULLISH'].some(k => r.includes(k))) {
    return { bg: 'bg-success/10', border: 'border-success/40', text: 'text-success' }
  }
  if (['AVOID', 'SELL', 'REDUCE', 'BEARISH'].some(k => r.includes(k))) {
    return { bg: 'bg-error/10', border: 'border-error/40', text: 'text-error' }
  }
  return { bg: 'bg-warning/10', border: 'border-warning/40', text: 'text-warning' }
}

function signColor(v: number | null): string {
  if (v === null) return 'text-text-secondary'
  return v > 0 ? 'text-success' : v < 0 ? 'text-error' : 'text-text-secondary'
}

function fmt(v: number | null, sign = true, decimals = 1): string {
  if (v === null || isNaN(v)) return '—'
  return `${sign && v > 0 ? '+' : ''}${v.toFixed(decimals)}%`
}

function convictionTier(
  convictionLevel: string | undefined,
  recommendedPct: number | undefined,
  evPct: number | null,
): string {
  const level = (convictionLevel ?? '').toLowerCase()
  const pct = recommendedPct ?? 0
  const ev = evPct ?? 0
  if (level === 'high' && pct >= 5 && ev >= 15) return 'Strategic'
  if (level === 'high') return 'High'
  if (level === 'medium' || level === 'moderate') return 'Moderate'
  return 'Low'
}

function capitalEfficiencyScore(
  confidencePct: number | null,
  evPct: number | null,
  convictionPct: number | undefined,
): number {
  const conf = (confidencePct ?? 50) / 100
  const ev = Math.min(Math.max((evPct ?? 0) / 30, 0), 1)    // normalise: 30% EV = full score
  const conv = Math.min((convictionPct ?? 3) / 8, 1)          // normalise: 8% allocation = full
  return Math.round(conf * ev * conv * 100)
}

// ── Metric cell ────────────────────────────────────────────────────────────────

function MetricCell({
  label,
  value,
  valueClass = 'text-text-primary',
  sub,
}: {
  label: string
  value: React.ReactNode
  valueClass?: string
  sub?: string
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[9px] uppercase tracking-[0.13em] font-semibold text-text-tertiary">
        {label}
      </span>
      <span className={`text-xl font-bold font-mono leading-none ${valueClass}`}>
        {value}
      </span>
      {sub && (
        <span className="text-[9px] text-text-tertiary/60 font-mono">{sub}</span>
      )}
    </div>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────────

export function CapitalSignalPanel({
  rating,
  ticker,
  currentPrice,
  fairValueCalibration,
  priceTargets,
  expectedReturnAnnualized,
  signalBreakdown,
  conviction,
}: CapitalSignalPanelProps) {
  const [showMethodology, setShowMethodology] = useState(false)

  // ── Compute EV% from price targets ─────────────────────────────────────────
  let evPct: number | null = null
  if (priceTargets && currentPrice > 0) {
    const bearW = priceTargets.bear_probability ?? 0.25
    const baseW = priceTargets.base_probability ?? 0.50
    const bullW = priceTargets.bull_probability ?? 0.25
    const pw =
      priceTargets.bear_target * bearW +
      priceTargets.base_target * baseW +
      priceTargets.bull_target * bullW
    evPct = ((pw - currentPrice) / currentPrice) * 100
  }

  // ── Confidence ──────────────────────────────────────────────────────────────
  const rawConfidence =
    signalBreakdown?.confidence_integrity?.effective_confidence_pct ??
    ((signalBreakdown?.signal_strength ?? null) !== null
      ? Math.round((signalBreakdown!.signal_strength!) * 100)
      : null)

  // ── Effective EV (stability-adjusted) ──────────────────────────────────────
  const stabilityMod = signalBreakdown?.data_integrity_confidence_factor ?? 1.0
  const effectiveEvPct = evPct !== null ? evPct * stabilityMod : null

  // ── Fair value / implied upside ─────────────────────────────────────────────
  const fvMid = fairValueCalibration?.internal_fair_value ?? null
  const impliedUpside =
    fvMid && currentPrice > 0
      ? ((fvMid - currentPrice) / currentPrice) * 100
      : null

  // ── Risk-adjusted IRR ───────────────────────────────────────────────────────
  const irr = expectedReturnAnnualized ?? null

  // ── Allocator metrics (Phase 8) ──────────────────────────────────────────────
  let asymmetryRatio: number | null = null
  if (priceTargets && currentPrice > 0) {
    const bullRet = ((priceTargets.bull_target - currentPrice) / currentPrice) * 100
    const bearRet = ((priceTargets.bear_target - currentPrice) / currentPrice) * 100
    if (Math.abs(bearRet) > 0.01) asymmetryRatio = bullRet / Math.abs(bearRet)
  }

  const capEffScore = capitalEfficiencyScore(rawConfidence, effectiveEvPct, conviction?.recommended_pct)
  const tier = convictionTier(conviction?.conviction_level, conviction?.recommended_pct, effectiveEvPct)

  const bias = deriveStructuralBias(rating)
  const { bg: ratingBg, border: ratingBorder, text: ratingText } = ratingColors(rating)

  // Conviction tier color
  const tierColor =
    tier === 'Strategic' ? 'text-primary' :
    tier === 'High' ? 'text-success' :
    tier === 'Moderate' ? 'text-warning' :
    'text-text-tertiary'

  // Cap efficiency label
  const effLabel =
    capEffScore >= 65 ? 'HIGH' :
    capEffScore >= 35 ? 'MOD' :
    'LOW'
  const effColor =
    capEffScore >= 65 ? 'text-success' :
    capEffScore >= 35 ? 'text-warning' :
    'text-error'

  return (
    <div className="rounded-xl border border-border/70 bg-surface-elevated/60 overflow-hidden">

      {/* ── Header row ─────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-4 px-5 py-4 border-b border-border/50">
        {/* Rating badge */}
        <div className={`px-4 py-2 rounded-lg border ${ratingBg} ${ratingBorder} flex-shrink-0`}>
          <span className={`text-sm font-bold tracking-widest uppercase ${ratingText}`}>
            {bias || rating || '—'}
          </span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3 flex-wrap">
            <span className="text-base font-bold text-text-primary">{ticker}</span>
            <span className="text-base font-semibold font-mono text-text-primary">
              ${currentPrice.toFixed(2)}
            </span>
            {fvMid && (
              <span className="text-[11px] text-text-tertiary font-mono">
                FV {fvMid.toFixed(2)}
              </span>
            )}
            {fairValueCalibration?.divergence_state && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${
                fairValueCalibration.divergence_state === 'Consensus Validated ✓'
                  ? 'text-success border-success/30 bg-success/5'
                  : 'text-text-tertiary border-border/40'
              }`}>
                {fairValueCalibration.divergence_state}
              </span>
            )}
          </div>
          <p className="text-[10px] text-text-tertiary/60 mt-0.5 uppercase tracking-wider">
            Capital Signal · {fairValueCalibration?.regime ?? 'Regime'} · {fairValueCalibration?.display_label ?? ''}
          </p>
        </div>
      </div>

      {/* ── Primary metrics ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-px bg-border/30">
        {/* EV */}
        <div className="bg-surface-elevated/80 px-4 py-3">
          <MetricCell
            label="EV"
            value={fmt(effectiveEvPct)}
            valueClass={signColor(effectiveEvPct)}
            sub={effectiveEvPct !== evPct && evPct !== null ? `raw ${fmt(evPct)}` : undefined}
          />
        </div>

        {/* Confidence */}
        <div className="bg-surface-elevated/80 px-4 py-3">
          <MetricCell
            label="Confidence"
            value={rawConfidence !== null ? `${rawConfidence}` : '—'}
            valueClass={
              rawConfidence === null ? 'text-text-secondary' :
              rawConfidence >= 65 ? 'text-success' :
              rawConfidence >= 40 ? 'text-warning' :
              'text-error'
            }
            sub={
              signalBreakdown?.confidence_integrity?.ev_confidence_level
                ? signalBreakdown.confidence_integrity.ev_confidence_level
                : undefined
            }
          />
        </div>

        {/* Risk-Adjusted IRR */}
        <div className="bg-surface-elevated/80 px-4 py-3">
          <MetricCell
            label="Ann. IRR"
            value={fmt(irr)}
            valueClass={signColor(irr)}
            sub="annualised"
          />
        </div>

        {/* FV Mid */}
        <div className="bg-surface-elevated/80 px-4 py-3">
          <MetricCell
            label="FV Mid"
            value={fvMid ? `$${fvMid.toFixed(0)}` : '—'}
            valueClass="text-text-primary"
            sub={fairValueCalibration?.display_label ?? undefined}
          />
        </div>

        {/* Implied upside */}
        <div className="bg-surface-elevated/80 px-4 py-3">
          <MetricCell
            label="Implied ↑/↓"
            value={
              impliedUpside !== null ? (
                <span className="flex items-center gap-1">
                  {impliedUpside > 0
                    ? <TrendingUp className="h-4 w-4 flex-shrink-0" />
                    : <TrendingDown className="h-4 w-4 flex-shrink-0" />}
                  {fmt(impliedUpside)}
                </span>
              ) : '—'
            }
            valueClass={signColor(impliedUpside)}
            sub="vs FV mid"
          />
        </div>
      </div>

      {/* ── Allocator metrics ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-border/20">
        <div className="bg-surface-elevated/40 px-4 py-3">
          <MetricCell
            label="U/D Asymmetry"
            value={asymmetryRatio !== null ? `${asymmetryRatio.toFixed(1)}×` : '—'}
            valueClass={
              asymmetryRatio === null ? 'text-text-secondary' :
              asymmetryRatio >= 2.0 ? 'text-success' :
              asymmetryRatio >= 1.0 ? 'text-warning' :
              'text-error'
            }
            sub="bull ÷ |bear|"
          />
        </div>

        <div className="bg-surface-elevated/40 px-4 py-3">
          <MetricCell
            label="PW Return"
            value={fmt(effectiveEvPct)}
            valueClass={signColor(effectiveEvPct)}
            sub="prob-weighted"
          />
        </div>

        <div className="bg-surface-elevated/40 px-4 py-3">
          <MetricCell
            label="Cap Efficiency"
            value={
              <span className="flex items-baseline gap-1.5">
                <span className={effColor}>{effLabel}</span>
                <span className="text-sm text-text-tertiary font-normal">{capEffScore}</span>
              </span>
            }
            valueClass=""
            sub="conv × conf × ev"
          />
        </div>

        <div className="bg-surface-elevated/40 px-4 py-3">
          <MetricCell
            label="Conviction Tier"
            value={tier}
            valueClass={`${tierColor} text-base`}
            sub={conviction?.conviction_level ?? undefined}
          />
        </div>
      </div>

      {/* ── Methodology toggle ──────────────────────────────────────────────── */}
      <div className="border-t border-border/30">
        <button
          onClick={() => setShowMethodology(o => !o)}
          className="w-full flex items-center justify-between px-5 py-2.5 text-left hover:bg-surface-elevated/20 transition-colors"
        >
          <span className="text-[11px] text-text-tertiary/60 uppercase tracking-wider font-medium">
            View Signal Methodology
          </span>
          {showMethodology
            ? <ChevronUp className="h-3 w-3 text-text-tertiary/50" />
            : <ChevronDown className="h-3 w-3 text-text-tertiary/50" />}
        </button>

        {showMethodology && (
          <div className="px-5 pb-4 pt-1 space-y-3 border-t border-border/20">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">

              <div className="rounded border border-border/40 px-3 py-2 space-y-1">
                <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/60">EV Source</p>
                {priceTargets ? (
                  <p className="text-text-tertiary leading-relaxed">
                    Scenario-weighted: bear×{Math.round((priceTargets.bear_probability ?? 0.25) * 100)}%
                    · base×{Math.round((priceTargets.base_probability ?? 0.50) * 100)}%
                    · bull×{Math.round((priceTargets.bull_probability ?? 0.25) * 100)}%
                    {stabilityMod < 1 && (
                      <span className="text-warning"> · stability adj {(stabilityMod * 100).toFixed(0)}%</span>
                    )}
                  </p>
                ) : (
                  <p className="text-text-tertiary/50 italic">No price target data</p>
                )}
              </div>

              <div className="rounded border border-border/40 px-3 py-2 space-y-1">
                <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/60">Confidence Source</p>
                <p className="text-text-tertiary leading-relaxed">
                  {signalBreakdown?.confidence_integrity
                    ? `Probabilistic engine — ${signalBreakdown.confidence_integrity.ev_confidence_level} · base ${signalBreakdown.confidence_integrity.base_confidence_pct?.toFixed(0) ?? '—'}% − ${signalBreakdown.confidence_integrity.total_degradation_pts?.toFixed(0) ?? '—'}pts degradation`
                    : signalBreakdown
                    ? `Signal composite: ${signalBreakdown.valid_signal_count ?? '—'}/${(signalBreakdown.valid_signal_count ?? 0) + (signalBreakdown.missing_signal_count ?? 0)} signals`
                    : '—'}
                </p>
              </div>

              <div className="rounded border border-border/40 px-3 py-2 space-y-1">
                <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/60">FV Method</p>
                <p className="text-text-tertiary leading-relaxed">
                  {fairValueCalibration
                    ? `${fairValueCalibration.regime} regime · dispersion ${fairValueCalibration.internal_method_dispersion_pct?.toFixed(1) ?? '—'}% across P/E + EV/EBITDA + DCF`
                    : '—'}
                </p>
              </div>

              <div className="rounded border border-border/40 px-3 py-2 space-y-1">
                <p className="text-[9px] font-semibold uppercase tracking-wider text-text-tertiary/60">Data Integrity</p>
                <p className="text-text-tertiary leading-relaxed">
                  {signalBreakdown
                    ? `${signalBreakdown.valid_signal_count ?? '—'} valid signals · integrity ${((signalBreakdown.data_integrity_pct ?? 1) * 100).toFixed(0)}% · ${signalBreakdown.data_integrity_label ?? '—'}`
                    : '—'}
                </p>
              </div>

            </div>

            {signalBreakdown?.confidence_integrity?.confidence_note && (
              <p className="text-[10px] text-text-tertiary/50 italic border-l-2 border-border pl-2.5 leading-relaxed">
                {signalBreakdown.confidence_integrity.confidence_note}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
