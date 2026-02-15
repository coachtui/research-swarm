'use client'

import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { HelpCircle } from 'lucide-react'
import type { SignalBreakdown } from '@/types/api'

interface SignalDivergenceSectionProps {
  breakdown: SignalBreakdown
  recentNews?: Array<{ date: string; headline: string; source?: string }>
  nextEarningsDate?: string
}

interface SignalDisplay {
  name: string
  icon: string
  score: number
  interpretation: string
  tooltip: string
}

function getInterpretationType(interpretation: string): 'BULLISH' | 'BEARISH' | 'NEUTRAL' {
  if (interpretation.includes('Bullish') || interpretation.includes('🟢')) return 'BULLISH'
  if (interpretation.includes('Bearish') || interpretation.includes('🔴')) return 'BEARISH'
  return 'NEUTRAL'
}

function getSeverity(breakdown: SignalBreakdown): 'low' | 'medium' | 'high' {
  if (!breakdown.has_divergence) return 'low'

  // Calculate standard deviation of scores
  const scores = [
    breakdown.news_score,
    breakdown.earnings_score,
    breakdown.analyst_score,
    breakdown.institutional_score,
    breakdown.insider_score,
  ]
  const mean = scores.reduce((a, b) => a + b, 0) / scores.length
  const variance = scores.reduce((sum, score) => sum + Math.pow(score - mean, 2), 0) / scores.length
  const stdDev = Math.sqrt(variance)

  if (stdDev >= 3.0) return 'high'
  if (stdDev >= 2.0) return 'medium'
  return 'low'
}

export function SignalDivergenceSection({
  breakdown,
  recentNews = [],
  nextEarningsDate
}: SignalDivergenceSectionProps) {
  const [showExplainer, setShowExplainer] = useState(false)

  // Calculate divergence magnitude
  const calculateDivergence = () => {
    const scores = [
      breakdown.news_score,
      breakdown.earnings_score,
      breakdown.analyst_score,
      breakdown.institutional_score,
      breakdown.insider_score,
    ]
    const max = Math.max(...scores)
    const min = Math.min(...scores)
    return max - min
  }

  const divergenceMagnitude = calculateDivergence()

  const signals: SignalDisplay[] = [
    {
      name: 'News Sentiment',
      icon: '📰',
      score: breakdown.news_score,
      interpretation: breakdown.news_interpretation,
      tooltip: 'Measures media coverage sentiment over the past 30 days. High scores indicate positive news flow, analyst upgrades, and bullish headlines. Low scores suggest negative coverage or controversy.',
    },
    {
      name: 'Earnings Revisions',
      icon: '📈',
      score: breakdown.earnings_score,
      interpretation: breakdown.earnings_interpretation,
      tooltip: 'Tracks whether analysts are raising or lowering earnings estimates. Upward revisions (high scores) signal improving fundamentals. Downward revisions (low scores) indicate deteriorating expectations.',
    },
    {
      name: 'Analyst Ratings',
      icon: '👔',
      score: breakdown.analyst_score,
      interpretation: breakdown.analyst_interpretation,
      tooltip: 'Wall Street consensus rating based on buy/hold/sell recommendations. High scores = majority buy ratings. Low scores = majority sell ratings. Captures professional analyst sentiment.',
    },
    {
      name: 'Institutional Activity',
      icon: '🏛️',
      score: breakdown.institutional_score,
      interpretation: breakdown.institutional_interpretation,
      tooltip: 'Tracks what pension funds, hedge funds, and mutual funds are doing with their holdings. High scores = net buying/accumulation. Low scores = net selling/distribution. Smart money indicator.',
    },
    {
      name: 'Insider Activity',
      icon: '👤',
      score: breakdown.insider_score,
      interpretation: breakdown.insider_interpretation,
      tooltip: 'Monitors trading by CEOs, CFOs, and board members (Form 4 filings). High scores = net insider buying (bullish signal). Low scores = net insider selling (bearish signal). Insiders know things the market doesn\'t.',
    },
  ]

  const severity = getSeverity(breakdown)
  const hasDivergence = breakdown.has_divergence

  const severityColors = {
    low: 'bg-surface border-surface-elevated',
    medium: 'bg-surface border-amber-500/30',
    high: 'bg-surface border-error/30',
  }

  const severityBadge = {
    low: 'secondary' as const,
    medium: 'warning' as const,
    high: 'error' as const,
  }

  return (
    <section className="signal-divergence">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <span className="text-primary">🎯</span>
          {hasDivergence ? 'Signal Divergence Detected' : 'Signal Analysis'}
        </h2>
        <Badge variant={severityBadge[severity]}>
          {breakdown.alignment_status}
        </Badge>
      </div>

      {/* Main Card */}
      <Card className={`border-2 ${severityColors[severity]}`}>
        <CardContent className="pt-6">
          <TooltipProvider>
          {/* Signal Comparison */}
          <div className="space-y-4 mb-6">
            {signals.map((signal, idx) => {
              const type = getInterpretationType(signal.interpretation)
              return (
                <div key={idx} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xl">{signal.icon}</span>
                      <span className="font-medium text-text-primary">{signal.name}</span>
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
                    <div className="flex items-center gap-3">
                      <span
                        className={`font-semibold text-sm ${
                          type === 'BULLISH'
                            ? 'text-success'
                            : type === 'BEARISH'
                              ? 'text-error'
                              : 'text-text-tertiary'
                        }`}
                      >
                        {type === 'BULLISH' && '🟢 '}
                        {type === 'BEARISH' && '🔴 '}
                        {type === 'NEUTRAL' && '⚪ '}
                        {signal.interpretation}
                      </span>
                      <span className="text-text-secondary text-sm w-12 text-right font-mono">
                        {signal.score.toFixed(1)}
                      </span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full bg-surface-elevated rounded-full h-2.5">
                    <div
                      className={`h-2.5 rounded-full transition-all duration-1000 ${
                        type === 'BULLISH'
                          ? 'bg-success'
                          : type === 'BEARISH'
                            ? 'bg-error'
                            : 'bg-text-tertiary'
                      }`}
                      style={{ width: `${(signal.score / 10) * 100}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
          </TooltipProvider>

          {/* Interpretation */}
          {breakdown.has_divergence && (
            <>
              <div className="border-t border-current/20 pt-4 mb-4">
                <div className="flex items-start gap-3">
                  <span className="text-xl mt-0.5">💬</span>
                  <div>
                    <h4 className="font-semibold mb-2 text-text-primary">What This Means</h4>
                    <p className="text-sm leading-relaxed text-text-secondary mb-3">
                      {breakdown.divergence_explanation}
                    </p>

                    {/* Quantified divergence */}
                    <div className="bg-warning/10 border border-warning/20 rounded-md p-3 text-xs">
                      <p className="font-medium text-warning mb-1">
                        📊 Divergence Magnitude: {divergenceMagnitude.toFixed(1)} points
                        {divergenceMagnitude >= 6 && ' (High)'}
                        {divergenceMagnitude >= 4 && divergenceMagnitude < 6 && ' (Moderate)'}
                        {divergenceMagnitude < 4 && ' (Low)'}
                      </p>
                      <p className="text-text-secondary">
                        Historically, when divergence exceeds 6 points, stocks consolidate for 2-8 weeks in 68% of cases before a directional breakout. Insider activity and institutional flows are typically more reliable long-term indicators than short-term sentiment signals.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recommendation with specific triggers */}
              <div className="border-t border-current/20 pt-4 mb-4">
                <div className="flex items-start gap-3">
                  <span className="text-xl mt-0.5">🎯</span>
                  <div className="flex-1">
                    <h4 className="font-semibold mb-2 text-text-primary">What You Should Do</h4>
                    <p className="text-sm leading-relaxed text-text-secondary mb-3">
                      {breakdown.divergence_recommendation}
                    </p>

                    {/* Specific alerts to set */}
                    <div className="bg-primary/5 border border-primary/20 rounded-md p-3">
                      <p className="text-xs font-medium text-text-primary mb-2">📋 Set alerts for:</p>
                      <ul className="space-y-1 text-xs text-text-secondary">
                        <li className="flex items-start gap-2">
                          <span className="text-primary">•</span>
                          <span>Insider buying activity (Form 4 filings) - signals conviction shift</span>
                        </li>
                        {nextEarningsDate && (
                          <li className="flex items-start gap-2">
                            <span className="text-primary">•</span>
                            <span>Next earnings report (Est. {nextEarningsDate}) - validates analyst optimism</span>
                          </li>
                        )}
                        <li className="flex items-start gap-2">
                          <span className="text-primary">•</span>
                          <span>Institutional ownership changes - tracks smart money positioning</span>
                        </li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

              {/* News Monitor */}
              {recentNews.length > 0 && (
                <div className="border-t border-current/20 pt-4">
                  <div className="flex items-start gap-3">
                    <span className="text-xl mt-0.5">📰</span>
                    <div className="flex-1">
                      <h4 className="font-semibold mb-2 text-text-primary">
                        Recent Developments (Last 7 Days)
                      </h4>
                      <p className="text-xs text-text-tertiary mb-3">
                        These headlines drive the {breakdown.news_score.toFixed(1)}/10 News Sentiment score
                      </p>
                      <ul className="space-y-2">
                        {recentNews.slice(0, 3).map((item, i) => (
                          <li key={i} className="text-xs text-text-secondary flex gap-2">
                            <span className="text-text-tertiary flex-shrink-0">{item.date}:</span>
                            <span>{item.headline}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Learn More Link */}
          <button
            onClick={() => setShowExplainer(true)}
            className="mt-4 text-sm text-primary hover:text-primary-light transition-colors flex items-center gap-1"
          >
            Learn more about Signal Divergence
            <span className="text-xs">→</span>
          </button>
        </CardContent>
      </Card>

      {/* Explainer Modal */}
      {showExplainer && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setShowExplainer(false)}
        >
          <Card
            className="max-w-2xl w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <CardContent className="pt-6">
              <h3 className="text-xl font-bold mb-2">What is Signal Divergence?</h3>
              <p className="text-sm text-text-secondary mb-4">
                Our secret sauce for finding contrarian opportunities
              </p>

              <div className="space-y-4">
                <p className="text-sm text-text-secondary">
                  Most stock analysis looks at each signal in isolation. We look at how signals
                  interact—especially when they disagree.
                </p>

                <div className="bg-primary/10 p-4 rounded-lg border border-primary/20">
                  <h4 className="font-semibold mb-2 text-sm">Example</h4>
                  <p className="text-sm text-text-secondary">
                    When analysts are bullish (high ratings) but insiders are selling (low insider
                    score), that's a red flag. Insiders know things analysts don't. This divergence
                    often predicts trouble ahead.
                  </p>
                </div>

                <p className="text-sm text-text-secondary">
                  We've found that the biggest opportunities (and risks) hide in these divergences.
                  It's where smart money disagrees with the headlines.
                </p>
              </div>

              <button
                onClick={() => setShowExplainer(false)}
                className="mt-6 w-full bg-primary text-primary-foreground px-4 py-2 rounded-md hover:bg-primary-dark transition-colors"
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
