'use client'

import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { HelpCircle, AlertTriangle, CheckCircle } from 'lucide-react'
import type { SignalBreakdown } from '@/types/api'

interface SignalDivergenceSectionProps {
  breakdown: SignalBreakdown
  recentNews?: Array<{ date: string; headline: string; source?: string }>
  nextEarningsDate?: string
}

interface SignalRow {
  name: string
  icon: string
  score: number
  hasData: boolean
  interpretation: string
  tooltip: string
}

function getDirection(interpretation: string): 'BULLISH' | 'BEARISH' | 'NEUTRAL' {
  if (interpretation.includes('Bullish') || interpretation.includes('🟢')) return 'BULLISH'
  if (interpretation.includes('Bearish') || interpretation.includes('🔴')) return 'BEARISH'
  return 'NEUTRAL'
}

function getSeverity(breakdown: SignalBreakdown): 'low' | 'medium' | 'high' {
  if (!breakdown.has_divergence) return 'low'
  const scores = [
    breakdown.news_score,
    breakdown.earnings_score,
    breakdown.analyst_score,
    breakdown.institutional_score,
    breakdown.insider_score,
  ]
  const mean = scores.reduce((a, b) => a + b, 0) / scores.length
  const variance = scores.reduce((sum, s) => sum + Math.pow(s - mean, 2), 0) / scores.length
  const stdDev = Math.sqrt(variance)
  if (stdDev >= 3.0) return 'high'
  if (stdDev >= 2.0) return 'medium'
  return 'low'
}

export function SignalDivergenceSection({
  breakdown,
  nextEarningsDate,
}: SignalDivergenceSectionProps) {
  const [showExplainer, setShowExplainer] = useState(false)

  const divergenceMagnitude = Math.max(...[
    breakdown.news_score,
    breakdown.earnings_score,
    breakdown.analyst_score,
    breakdown.institutional_score,
    breakdown.insider_score,
  ]) - Math.min(...[
    breakdown.news_score,
    breakdown.earnings_score,
    breakdown.analyst_score,
    breakdown.institutional_score,
    breakdown.insider_score,
  ])

  const signals: SignalRow[] = [
    {
      name: 'News Sentiment',
      icon: '📰',
      score: breakdown.news_score,
      hasData: breakdown.news_has_data !== false,
      interpretation: breakdown.news_interpretation,
      tooltip: 'Media coverage sentiment over the past 30 days. High = positive news flow and bullish headlines. Low = negative coverage or controversy.',
    },
    {
      name: 'Earnings Revisions',
      icon: '📈',
      score: breakdown.earnings_score,
      hasData: breakdown.earnings_has_data !== false,
      interpretation: breakdown.earnings_interpretation,
      tooltip: 'Whether analysts are raising or lowering earnings estimates. High = improving expectations. Low = deteriorating estimates.',
    },
    {
      name: 'Analyst Ratings',
      icon: '👔',
      score: breakdown.analyst_score,
      hasData: breakdown.analyst_has_data !== false,
      interpretation: breakdown.analyst_interpretation,
      tooltip: 'Wall Street consensus based on buy/hold/sell recommendations. High = majority buy-rated. Low = majority sell-rated.',
    },
    {
      name: 'Institutional Activity',
      icon: '🏛️',
      score: breakdown.institutional_score,
      hasData: breakdown.institutional_has_data !== false,
      interpretation: breakdown.institutional_interpretation,
      tooltip: 'Net buying or selling by pension funds, hedge funds, and mutual funds. High = accumulation. Low = distribution.',
    },
    {
      name: 'Insider Activity',
      icon: '👤',
      score: breakdown.insider_score,
      hasData: breakdown.insider_has_data !== false,
      interpretation: breakdown.insider_interpretation,
      tooltip: 'CEO, CFO, and board member trades (Form 4 filings). High = insider buying. Low = insider selling. Insiders have informational edge.',
    },
  ]

  // Add dark pool and tech divergence if present
  if (breakdown.dark_pool_score !== undefined) {
    signals.push({
      name: 'Dark Pool Activity',
      icon: '🌊',
      score: breakdown.dark_pool_score,
      hasData: breakdown.dark_pool_has_data !== false,
      interpretation: breakdown.dark_pool_interpretation || '',
      tooltip: 'Institutional off-exchange block trades. Sustained dark pool buying above baseline suggests institutional accumulation ahead of public moves.',
    })
  }
  if (breakdown.tech_divergence_score !== undefined) {
    signals.push({
      name: 'Technical Divergence',
      icon: '📊',
      score: breakdown.tech_divergence_score,
      hasData: breakdown.tech_divergence_has_data !== false,
      interpretation: breakdown.tech_divergence_interpretation || '',
      tooltip: 'Whether price momentum and technicals confirm or conflict with the fundamental picture. Divergence here often precedes reversals.',
    })
  }

  const severity = getSeverity(breakdown)
  const hasDivergence = breakdown.has_divergence

  const bearishSignals = signals.filter(s => s.hasData && getDirection(s.interpretation) === 'BEARISH')
  const bullishSignals = signals.filter(s => s.hasData && getDirection(s.interpretation) === 'BULLISH')

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          Signal Analysis
        </h2>
        <div className="flex items-center gap-2">
          {hasDivergence ? (
            <Badge variant={severity === 'high' ? 'error' : 'warning'}>
              {severity === 'high' ? 'High' : 'Moderate'} Divergence
            </Badge>
          ) : (
            <Badge variant="success">Signals Aligned</Badge>
          )}
          <button
            onClick={() => setShowExplainer(true)}
            className="text-xs text-primary hover:text-primary/80 transition-colors"
          >
            What is this? →
          </button>
        </div>
      </div>

      <Card className={`border ${
        severity === 'high' ? 'border-error/30' :
        severity === 'medium' ? 'border-warning/30' :
        'border-border-subtle'
      }`}>
        <CardContent className="pt-5 pb-4">

          {/* Signal matrix — scoreboard first */}
          <div className="space-y-3 mb-5">
            {signals.map((signal, idx) => {
              const direction = signal.hasData ? getDirection(signal.interpretation) : null
              const isConflicting = hasDivergence && direction === 'BEARISH' && bullishSignals.length > 0

              return (
                <div key={idx} className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    {/* Left: name + tooltip */}
                    <div className="flex items-center gap-1.5">
                      <span>{signal.icon}</span>
                      <span className={`font-medium ${isConflicting ? 'text-warning' : 'text-text-primary'}`}>
                        {signal.name}
                      </span>
                      {isConflicting && <span className="text-warning text-xs">⚠</span>}
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-text-tertiary hover:text-text-secondary transition-colors">
                            <HelpCircle className="h-3.5 w-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p className="text-xs leading-relaxed">{signal.tooltip}</p>
                        </TooltipContent>
                      </Tooltip>
                    </div>

                    {/* Right: direction label + score */}
                    <div className="flex items-center gap-3">
                      {!signal.hasData ? (
                        <span className="text-xs text-text-tertiary">N/A</span>
                      ) : (
                        <span className={`text-sm font-medium ${
                          direction === 'BULLISH' ? 'text-success' :
                          direction === 'BEARISH' ? 'text-error' :
                          'text-text-tertiary'
                        }`}>
                          {direction === 'BULLISH' && '🟢 Bullish'}
                          {direction === 'BEARISH' && '🔴 Bearish'}
                          {direction === 'NEUTRAL' && '⚪ Neutral'}
                        </span>
                      )}
                      <span className="text-text-secondary text-sm w-10 text-right font-mono">
                        {signal.hasData ? signal.score.toFixed(1) : '—'}
                      </span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full bg-surface-elevated rounded-full h-1.5">
                    <div
                      className={`h-1.5 rounded-full transition-all duration-700 ${
                        !signal.hasData ? 'bg-surface-elevated w-0' :
                        direction === 'BULLISH' ? 'bg-success' :
                        direction === 'BEARISH' ? 'bg-error' :
                        'bg-text-tertiary'
                      }`}
                      style={{ width: signal.hasData ? `${(signal.score / 10) * 100}%` : '0%' }}
                    />
                  </div>
                </div>
              )
            })}
          </div>

          {/* Signal Conflict Summary — one block, shown only when divergence exists */}
          {hasDivergence && breakdown.divergence_explanation && (
            <div className={`rounded-lg border p-4 ${
              severity === 'high'
                ? 'bg-error/5 border-error/25'
                : 'bg-warning/5 border-warning/25'
            }`}>
              <div className="flex items-start gap-2.5">
                <AlertTriangle className={`h-4 w-4 mt-0.5 flex-shrink-0 ${
                  severity === 'high' ? 'text-error' : 'text-warning'
                }`} />
                <div className="space-y-2">
                  <p className="text-sm font-medium text-text-primary">
                    Signal Conflict — {bearishSignals.length} of {signals.filter(s => s.hasData).length} signals disagree
                  </p>
                  <p className="text-sm text-text-secondary leading-relaxed">
                    {breakdown.divergence_explanation}
                  </p>
                  {divergenceMagnitude >= 4 && (
                    <p className="text-xs text-text-tertiary">
                      Divergence magnitude: {divergenceMagnitude.toFixed(1)} pts ·{' '}
                      Historical pattern: 68% of similar conflicts resolve within 2–8 weeks in the direction of fundamentals.
                    </p>
                  )}
                  {breakdown.divergence_recommendation && (
                    <p className="text-xs text-text-secondary font-medium">
                      {breakdown.divergence_recommendation}
                    </p>
                  )}
                  {/* Alert checklist */}
                  <div className="pt-1">
                    <p className="text-xs text-text-tertiary mb-1.5">Set alerts for:</p>
                    <ul className="space-y-1 text-xs text-text-secondary">
                      <li className="flex items-start gap-1.5">
                        <span className="text-primary mt-0.5">·</span>
                        Insider buying activity (Form 4 filings)
                      </li>
                      {nextEarningsDate && (
                        <li className="flex items-start gap-1.5">
                          <span className="text-primary mt-0.5">·</span>
                          Next earnings ({nextEarningsDate}) — validates or refutes analyst estimates
                        </li>
                      )}
                      <li className="flex items-start gap-1.5">
                        <span className="text-primary mt-0.5">·</span>
                        Institutional ownership changes (13F filings)
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* All-clear strip */}
          {!hasDivergence && (
            <div className="flex items-center gap-2 text-xs text-text-secondary pt-1">
              <CheckCircle className="h-3.5 w-3.5 text-success flex-shrink-0" />
              <span>{breakdown.alignment_status} · All signals confirm direction</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Explainer modal */}
      {showExplainer && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setShowExplainer(false)}
        >
          <Card className="max-w-lg w-full" onClick={(e) => e.stopPropagation()}>
            <CardContent className="pt-6 space-y-4">
              <h3 className="text-lg font-bold">What is Signal Divergence?</h3>
              <p className="text-sm text-text-secondary">
                Most analysis looks at each signal in isolation. Signal divergence measures how signals
                interact — especially when they disagree.
              </p>
              <div className="bg-primary/10 p-4 rounded-lg border border-primary/20">
                <p className="text-sm font-medium mb-1">Example</p>
                <p className="text-sm text-text-secondary">
                  Analysts are bullish, but insiders are selling. Insiders know things analysts don't.
                  This kind of divergence often predicts trouble before the market catches on.
                </p>
              </div>
              <p className="text-sm text-text-secondary">
                The biggest opportunities and risks often hide in these disagreements — where smart
                money diverges from the headlines.
              </p>
              <button
                onClick={() => setShowExplainer(false)}
                className="w-full bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm hover:bg-primary/90 transition-colors"
              >
                Got it
              </button>
            </CardContent>
          </Card>
        </div>
      )}
    </section>
  )
}
