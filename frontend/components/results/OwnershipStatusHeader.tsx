'use client'

import { usePortfolioPosition } from '@/lib/hooks/usePortfolio'
import { mapToThesisState, formatWeight } from '@/lib/ownership-mapping'
import type { EngineAction, EngineActionType } from '@/types/api'

const ACTION_LABELS: Record<EngineActionType, string> = {
  INITIATE:      'Initiate',
  ADD_TIER_20:   'Add +2% (Tier 1)',
  ADD_TIER_30:   'Add +4% (Tier 2)',
  ADD_TIER_40:   'Add +6% (Tier 3)',
  ADD_TIER_50:   'Add +8% (Tier 4)',
  TRIM_EUPHORIA: 'Trim — Euphoria',
  TRIM_CAP:      'Trim — Cap',
  EXIT_THESIS:   'Exit — Thesis Break',
  REPLACE:       'Replace',
  HOLD:          'Hold',
}

const ACTION_COLORS: Record<EngineActionType, string> = {
  INITIATE:      'text-success',
  ADD_TIER_20:   'text-success',
  ADD_TIER_30:   'text-success',
  ADD_TIER_40:   'text-success',
  ADD_TIER_50:   'text-success',
  TRIM_EUPHORIA: 'text-warning',
  TRIM_CAP:      'text-warning',
  EXIT_THESIS:   'text-error',
  REPLACE:       'text-primary',
  HOLD:          'text-text-tertiary',
}

/**
 * OwnershipStatusHeader — engine-first ownership panel.
 *
 * Shows ONLY engine-derived state — no initiation score, no entry zone,
 * no intrinsic price thresholds.
 *
 * Top row:  Eligibility | Thesis | Action Now
 * Tiles:    Weight | Drawdown% | Tier | Add Capacity
 *
 * Falls back gracefully when user has no portfolio position.
 */
export function OwnershipStatusHeader({
  ticker,
  initiationStatus,
  pendingAction,
}: {
  ticker: string
  initiationStatus: string | null
  pendingAction?: EngineAction | null
}) {
  const { portfolio, position } = usePortfolioPosition(ticker)

  // ── Eligibility ───────────────────────────────────────────────────────────
  const eligibility = position
    ? {
        pending:      { label: 'Awaiting Engine', color: 'text-text-tertiary' },
        eligible:     { label: 'Eligible',    color: 'text-success' },
        disqualified: { label: 'Disqualified', color: 'text-error' },
      }[position.eligibility_state] ?? { label: position.eligibility_state, color: 'text-text-secondary' }
    : initiationStatus === 'INITIATE'  ? { label: 'Eligible',     color: 'text-success' }
    : initiationStatus === 'WATCHLIST' ? { label: 'Watch',         color: 'text-warning' }
    : initiationStatus === 'WAIT'      ? { label: 'Not Eligible',  color: 'text-error' }
    : { label: '—', color: 'text-text-tertiary' }

  // ── Thesis ────────────────────────────────────────────────────────────────
  const thesis = mapToThesisState(position)

  // ── Action Now ────────────────────────────────────────────────────────────
  const actionType = pendingAction?.action_type as EngineActionType | undefined
  const actionLabel = actionType ? (ACTION_LABELS[actionType] || actionType) : '—'
  const actionColor = actionType ? (ACTION_COLORS[actionType] || 'text-text-secondary') : 'text-text-tertiary'

  // ── Drawdown / Tier ───────────────────────────────────────────────────────
  const drawdownPct = position?.last_drawdown ?? null
  const drawdownColor =
    drawdownPct === null      ? 'text-text-secondary' :
    drawdownPct <= -0.30      ? 'text-error' :
    drawdownPct <= -0.20      ? 'text-warning' :
    'text-text-secondary'

  const tierMap: Record<string, string> = {
    none:  'None',
    t1_20: 'T1 −20%',
    t2_30: 'T2 −30%',
    t3_40: 'T3 −40%',
    t4_50: 'T4 −50%',
  }
  const tierLabel = position ? (tierMap[position.tier_state] ?? position.tier_state) : '—'

  // ── Add Capacity (25% hard cap) ───────────────────────────────────────────
  const addCapacity = position ? Math.max(0, 0.25 - position.current_weight) : null

  return (
    <div className="rounded-xl border border-border/60 bg-surface/30 overflow-hidden">
      <div className="px-5 py-4 space-y-4">

        {/* ── Engine State Row ──────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <StatusPill label="Eligibility" value={eligibility.label} color={eligibility.color} />
          <span className="text-border hidden sm:block">|</span>
          <StatusPill label="Thesis" value={thesis.state} color={thesis.color} />
          <span className="text-border hidden sm:block">|</span>
          <StatusPill label="Action Now" value={actionLabel} color={actionColor} />
        </div>

        {/* ── Portfolio Context Tiles ───────────────────────────────────── */}
        {position ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <ContextTile
              label="Current Weight"
              value={formatWeight(position.current_weight)}
              sublabel={
                position.ownership_status === 'core_compounder' ? 'Core Compounder' :
                position.ownership_status === 'disqualified'    ? 'Disqualified' :
                'Watch'
              }
            />
            <ContextTile
              label="Drawdown"
              value={drawdownPct !== null ? `${(drawdownPct * 100).toFixed(1)}%` : '—'}
              valueColor={drawdownColor}
            />
            <ContextTile
              label="Tier State"
              value={tierLabel}
            />
            <ContextTile
              label="Add Capacity"
              value={addCapacity !== null ? formatWeight(addCapacity) : '—'}
              sublabel="to 25% cap"
            />
          </div>
        ) : (
          <div className="rounded-lg border border-border/40 bg-surface-elevated/50 px-3 py-2.5 text-[11px] text-text-tertiary">
            {portfolio
              ? 'Not in portfolio — add via Holdings tab to track state.'
              : 'Create a portfolio to track ownership state, tier triggers, and drawdown.'}
          </div>
        )}

        {/* ── Pending action reason codes ───────────────────────────────── */}
        {pendingAction?.reason_codes && pendingAction.reason_codes.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {pendingAction.reason_codes.map((code, i) => (
              <span
                key={i}
                className="text-[9px] font-mono bg-surface-elevated px-1.5 py-0.5 rounded text-text-tertiary"
              >
                {code}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatusPill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">{label}</span>
      <span className={`text-sm font-bold ${color}`}>{value}</span>
    </div>
  )
}

function ContextTile({
  label,
  value,
  sublabel,
  valueColor,
}: {
  label: string
  value: string
  sublabel?: string
  valueColor?: string
}) {
  return (
    <div className="rounded-lg border border-border/40 bg-surface-elevated/50 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">{label}</p>
      <p className={`text-sm font-bold mt-0.5 font-mono tabular-nums ${valueColor || 'text-text-primary'}`}>
        {value}
      </p>
      {sublabel && <p className="text-[10px] text-text-tertiary mt-0.5">{sublabel}</p>}
    </div>
  )
}
