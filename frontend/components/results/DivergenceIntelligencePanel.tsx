'use client'

import { useState } from 'react'
import type { DivergenceOverlay, ScoreComponent } from '@/types/api'

interface DivergenceIntelligencePanelProps {
  overlay: DivergenceOverlay | null | undefined
}

/**
 * DivergenceIntelligencePanel — timing intelligence & allocation adjustment.
 *
 * Shows divergence score, phase classification, sub-metrics detail grid,
 * phase tier table, and allocation adjustment logic.
 *
 * Non-destructive: divergence affects initial allocation sizing and add intensity,
 * but does NOT override gating, drawdown tiers, or max caps.
 */
export function DivergenceIntelligencePanel({ overlay }: DivergenceIntelligencePanelProps) {
  if (!overlay) return null

  const [showBreakdown, setShowBreakdown] = useState(false)

  const {
    divergence_score,
    divergence_phase,
    phase_label,
    phase_interpretation,
    dvrg_mode,
    divergence_type,
    price_vs_intrinsic_pct,
    eps_revision_direction,
    institutional_flow,
    technical_structure,
    initial_allocation_base,
    initial_allocation_adjustment,
    initial_allocation_final,
    add_intensity_modifier,
    score_components,
    score_coverage,
  } = overlay

  // ── Phase color, badge & discipline label ─────────────────────────────────
  // Visual scarcity: muted for weak, neutral for emerging, accent only for confirmed edge
  const phaseConfig: Record<string, { color: string; bg: string; disciplineLabel: string }> = {
    Weak:     { color: 'text-text-tertiary',  bg: 'bg-surface-elevated/50',  disciplineLabel: 'No Timing Edge' },
    Emerging: { color: 'text-text-secondary', bg: 'bg-surface-elevated/60',  disciplineLabel: 'Monitoring Edge' },
    Strong:   { color: 'text-primary',        bg: 'bg-primary/10',           disciplineLabel: 'Accumulation Edge' },
    Extreme:  { color: 'text-success',        bg: 'bg-success/15',           disciplineLabel: 'Dislocation Edge' },
  }

  const phaseStyle = phaseConfig[divergence_phase] || phaseConfig.Weak

  return (
    <div className="rounded-xl border border-border/60 bg-surface/30 overflow-hidden">
      <div className="px-5 py-4 space-y-4">
        {/* Score header row — clickable to reveal component breakdown */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => setShowBreakdown(v => !v)}
            className="flex-shrink-0 text-left group"
            title="Click to see score breakdown"
          >
            <div className="text-4xl font-bold font-mono text-text-primary tabular-nums group-hover:text-primary transition-colors">
              {divergence_score.toFixed(1)}
            </div>
            <p className="text-[10px] text-text-tertiary mt-0.5 flex items-center gap-1">
              Score (0–10)
              <span className="text-primary">{showBreakdown ? '▴' : '▾'}</span>
            </p>
          </button>
          <div className="flex-1 space-y-2">
            <div className="flex items-center gap-2">
              <span className={`px-2.5 py-1 rounded text-xs font-semibold uppercase tracking-wider ${phaseStyle.bg} ${phaseStyle.color}`}>
                {phaseStyle.disciplineLabel}
              </span>
              <span className="text-sm font-medium text-text-secondary">{phase_label}</span>
            </div>
            <p className="text-sm text-text-secondary italic">{phase_interpretation}</p>
            <p className="text-[10px] text-text-tertiary font-mono italic">DVRG Mode: {dvrg_mode}</p>
          </div>
        </div>

        {/* ── Score Breakdown (expandable) ──────────────────────────────── */}
        {showBreakdown && score_components && score_components.length > 0 && (
          <ScoreBreakdown components={score_components} coverage={score_coverage} />
        )}

        {/* Detail grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <DetailTile
            label="Divergence Type"
            value={divergence_type ?? '—'}
            mono
          />
          <DetailTile
            label="Price vs Intrinsic"
            value={price_vs_intrinsic_pct !== null ? `${price_vs_intrinsic_pct > 0 ? '+' : ''}${price_vs_intrinsic_pct.toFixed(1)}%` : '—'}
            valueColor={
              price_vs_intrinsic_pct === null
                ? 'text-text-secondary'
                : price_vs_intrinsic_pct > 10
                  ? 'text-error'
                  : price_vs_intrinsic_pct < -10
                    ? 'text-success'
                    : 'text-warning'
            }
          />
          <DetailTile
            label="EPS Revision"
            value={eps_revision_direction ?? '—'}
            valueColor={
              eps_revision_direction === 'Positive'
                ? 'text-success'
                : eps_revision_direction === 'Negative'
                  ? 'text-error'
                  : 'text-text-secondary'
            }
          />
          <DetailTile
            label="Institutional Flow"
            value={institutional_flow ?? '—'}
            valueColor={
              institutional_flow === 'Strong'
                ? 'text-success'
                : institutional_flow === 'Moderate'
                  ? 'text-warning'
                  : 'text-text-tertiary'
            }
          />
          <DetailTile
            label="Technical Structure"
            value={technical_structure ?? '—'}
            valueColor={
              technical_structure === 'Strong'
                ? 'text-success'
                : technical_structure === 'Stabilizing'
                  ? 'text-warning'
                  : 'text-text-tertiary'
            }
          />
        </div>

        {/* Phase tier table */}
        <div className="border-t border-border/40 pt-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Divergence Phases
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border/40">
                  <th className="text-left py-1.5 px-2 text-text-tertiary font-semibold">Phase</th>
                  <th className="text-left py-1.5 px-2 text-text-tertiary font-semibold">Score</th>
                  <th className="text-left py-1.5 px-2 text-text-tertiary font-semibold">Label</th>
                  <th className="text-center py-1.5 px-2 text-text-tertiary font-semibold">Multiplier</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { phase: 'Weak', score: '0–3', label: 'No Timing Edge', multiplier: '0.8×' },
                  { phase: 'Emerging', score: '4–6', label: 'Monitoring Edge', multiplier: '1.0×' },
                  { phase: 'Strong', score: '7–8', label: 'Accumulation Edge', multiplier: '1.2×' },
                  { phase: 'Extreme', score: '9–10', label: 'Dislocation Edge', multiplier: '1.2×' },
                ].map(row => (
                  <tr
                    key={row.phase}
                    className={`border-b border-border/30 ${
                      row.phase === divergence_phase ? 'bg-primary/10 border-primary/30' : ''
                    }`}
                  >
                    <td className="py-1.5 px-2 font-semibold text-text-primary">{row.phase}</td>
                    <td className="py-1.5 px-2 text-text-secondary">{row.score}</td>
                    <td className="py-1.5 px-2 text-text-secondary">{row.label}</td>
                    <td className="py-1.5 px-2 text-center font-mono text-text-secondary">{row.multiplier}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Allocation adjustment block — only show if adjustment exists */}
        {(initial_allocation_adjustment !== 0 || add_intensity_modifier !== 1.0) && (
          <div className="border-t border-border/40 pt-3 space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
              Allocation Adjustment
            </p>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">Base Allocation</span>
                <span className="font-mono font-bold text-text-primary">{(initial_allocation_base * 100).toFixed(1)}%</span>
              </div>
              {initial_allocation_adjustment !== 0 && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">
                    Divergence {initial_allocation_adjustment > 0 ? '↑' : '↓'}
                  </span>
                  <span className={`font-mono font-bold ${initial_allocation_adjustment > 0 ? 'text-success' : 'text-error'}`}>
                    {initial_allocation_adjustment > 0 ? '+' : ''}
                    {(initial_allocation_adjustment * 100).toFixed(1)}%
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between border-t border-border/40 pt-1.5">
                <span className="text-sm font-semibold text-text-primary">Adjusted Allocation</span>
                <span className="font-mono font-bold text-primary text-base">
                  {(initial_allocation_final * 100).toFixed(1)}%
                </span>
              </div>
            </div>

            {/* Add intensity modifier badge */}
            {add_intensity_modifier !== 1.0 && (
              <div className="flex items-center gap-2 pt-1.5 border-t border-border/40">
                <span className="text-[10px] text-text-tertiary">Add Intensity Modifier:</span>
                <span className="bg-primary/15 text-primary border border-primary/30 rounded px-1.5 py-0.5 text-[10px] font-semibold font-mono">
                  {add_intensity_modifier.toFixed(2)}×
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function ScoreBreakdown({
  components,
  coverage,
}: {
  components: ScoreComponent[]
  coverage?: number
}) {
  const activeCount = components.filter(c => c.active).length

  return (
    <div className="rounded-lg border border-border/40 bg-surface-elevated/40 px-3 py-3 space-y-2.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
          Score Components
        </p>
        <span className="text-[10px] text-text-tertiary font-mono">
          {activeCount}/{components.length} active
          {coverage !== undefined && (
            <span className="ml-1 text-text-tertiary">({coverage}% coverage)</span>
          )}
        </span>
      </div>

      {/* Component rows */}
      <div className="space-y-1.5">
        {components.map(c => (
          <ScoreComponentRow key={c.key} component={c} />
        ))}
      </div>

      <p className="text-[9px] text-text-tertiary border-t border-border/30 pt-2">
        Score = equal-weight average of active components × data coverage factor
      </p>
    </div>
  )
}

function ScoreComponentRow({ component: c }: { component: ScoreComponent }) {
  const barWidth = `${c.score * 10}%`
  // Visual scarcity: 0–3 muted · 4–5 neutral · 6–7 accent · 8+ strong accent
  const barColor =
    !c.active     ? 'bg-border/40' :
    c.score >= 8  ? 'bg-success/70' :
    c.score >= 6  ? 'bg-primary/50' :
    c.score >= 4  ? 'bg-text-secondary/30' :
    'bg-border/40'

  const scoreColor =
    !c.active     ? 'text-text-tertiary' :
    c.score >= 8  ? 'text-success' :
    c.score >= 6  ? 'text-primary' :
    c.score >= 4  ? 'text-text-secondary' :
    'text-text-tertiary'

  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className={`text-[9px] ${c.active ? 'text-success' : 'text-text-tertiary'}`}>
            {c.active ? '●' : '○'}
          </span>
          <span className="text-[11px] font-semibold text-text-primary truncate">{c.label}</span>
        </div>
        <span className={`text-[11px] font-mono font-bold flex-shrink-0 ${scoreColor}`}>
          {c.active ? `${c.score.toFixed(1)}` : '—'}
        </span>
      </div>
      {/* Bar */}
      <div className="h-1 bg-border/30 rounded-full overflow-hidden ml-3.5">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: barWidth }}
        />
      </div>
      {/* Detail line */}
      <p className="text-[9px] text-text-tertiary ml-3.5">{c.detail}</p>
    </div>
  )
}

function DetailTile({
  label,
  value,
  valueColor,
  mono = false,
}: {
  label: string
  value: string
  valueColor?: string
  mono?: boolean
}) {
  return (
    <div className="rounded-lg border border-border/40 bg-surface-elevated/50 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">{label}</p>
      <p className={`text-sm font-bold mt-0.5 ${mono ? 'font-mono tabular-nums' : ''} ${valueColor || 'text-text-primary'}`}>
        {value}
      </p>
    </div>
  )
}
