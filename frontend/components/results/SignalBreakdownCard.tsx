'use client'

// All scoring, threshold, and signal logic is IDENTICAL to the original.
// Changes: signal grouping by analytical category, regime-conditioned framing labels,
// two-tier progressive disclosure (Analytical Layer / Advanced Mechanics),
// and Signal Regime Context header for fragility vs confirmation state framing.

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { SignalBreakdown } from '@/types/api'

interface SignalBreakdownCardProps {
  breakdown: SignalBreakdown
}

// ── Signal groups: organised by analytical category for institutional legibility ──
// Reliability qualifiers reflect data characteristics — no scoring changes.
const SIGNAL_GROUPS = [
  {
    group: 'Fundamental',
    reliabilityTag: 'Regime-stable',
    reliabilityNote: 'Low-frequency · high structural weight',
    signals: [
      { key: 'earnings' as const, label: 'Earnings Revisions', badge: 'PRIMARY' as const },
      { key: 'analyst' as const, label: 'Analyst Ratings', badge: null },
    ],
  },
  {
    group: 'Capital Flow & Positioning',
    reliabilityTag: 'Regime-sensitive',
    reliabilityNote: 'Tracks informed capital positioning and smart-money flow',
    signals: [
      { key: 'institutional' as const, label: 'Institutional Activity', badge: null },
      { key: 'insider' as const, label: 'Insider Activity', badge: null },
      { key: 'dark_pool' as const, label: 'Dark Pool Flow', badge: null },
    ],
  },
  {
    group: 'Sentiment & Technical',
    reliabilityTag: 'Liquidity-dependent',
    reliabilityNote: 'Regime-conditioned reliability · elevated noise floor in low-liquidity periods',
    signals: [
      { key: 'news' as const, label: 'News Sentiment', badge: null },
      {
        key: 'tech_divergence' as const,
        label: 'Technical Divergence',
        badge: 'REGIME-CONDITIONED' as const,
      },
    ],
  },
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

// Derive a Signal Regime State label from existing breakdown fields — purely informational.
// No thresholds were changed; this is label-only framing for interpretability.
function getSignalRegimeState(breakdown: SignalBreakdown): {
  label: string
  sublabel: string
  colorClass: string
} {
  const hasHigh = breakdown.has_divergence &&
    (breakdown.signal_spread_label === 'High' || breakdown.component_gap_label === 'High')
  if (hasHigh)
    return {
      label: 'Cross-Category Fragility State',
      sublabel: 'Fundamental and technical signals in active conflict — regime-sensitive path probability',
      colorClass: 'text-error',
    }
  if (breakdown.has_divergence)
    return {
      label: 'Moderate Divergence — Regime-Sensitive',
      sublabel: 'Mixed signals across analytical categories — monitor for convergence or escalation',
      colorClass: 'text-warning',
    }
  if (breakdown.alignment_status?.includes('STRONG'))
    return {
      label: 'Confirmation State — Cross-Category Alignment',
      sublabel: 'Signals aligned across fundamental, flow, and technical categories',
      colorClass: 'text-success',
    }
  return {
    label: 'Partial Alignment',
    sublabel: 'Signals partially aligned — monitor for divergence resolution',
    colorClass: 'text-text-secondary',
  }
}

export function SignalBreakdownCard({ breakdown }: SignalBreakdownCardProps) {
  const [showAnalytical, setShowAnalytical] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Directional bias + agreement — unchanged logic
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

  const biasTextColor =
    directionalBias === 'Bullish'
      ? 'text-success'
      : directionalBias === 'Bearish'
        ? 'text-error'
        : 'text-warning'

  const regimeState = getSignalRegimeState(breakdown)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Multi-Factor Signal Assessment</CardTitle>
            <p className="text-[10px] text-text-tertiary/70 mt-0.5">
              7-signal cross-category evaluation · regime-conditioned weighting
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-tertiary">Composite:</span>
              <span className={`text-base font-bold ${getColor(breakdown.overall_score).text}`}>
                {breakdown.overall_score.toFixed(1)}
              </span>
            </div>
            {/* Directional Bias + Signal Agreement — unchanged concepts, clearer labels */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-text-tertiary">
                Bias:{' '}
                <span className={`font-medium ${biasTextColor}`}>{directionalBias}</span>
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
        {/* ── Primary Interpretation Layer — always visible ── */}

        {/* Signal Regime Context strip */}
        <div className="mb-3 px-3 py-2 rounded-md bg-surface-elevated border border-border/60">
          <div className="flex items-center gap-2">
            <span className={`text-xs font-medium ${regimeState.colorClass}`}>
              {regimeState.label}
            </span>
          </div>
          <p className="text-[11px] text-text-tertiary leading-relaxed mt-0.5">
            {regimeState.sublabel}
          </p>
        </div>

        {/* P0: Data integrity summary */}
        {breakdown.missing_signal_count !== undefined && breakdown.missing_signal_count > 0 && (
          <div className="mb-3 p-2.5 rounded-md bg-warning/10 border border-warning/20 flex items-start gap-2">
            <span className="text-warning text-sm mt-0.5">⚠</span>
            <div>
              <span className="text-xs font-semibold text-warning">
                {breakdown.valid_signal_count}/
                {(breakdown.valid_signal_count ?? 0) + (breakdown.missing_signal_count ?? 0)} signals confirmed
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
              <span className="text-xs font-semibold text-error block mb-0.5">
                Volume Data — Suspect Reading
              </span>
              <p className="text-xs text-text-tertiary leading-relaxed">
                {breakdown.volume_data_flag}
              </p>
            </div>
          </div>
        )}

        {/* P0: Volume elevated flag (softer warning) */}
        {breakdown.volume_data_quality === 'ELEVATED' && breakdown.volume_data_flag && (
          <div className="mb-3 p-2.5 rounded-md bg-warning/10 border border-warning/20 flex items-start gap-2">
            <span className="text-warning text-sm mt-0.5">↑</span>
            <div>
              <span className="text-xs font-semibold text-warning block mb-0.5">
                Volume — Elevated
              </span>
              <p className="text-xs text-text-tertiary leading-relaxed">
                {breakdown.volume_data_flag}
              </p>
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
            <p className="text-xs font-semibold text-primary mb-1">
              Insider Activity — Notable Signal
            </p>
            <p className="text-xs text-text-tertiary leading-relaxed">
              {breakdown.insider_anomaly_note}
            </p>
          </div>
        )}

        {/* ── Signal Bars — grouped by analytical category ── */}
        <div className="space-y-4">
          {SIGNAL_GROUPS.map(({ group, reliabilityTag, reliabilityNote, signals }) => (
            <div key={group}>
              {/* Group header with reliability framing */}
              <div className="flex items-baseline justify-between mb-1.5">
                <span className="text-[10px] uppercase tracking-wider font-semibold text-text-tertiary">
                  {group}
                </span>
                <span className="text-[10px] text-text-tertiary/60 italic">
                  {reliabilityTag}
                </span>
              </div>
              {showAnalytical && (
                <p className="text-[10px] text-text-tertiary/50 mb-1.5 leading-relaxed -mt-1">
                  {reliabilityNote}
                </p>
              )}

              <div className="space-y-3">
                {signals.map(({ key, label, badge }) => {
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
                        {/* Label + optional badge */}
                        <div className="w-36 flex items-center gap-1.5 shrink-0 min-w-0">
                          <span className="text-sm text-text-secondary truncate">{label}</span>
                          {badge === 'PRIMARY' && (
                            <span className="text-[9px] font-semibold text-primary/70 border border-primary/30 rounded px-1 py-0 shrink-0">
                              PRI
                            </span>
                          )}
                          {badge === 'REGIME-CONDITIONED' && (
                            <span className="text-[9px] font-medium text-text-tertiary/60 border border-border rounded px-1 py-0 shrink-0">
                              RC
                            </span>
                          )}
                        </div>

                        {hasData ? (
                          <>
                            <div className="flex-1 h-2.5 bg-surface-elevated rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all duration-500 ${colors.bar}`}
                                style={{ width: `${(score / 10) * 100}%` }}
                              />
                            </div>
                            <span
                              className={`w-8 text-right text-sm font-semibold ${colors.text}`}
                            >
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

                      {/* ── Analytical Layer: signal interpretations ── */}
                      {showAnalytical && (
                        <p className="ml-[9.5rem] text-xs text-text-tertiary mt-0.5">
                          {hasData
                            ? interpretation
                            : 'Data unavailable. Excluded from overall score — not defaulted to neutral.'}
                        </p>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Group divider (except last) */}
              <div className="mt-3 border-t border-border/40" />
            </div>
          ))}
        </div>

        {/* ── Analytical Layer (Tier 2) — expanded metrics ── */}
        {showAnalytical && (
          <>
            {/* Divergence metrics panel */}
            {(breakdown.signal_spread !== undefined || breakdown.component_gap !== undefined) && (
              <div className="mt-4 pt-3 border-t border-surface-elevated space-y-2">
                <div className="flex items-baseline justify-between">
                  <p className="text-xs font-semibold text-text-secondary">Divergence Metrics</p>
                  <span className="text-[10px] text-text-tertiary/60 italic">
                    Signal interaction quantification
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  {breakdown.signal_spread !== undefined && (
                    <div>
                      <span className="text-text-tertiary block">Signal Spread (σ)</span>
                      <span
                        className={`font-semibold ${spreadLabelColor(breakdown.signal_spread_label)}`}
                      >
                        {breakdown.signal_spread.toFixed(2)}
                      </span>
                      <span className="text-text-tertiary ml-1">
                        {breakdown.signal_spread_label ?? ''}
                      </span>
                      <p className="text-text-tertiary mt-0.5 leading-relaxed">
                        Std deviation across all 7 signals — drives the Aligned/Conflict badge.
                      </p>
                    </div>
                  )}
                  {breakdown.component_gap !== undefined && (
                    <div>
                      <span className="text-text-tertiary block">Fund / Tech Gap</span>
                      <span
                        className={`font-semibold ${spreadLabelColor(breakdown.component_gap_label)}`}
                      >
                        {breakdown.component_gap.toFixed(1)} pts
                      </span>
                      <span className="text-text-tertiary ml-1">
                        {breakdown.component_gap_label ?? ''}
                      </span>
                      <p className="text-text-tertiary mt-0.5 leading-relaxed">
                        Value-vs-momentum construct — fundamental vs technical gap.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Model confidence dimensions */}
            {(breakdown.signal_strength !== undefined ||
              breakdown.signal_stability !== undefined) && (
              <div className="mt-4 pt-3 border-t border-surface-elevated space-y-2">
                <div className="flex items-baseline justify-between">
                  <p className="text-xs font-semibold text-text-secondary">Model Confidence Dimensions</p>
                  <span className="text-[10px] text-text-tertiary/60 italic">
                    Stability-weight indicators
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-text-tertiary block">Signal Strength</span>
                    <span
                      className={`font-semibold ${
                        (breakdown.signal_strength ?? 5) >= 7
                          ? 'text-success'
                          : (breakdown.signal_strength ?? 5) >= 4
                            ? 'text-warning'
                            : 'text-error'
                      }`}
                    >
                      {breakdown.signal_strength_label ?? '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-text-tertiary block">Signal Stability</span>
                    <span
                      className={`font-semibold ${
                        (breakdown.signal_stability ?? 5) >= 7
                          ? 'text-success'
                          : (breakdown.signal_stability ?? 5) >= 4
                            ? 'text-warning'
                            : 'text-error'
                      }`}
                    >
                      {breakdown.signal_stability_label ?? '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-text-tertiary block">Data Integrity</span>
                    <span
                      className={`font-semibold ${
                        breakdown.data_integrity_label === 'Complete'
                          ? 'text-success'
                          : breakdown.data_integrity_label === 'Partial'
                            ? 'text-warning'
                            : 'text-error'
                      }`}
                    >
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
          </>
        )}

        {/* ── Advanced Mechanics (Tier 3) — confidence reduction log ── */}
        {showAnalytical && showAdvanced &&
          breakdown.confidence_reduction_log &&
          breakdown.confidence_reduction_log.length > 0 && (
            <div className="mt-4 pt-3 border-t border-surface-elevated space-y-2">
              <p className="text-xs font-semibold text-text-secondary">Confidence Reduction Log</p>
              <div className="space-y-2">
                {breakdown.confidence_reduction_log.map((entry, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <span className="text-error font-semibold w-10 shrink-0">
                      −{entry.penalty_pct}%
                    </span>
                    <div>
                      <span className="text-text-secondary font-medium">{entry.trigger}</span>
                      <p className="text-text-tertiary leading-relaxed mt-0.5">{entry.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        {/* ── Progressive disclosure controls ── */}
        <div className="mt-3 flex items-center gap-3 flex-wrap">
          <button
            onClick={() => {
              setShowAnalytical(!showAnalytical)
              if (showAnalytical) setShowAdvanced(false)
            }}
            className="text-xs text-primary hover:text-primary-light transition-colors"
          >
            {showAnalytical ? 'Collapse ↑' : 'Analytical Layer →'}
          </button>

          {showAnalytical &&
            breakdown.confidence_reduction_log &&
            breakdown.confidence_reduction_log.length > 0 && (
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="text-xs text-text-tertiary hover:text-text-secondary transition-colors"
              >
                {showAdvanced ? 'Hide Mechanics' : 'Advanced Mechanics →'}
              </button>
            )}
        </div>
      </CardContent>
    </Card>
  )
}
