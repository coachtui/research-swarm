'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp, Check, X } from 'lucide-react'
import { useExecuteAction, useCancelAction } from '@/lib/hooks/usePortfolio'
import { formatActionType, getActionColor } from '@/lib/ownership-mapping'
import { Button } from '@/components/ui/button'
import type { EngineAction } from '@/types/api'

interface ActionPlanCardProps {
  ticker: string
  actions: EngineAction[]
}

/**
 * ActionPlanCard — expandable per-position card showing a conditional action ladder.
 *
 * Separates parent actions (no parent_action_id) from children, displays them as a
 * "ladder" with parent steps and indented children. Shows trigger conditions, price
 * levels, status badges, and action buttons.
 */
export function ActionPlanCard({
  ticker,
  actions,
}: ActionPlanCardProps) {
  const executeAction = useExecuteAction()
  const cancelAction = useCancelAction()
  const [expanded, setExpanded] = useState(false)

  // Separate parent actions from children
  const parents = actions.filter(a => a.parent_action_id === null)
  const children = new Map<string, EngineAction[]>()
  actions.forEach(a => {
    if (a.parent_action_id !== null) {
      const parentId = a.parent_action_id
      if (!children.has(parentId)) {
        children.set(parentId, [])
      }
      children.get(parentId)!.push(a)
    }
  })

  const pendingCount = actions.filter(a => a.status === 'pending').length
  const totalCount = actions.length

  return (
    <div className="rounded-lg border border-border/60 bg-surface/30 overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-surface-elevated/20 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-surface-elevated text-xs font-semibold text-text-secondary">
            {ticker}
          </span>
          <span className="text-xs text-text-tertiary">
            {totalCount} action{totalCount !== 1 ? 's' : ''}
          </span>
          {pendingCount > 0 && (
            <span className="text-xs font-semibold text-success">
              {pendingCount} pending
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {expanded
            ? <ChevronUp className="h-3.5 w-3.5 text-text-tertiary" />
            : <ChevronDown className="h-3.5 w-3.5 text-text-tertiary" />}
        </div>
      </button>

      {/* ── Expanded Ladder ────────────────────────────────────────────────── */}
      {expanded && (
        <div className="border-t border-border/40 px-4 py-3 space-y-4">
          {parents.length === 0 ? (
            <p className="text-xs text-text-tertiary italic">No parent actions</p>
          ) : (
            parents.map((parent, parentIdx) => (
              <div key={parent.id} className="space-y-3">
                {/* Parent action step */}
                <ActionStep
                  action={parent}
                  isParent={true}
                  onExecute={(id) => executeAction.mutate(id)}
                  onCancel={(id) => cancelAction.mutate(id)}
                  isUpdating={executeAction.isPending || cancelAction.isPending}
                />

                {/* Child actions (indented) */}
                {children.has(parent.id) && children.get(parent.id)!.length > 0 && (
                  <div className="pl-4 space-y-2 border-l border-border/40">
                    {children.get(parent.id)!.map((child) => (
                      <ActionStep
                        key={child.id}
                        action={child}
                        isParent={false}
                        onExecute={(id) => executeAction.mutate(id)}
                        onCancel={(id) => cancelAction.mutate(id)}
                        isUpdating={executeAction.isPending || cancelAction.isPending}
                      />
                    ))}
                  </div>
                )}

                {/* Visual separator between parent groups */}
                {parentIdx < parents.length - 1 && (
                  <div className="h-px bg-border/30" />
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

/**
 * ActionStep — renders a single action with status, type, trigger condition, and controls.
 */
function ActionStep({
  action,
  isParent,
  onExecute,
  onCancel,
  isUpdating,
}: {
  action: EngineAction
  isParent: boolean
  onExecute: (actionId: string) => void
  onCancel: (actionId: string) => void
  isUpdating: boolean
}) {
  const actionColor = getActionColor(action.action_type)
  const isPending = action.status === 'pending'

  // Status badge styling
  const statusStyles = {
    pending: { label: 'Pending', className: 'bg-success/10 text-success' },
    executed: { label: 'Executed', className: 'bg-primary/10 text-primary' },
    ignored: { label: 'Ignored', className: 'bg-surface text-text-tertiary' },
    cancelled: { label: 'Cancelled', className: 'bg-surface text-text-tertiary line-through' },
    expired: { label: 'Expired', className: 'bg-surface text-text-tertiary line-through' },
  }[action.status] || { label: action.status, className: 'bg-surface text-text-tertiary' }

  // Format trigger condition
  const triggerText = formatTriggerCondition(action)

  return (
    <div className="space-y-2">
      {/* Top row: status badge + type + trigger condition */}
      <div className="flex items-start gap-2 flex-wrap">
        <span className={`text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded flex-shrink-0 ${statusStyles.className}`}>
          {statusStyles.label}
        </span>
        <span className={`text-sm font-bold leading-tight ${actionColor}`}>
          {formatActionType(action.action_type)}
        </span>
        {triggerText && (
          <span className="text-xs text-text-tertiary">
            {triggerText}
          </span>
        )}
      </div>

      {/* Price level (if applicable) */}
      {action.trigger_price !== null && (
        <div className="text-xs text-text-secondary">
          Price level: <span className="font-mono font-semibold">${action.trigger_price.toFixed(2)}</span>
        </div>
      )}

      {/* Reason text (truncated) */}
      {action.reason_text && (
        <p className="text-xs text-text-secondary line-clamp-2">
          {action.reason_text}
        </p>
      )}

      {/* Action buttons */}
      {isPending && (
        <div className="flex items-center gap-2 pt-1">
          {/* Execute button: only if trigger_condition is 'immediate' */}
          {action.trigger_condition === 'immediate' && (
            <Button
              size="sm"
              onClick={(e) => {
                e.stopPropagation()
                onExecute(action.id)
              }}
              disabled={isUpdating}
              className="h-7 text-xs"
            >
              <Check className="h-3 w-3 mr-1" /> Execute
            </Button>
          )}

          {/* Cancel button: always available for pending */}
          <Button
            size="sm"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation()
              onCancel(action.id)
            }}
            disabled={isUpdating}
            className="h-7 text-xs"
          >
            <X className="h-3 w-3 mr-1" /> Cancel
          </Button>
        </div>
      )}
    </div>
  )
}

/**
 * formatTriggerCondition — convert trigger condition to human-readable text.
 */
function formatTriggerCondition(action: EngineAction): string {
  if (!action.trigger_condition) return ''

  switch (action.trigger_condition) {
    case 'price_above':
      return action.trigger_price ? `if price > $${action.trigger_price.toFixed(2)}` : 'if price above'
    case 'price_below':
      return action.trigger_price ? `if price < $${action.trigger_price.toFixed(2)}` : 'if price below'
    case 'catalyst_confirmed':
      return 'catalyst confirmed'
    case 'immediate':
      return 'immediate'
    default:
      return ''
  }
}
