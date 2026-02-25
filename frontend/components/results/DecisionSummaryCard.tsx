'use client'

import type { InvestmentThesisStructured, TriggerItem } from '@/types/api'
import {
  deriveStructuralBias,
  deriveTacticalStance,
  derivePortfolioBias,
  deploymentGateCopy,
  isDeploymentGated,
  structuralBiasColor,
  tacticalStanceColor,
} from '@/lib/utils/decisionDimensions'

interface DecisionSummaryCardProps {
  rating: string | null
  riskLevel: string | null
  convictionLevel: string | null
  thesis: InvestmentThesisStructured | string | null
  upgradeTriggers?: TriggerItem[] | null
  downgradeTriggers?: TriggerItem[] | null
  /** New-buyers action from the decision framework (for Tactical Stance derivation) */
  newBuyersAction?: string | null
  hasDivergence?: boolean
  divergenceSeverity?: 'HIGH' | 'MODERATE' | null
}

/**
 * Above-the-fold Decision Summary Card — dual-dimension decision framing.
 *
 * Primary anchor : Structural Bias  — "Should this asset exist in my portfolio?"
 * Secondary layer: Tactical Stance  — "Should I deploy capital now?"
 * Deployment Gate: explicit capital-deployment authorization/deferral signal
 *
 * Designed for PM consumption in <5 seconds. Eliminates BUY/HOLD/SELL retail semantics.
 */
export function DecisionSummaryCard({
  rating,
  riskLevel,
  convictionLevel,
  thesis,
  upgradeTriggers,
  downgradeTriggers,
  newBuyersAction,
  hasDivergence = false,
  divergenceSeverity,
}: DecisionSummaryCardProps) {
  const bias = deriveStructuralBias(rating)
  const stance = deriveTacticalStance(
    newBuyersAction ?? null,
    rating,
    hasDivergence,
    divergenceSeverity,
    false, // dislocation context not available at this level; full derivation in DecisionAction
  )
  const portfolioBias = derivePortfolioBias(rating)
  const gateCopy = deploymentGateCopy(stance)
  const gated = isDeploymentGated(stance)

  const biasColors = structuralBiasColor(bias)
  const stanceColors = tacticalStanceColor(stance)

  // Gate banner color — green for active, amber for deferred/constrained, red for defensive
  const gateBannerColor = (() => {
    if (!gated) return 'bg-success/8 border-success/25 text-success'
    if (stance === 'Defensive') return 'bg-error/8 border-error/25 text-error'
    return 'bg-warning/8 border-warning/25 text-warning'
  })()

  const thesisLine = (() => {
    if (!thesis) return null
    if (typeof thesis === 'string') {
      const s = thesis.split(/\.\s+/)
      return s[0] + (s[0].endsWith('.') ? '' : '.')
    }
    const full = (thesis as InvestmentThesisStructured).recommendation_summary ?? ''
    const sentences = full.split(/\.\s+/)
    return sentences[0] + (sentences[0].endsWith('.') ? '' : '.')
  })()

  const primaryCatalyst = (upgradeTriggers ?? []).find(t => t.metric && t.threshold) ?? null
  const primaryRisk = (downgradeTriggers ?? []).find(t => t.metric && t.threshold) ?? null

  return (
    <div className={`rounded-xl border-2 ${biasColors.border} ${biasColors.bg} p-5 space-y-4`}>

      {/* Row 1: Dual-Dimension Decision Display */}
      <div className="grid grid-cols-2 gap-3">

        {/* Structural Bias — Primary Decision Anchor (dominant visual weight) */}
        <div className={`rounded-lg border-2 ${biasColors.border} ${biasColors.bg} px-4 py-3`}>
          <p className="text-[10px] uppercase tracking-[0.16em] text-text-tertiary font-bold mb-1">
            Structural Bias
          </p>
          <p className={`text-2xl font-bold tracking-wide ${biasColors.text}`}>
            {bias}
          </p>
          <p className="text-[10px] text-text-tertiary mt-1 leading-tight">
            Business quality · Long-term EV direction
          </p>
        </div>

        {/* Tactical Stance — Execution Context (secondary weight) */}
        <div className={`rounded-lg border ${stanceColors.border} bg-surface-elevated px-4 py-3`}>
          <p className="text-[10px] uppercase tracking-[0.16em] text-text-tertiary font-bold mb-1">
            Tactical Stance
          </p>
          <p className={`text-2xl font-bold tracking-wide ${stanceColors.text}`}>
            {stance}
          </p>
          <p className="text-[10px] text-text-tertiary mt-1 leading-tight">
            Entry conditions · Capital deployment
          </p>
        </div>
      </div>

      {/* Row 2: Deployment Gate Banner — most salient line after the dual-dimension block */}
      <div className={`flex items-center justify-between rounded-lg border px-4 py-2.5 ${gateBannerColor}`}>
        <div>
          <p className="text-sm font-bold tracking-wide">{gateCopy.title}</p>
          <p className="text-[11px] opacity-80 leading-snug mt-0.5">{gateCopy.subtitle}</p>
        </div>
        {/* Portfolio Bias — institutional label replacing retail BUY/HOLD/SELL */}
        <div className="text-right shrink-0 pl-4">
          <p className="text-[10px] uppercase tracking-wider opacity-60 font-semibold mb-0.5">
            Portfolio Bias
          </p>
          <p className="text-base font-bold">{portfolioBias}</p>
          {rating && (
            <p className="text-[9px] opacity-50 mt-0.5">Legacy: {rating}</p>
          )}
        </div>
      </div>

      {/* Row 3: Meta chips */}
      {(riskLevel || convictionLevel) && (
        <div className="flex flex-wrap items-center gap-2">
          {riskLevel && (
            <span className="text-xs font-medium px-2.5 py-1 rounded border border-border text-text-secondary bg-surface-elevated">
              {riskLevel} Risk
            </span>
          )}
          {convictionLevel && (
            <span className="text-xs font-medium px-2.5 py-1 rounded border border-border text-text-secondary bg-surface-elevated">
              Conviction: {convictionLevel}
            </span>
          )}
        </div>
      )}

      {/* Row 4: 1-sentence thesis */}
      {thesisLine && (
        <p className="text-[15px] font-semibold text-text-primary leading-snug">
          {thesisLine}
        </p>
      )}

      {/* Row 5: Primary Catalyst + Primary Risk */}
      {(primaryCatalyst || primaryRisk) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3 border-t border-border/60">
          {primaryCatalyst && (
            <div className="flex items-start gap-2">
              <span className="text-success font-bold mt-0.5 shrink-0 text-sm leading-none">↑</span>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-text-tertiary font-semibold mb-0.5">
                  Primary Catalyst
                </p>
                <p className="text-xs text-text-secondary leading-relaxed">
                  <span className="font-medium text-text-primary">{primaryCatalyst.metric}:</span>{' '}
                  {primaryCatalyst.threshold}
                </p>
              </div>
            </div>
          )}
          {primaryRisk && (
            <div className="flex items-start gap-2">
              <span className="text-error font-bold mt-0.5 shrink-0 text-sm leading-none">↓</span>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-text-tertiary font-semibold mb-0.5">
                  Primary Risk
                </p>
                <p className="text-xs text-text-secondary leading-relaxed">
                  <span className="font-medium text-text-primary">{primaryRisk.metric}:</span>{' '}
                  {primaryRisk.threshold}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
