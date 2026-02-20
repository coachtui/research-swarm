'use client'

import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, Scale, AlertTriangle } from 'lucide-react'
import type { FairValueCalibration } from '@/types/api'

const STORAGE_KEY = 'dvrg_fv_regime_check_expanded'

interface FairValueRegimeCheckProps {
  calibration: FairValueCalibration
}

function fmt(n: number | null | undefined): string {
  if (n == null) return 'N/A'
  return `$${n.toFixed(2)}`
}

function fmtPct(n: number | null | undefined, alwaysSign = false): string {
  if (n == null) return 'N/A'
  const sign = alwaysSign && n > 0 ? '+' : ''
  return `${sign}${n.toFixed(1)}%`
}

function fmtRatio(r: number | null | undefined): string {
  if (r == null) return 'N/A'
  return r.toFixed(3) + 'x'
}

function StateChip({ state, warning }: { state: string; warning: boolean }) {
  if (warning) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-error/10 text-error border border-error/20">
        <AlertTriangle className="h-3 w-3" /> Model Stability Warning
      </span>
    )
  }
  if (state === 'Consensus Validated ✓') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-success/10 text-success border border-success/20">
        Consensus Validated ✓
      </span>
    )
  }
  if (state === 'Model-Driven Upside Scenario') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
        Model-Driven Upside
      </span>
    )
  }
  if (state === 'Model-Conservative Regime') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
        Model-Conservative
      </span>
    )
  }
  // No Consensus Data
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-surface-elevated text-text-tertiary border border-border">
      No Consensus Data
    </span>
  )
}

function DivergenceBadge({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-text-tertiary">—</span>
  const abs = Math.abs(pct)
  let color = 'text-text-secondary'
  if (abs > 40) color = 'text-error font-semibold'
  else if (abs > 20) color = 'text-warning'
  return (
    <span className={color}>
      {pct > 0 ? '+' : ''}{pct.toFixed(1)}%
    </span>
  )
}

export function FairValueRegimeCheck({ calibration }: FairValueRegimeCheckProps) {
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'true') {
      setExpanded(true)
    } else if (
      calibration.model_stability_warning ||
      Math.abs(calibration.divergence_pct ?? 0) > 30
    ) {
      setExpanded(true)
    }
  }, [calibration.divergence_pct, calibration.model_stability_warning])

  const toggle = () => {
    const next = !expanded
    setExpanded(next)
    localStorage.setItem(STORAGE_KEY, String(next))
  }

  const { divergence_state, model_stability_warning } = calibration

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between px-5 py-4 bg-surface hover:bg-surface-elevated transition-colors text-left"
      >
        <div className="flex items-center gap-2.5">
          <Scale className="h-4 w-4 text-text-tertiary" />
          <span className="text-sm font-medium text-text-primary">Fair Value Regime</span>
          <StateChip state={divergence_state} warning={model_stability_warning} />
        </div>
        {expanded
          ? <ChevronUp className="h-4 w-4 text-text-tertiary flex-shrink-0" />
          : <ChevronDown className="h-4 w-4 text-text-tertiary flex-shrink-0" />
        }
      </button>

      {expanded && (
        <div className="border-t border-border p-5 space-y-4">

          {/* Stability warning — top priority if present */}
          {model_stability_warning && (
            <div className="rounded-md p-3.5 bg-error/8 border border-error/20">
              <p className="text-error font-medium text-sm mb-1 flex items-center gap-1.5">
                <AlertTriangle className="h-4 w-4" /> Model Stability Warning
              </p>
              <p className="text-xs text-text-tertiary mb-1.5">
                The following anomalies were detected. This does not affect the reported values —
                fair value and price targets are unchanged. Review input data quality before
                acting on this analysis.
              </p>
              <ul className="space-y-1">
                {calibration.stability_warning_reasons.map((r, i) => (
                  <li key={i} className="text-xs text-text-secondary leading-relaxed">
                    • {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 3-column comparison: FV | Consensus Target | Divergence */}
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center">
              <div className="text-xs text-text-tertiary mb-1">Intrinsic Fair Value</div>
              <div className="text-xl font-mono font-semibold text-text-primary">
                {fmt(calibration.internal_fair_value)}
              </div>
              <div className="text-xs text-text-tertiary mt-0.5">structural estimate</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-text-tertiary mb-1">Analyst Consensus Target</div>
              <div className="text-xl font-mono font-semibold text-text-secondary">
                {fmt(calibration.consensus_target)}
              </div>
              <div className="text-xs text-text-tertiary mt-0.5">
                {calibration.num_analysts != null
                  ? `${calibration.num_analysts} analyst${calibration.num_analysts !== 1 ? 's' : ''}`
                  : 'forward expectation'}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs text-text-tertiary mb-1">Divergence</div>
              <div className="text-xl font-mono font-semibold">
                <DivergenceBadge pct={calibration.divergence_pct} />
              </div>
              <div className="text-xs text-text-tertiary mt-0.5">
                {calibration.divergence_ratio != null
                  ? `ratio ${fmtRatio(calibration.divergence_ratio)}`
                  : 'FV vs consensus'}
              </div>
            </div>
          </div>

          {/* Metadata strip */}
          <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-text-tertiary">
            <span>
              <span className="text-text-secondary font-medium">Regime:</span>{' '}
              {calibration.regime} (rev growth {fmtPct(calibration.regime_rev_growth_pct, true)})
            </span>
            {calibration.internal_method_dispersion_pct != null && (
              <span>
                <span className="text-text-secondary font-medium">Internal dispersion:</span>{' '}
                {calibration.internal_method_dispersion_pct.toFixed(1)}% across P/E · EV/EBITDA · DCF
              </span>
            )}
          </div>

          {/* Regime explanation */}
          {divergence_state === 'Model-Conservative Regime' && !model_stability_warning && (
            <div className="rounded-md p-3.5 text-sm bg-yellow-500/8 border border-yellow-500/20">
              <p className="text-yellow-300 font-medium mb-1">Model-Conservative Regime</p>
              <p className="text-text-secondary leading-relaxed text-xs">
                Intrinsic fair value ({fmt(calibration.internal_fair_value)}) is{' '}
                {fmtPct(Math.abs(calibration.divergence_pct ?? 0))} below the analyst consensus
                target ({fmt(calibration.consensus_target)}). The model assigns lower economic
                worth than market participants expect. This is structurally valid — growth
                premiums and execution optionality are not captured in fundamental multiples.
                Divergence is informational only. Fair value and price targets are unchanged.
              </p>
            </div>
          )}

          {divergence_state === 'Model-Driven Upside Scenario' && !model_stability_warning && (
            <div className="rounded-md p-3.5 text-sm bg-cyan-500/8 border border-cyan-500/20">
              <p className="text-cyan-300 font-medium mb-1">Model-Driven Upside Scenario</p>
              <p className="text-text-secondary leading-relaxed text-xs">
                Intrinsic fair value ({fmt(calibration.internal_fair_value)}) is{' '}
                {fmtPct(calibration.divergence_pct ?? 0, true)} above the analyst consensus
                target ({fmt(calibration.consensus_target)}). The model identifies more
                fundamental value than the sell-side consensus. Verify assumptions; if supported
                by earnings quality and balance sheet, this is a contrarian setup worth examining.
              </p>
            </div>
          )}

          {divergence_state === 'Consensus Validated ✓' && (
            <div className="rounded-md p-3.5 text-sm bg-success/8 border border-success/20">
              <p className="text-success font-medium mb-1">Consensus Validated ✓</p>
              <p className="text-text-secondary text-xs">
                Intrinsic fair value ({fmt(calibration.internal_fair_value)}) and analyst
                consensus target ({fmt(calibration.consensus_target)}) are within the aligned
                threshold. Structural and market-implied estimates are in agreement.
              </p>
            </div>
          )}

          {divergence_state === 'No Consensus Data' && (
            <p className="text-xs text-text-tertiary italic">
              No analyst price target data available for divergence analysis.
              Regime classification and stability checks are still active.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
