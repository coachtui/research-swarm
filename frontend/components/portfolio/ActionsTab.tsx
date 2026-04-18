'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp, Check, X, Clock } from 'lucide-react'
import { usePortfolioActions, useMarkAction } from '@/lib/hooks/usePortfolio'
import { formatActionType, getActionColor, formatWeightDelta } from '@/lib/ownership-mapping'
import { ActionDisclaimer } from '@/components/portfolio/ActionDisclaimer'
import { Button } from '@/components/ui/button'
import type { EngineAction } from '@/types/api'

/**
 * ActionsTab — chronological action feed with trigger details.
 *
 * Each action shows: ticker, action_type badge, weight_delta, reason_text,
 * trigger_cycle, signal snapshot (expandable), portfolio impact.
 * Pending actions have Execute / Ignore buttons.
 */
export function ActionsTab({ portfolioId }: { portfolioId: string }) {
  const { data: feed, isLoading } = usePortfolioActions(portfolioId)
  const markAction = useMarkAction()

  if (isLoading) {
    return <div className="text-sm text-text-tertiary text-center py-8">Loading actions...</div>
  }

  if (!feed || feed.actions.length === 0) {
    return (
      <div className="text-center py-12 space-y-3">
        <div className="text-3xl">⚡</div>
        <p className="text-sm text-text-secondary">No engine actions yet.</p>
        <p className="text-xs text-text-tertiary">
          Actions will appear after the engine runs on your portfolio (monthly cycle or manual trigger).
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <ActionDisclaimer />

      {feed.pending_count > 0 && (
        <div className="flex items-center gap-2 text-xs">
          <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
          <span className="text-text-secondary font-medium">
            {feed.pending_count} pending action{feed.pending_count > 1 ? 's' : ''}
          </span>
        </div>
      )}

      <div className="space-y-2">
        {feed.actions.map((action) => (
          <ActionCard
            key={action.id}
            action={action}
            portfolioId={portfolioId}
            onExecute={() => markAction.mutate({ portfolioId, actionId: action.id, status: 'executed' })}
            onIgnore={() => markAction.mutate({ portfolioId, actionId: action.id, status: 'ignored' })}
            isUpdating={markAction.isPending}
          />
        ))}
      </div>
    </div>
  )
}

function ActionCard({
  action,
  portfolioId,
  onExecute,
  onIgnore,
  isUpdating,
}: {
  action: EngineAction
  portfolioId: string
  onExecute: () => void
  onIgnore: () => void
  isUpdating: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const isPending = action.status === 'pending'
  const actionColor = getActionColor(action.action_type)

  const statusBadge = {
    pending: { label: 'Pending', className: 'bg-success/10 text-success' },
    executed: { label: 'Executed', className: 'bg-primary/10 text-primary' },
    ignored: { label: 'Ignored', className: 'bg-surface text-text-tertiary' },
    expired: { label: 'Expired', className: 'bg-surface text-text-tertiary line-through' },
    cancelled: { label: 'Cancelled', className: 'bg-surface text-text-tertiary line-through' },
  }[action.status] || { label: action.status, className: 'bg-surface text-text-tertiary' }

  return (
    <div className={`rounded-lg border ${isPending ? 'border-success/30 bg-success/5' : 'border-border/60 bg-surface/30'} overflow-hidden`}>
      {/* ── Header ─────────────────────────────────────────────────── */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-surface-elevated/20 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className={`text-sm font-bold ${actionColor}`}>
            {formatActionType(action.action_type)}
          </span>
          <span className="text-sm font-bold font-mono text-text-primary">
            {action.ticker}
          </span>
          <span className={`text-xs font-mono font-semibold ${
            action.weight_delta >= 0 ? 'text-success' : 'text-error'
          }`}>
            {formatWeightDelta(action.weight_delta)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded ${statusBadge.className}`}>
            {statusBadge.label}
          </span>
          {expanded
            ? <ChevronUp className="h-3.5 w-3.5 text-text-tertiary" />
            : <ChevronDown className="h-3.5 w-3.5 text-text-tertiary" />}
        </div>
      </button>

      {/* ── Expanded Details ────────────────────────────────────────── */}
      {expanded && (
        <div className="border-t border-border/40 px-4 py-3 space-y-3">
          {/* Reason */}
          {action.reason_text && (
            <p className="text-xs text-text-secondary">{action.reason_text}</p>
          )}

          {/* Reason codes */}
          {action.reason_codes.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {action.reason_codes.map((code, i) => (
                <span key={i} className="text-[9px] font-mono bg-surface-elevated px-1.5 py-0.5 rounded text-text-tertiary">
                  {code}
                </span>
              ))}
            </div>
          )}

          {/* Signal snapshot */}
          {action.signal_snapshot && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.entries(action.signal_snapshot).map(([key, val]) => (
                val !== null && val !== undefined && (
                  <div key={key} className="text-[10px]">
                    <span className="text-text-tertiary">{key.replace(/_/g, ' ')}: </span>
                    <span className="font-mono font-semibold text-text-secondary">
                      {typeof val === 'number' ? val.toFixed(2) : String(val)}
                    </span>
                  </div>
                )
              ))}
            </div>
          )}

          {/* Trigger cycle + timestamp */}
          <div className="flex items-center gap-3 text-[10px] text-text-tertiary">
            {action.trigger_cycle && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {action.trigger_cycle}
              </span>
            )}
            <span>{new Date(action.created_at).toLocaleDateString()}</span>
          </div>

          {/* Action buttons (pending only) */}
          {isPending && (
            <div className="flex items-center gap-2 pt-1">
              <Button
                size="sm"
                onClick={(e) => { e.stopPropagation(); onExecute() }}
                disabled={isUpdating}
                className="h-7 text-xs"
              >
                <Check className="h-3 w-3 mr-1" /> Execute
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={(e) => { e.stopPropagation(); onIgnore() }}
                disabled={isUpdating}
                className="h-7 text-xs"
              >
                <X className="h-3 w-3 mr-1" /> Ignore
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
