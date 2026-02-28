'use client'

// Phase 2 — Asymmetry & Scenario Panel
// Number-first hierarchy. Bar as visual confirmation only.
// Adds: Downside Severity, Upside Skew Ratio, Prob-Weighted Price Target.
// All computations are identical to PriceTargetsCard — presentation only.

import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import type { SignalBreakdown } from '@/types/api'

interface AsymmetryPanelProps {
  priceTargets: {
    bull_target: number
    bull_probability: number
    bull_assumptions: string
    base_target: number
    base_probability: number
    base_assumptions: string
    bear_target: number
    bear_probability: number
    bear_assumptions: string
    methodology: string
  }
  currentPrice: number
  ticker: string
  signalBreakdown?: SignalBreakdown | null
}

function pct(target: number, current: number): number {
  return ((target - current) / current) * 100
}
function fmtPct(v: number, force = false): string {
  return `${v > 0 || force ? (v > 0 ? '+' : '') : ''}${v.toFixed(1)}%`
}

export function AsymmetryPanel({ priceTargets, currentPrice, ticker: _ticker, signalBreakdown }: AsymmetryPanelProps) {
  const [showAssumptions, setShowAssumptions] = useState(false)

  const bearW  = priceTargets.bear_probability ?? 0.25
  const baseW  = priceTargets.base_probability ?? 0.50
  const bullW  = priceTargets.bull_probability ?? 0.25

  const bearPct = Math.round(bearW * 100)
  const basePct = Math.round(baseW * 100)
  const bullPct = Math.round(bullW * 100)

  const bearRet  = pct(priceTargets.bear_target, currentPrice)
  const baseRet  = pct(priceTargets.base_target, currentPrice)
  const bullRet  = pct(priceTargets.bull_target, currentPrice)

  // Probability-weighted price target
  const pwTarget =
    priceTargets.bear_target * bearW +
    priceTargets.base_target * baseW +
    priceTargets.bull_target * bullW
  const pwRet = pct(pwTarget, currentPrice)

  // Stability modifier for effective EV
  const stabMod = signalBreakdown?.data_integrity_confidence_factor ?? 1.0
  const effectivePwRet = pwRet * stabMod

  // Downside Severity: maximum modeled drawdown
  const downsideSeverity = bearRet   // most negative scenario return

  // Upside Skew Ratio: bull return / |bear return|
  const upsideSkewRatio = Math.abs(bearRet) > 0.01 ? bullRet / Math.abs(bearRet) : null

  // Scenario rows: ordered Base → Bull → Bear for quick scanning
  const rows = [
    {
      label: 'BASE CASE',
      weight: basePct,
      target: priceTargets.base_target,
      ret: baseRet,
      assumptions: priceTargets.base_assumptions,
      barColor: 'bg-blue-500/70',
      retColor: baseRet >= 0 ? 'text-success' : 'text-error',
      borderColor: 'border-l-blue-500',
      labelColor: 'text-blue-400',
    },
    {
      label: 'BULL CASE',
      weight: bullPct,
      target: priceTargets.bull_target,
      ret: bullRet,
      assumptions: priceTargets.bull_assumptions,
      barColor: 'bg-success/70',
      retColor: 'text-success',
      borderColor: 'border-l-success',
      labelColor: 'text-success',
    },
    {
      label: 'BEAR CASE',
      weight: bearPct,
      target: priceTargets.bear_target,
      ret: bearRet,
      assumptions: priceTargets.bear_assumptions,
      barColor: 'bg-error/70',
      retColor: 'text-error',
      borderColor: 'border-l-error',
      labelColor: 'text-error',
    },
  ]

  return (
    <div className="rounded-xl border border-border/70 bg-card overflow-hidden">

      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-border/40 flex items-start justify-between">
        <div>
          <h2 className="text-sm font-semibold text-text-primary tracking-tight uppercase">
            Asymmetry &amp; Scenarios
          </h2>
          <p className="text-[10px] text-text-tertiary/60 mt-0.5 uppercase tracking-wider">
            {priceTargets.methodology} · 12-Month calibration
          </p>
        </div>
        <span className="text-[9px] font-mono text-text-tertiary/50 border border-border rounded px-1.5 py-0.5 mt-0.5 shrink-0 uppercase tracking-wider">
          Probability-Weighted
        </span>
      </div>

      {/* Scenario rows — number-first */}
      <div className="divide-y divide-border/30">
        {rows.map(row => (
          <div
            key={row.label}
            className={`flex items-center gap-4 px-5 py-3.5 border-l-4 ${row.borderColor}`}
          >
            {/* Label + weight */}
            <div className="w-24 shrink-0">
              <p className={`text-[9px] font-bold uppercase tracking-[0.12em] ${row.labelColor}`}>
                {row.label}
              </p>
              <p className="text-[11px] font-bold font-mono text-text-secondary mt-0.5">
                {row.weight}%
              </p>
            </div>

            {/* Price target */}
            <div className="w-20 shrink-0">
              <p className="text-xl font-bold font-mono text-text-primary leading-none">
                ${row.target.toFixed(0)}
              </p>
              <p className={`text-xs font-mono font-semibold mt-0.5 ${row.retColor}`}>
                {fmtPct(row.ret, true)}
              </p>
            </div>

            {/* Visual bar — confirmation only */}
            <div className="flex-1 min-w-0">
              <div className="h-1.5 bg-surface-elevated rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${row.barColor}`}
                  style={{ width: `${Math.min(Math.abs(row.ret) * 2.5, 100)}%` }}
                />
              </div>
              <p className="text-[9px] text-text-tertiary/50 mt-0.5 truncate">
                {row.assumptions.split('.')[0]}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Derived metrics strip */}
      <div className="grid grid-cols-3 gap-px bg-border/30 border-t border-border/40">
        <div className="bg-surface-elevated/60 px-4 py-3">
          <p className="text-[9px] uppercase tracking-[0.12em] font-semibold text-text-tertiary">
            PW Price Target
          </p>
          <p className="text-xl font-bold font-mono text-text-primary mt-0.5">
            ${pwTarget.toFixed(0)}
          </p>
          <p className={`text-[11px] font-mono ${pwRet >= 0 ? 'text-success' : 'text-error'}`}>
            {fmtPct(pwRet, true)}
            {stabMod < 1 && (
              <span className="text-text-tertiary/50 ml-1">
                → eff {fmtPct(effectivePwRet, true)}
              </span>
            )}
          </p>
        </div>

        <div className="bg-surface-elevated/60 px-4 py-3">
          <p className="text-[9px] uppercase tracking-[0.12em] font-semibold text-text-tertiary">
            Downside Severity
          </p>
          <p className="text-xl font-bold font-mono text-error mt-0.5">
            {fmtPct(downsideSeverity, true)}
          </p>
          <p className="text-[10px] text-text-tertiary/60">
            Max modeled drawdown
          </p>
        </div>

        <div className="bg-surface-elevated/60 px-4 py-3">
          <p className="text-[9px] uppercase tracking-[0.12em] font-semibold text-text-tertiary">
            Upside Skew
          </p>
          <p className={`text-xl font-bold font-mono mt-0.5 ${
            upsideSkewRatio === null ? 'text-text-secondary' :
            upsideSkewRatio >= 2 ? 'text-success' :
            upsideSkewRatio >= 1 ? 'text-warning' :
            'text-error'
          }`}>
            {upsideSkewRatio !== null ? `${upsideSkewRatio.toFixed(1)}×` : '—'}
          </p>
          <p className="text-[10px] text-text-tertiary/60">
            Bull% ÷ |Bear%|
          </p>
        </div>
      </div>

      {/* Scenario assumptions toggle */}
      <div className="border-t border-border/30">
        <button
          onClick={() => setShowAssumptions(o => !o)}
          className="w-full flex items-center justify-between px-5 py-2.5 text-left hover:bg-surface-elevated/20 transition-colors"
        >
          <span className="text-[11px] text-text-tertiary/60 uppercase tracking-wider font-medium">
            Scenario Assumptions
          </span>
          {showAssumptions
            ? <ChevronUp className="h-3 w-3 text-text-tertiary/50" />
            : <ChevronDown className="h-3 w-3 text-text-tertiary/50" />}
        </button>

        {showAssumptions && (
          <div className="px-5 pb-4 pt-1 border-t border-border/20 space-y-3">
            {rows.map(row => (
              <div key={row.label} className={`border-l-2 ${row.borderColor.replace('border-l-4', 'border-l-2')} pl-3`}>
                <p className={`text-[9px] font-semibold uppercase tracking-wider mb-1 ${row.labelColor}`}>
                  {row.label} · {row.weight}%
                </p>
                <p className="text-[11px] text-text-tertiary leading-relaxed">
                  {row.assumptions}
                </p>
              </div>
            ))}
            <p className="text-[9px] text-text-tertiary/40 italic pt-1">
              Heuristic weights · regime-conditioned reliability · not forward guidance
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
