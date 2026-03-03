'use client'

import { usePortfolioPosition } from '@/lib/hooks/usePortfolio'
import { mapToOwnershipStatus, mapToThesisState, mapToActionLabel, formatWeight } from '@/lib/ownership-mapping'
import type { PortfolioPosition, EngineAction } from '@/types/api'

/**
 * OwnershipStatusHeader — always-visible header for the report page.
 *
 * Replaces CapitalDeploymentSummary as the canonical Section 1.
 * Shows: Ownership Status, Thesis State, Action Now, Portfolio Context.
 *
 * Falls back gracefully when user has no portfolio (derives from initiation_decision).
 */
export function OwnershipStatusHeader({
  ticker,
  rating,
  initiationStatus,
  initiationScore,
  starterPct,
  maxPct,
  entryZone,
  pendingAction,
}: {
  ticker: string
  rating: string | null
  initiationStatus: string | null
  initiationScore: number | null
  starterPct: number | null
  maxPct: number | null
  entryZone: string | null
  pendingAction?: EngineAction | null
}) {
  const { portfolio, position } = usePortfolioPosition(ticker)

  const ownership = mapToOwnershipStatus(rating, initiationStatus, position)
  const thesis = mapToThesisState(position)
  const action = mapToActionLabel(pendingAction)

  return (
    <div className="rounded-xl border border-border/60 bg-surface/30 overflow-hidden">
      <div className="px-5 py-4 space-y-4">

        {/* ── Status Row ────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Ownership Status Badge */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
              Status
            </span>
            <span className={`text-sm font-bold ${ownership.color}`}>
              {ownership.status}
            </span>
          </div>

          <span className="text-border">|</span>

          {/* Thesis State */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
              Thesis
            </span>
            <span className={`text-sm font-bold ${thesis.color}`}>
              {thesis.state}
            </span>
          </div>

          <span className="text-border">|</span>

          {/* Action Now */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
              Action
            </span>
            <span className={`text-sm font-bold ${action.color}`}>
              {action.label}
            </span>
          </div>
        </div>

        {/* ── Metrics Row ───────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {/* Initiation Score */}
          <MetricTile
            label="Initiation Score"
            value={initiationScore !== null ? `${Math.round(initiationScore)}` : '—'}
            sublabel={initiationStatus || undefined}
          />

          {/* Starter % */}
          <MetricTile
            label="Starter %"
            value={starterPct !== null ? `${starterPct.toFixed(1)}%` : '—'}
            sublabel={maxPct !== null ? `Max ${maxPct.toFixed(1)}%` : undefined}
          />

          {/* Entry Zone */}
          <MetricTile
            label="Entry Zone"
            value={entryZone || '—'}
          />

          {/* Portfolio Context (only if position exists) */}
          {position ? (
            <MetricTile
              label="Portfolio Weight"
              value={formatWeight(position.current_weight)}
              sublabel={position.tier_state !== 'none' ? `Tier: ${position.tier_state.toUpperCase()}` : undefined}
            />
          ) : (
            <MetricTile
              label="Portfolio"
              value="Not Held"
              sublabel={portfolio ? 'Add via Holdings' : 'Create portfolio first'}
            />
          )}
        </div>

        {/* ── Drawdown context (if in portfolio) ────────────────────────── */}
        {position && position.last_drawdown !== null && position.last_drawdown < -0.05 && (
          <div className="flex items-center gap-2 pt-1">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
              Drawdown
            </span>
            <span className={`text-xs font-mono font-bold ${
              position.last_drawdown <= -0.30 ? 'text-error' :
              position.last_drawdown <= -0.20 ? 'text-warning' :
              'text-text-secondary'
            }`}>
              {(position.last_drawdown * 100).toFixed(1)}%
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

function MetricTile({
  label,
  value,
  sublabel,
}: {
  label: string
  value: string
  sublabel?: string
}) {
  return (
    <div className="rounded-lg border border-border/40 bg-surface-elevated/50 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">{label}</p>
      <p className="text-sm font-bold text-text-primary mt-0.5 font-mono tabular-nums">{value}</p>
      {sublabel && (
        <p className="text-[10px] text-text-tertiary mt-0.5">{sublabel}</p>
      )}
    </div>
  )
}
