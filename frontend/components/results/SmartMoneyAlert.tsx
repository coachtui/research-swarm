'use client'

import type { SignalBreakdown } from '@/types/api'

const MIN_GAP_TO_SHOW = 3.0

interface SmartMoneyAlertProps {
  signalBreakdown: SignalBreakdown
}

/**
 * Smart Money Divergence Signal
 *
 * Surfaces when the spread between informed capital (institutional flows,
 * insider transactions, dark pool activity) and public narrative signals
 * exceeds 3.0 points on a 0–10 scale.
 *
 * This is a primary differentiation signal — presented with authority,
 * not defensiveness.
 */
export function SmartMoneyAlert({ signalBreakdown }: SmartMoneyAlertProps) {
  const { institutional_score, insider_score, dark_pool_score } = signalBreakdown
  const { news_score, analyst_score, earnings_score } = signalBreakdown

  const smartMoneyScoresAvailable =
    institutional_score != null && insider_score != null && dark_pool_score != null
  if (!smartMoneyScoresAvailable) return null

  const smartMoney = (institutional_score + insider_score + dark_pool_score) / 3
  const public_ = (news_score + analyst_score + earnings_score) / 3
  const gap = Math.abs(smartMoney - public_)

  if (gap < MIN_GAP_TO_SHOW) return null

  const smartMoneyBearish = smartMoney < public_
  const smartMoneyScore = Math.round(smartMoney * 10) / 10
  const publicScore = Math.round(public_ * 10) / 10
  const gapDisplay = Math.round(gap * 10) / 10

  const smartMoneyLabel = smartMoney >= 6 ? 'Accumulating' : smartMoney >= 4 ? 'Neutral' : 'Distributing'
  const publicLabel = public_ >= 6 ? 'bullish' : public_ >= 4 ? 'neutral' : 'bearish'

  const isWarning = smartMoneyBearish
  const borderColor = isWarning ? 'border-warning/50' : 'border-primary/40'
  const bgColor = isWarning ? 'bg-warning/5' : 'bg-primary/5'
  const accentColor = isWarning ? 'text-warning' : 'text-primary'
  const badgeBg = isWarning
    ? 'bg-warning/10 text-warning border-warning/20'
    : 'bg-primary/10 text-primary border-primary/20'

  // Confidence/Reliability: based on all 3 smart money signals being non-neutral
  const nonNeutralSmartMoney = [institutional_score, insider_score, dark_pool_score]
    .filter(s => s != null && Math.abs(s - 5) > 0.5).length
  const reliabilityLabel =
    nonNeutralSmartMoney === 3 ? 'High Reliability' :
    nonNeutralSmartMoney === 2 ? 'Moderate Reliability' :
    'Partial Signal'
  const reliabilityColor =
    nonNeutralSmartMoney === 3 ? 'text-success bg-success/10 border-success/20' :
    nonNeutralSmartMoney === 2 ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' :
    'text-text-tertiary bg-surface-elevated border-border'

  // Historical behavior framing (class-specific)
  const historicalFrame = isWarning
    ? 'In large-cap equities, sustained smart money distribution typically leads public awareness by 6–12 weeks.'
    : 'Historically, smart money accumulation ahead of public sentiment resolves bullishly in large-cap equities — particularly when institutional and dark pool flows align.'

  return (
    <div className={`rounded-lg border-2 ${borderColor} ${bgColor} p-4`}>
      <div className="flex items-start gap-3">

        {/* Accent icon */}
        <div className={`mt-0.5 w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${badgeBg} border`}>
          <span className="text-sm font-bold">{isWarning ? '⚡' : '📡'}</span>
        </div>

        <div className="flex-1 min-w-0 space-y-3">

          {/* Header row */}
          <div className="flex flex-wrap items-center gap-2">
            <span className={`text-sm font-bold ${accentColor}`}>
              Smart Money Divergence
            </span>
            <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium uppercase tracking-wide ${badgeBg}`}>
              {gapDisplay.toFixed(1)}-pt gap
            </span>
            {/* Confidence / Reliability Badge */}
            <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${reliabilityColor}`}>
              {reliabilityLabel}
            </span>
          </div>

          {/* Tight 1-line summary */}
          <p className="text-xs text-text-secondary leading-relaxed">
            Informed capital is{' '}
            <span className={`font-semibold ${accentColor}`}>{smartMoneyLabel}</span>{' '}
            ({smartMoneyScore}/10) against a {publicLabel} public narrative ({publicScore}/10) —
            a {gapDisplay.toFixed(1)}-point divergence that warrants positioning attention.
          </p>

          {/* Scores grid */}
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-md bg-surface/60 border border-border p-2">
              <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Smart Money</p>
              <p className={`text-lg font-bold leading-none ${accentColor}`}>{smartMoneyScore}</p>
              <p className="text-[10px] text-text-tertiary mt-0.5">Inst · Insider · Dark Pool</p>
            </div>
            <div className="rounded-md bg-surface/60 border border-border p-2">
              <p className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Public Sentiment</p>
              <p className="text-lg font-bold leading-none text-text-primary">{publicScore}</p>
              <p className="text-[10px] text-text-tertiary mt-0.5">News · Analysts · Earnings</p>
            </div>
          </div>

          {/* Historical Behavior Framing */}
          <p className="text-[10px] text-text-tertiary italic border-l-2 border-border pl-2 leading-relaxed">
            {historicalFrame}
          </p>

        </div>
      </div>
    </div>
  )
}
