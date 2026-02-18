'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { SignalBreakdown } from '@/types/api'

interface SignalBreakdownCardProps {
  breakdown: SignalBreakdown
}

const SIGNALS = [
  { key: 'earnings' as const, label: 'Earnings Revisions (PRIMARY)', icon: '🎯' },
  { key: 'news' as const, label: 'News Sentiment', icon: '📰' },
  { key: 'analyst' as const, label: 'Analyst Ratings', icon: '📊' },
  { key: 'institutional' as const, label: 'Institutional (Blended)', icon: '🏦' },
  { key: 'dark_pool' as const, label: 'Dark Pool Activity', icon: '🌊' },
  { key: 'insider' as const, label: 'Insider Activity', icon: '👔' },
  { key: 'tech_divergence' as const, label: 'Technical Divergence', icon: '📈' },
]

function getColor(score: number, hasData: boolean = true) {
  // Missing data - show muted gray
  if (!hasData) return { bar: 'bg-surface-elevated', text: 'text-text-tertiary', dot: 'bg-surface-elevated' }

  // Normal coloring when data is available
  if (score >= 7.0) return { bar: 'bg-success', text: 'text-success', dot: 'bg-success' }
  if (score >= 4.0) return { bar: 'bg-warning', text: 'text-warning', dot: 'bg-warning' }
  return { bar: 'bg-error', text: 'text-error', dot: 'bg-error' }
}

export function SignalBreakdownCard({ breakdown }: SignalBreakdownCardProps) {
  const [expanded, setExpanded] = useState(false)

  const alignmentVariant = breakdown.has_divergence
    ? 'error'
    : breakdown.alignment_status.includes('STRONG')
      ? 'success'
      : 'warning'

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Signal Analysis</CardTitle>
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-secondary">Overall:</span>
            <span className={`text-lg font-bold ${getColor(breakdown.overall_score).text}`}>
              {breakdown.overall_score.toFixed(1)}
            </span>
            <Badge variant={alignmentVariant}>
              {breakdown.has_divergence ? 'DIVERGENT' : 'ALIGNED'}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Compact signal bars */}
        <div className="space-y-3">
          {SIGNALS.map(({ key, label }) => {
            const scoreKey = `${key}_score` as keyof SignalBreakdown
            const interpKey = `${key}_interpretation` as keyof SignalBreakdown
            const hasDataKey = `${key}_has_data` as keyof SignalBreakdown
            const score = breakdown[scoreKey] as number
            const interpretation = breakdown[interpKey] as string
            const hasData = breakdown[hasDataKey] !== false // Default to true if not present (backward compat)
            const colors = getColor(score, hasData)

            return (
              <div key={key}>
                <div className="flex items-center gap-3">
                  <span className="w-28 text-sm text-text-secondary truncate">{label}</span>
                  <div className="flex-1 h-2.5 bg-surface-elevated rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${colors.bar}`}
                      style={{ width: hasData ? `${(score / 10) * 100}%` : '100%' }}
                    />
                  </div>
                  <span className={`w-8 text-right text-sm font-semibold ${colors.text}`}>
                    {hasData ? score.toFixed(1) : 'N/A'}
                  </span>
                </div>
                {expanded && (
                  <p className="ml-[7.75rem] text-xs text-text-tertiary mt-0.5">
                    {interpretation}
                  </p>
                )}
              </div>
            )
          })}
        </div>

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-3 text-xs text-primary hover:text-primary-light transition-colors"
        >
          {expanded ? 'Hide details' : 'Show interpretations'}
        </button>

        {/* Direction consensus */}
        <p className="text-xs text-text-tertiary mt-3 pt-3 border-t border-surface-elevated">
          Direction: {breakdown.direction_consensus.charAt(0).toUpperCase() + breakdown.direction_consensus.slice(1)}
        </p>
      </CardContent>
    </Card>
  )
}
