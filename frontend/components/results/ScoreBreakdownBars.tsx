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
    tooltip: 'Compares current price to intrinsic value using P/E, PEG, DCF, and peer multiples. Lower scores mean expensive relative to fundamentals.',
  },
  {
    key: 'technical_strength' as const,
    label: 'Technical/Momentum',
    primary: false,
    tooltip: 'Analyzes price trends, volume patterns, and momentum indicators (RSI, MACD). Strong technicals suggest institutional accumulation.',
  },
  {
    key: 'sentiment_catalysts' as const,
    label: 'Sentiment/Catalysts',
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

export function ScoreBreakdownBars({ breakdown, overallScore }: ScoreBreakdownBarsProps) {
  return (
    <section className="score-breakdown">
      {/* Component Breakdown */}
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
          <div className="space-y-4">
            {COMPONENTS.map(({ key, label, primary, tooltip }) => {
              const score = breakdown[key]
              return (
                <div key={key} className="space-y-1.5">
                  <div className="flex justify-between items-center">
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
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-text-tertiary">{getBand(score)}</span>
                      <span className={`text-sm font-semibold ${getTextColor(score)}`}>
                        {score.toFixed(1)}
                      </span>
                    </div>
                  </div>
                  <div className="h-3 bg-surface-elevated rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ease-out ${getBarColor(score)}`}
                      style={{ width: `${(score / 10) * 100}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>

        {/* Legend */}
        <div className="flex items-center justify-center gap-5 text-xs text-text-tertiary pt-4 mt-4 border-t border-surface-elevated">
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
