'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { SignalBreakdown } from '@/types/api'

// Stop quality badge colors
const STOP_QUALITY_VARIANT: Record<string, 'success' | 'warning' | 'default'> = {
  ALIGNED: 'success',
  WIDE: 'warning',
  ADJUSTED: 'default',
}

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
        {/* P0: Data integrity summary */}
        {breakdown.missing_signal_count !== undefined && breakdown.missing_signal_count > 0 && (
          <div className="mb-3 p-2.5 rounded-md bg-warning/10 border border-warning/20 flex items-start gap-2">
            <span className="text-warning text-sm mt-0.5">⚠</span>
            <div>
              <span className="text-xs font-semibold text-warning">
                {breakdown.valid_signal_count}/{(breakdown.valid_signal_count ?? 0) + (breakdown.missing_signal_count ?? 0)} signals confirmed
              </span>
              <span className="text-xs text-text-tertiary ml-1">
                — {breakdown.missing_signal_count} excluded from overall score. Missing data ≠ Neutral.
              </span>
            </div>
          </div>
        )}

        {/* P1: RSI extreme condition flag */}
        {breakdown.rsi_extreme_flag && (
          <div className="mb-3 p-2.5 rounded-md bg-warning/10 border border-warning/20">
            <p className="text-xs font-semibold text-warning mb-1">
              {breakdown.rsi_extreme_flag.label}
            </p>
            <p className="text-xs text-text-tertiary leading-relaxed">
              {breakdown.rsi_extreme_flag.interpretation}
            </p>
          </div>
        )}

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
                  {hasData ? (
                    <>
                      <div className="flex-1 h-2.5 bg-surface-elevated rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${colors.bar}`}
                          style={{ width: `${(score / 10) * 100}%` }}
                        />
                      </div>
                      <span className={`w-8 text-right text-sm font-semibold ${colors.text}`}>
                        {score.toFixed(1)}
                      </span>
                    </>
                  ) : (
                    <>
                      <div className="flex-1">
                        <span className="text-xs text-warning bg-warning/10 border border-warning/20 rounded px-2 py-0.5">
                          No Data — Score Excluded
                        </span>
                      </div>
                      <span className="w-8 text-right text-xs text-text-tertiary">—</span>
                    </>
                  )}
                </div>
                {expanded && (
                  <p className="ml-[7.75rem] text-xs text-text-tertiary mt-0.5">
                    {hasData
                      ? interpretation
                      : 'Data unavailable. This signal was excluded from the overall score rather than defaulted to neutral.'}
                  </p>
                )}
              </div>
            )
          })}
        </div>

        {/* P3: Model confidence dimensions (collapsed by default, shown in expanded) */}
        {expanded && (breakdown.signal_strength !== undefined || breakdown.signal_stability !== undefined) && (
          <div className="mt-4 pt-3 border-t border-surface-elevated space-y-2">
            <p className="text-xs font-semibold text-text-secondary">Model Confidence</p>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <span className="text-text-tertiary block">Signal Strength</span>
                <span className={`font-semibold ${
                  (breakdown.signal_strength ?? 5) >= 7 ? 'text-success' :
                  (breakdown.signal_strength ?? 5) >= 4 ? 'text-warning' : 'text-error'
                }`}>
                  {breakdown.signal_strength_label ?? '—'}
                </span>
              </div>
              <div>
                <span className="text-text-tertiary block">Signal Stability</span>
                <span className={`font-semibold ${
                  (breakdown.signal_stability ?? 5) >= 7 ? 'text-success' :
                  (breakdown.signal_stability ?? 5) >= 4 ? 'text-warning' : 'text-error'
                }`}>
                  {breakdown.signal_stability_label ?? '—'}
                </span>
              </div>
              <div>
                <span className="text-text-tertiary block">Data Integrity</span>
                <span className={`font-semibold ${
                  breakdown.data_integrity_label === 'Complete' ? 'text-success' :
                  breakdown.data_integrity_label === 'Partial' ? 'text-warning' : 'text-error'
                }`}>
                  {breakdown.data_integrity_label ?? '—'}
                  {breakdown.data_integrity_pct !== undefined && (
                    <span className="text-text-tertiary font-normal ml-1">
                      ({breakdown.data_integrity_pct}%)
                    </span>
                  )}
                </span>
              </div>
            </div>
          </div>
        )}

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
