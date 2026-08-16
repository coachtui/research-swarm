'use client'

// PM Memo Snapshot — Persistent pinned top-of-report block.
// Answers 7 key questions in under 15 seconds.
// Non-destructive: reads from existing computed data, no new calculations.

import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import type {
  DivergenceOverlay,
  FairValueCalibration,
  SignalBreakdown,
} from '@/types/api'

interface PMSnapshotCardProps {
  moatScore: number | null
  priceTargets?: {
    bull_target: number
    bull_probability: number
    base_target: number
    base_probability: number
    bear_target: number
    bear_probability: number
  } | null
  currentPrice?: number | null
  divergenceOverlay?: DivergenceOverlay | null
  fairValueCalibration?: FairValueCalibration | null
  initiationStatus?: string | null
  signalBreakdown?: SignalBreakdown | null
}

// ── Derivation helpers ────────────────────────────────────────────────────────

function deriveStructuralStrength(moatScore: number | null): {
  label: 'Strong' | 'Moderate' | 'Weak' | '—'
  color: string
} {
  // Missing data is an honest blank, not a negative signal
  if (moatScore === null) return { label: '—', color: 'text-text-tertiary' }
  if (moatScore >= 7) return { label: 'Strong', color: 'text-success' }
  if (moatScore >= 5) return { label: 'Moderate', color: 'text-text-secondary' }
  return { label: 'Weak', color: 'text-text-tertiary' }
}

function derivePositioningEdge(phase?: DivergenceOverlay['divergence_phase'] | null): {
  label: 'Absent' | 'Emerging' | 'Confirmed'
  color: string
} {
  if (!phase || phase === 'Weak') return { label: 'Absent', color: 'text-text-tertiary' }
  if (phase === 'Emerging') return { label: 'Emerging', color: 'text-text-secondary' }
  return { label: 'Confirmed', color: 'text-primary' }
}

function deriveMacroRegime(overlay?: DivergenceOverlay | null): {
  label: 'Expansion' | 'Neutral' | 'Contraction'
  color: string
} {
  const eps = overlay?.eps_revision_direction
  if (eps === 'Positive') return { label: 'Expansion', color: 'text-success' }
  if (eps === 'Negative') return { label: 'Contraction', color: 'text-warning' }
  return { label: 'Neutral', color: 'text-text-secondary' }
}

function deriveCapitalBias(initiationStatus?: string | null): {
  label: 'Preserve' | 'Monitor' | 'Accumulate' | 'Scale'
  color: string
} {
  const s = (initiationStatus ?? '').toUpperCase()
  if (s === 'WAIT') return { label: 'Preserve', color: 'text-text-tertiary' }
  if (s === 'WATCHLIST') return { label: 'Monitor', color: 'text-text-secondary' }
  if (s === 'INITIATE') return { label: 'Accumulate', color: 'text-primary' }
  return { label: 'Monitor', color: 'text-text-secondary' }
}

function deriveValuationAlignment(valuationGapPct: number | null): {
  label: 'Attractive' | 'Fair' | 'Extended'
  color: string
} {
  if (valuationGapPct === null) return { label: 'Fair', color: 'text-text-secondary' }
  if (valuationGapPct > 10) return { label: 'Attractive', color: 'text-success' }
  if (valuationGapPct < -10) return { label: 'Extended', color: 'text-warning' }
  return { label: 'Fair', color: 'text-text-secondary' }
}

function derivePositioningAlignment(flow?: DivergenceOverlay['institutional_flow'] | null): {
  label: 'Accumulating' | 'Neutral' | 'Distributing'
  color: string
} {
  if (flow === 'Strong') return { label: 'Accumulating', color: 'text-success' }
  if (flow === 'Weak') return { label: 'Distributing', color: 'text-warning' }
  return { label: 'Neutral', color: 'text-text-secondary' }
}

function buildSynthesis(
  structuralStrength: 'Strong' | 'Moderate' | 'Weak' | '—',
  valuationAlignment: 'Attractive' | 'Fair' | 'Extended',
  positioningEdge: 'Absent' | 'Emerging' | 'Confirmed',
): string {
  // Sentence 1 — structural + valuation state
  let s1 = ''
  if (structuralStrength === '—') {
    s1 = 'Structural quality unavailable — insufficient data.'
  } else if (structuralStrength === 'Strong' && valuationAlignment === 'Attractive') {
    s1 = 'Structural quality confirmed with meaningful discount to intrinsic estimate.'
  } else if (structuralStrength === 'Strong' && valuationAlignment === 'Fair') {
    s1 = 'Structural quality confirmed with pricing near intrinsic estimate.'
  } else if (structuralStrength === 'Strong' && valuationAlignment === 'Extended') {
    s1 = 'Structural quality confirmed. Current levels present limited upside relative to intrinsic estimate.'
  } else if (structuralStrength === 'Moderate' && valuationAlignment === 'Attractive') {
    s1 = 'Moderate structural foundation with meaningful upside to intrinsic estimate.'
  } else if (structuralStrength === 'Moderate') {
    s1 = 'Moderate structural foundation with pricing near intrinsic estimate.'
  } else {
    s1 = 'Structural quality is below threshold.'
  }

  // Sentence 2 — positioning edge context
  let s2 = ''
  if (positioningEdge === 'Confirmed') {
    s2 = 'Positioning signals support the setup.'
  } else if (positioningEdge === 'Emerging') {
    s2 = 'Positioning signals are early-stage — monitoring appropriate.'
  } else {
    if (valuationAlignment === 'Extended' || structuralStrength === 'Weak') {
      s2 = 'No confirmed positioning edge at present levels.'
    } else {
      s2 = 'No confirmed positioning edge. Setup warrants patience.'
    }
  }

  return `${s1} ${s2}`
}

// ── Snapshot metric tile ──────────────────────────────────────────────────────

function SnapshotTile({
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
      <p className={`text-sm font-bold mt-0.5 ${mono ? 'font-mono tabular-nums' : ''} ${valueColor ?? 'text-text-primary'}`}>
        {value}
      </p>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function PMSnapshotCard({
  moatScore,
  priceTargets,
  currentPrice,
  divergenceOverlay,
  fairValueCalibration,
  initiationStatus,
  signalBreakdown,
}: PMSnapshotCardProps) {
  const [showCapitalEnv, setShowCapitalEnv] = useState(false)

  // ── Derived values ──────────────────────────────────────────────────────────

  const structural = deriveStructuralStrength(moatScore)

  // Valuation gap: upside from current price to base scenario target
  const valuationGapPct =
    priceTargets && currentPrice && currentPrice > 0
      ? ((priceTargets.base_target - currentPrice) / currentPrice) * 100
      : null

  const valuationAlignment = deriveValuationAlignment(valuationGapPct)
  const positioningEdge = derivePositioningEdge(divergenceOverlay?.divergence_phase)
  const macroRegime = deriveMacroRegime(divergenceOverlay)
  const capitalBias = deriveCapitalBias(initiationStatus)

  // Probability-weighted EV (same logic as PriceTargetsCard — display only)
  let evPct: number | null = null
  let rrRatio: number | null = null
  if (priceTargets && currentPrice && currentPrice > 0) {
    const bearW = priceTargets.bear_probability ?? 0.25
    const baseW = priceTargets.base_probability ?? 0.50
    const bullW = priceTargets.bull_probability ?? 0.25
    const probWeightedEV =
      priceTargets.bear_target * bearW +
      priceTargets.base_target * baseW +
      priceTargets.bull_target * bullW
    const rawEvPct = ((probWeightedEV - currentPrice) / currentPrice) * 100
    const stabilityMod = signalBreakdown?.data_integrity_confidence_factor ?? 1.0
    evPct = rawEvPct * stabilityMod

    // Risk/Reward: bull upside / bear downside (absolute)
    const bullUpside = ((priceTargets.bull_target - currentPrice) / currentPrice) * 100
    const bearDownside = Math.abs(((priceTargets.bear_target - currentPrice) / currentPrice) * 100)
    rrRatio = bearDownside > 0 ? bullUpside / bearDownside : null
  }

  // Capital Environment proxies — liquidity from institutional flow, risk premium from divergence score
  const liquidityTrend =
    divergenceOverlay?.institutional_flow === 'Strong' ? 'Loose' :
    divergenceOverlay?.institutional_flow === 'Weak' ? 'Tight' : 'Neutral'

  const riskPremiumState =
    (divergenceOverlay?.divergence_score ?? 0) >= 7 ? 'Expanding' :
    (divergenceOverlay?.divergence_score ?? 0) >= 4 ? 'Stable' : 'Compressing'

  const breadth =
    (divergenceOverlay?.score_coverage ?? 0) >= 75 ? 'Broad' : 'Narrow'

  // Synthesis
  const synthesis = buildSynthesis(
    structural.label,
    valuationAlignment.label,
    positioningEdge.label,
  )

  const isContraction = macroRegime.label === 'Contraction'

  return (
    <div className="rounded-xl border-2 border-primary/20 bg-card overflow-hidden">

      {/* Header */}
      <div className="px-5 pt-4 pb-2 flex items-center justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-tertiary">
            PM Memo
          </p>
          <p className="text-sm font-semibold text-text-primary mt-0.5">Snapshot</p>
        </div>
        <span className="text-[9px] font-mono text-text-tertiary/50 border border-border rounded px-1.5 py-0.5 uppercase tracking-wider">
          2026 Standard
        </span>
      </div>

      {/* Contraction banner */}
      {isContraction && (
        <div className="mx-4 mb-2 rounded-md border border-warning/30 bg-warning/5 px-3 py-2">
          <p className="text-[11px] text-warning font-medium">
            Capital preservation environment. Elevated margin of safety required.
          </p>
        </div>
      )}

      {/* 7-metric grid — 4 columns, 2 rows */}
      <div className="px-4 pb-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
        <SnapshotTile
          label="Structural Strength"
          value={structural.label}
          valueColor={structural.color}
        />
        <SnapshotTile
          label="Valuation Gap vs Base"
          value={valuationGapPct !== null ? `${valuationGapPct > 0 ? '+' : ''}${valuationGapPct.toFixed(1)}%` : '—'}
          valueColor={
            valuationGapPct === null ? 'text-text-tertiary' :
            valuationGapPct > 10 ? 'text-success' :
            valuationGapPct < -10 ? 'text-warning' :
            'text-text-secondary'
          }
          mono
        />
        <SnapshotTile
          label="Positioning Edge"
          value={positioningEdge.label}
          valueColor={positioningEdge.color}
        />
        <SnapshotTile
          label="Macro Regime"
          value={macroRegime.label}
          valueColor={macroRegime.color}
        />
        <SnapshotTile
          label="Expected Value"
          value={evPct !== null ? `${evPct > 0 ? '+' : ''}${evPct.toFixed(1)}%` : '—'}
          valueColor={
            evPct === null ? 'text-text-tertiary' :
            evPct >= 10 ? 'text-success' :
            evPct >= 3 ? 'text-text-secondary' :
            'text-warning'
          }
          mono
        />
        <SnapshotTile
          label="Risk / Reward"
          value={rrRatio !== null ? `${rrRatio.toFixed(1)}:1` : '—'}
          valueColor={
            rrRatio === null ? 'text-text-tertiary' :
            rrRatio >= 2.0 ? 'text-success' :
            rrRatio >= 1.0 ? 'text-text-secondary' :
            'text-warning'
          }
          mono
        />
        <SnapshotTile
          label="Capital Bias"
          value={capitalBias.label}
          valueColor={capitalBias.color}
        />
        <SnapshotTile
          label="Regime"
          value={fairValueCalibration?.regime ?? '—'}
          valueColor="text-text-secondary"
        />
      </div>

      {/* Synthesis */}
      <div className="mx-4 mb-3 rounded-lg border border-border/40 bg-surface-elevated/30 px-4 py-3">
        <p className="text-xs text-text-secondary leading-relaxed italic">
          {synthesis}
        </p>
      </div>

      {/* Capital Alignment Matrix */}
      <div className="mx-4 mb-3 rounded-lg border border-border/40 bg-surface-elevated/20 overflow-hidden">
        <div className="px-3 py-2 border-b border-border/30">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-text-tertiary">
            Capital Alignment Matrix
          </p>
        </div>
        <div className="divide-y divide-border/30">
          {[
            {
              component: 'Structural',
              status: structural.label,
              interpretation: 'Business durability',
              statusColor: structural.color,
            },
            {
              component: 'Valuation',
              status: valuationAlignment.label,
              interpretation: 'Margin of safety',
              statusColor: valuationAlignment.color,
            },
            {
              component: 'Positioning',
              status: derivePositioningAlignment(divergenceOverlay?.institutional_flow).label,
              interpretation: 'Capital flow',
              statusColor: derivePositioningAlignment(divergenceOverlay?.institutional_flow).color,
            },
            {
              component: 'Macro',
              status: macroRegime.label === 'Expansion' ? 'Tailwind' : macroRegime.label === 'Contraction' ? 'Headwind' : 'Neutral',
              interpretation: 'Environment',
              statusColor: macroRegime.label === 'Expansion' ? 'text-success' : macroRegime.label === 'Contraction' ? 'text-warning' : 'text-text-secondary',
            },
          ].map(row => (
            <div key={row.component} className="grid grid-cols-3 px-3 py-2 text-xs">
              <span className="text-text-tertiary font-medium">{row.component}</span>
              <span className={`font-semibold ${row.statusColor}`}>{row.status}</span>
              <span className="text-text-tertiary/70 text-[11px]">{row.interpretation}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Capital Environment Context (expandable) */}
      <div className="mx-4 mb-4">
        <button
          onClick={() => setShowCapitalEnv(v => !v)}
          className="flex items-center gap-1.5 text-[11px] text-text-tertiary hover:text-text-secondary transition-colors"
        >
          <span>Capital Environment</span>
          {showCapitalEnv
            ? <ChevronUp className="h-3 w-3" />
            : <ChevronDown className="h-3 w-3" />}
        </button>

        {showCapitalEnv && (
          <div className="mt-2 rounded-lg border border-border/40 bg-surface-elevated/20 divide-y divide-border/30">
            {[
              { label: 'Macro Regime', value: macroRegime.label, color: macroRegime.color },
              { label: 'Liquidity Trend', value: liquidityTrend, color: liquidityTrend === 'Loose' ? 'text-success' : liquidityTrend === 'Tight' ? 'text-warning' : 'text-text-secondary' },
              { label: 'Risk Premium', value: riskPremiumState, color: riskPremiumState === 'Compressing' ? 'text-success' : riskPremiumState === 'Expanding' ? 'text-warning' : 'text-text-secondary' },
              { label: 'Breadth', value: breadth, color: breadth === 'Broad' ? 'text-success' : 'text-text-secondary' },
            ].map(row => (
              <div key={row.label} className="flex items-center justify-between px-3 py-2 text-xs">
                <span className="text-text-tertiary">{row.label}</span>
                <span className={`font-semibold ${row.color}`}>{row.value}</span>
              </div>
            ))}
            <div className="px-3 py-2">
              <p className="text-[9px] text-text-tertiary/50 italic">
                Liquidity and breadth are proxied from institutional flow and signal coverage — not direct macro data.
              </p>
            </div>
          </div>
        )}
      </div>

    </div>
  )
}
