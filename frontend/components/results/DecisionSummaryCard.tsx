'use client'

import type { InvestmentThesisStructured, TriggerItem } from '@/types/api'

interface DecisionSummaryCardProps {
  rating: string | null
  riskLevel: string | null
  convictionLevel: string | null
  thesis: InvestmentThesisStructured | string | null
  upgradeTriggers?: TriggerItem[] | null
  downgradeTriggers?: TriggerItem[] | null
}

function ratingColors(rating: string | null): { bg: string; border: string; text: string; ratingBg: string } {
  if (!rating) return { bg: 'bg-surface', border: 'border-border', text: 'text-text-primary', ratingBg: 'bg-surface-elevated' }
  if (rating.includes('BUY')) return { bg: 'bg-success/5', border: 'border-success/35', text: 'text-success', ratingBg: 'bg-success/12' }
  if (rating === 'HOLD') return { bg: 'bg-warning/5', border: 'border-warning/35', text: 'text-warning', ratingBg: 'bg-warning/12' }
  return { bg: 'bg-error/5', border: 'border-error/35', text: 'text-error', ratingBg: 'bg-error/12' }
}

/**
 * Above-the-fold Decision Summary Card.
 *
 * Designed for PM consumption in <5 seconds. Contains ONLY:
 * – Rating (large, prominent)
 * – 1-sentence thesis
 * – Primary catalyst (top upgrade trigger)
 * – Primary risk (top downgrade trigger)
 * – Risk level + Conviction chips
 *
 * No valuation anchors, structural bands, or asymmetry math.
 */
export function DecisionSummaryCard({
  rating,
  riskLevel,
  convictionLevel,
  thesis,
  upgradeTriggers,
  downgradeTriggers,
}: DecisionSummaryCardProps) {
  const colors = ratingColors(rating)

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
    <div className={`rounded-xl border-2 ${colors.border} ${colors.bg} p-5 space-y-4`}>

      {/* Row 1: Rating + meta chips */}
      <div className="flex flex-wrap items-center gap-2.5">
        <span
          className={`inline-flex items-center px-4 py-1.5 rounded-lg font-bold tracking-widest text-lg ${colors.ratingBg} ${colors.text} border ${colors.border}`}
          style={{ letterSpacing: '0.12em' }}
        >
          {rating ?? '—'}
        </span>
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

      {/* Row 2: 1-sentence thesis */}
      {thesisLine && (
        <p className="text-[15px] font-semibold text-text-primary leading-snug">
          {thesisLine}
        </p>
      )}

      {/* Row 3: Primary Catalyst + Primary Risk */}
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
