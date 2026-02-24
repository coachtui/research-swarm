'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { HelpCircle } from 'lucide-react'

interface ScoreBreakdownBarsProps {
  breakdown: {
    earnings_momentum: number
    financial_health: number
    valuation: number
    technical_strength: number
    sentiment_catalysts: number
  }
  overallScore: number
}

const COMPONENTS = [
  {
    key: 'earnings_momentum' as const,
    label: 'Earnings Momentum',
    primary: true,
    tooltip: 'Tracks whether the company is beating earnings expectations and raising guidance. Higher scores indicate consistent earnings beats and positive revisions.',
  },
  {
    key: 'financial_health' as const,
    label: 'Financial Health',
    primary: false,
    tooltip: 'Measures balance sheet strength, profitability, and cash flow stability. Strong companies have low debt, high margins, and growing free cash flow.',
  },
  {
    key: 'valuation' as const,
    label: 'Valuation',
    primary: false,
    tooltip: 'Compares current price to intrinsic value using P/E, PEG, DCF, and peer multiples. Higher scores signal more attractive valuation vs. fundamentals.',
  },
  {
    key: 'technical_strength' as const,
    label: 'Technical / Momentum',
    primary: false,
    tooltip: 'Analyzes price trends, volume patterns, and momentum indicators (RSI, MACD). Strong technicals suggest institutional accumulation.',
  },
  {
    key: 'sentiment_catalysts' as const,
    label: 'Sentiment / Catalysts',
    primary: false,
    tooltip: 'Evaluates market sentiment, news flow, and upcoming catalysts (earnings, product launches, regulatory). Positive sentiment can drive near-term moves.',
  },
]

function getBarColor(score: number): string {
  if (score >= 7.0) return 'bg-success'
  if (score >= 4.0) return 'bg-warning'
  return 'bg-error'
}

function getTextColor(score: number): string {
  if (score >= 7.0) return 'text-success'
  if (score >= 4.0) return 'text-warning'
  return 'text-error'
}

function getBand(score: number): string {
  if (score >= 7.0) return 'Strong'
  if (score >= 4.0) return 'Moderate'
  return 'Weak'
}

/**
 * Component-specific institutional context label.
 * Maps score tiers to qualitative descriptors meaningful to institutional readers.
 * Provides peer-relative framing without fabricating actual percentile data.
 */
function getContextLabel(key: keyof ScoreBreakdownBarsProps['breakdown'], score: number): string {
  switch (key) {
    case 'earnings_momentum':
      if (score >= 8.5) return 'Consistently beating estimates'
      if (score >= 7.0) return 'Above-consensus execution'
      if (score >= 5.5) return 'In-line with estimates'
      if (score >= 4.0) return 'Mixed earnings quality'
      return 'Missing expectations'

    case 'financial_health':
      if (score >= 8.5) return 'Investment-grade balance sheet'
      if (score >= 7.0) return 'Solid fundamentals'
      if (score >= 5.5) return 'Adequate liquidity'
      if (score >= 4.0) return 'Moderate leverage'
      return 'Elevated credit risk'

    case 'valuation':
      if (score >= 8.5) return 'Significant discount to fundamentals'
      if (score >= 7.0) return 'Attractive vs. intrinsic value'
      if (score >= 5.5) return 'Approximate fair value'
      if (score >= 4.0) return 'Slight premium to peers'
      return 'Stretched vs. fundamentals'

    case 'technical_strength':
      if (score >= 8.5) return 'Strong uptrend, institutional bid'
      if (score >= 7.0) return 'Positive momentum structure'
      if (score >= 5.5) return 'Neutral technical backdrop'
      if (score >= 4.0) return 'Mixed price signals'
      return 'Distribution phase'

    case 'sentiment_catalysts':
      if (score >= 8.5) return 'Strong near-term catalyst pipeline'
      if (score >= 7.0) return 'Positive sentiment backdrop'
      if (score >= 5.5) return 'Neutral news flow'
      if (score >= 4.0) return 'Limited near-term catalysts'
      return 'Headwinds in sentiment'

    default:
      return score >= 7 ? 'Above average' : score >= 4 ? 'Average' : 'Below average'
  }
}

export function ScoreBreakdownBars({ breakdown, overallScore }: ScoreBreakdownBarsProps) {
  return (
    <section className="score-breakdown">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            Component Breakdown
            <span className="ml-3 text-sm font-normal text-text-tertiary">
              Overall Score: <span className="font-semibold text-text-primary">{overallScore.toFixed(1)}/10</span>
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-5">
            {COMPONENTS.map(({ key, label, primary, tooltip }) => {
              const score = breakdown[key]
              const contextLabel = getContextLabel(key, score)
              return (
                <div key={key} className="space-y-1.5">
                  <div className="flex justify-between items-start">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm text-text-secondary">
                        {label}
                        {primary && (
                          <span className="ml-1.5 text-xs text-primary font-medium">PRIMARY</span>
                        )}
                      </span>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-text-tertiary hover:text-text-secondary transition-colors">
                            <HelpCircle className="h-3.5 w-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p className="text-xs leading-relaxed">{tooltip}</p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                    <div className="flex items-center gap-2 text-right">
                      {/* Context label — institutional peer framing */}
                      <span className="text-[10px] text-text-tertiary italic hidden sm:inline">
                        {contextLabel}
                      </span>
                      <span className="text-xs text-text-tertiary">{getBand(score)}</span>
                      <span className={`text-sm font-semibold tabular-nums ${getTextColor(score)}`}>
                        {score.toFixed(1)}
                      </span>
                    </div>
                  </div>
                  <div className="h-2.5 bg-surface-elevated rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ease-out ${getBarColor(score)}`}
                      style={{ width: `${(score / 10) * 100}%` }}
                    />
                  </div>
                  {/* Context label — mobile fallback (below bar) */}
                  <p className="text-[10px] text-text-tertiary italic sm:hidden">{contextLabel}</p>
                </div>
              )
            })}
          </div>

          {/* Legend */}
          <div className="flex items-center justify-center gap-5 text-xs text-text-tertiary pt-5 mt-4 border-t border-surface-elevated">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-success" />
              <span>Strong (7+)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-warning" />
              <span>Moderate (4–6.9)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-error" />
              <span>Weak (&lt;4)</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </section>
  )
}
