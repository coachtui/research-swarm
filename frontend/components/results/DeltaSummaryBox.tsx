'use client'

import type { PreviousAnalysisDelta } from '@/types/api'

interface DeltaSummaryBoxProps {
  delta: PreviousAnalysisDelta
  ticker: string
}

function ratingColor(rating: string): string {
  if (rating.includes('BUY')) return 'text-success'
  if (rating === 'HOLD') return 'text-warning'
  return 'text-error'
}

function thesisDirectionStyle(direction: string): { label: string; color: string; icon: string } {
  switch (direction) {
    case 'strengthened': return { label: 'Strengthened', color: 'text-success', icon: '↑' }
    case 'weakened':     return { label: 'Weakened',     color: 'text-warning', icon: '↓' }
    case 'reversed':     return { label: 'Reversed',     color: 'text-error',   icon: '⟳' }
    default:             return { label: 'Held',         color: 'text-text-secondary', icon: '→' }
  }
}

function priceDeltaColor(pct: number | null): string {
  if (pct === null) return 'text-text-secondary'
  if (pct > 3) return 'text-success'
  if (pct < -3) return 'text-error'
  return 'text-text-secondary'
}

function scoreDeltaColor(delta: number | null): string {
  if (delta === null) return 'text-text-secondary'
  if (delta > 0.3) return 'text-success'
  if (delta < -0.3) return 'text-error'
  return 'text-text-secondary'
}

/**
 * DeltaSummaryBox — opens the report with a "Since Last Analysis" summary
 * when the same user has a prior analysis for the same ticker.
 *
 * This is DVRG's longitudinal thesis tracker — transforms point-in-time snapshots
 * into a living thesis timeline for Trader-tier subscribers.
 */
export function DeltaSummaryBox({ delta, ticker }: DeltaSummaryBoxProps) {
  const {
    prior_recommendation,
    current_recommendation,
    prior_price,
    current_price,
    price_change_pct,
    prior_smart_money_score,
    current_smart_money_score,
    prior_moat_score,
    current_moat_score,
    thesis_direction,
    days_since_last,
    prior_analysis_date,
  } = delta

  const direction = thesisDirectionStyle(thesis_direction)
  const ratingChanged = prior_recommendation !== current_recommendation
  const smDelta = (current_smart_money_score != null && prior_smart_money_score != null)
    ? current_smart_money_score - prior_smart_money_score : null
  const moatDelta = (current_moat_score != null && prior_moat_score != null)
    ? current_moat_score - prior_moat_score : null

  const priorDateFormatted = prior_analysis_date
    ? new Date(prior_analysis_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : null

  return (
    <div className="rounded-lg border border-primary/25 bg-primary/5 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-primary uppercase tracking-wide">
            Since Last Analysis
          </span>
          {priorDateFormatted && (
            <span className="text-[10px] text-text-tertiary">
              {days_since_last}d ago · {priorDateFormatted}
            </span>
          )}
        </div>
        <div className={`text-xs font-bold ${direction.color}`}>
          {direction.icon} Thesis {direction.label}
        </div>
      </div>

      {/* Delta grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">

        {/* Recommendation */}
        <div className="rounded-md bg-surface/60 border border-border p-2.5">
          <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-1">Recommendation</p>
          <div className="flex items-center gap-1">
            <span className={`text-sm font-bold ${ratingColor(prior_recommendation)}`}>
              {prior_recommendation}
            </span>
            {ratingChanged && (
              <>
                <span className="text-text-tertiary text-xs">→</span>
                <span className={`text-sm font-bold ${ratingColor(current_recommendation)}`}>
                  {current_recommendation}
                </span>
              </>
            )}
            {!ratingChanged && (
              <span className="text-[10px] text-text-tertiary ml-1">(unchanged)</span>
            )}
          </div>
        </div>

        {/* Price */}
        <div className="rounded-md bg-surface/60 border border-border p-2.5">
          <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-1">Price Change</p>
          {prior_price != null && current_price != null ? (
            <div>
              <p className="text-sm font-bold text-text-primary">
                ${prior_price.toFixed(2)} → ${current_price.toFixed(2)}
              </p>
              {price_change_pct != null && (
                <p className={`text-[10px] font-medium ${priceDeltaColor(price_change_pct)}`}>
                  {price_change_pct > 0 ? '+' : ''}{price_change_pct.toFixed(1)}%
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-text-tertiary">N/A</p>
          )}
        </div>

        {/* Smart Money Score */}
        <div className="rounded-md bg-surface/60 border border-border p-2.5">
          <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-1">Smart Money</p>
          {prior_smart_money_score != null && current_smart_money_score != null ? (
            <div>
              <p className="text-sm font-bold text-text-primary">
                {prior_smart_money_score} → {current_smart_money_score}
              </p>
              {smDelta != null && (
                <p className={`text-[10px] font-medium ${scoreDeltaColor(smDelta)}`}>
                  {smDelta > 0 ? '+' : ''}{smDelta.toFixed(1)} pts
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-text-tertiary">N/A</p>
          )}
        </div>

        {/* Overall Score */}
        <div className="rounded-md bg-surface/60 border border-border p-2.5">
          <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-1">Overall Score</p>
          {prior_moat_score != null && current_moat_score != null ? (
            <div>
              <p className="text-sm font-bold text-text-primary">
                {prior_moat_score.toFixed(1)} → {current_moat_score.toFixed(1)}
              </p>
              {moatDelta != null && (
                <p className={`text-[10px] font-medium ${scoreDeltaColor(moatDelta)}`}>
                  {moatDelta > 0 ? '+' : ''}{moatDelta.toFixed(1)} pts
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-text-tertiary">N/A</p>
          )}
        </div>
      </div>

      {/* Thesis direction note */}
      <p className="text-[10px] text-text-tertiary leading-relaxed">
        {thesis_direction === 'reversed' && (
          `The rating has reversed since your last ${ticker} analysis ${days_since_last} days ago — review Key Takeaways and upgrade/downgrade triggers for what changed.`
        )}
        {thesis_direction === 'weakened' && (
          `The thesis has weakened since your last ${ticker} analysis. Check Key Risks and downgrade triggers below for evolving concerns.`
        )}
        {thesis_direction === 'strengthened' && (
          `The thesis has strengthened since your last ${ticker} analysis. Review Investment Highlights for updated supporting evidence.`
        )}
        {thesis_direction === 'held' && (
          `The thesis is holding at the same rating since your last ${ticker} analysis ${days_since_last} days ago. Check for changes in signal composition or price target movement.`
        )}
      </p>
    </div>
  )
}
