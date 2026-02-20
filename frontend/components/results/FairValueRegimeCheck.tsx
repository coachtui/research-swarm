'use client'

import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, Scale, AlertTriangle, TrendingUp } from 'lucide-react'
import type { FairValueCalibration } from '@/types/api'

const STORAGE_KEY = 'dvrg_fv_regime_check_expanded'

interface FairValueRegimeCheckProps {
  calibration: FairValueCalibration
  currentPrice?: number
  financialHealthScore?: number
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

/**
 * Structural Premium Regime: stock is a high-quality growth business trading
 * at a significant premium to intrinsic value — not a valuation problem,
 * but a framing context that changes how numbers should be interpreted.
 */
function detectStructuralPremium(
  calibration: FairValueCalibration,
  currentPrice?: number,
  financialHealthScore?: number
): boolean {
  if (!currentPrice || financialHealthScore == null) return false
  const fv = calibration.internal_fair_value
  if (!fv || fv <= 0) return false
  const premiumRatio = (currentPrice - fv) / fv
  return premiumRatio > 0.5 && calibration.regime === 'Growth' && financialHealthScore > 7.0
}

/**
 * Market-implied band: where institutional pricing clusters between
 * current price and analyst consensus (45–65% of the gap).
 * Falls back to ±10% band if no consensus target.
 */
function getMarketImpliedBand(
  currentPrice: number,
  consensusTarget: number | null
): { low: number; high: number } | null {
  if (!currentPrice || currentPrice <= 0) return null
  if (consensusTarget && consensusTarget > currentPrice) {
    const gap = consensusTarget - currentPrice
    return {
      low: Math.round((currentPrice + gap * 0.45) / 5) * 5,
      high: Math.round((currentPrice + gap * 0.65) / 5) * 5,
    }
  }
  return {
    low: Math.round(currentPrice * 0.90),
    high: Math.round(currentPrice * 1.10),
  }
}

function StructuralPremiumChip() {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary border border-primary/20">
      <TrendingUp className="h-3 w-3" /> Structural Premium — Growth Equity
    </span>
  )
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

export function FairValueRegimeCheck({ calibration, currentPrice, financialHealthScore }: FairValueRegimeCheckProps) {
  const [expanded, setExpanded] = useState(false)

  const isStructuralPremium = detectStructuralPremium(calibration, currentPrice, financialHealthScore)

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'true') {
      setExpanded(true)
    } else if (
      isStructuralPremium ||
      calibration.model_stability_warning ||
      Math.abs(calibration.divergence_pct ?? 0) > 30
    ) {
      setExpanded(true)
    }
  }, [calibration.divergence_pct, calibration.model_stability_warning, isStructuralPremium])

  const toggle = () => {
    const next = !expanded
    setExpanded(next)
    localStorage.setItem(STORAGE_KEY, String(next))
  }

  const { divergence_state, model_stability_warning } = calibration

  const marketImpliedBand =
    isStructuralPremium && currentPrice
      ? getMarketImpliedBand(currentPrice, calibration.consensus_target)
      : null

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between px-5 py-4 bg-surface hover:bg-surface-elevated transition-colors text-left"
      >
        <div className="flex items-center gap-2.5">
          <Scale className="h-4 w-4 text-text-tertiary" />
          <span className="text-sm font-medium text-text-primary">
            {isStructuralPremium ? 'Valuation Regime' : 'Fair Value Regime'}
          </span>
          {isStructuralPremium
            ? <StructuralPremiumChip />
            : <StateChip state={divergence_state} warning={model_stability_warning} />
          }
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

          {/* 3-column comparison: Structural Anchor | Analyst Consensus | Divergence */}
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center">
              <div className="text-xs text-text-tertiary mb-1">
                {isStructuralPremium ? 'Structural Value Anchor' : 'Intrinsic Fair Value'}
              </div>
              <div className="text-xl font-mono font-semibold text-text-primary">
                {fmt(calibration.internal_fair_value)}
              </div>
              <div className="text-xs text-text-tertiary mt-0.5">
                {isStructuralPremium
                  ? 'Long-term intrinsic basis — not a near-term price target'
                  : 'structural estimate'
                }
              </div>
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

          {/* Market-Implied Band — Structural Premium only (Fix 3) */}
          {isStructuralPremium && marketImpliedBand && (
            <div className="rounded-md p-3 bg-primary/5 border border-primary/20">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-xs font-medium text-text-secondary">Market-Implied Value</div>
                  <div className="text-xs text-text-tertiary mt-0.5">
                    Current growth premium embedded in price
                  </div>
                </div>
                <div className="text-sm font-mono font-semibold text-primary shrink-0">
                  ${marketImpliedBand.low.toLocaleString()} – ${marketImpliedBand.high.toLocaleString()}
                </div>
              </div>
              <div className="mt-2 pt-2 border-t border-primary/15 grid grid-cols-3 gap-2 text-[10px] text-text-tertiary text-center">
                <div>
                  <span className="font-medium text-text-secondary block">Structural Anchor</span>
                  <span className="font-mono">{fmt(calibration.internal_fair_value)}</span>
                  <span className="block italic mt-0.5">intrinsic basis, 12–24 mo mean reversion</span>
                </div>
                <div>
                  <span className="font-medium text-text-secondary block">Market-Implied</span>
                  <span className="font-mono">${marketImpliedBand.low.toLocaleString()} – ${marketImpliedBand.high.toLocaleString()}</span>
                  <span className="block italic mt-0.5">current growth premium embedded in price</span>
                </div>
                <div>
                  <span className="font-medium text-text-secondary block">Analyst Consensus</span>
                  <span className="font-mono">{fmt(calibration.consensus_target)}</span>
                  <span className="block italic mt-0.5">sell-side forward target</span>
                </div>
              </div>
            </div>
          )}

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

          {/* Structural Premium explanation block (Fix 1) */}
          {isStructuralPremium && !model_stability_warning && (
            <div className="rounded-md p-3.5 text-sm bg-primary/8 border border-primary/20">
              <p className="text-primary font-medium mb-1">Structural Premium — Growth Equity</p>
              <p className="text-text-secondary leading-relaxed text-xs">
                Current price ({fmt(currentPrice)}) trades at a significant premium to the structural
                value anchor ({fmt(calibration.internal_fair_value)}). This is structurally expected for
                high-quality growth businesses — the market prices in future execution optionality that
                fundamental multiples do not capture. The structural anchor is a long-term mean-reversion
                reference, not a near-term price target. Tactical targets and analyst consensus operate
                within the current market pricing regime, not the structural zone.
              </p>
            </div>
          )}

          {/* Regime explanations — only for non-premium stocks */}
          {!isStructuralPremium && divergence_state === 'Model-Conservative Regime' && !model_stability_warning && (
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

          {!isStructuralPremium && divergence_state === 'Model-Driven Upside Scenario' && !model_stability_warning && (
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

          {!isStructuralPremium && divergence_state === 'Consensus Validated ✓' && (
            <div className="rounded-md p-3.5 text-sm bg-success/8 border border-success/20">
              <p className="text-success font-medium mb-1">Consensus Validated ✓</p>
              <p className="text-text-secondary text-xs">
                Intrinsic fair value ({fmt(calibration.internal_fair_value)}) and analyst
                consensus target ({fmt(calibration.consensus_target)}) are within the aligned
                threshold. Structural and market-implied estimates are in agreement.
              </p>
            </div>
          )}

          {!isStructuralPremium && divergence_state === 'No Consensus Data' && (
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
