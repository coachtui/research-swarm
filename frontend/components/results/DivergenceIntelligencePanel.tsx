'use client'

import type { DivergenceOverlay } from '@/types/api'

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
  } = overlay

  // ── Phase color & badge ────────────────────────────────────────────────────
  const phaseColors: Record<string, { color: string; bg: string }> = {
    Weak: { color: 'text-text-tertiary', bg: 'bg-surface-elevated/50' },
    Emerging: { color: 'text-warning', bg: 'bg-warning/10' },
    Strong: { color: 'text-primary', bg: 'bg-primary/10' },
    Extreme: { color: 'text-success', bg: 'bg-success/10' },
  }

  const phaseStyle = phaseColors[divergence_phase] || phaseColors.Weak

  // ── Sub-metric detail grid ─────────────────────────────────────────────────
  // Type | Price vs Intrinsic | EPS Revisions | Institutional Flow | Technical Structure

  return (
    <div className="rounded-xl border border-border/60 bg-surface/30 overflow-hidden">
      <div className="px-5 py-4 space-y-4">
        {/* Score header row */}
        <div className="flex items-center gap-4">
          <div>
            <div className="text-4xl font-bold font-mono text-text-primary tabular-nums">
              {divergence_score.toFixed(1)}
            </div>
            <p className="text-[10px] text-text-tertiary mt-0.5">Divergence Score (0–10)</p>
          </div>
          <div className="flex-1 space-y-2">
            <div className="flex items-center gap-2">
              <span className={`px-2.5 py-1 rounded text-xs font-semibold uppercase tracking-wider ${phaseStyle.bg} ${phaseStyle.color}`}>
                {divergence_phase} Phase
              </span>
              <span className="text-sm font-medium text-text-secondary">{phase_label}</span>
            </div>
            <p className="text-sm text-text-secondary italic">{phase_interpretation}</p>
            <p className="text-[10px] text-text-tertiary font-mono italic">DVRG Mode: {dvrg_mode}</p>
          </div>
        </div>

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
                  { phase: 'Emerging', score: '4–6', label: 'Early Mispricing', multiplier: '1.0×' },
                  { phase: 'Strong', score: '7–8', label: 'Active Accumulation', multiplier: '1.2×' },
                  { phase: 'Extreme', score: '9–10', label: 'Deep Dislocation', multiplier: '1.2×' },
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
