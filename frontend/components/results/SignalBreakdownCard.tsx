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
  if (!hasData) return { bar: 'bg-surface-elevated', text: 'text-text-tertiary', dot: 'bg-surface-elevated' }
  if (score >= 7.0) return { bar: 'bg-success', text: 'text-success', dot: 'bg-success' }
  if (score >= 4.0) return { bar: 'bg-warning', text: 'text-warning', dot: 'bg-warning' }
  return { bar: 'bg-error', text: 'text-error', dot: 'bg-error' }
}

function spreadLabelColor(label?: string) {
  if (label === 'High') return 'text-error'
  if (label === 'Moderate') return 'text-warning'
  return 'text-success'
}

export function SignalBreakdownCard({ breakdown }: SignalBreakdownCardProps) {
  const [expanded, setExpanded] = useState(false)

  // Req 3: Separate directional bias from signal agreement — two distinct concepts
  const directionalBias = (() => {
    const d = (breakdown.direction_consensus ?? '').toLowerCase()
    if (d.includes('bull')) return 'Bullish'
    if (d.includes('bear')) return 'Bearish'
    return 'Neutral'
  })()

  const agreementLabel = breakdown.has_divergence
    ? (breakdown.signal_spread_label === 'High' || breakdown.alignment_status.includes('HIGH')
        ? 'High Conflict'
        : 'Moderate Conflict')
    : 'Aligned'

  const alignmentVariant = breakdown.has_divergence
    ? 'error'
    : breakdown.alignment_status.includes('STRONG')
      ? 'success'
      : 'warning'

  const biasTextColor = directionalBias === 'Bullish' ? 'text-success' : directionalBias === 'Bearish' ? 'text-error' : 'text-warning'

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Signal Analysis</CardTitle>
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-tertiary">Overall:</span>
              <span className={`text-base font-bold ${getColor(breakdown.overall_score).text}`}>
                {breakdown.overall_score.toFixed(1)}
              </span>
            </div>
            {/* Req 3: Directional Bias + Signal Agreement as separate concepts */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-text-tertiary">
                Bias: <span className={`font-medium ${biasTextColor}`}>{directionalBias}</span>
              </span>
              <span className="text-text-tertiary">·</span>
              <Badge variant={alignmentVariant} className="text-xs font-normal py-0">
                {agreementLabel}
              </Badge>
            </div>
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

        {/* P0: Volume data suspect flag */}
        {breakdown.volume_data_quality === 'SUSPECT' && breakdown.volume_data_flag && (
          <div className="mb-3 p-2.5 rounded-md bg-error/10 border border-error/20 flex items-start gap-2">
            <span className="text-error text-sm mt-0.5">⚠</span>
            <div>
              <span className="text-xs font-semibold text-error block mb-0.5">Volume Data — Suspect Reading</span>
              <p className="text-xs text-text-tertiary leading-relaxed">{breakdown.volume_data_flag}</p>
            </div>
          </div>
        )}

        {/* P0: Volume elevated flag (softer warning) */}
        {breakdown.volume_data_quality === 'ELEVATED' && breakdown.volume_data_flag && (
          <div className="mb-3 p-2.5 rounded-md bg-warning/10 border border-warning/20 flex items-start gap-2">
            <span className="text-warning text-sm mt-0.5">↑</span>
            <div>
              <span className="text-xs font-semibold text-warning block mb-0.5">Volume — Elevated</span>
              <p className="text-xs text-text-tertiary leading-relaxed">{breakdown.volume_data_flag}</p>
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

        {/* P2: Insider anomaly note */}
        {breakdown.insider_anomaly_note && (
          <div className="mb-3 p-2.5 rounded-md bg-primary/10 border border-primary/20">
            <p className="text-xs font-semibold text-primary mb-1">Insider Activity — Notable Signal</p>
            <p className="text-xs text-text-tertiary leading-relaxed">{breakdown.insider_anomaly_note}</p>
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
            const hasData = breakdown[hasDataKey] !== false
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

        {/* Expanded: Divergence metrics panel */}
        {expanded && (breakdown.signal_spread !== undefined || breakdown.component_gap !== undefined) && (
          <div className="mt-4 pt-3 border-t border-surface-elevated space-y-2">
            <p className="text-xs font-semibold text-text-secondary">Divergence Metrics</p>
            <div className="grid grid-cols-2 gap-3 text-xs">
              {breakdown.signal_spread !== undefined && (
                <div>
                  <span className="text-text-tertiary block">Signal Spread (σ)</span>
                  <span className={`font-semibold ${spreadLabelColor(breakdown.signal_spread_label)}`}>
                    {breakdown.signal_spread.toFixed(2)}
                  </span>
                  <span className="text-text-tertiary ml-1">{breakdown.signal_spread_label ?? ''}</span>
                  <p className="text-text-tertiary mt-0.5 leading-relaxed">
                    Std deviation across all 7 signals — drives the headline Divergent/Aligned badge.
                  </p>
                </div>
              )}
              {breakdown.component_gap !== undefined && (
                <div>
                  <span className="text-text-tertiary block">Fund / Tech Gap</span>
                  <span className={`font-semibold ${spreadLabelColor(breakdown.component_gap_label)}`}>
                    {breakdown.component_gap.toFixed(1)} pts
                  </span>
                  <span className="text-text-tertiary ml-1">{breakdown.component_gap_label ?? ''}</span>
                  <p className="text-text-tertiary mt-0.5 leading-relaxed">
                    Raw gap between fundamental valuation score and technical score — value-vs-momentum construct.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* P3: Model confidence dimensions */}
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

        {/* P1: Confidence reduction log */}
        {expanded && breakdown.confidence_reduction_log && breakdown.confidence_reduction_log.length > 0 && (
          <div className="mt-4 pt-3 border-t border-surface-elevated space-y-2">
            <p className="text-xs font-semibold text-text-secondary">Confidence Reduction Log</p>
            <div className="space-y-2">
              {breakdown.confidence_reduction_log.map((entry, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className="text-error font-semibold w-10 shrink-0">−{entry.penalty_pct}%</span>
                  <div>
                    <span className="text-text-secondary font-medium">{entry.trigger}</span>
                    <p className="text-text-tertiary leading-relaxed mt-0.5">{entry.detail}</p>
                  </div>
                </div>
              ))}
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

        {/* Direction consensus — surfaced in header as Directional Bias */}
      </CardContent>
    </Card>
  )
}
