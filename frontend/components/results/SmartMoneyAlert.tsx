'use client'

import type { SignalBreakdown } from '@/types/api'

const MIN_GAP_TO_SHOW = 3.0

interface SmartMoneyAlertProps {
  signalBreakdown: SignalBreakdown
}

/**
 * Prominent callout displayed when the gap between Smart Money signals and
 * Public Sentiment signals exceeds MIN_GAP_TO_SHOW (3.0 points on a 0–10 scale).
 *
 * Smart Money = avg(institutional + insider + dark_pool)
 * Public Sentiment = avg(news + analyst + earnings)
 *
 * This divergence is DVRG's core differentiator — it surfaces what informed,
 * capital-committed actors are doing vs. what public opinion reflects.
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

  // Direction string
  const smartMoneyLabel = smartMoney >= 6 ? 'bullish' : smartMoney >= 4 ? 'neutral' : 'bearish'
  const publicLabel = public_ >= 6 ? 'bullish' : public_ >= 4 ? 'neutral' : 'bearish'

  // Visual treatment: amber when smart money is bearish (warning), blue/teal when bullish (info)
  const isWarning = smartMoneyBearish
  const borderColor = isWarning ? 'border-warning/50' : 'border-primary/40'
  const bgColor = isWarning ? 'bg-warning/5' : 'bg-primary/5'
  const accentColor = isWarning ? 'text-warning' : 'text-primary'
  const badgeBg = isWarning ? 'bg-warning/10 text-warning border-warning/20' : 'bg-primary/10 text-primary border-primary/20'

  return (
    <div className={`rounded-lg border-2 ${borderColor} ${bgColor} p-4`}>
      <div className="flex items-start gap-3">
        {/* Icon / accent mark */}
        <div className={`mt-0.5 w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${badgeBg} border`}>
          <span className="text-sm font-bold">{isWarning ? '⚡' : '📡'}</span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className={`text-sm font-bold ${accentColor}`}>
              Smart Money Divergence Alert
            </span>
            <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium uppercase tracking-wide ${badgeBg}`}>
              {gapDisplay.toFixed(1)}-pt gap
            </span>
          </div>

          <p className="text-xs text-text-secondary leading-relaxed mb-2">
            Informed capital (institutional flows, insider transactions, dark pool activity) is{' '}
            <span className={`font-semibold ${accentColor}`}>{smartMoneyLabel}</span>{' '}
            at <strong>{smartMoneyScore}/10</strong>, while public signals (news, analyst ratings, earnings revisions)
            are <span className="font-semibold">{publicLabel}</span> at <strong>{publicScore}/10</strong>.
            A {gapDisplay.toFixed(1)}-point divergence is significant — capital-committed actors and public
            narrative are telling different stories.
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

          <p className="text-[10px] text-text-tertiary mt-2 italic">
            {isWarning
              ? 'Smart money distribution signals active — proceed with caution. Informed actors may be reducing exposure ahead of public awareness.'
              : 'Smart money accumulation signals active despite muted public sentiment — a potential contrarian setup. Fundamentals and flow alignment are key to conviction.'}
          </p>
        </div>
      </div>
    </div>
  )
}
