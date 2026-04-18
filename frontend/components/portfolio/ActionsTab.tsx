'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp, AlertTriangle, TrendingDown, TrendingUp, Minus } from 'lucide-react'
import { usePortfolioActions, useMarkAction } from '@/lib/hooks/usePortfolio'
import { Button } from '@/components/ui/button'
import type { EngineAction, EngineActionType } from '@/types/api'

// ── Plain-language descriptions ──────────────────────────────────────────────

const ACTION_HEADLINE: Record<EngineActionType, (ticker: string) => string> = {
  INITIATE:      (t) => `Start a position in ${t}`,
  ADD_TIER_20:   (t) => `Add to ${t} — down 20%+ from its high`,
  ADD_TIER_30:   (t) => `Add to ${t} — down 30%+ from its high`,
  ADD_TIER_40:   (t) => `Add to ${t} — down 40%+ from its high`,
  ADD_TIER_50:   (t) => `Add to ${t} — down 50%+ from its high`,
  TRIM_EUPHORIA: (t) => `Consider trimming ${t} — trading well above its 200-day average`,
  TRIM_CAP:      (t) => `Consider trimming ${t} — at or near portfolio cap`,
  EXIT_THESIS:   (t) => `Consider selling ${t} — investment thesis shows signs of breakdown`,
  REPLACE:       (t) => `Consider replacing ${t} with a stronger compounder`,
  HOLD:          (t) => `Hold ${t} — no action needed`,
}

const ACTION_CONTEXT: Record<EngineActionType, string> = {
  INITIATE:      'The engine identified this as a quality compounder worth starting a position in.',
  ADD_TIER_20:   'A meaningful drawdown from the 52-week high is a planned accumulation opportunity.',
  ADD_TIER_30:   'A significant drawdown. This tier calls for a larger add if the thesis is intact.',
  ADD_TIER_40:   'A severe drawdown. High-conviction add for positions with an unbroken thesis.',
  ADD_TIER_50:   'A deep, capitulation-level drawdown. Maximum add tier.',
  TRIM_EUPHORIA: 'When a stock runs far ahead of its 200-day average it is often wise to reduce exposure and lock in gains.',
  TRIM_CAP:      'Position has grown to or above the 25% portfolio cap. Trim to rebalance.',
  EXIT_THESIS:   'The engine flagged a deterioration in the fundamental signals that originally justified owning this stock. This is a review prompt, not a command.',
  REPLACE:       'A better compounder candidate may exist. Consider swapping the capital.',
  HOLD:          'No change warranted at this time.',
}

const ACTION_SENTIMENT: Record<EngineActionType, 'buy' | 'sell' | 'neutral'> = {
  INITIATE:      'buy',
  ADD_TIER_20:   'buy',
  ADD_TIER_30:   'buy',
  ADD_TIER_40:   'buy',
  ADD_TIER_50:   'buy',
  TRIM_EUPHORIA: 'sell',
  TRIM_CAP:      'sell',
  EXIT_THESIS:   'sell',
  REPLACE:       'neutral',
  HOLD:          'neutral',
}

function cleanReason(raw: string | null | undefined): string | null {
  if (!raw) return null
  return raw
    .replace(/^THESIS BREAK:\s*/i, '')
    .replace(/;\s*/g, ' · ')
    .trim()
}

// ── Component ────────────────────────────────────────────────────────────────

export function ActionsTab({ portfolioId }: { portfolioId: string }) {
  const { data: feed, isLoading } = usePortfolioActions(portfolioId)
  const markAction = useMarkAction()

  if (isLoading) {
    return <div className="text-sm text-text-tertiary text-center py-8">Loading recommendations...</div>
  }

  const actions = feed?.actions ?? []
  const pending = actions.filter(a => a.status === 'pending')
  const past    = actions.filter(a => a.status !== 'pending')

  if (actions.length === 0) {
    return (
      <div className="text-center py-12 space-y-3">
        <p className="text-sm text-text-secondary font-medium">No recommendations yet</p>
        <p className="text-xs text-text-tertiary max-w-sm mx-auto">
          Run the engine from the Portfolio tab to generate buy, add, trim, and sell recommendations based on your current holdings and latest analyses.
        </p>
      </div>
    )
  }

  const mark = (actionId: string, status: 'executed' | 'ignored') =>
    markAction.mutate({ portfolioId, actionId, status })

  return (
    <div className="space-y-5">

      {/* ── Disclaimer ─────────────────────────────────────────────── */}
      <div className="flex items-start gap-2.5 rounded-lg bg-surface-elevated/60 border border-border/40 px-3.5 py-2.5">
        <AlertTriangle className="h-3.5 w-3.5 text-text-tertiary mt-0.5 flex-shrink-0" />
        <p className="text-[11px] text-text-tertiary leading-relaxed">
          These are model-generated suggestions based on your holdings and latest research. Review before acting — all decisions are yours.
        </p>
      </div>

      {/* ── Pending ────────────────────────────────────────────────── */}
      {pending.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
            Pending · {pending.length}
          </h3>
          {pending.map(action => (
            <ActionCard
              key={action.id}
              action={action}
              onDone={() => mark(action.id, 'executed')}
              onDismiss={() => mark(action.id, 'ignored')}
              isUpdating={markAction.isPending}
            />
          ))}
        </section>
      )}

      {/* ── Past ───────────────────────────────────────────────────── */}
      {past.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
            History · {past.length}
          </h3>
          {past.map(action => (
            <ActionCard key={action.id} action={action} muted />
          ))}
        </section>
      )}
    </div>
  )
}

// ── Action Card ──────────────────────────────────────────────────────────────

function ActionCard({
  action,
  onDone,
  onDismiss,
  isUpdating,
  muted = false,
}: {
  action: EngineAction
  onDone?: () => void
  onDismiss?: () => void
  isUpdating?: boolean
  muted?: boolean
}) {
  const [expanded, setExpanded] = useState(false)

  const type     = action.action_type as EngineActionType
  const headline = (ACTION_HEADLINE[type] ?? (() => action.action_type))(action.ticker)
  const context  = ACTION_CONTEXT[type]
  const sentiment = ACTION_SENTIMENT[type] ?? 'neutral'
  const reason   = cleanReason(action.reason_text)

  const sentimentColor = muted
    ? 'text-text-tertiary'
    : sentiment === 'buy'  ? 'text-success'
    : sentiment === 'sell' ? 'text-error'
    : 'text-text-secondary'

  const SentimentIcon = sentiment === 'buy'  ? TrendingUp
                      : sentiment === 'sell' ? TrendingDown
                      : Minus

  const statusLabel: Record<string, string> = {
    executed: 'Done',
    ignored: 'Dismissed',
    expired: 'Expired',
    cancelled: 'Cancelled',
  }

  return (
    <div className={`rounded-lg border overflow-hidden ${
      muted
        ? 'border-border/40 bg-surface/20'
        : sentiment === 'sell'
          ? 'border-error/20 bg-error/5'
          : 'border-success/20 bg-success/5'
    }`}>

      {/* ── Main row ───────────────────────────────────────────────── */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-start justify-between px-4 py-3 text-left hover:bg-surface-elevated/20 transition-colors gap-3"
      >
        <div className="flex items-start gap-3 min-w-0">
          <SentimentIcon className={`h-4 w-4 mt-0.5 flex-shrink-0 ${sentimentColor}`} />
          <div className="min-w-0">
            <p className={`text-sm font-semibold leading-snug ${muted ? 'text-text-tertiary' : 'text-text-primary'}`}>
              {headline}
            </p>
            {reason && !expanded && (
              <p className="text-[11px] text-text-tertiary mt-0.5 truncate">{reason}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 mt-0.5">
          {muted && action.status in statusLabel && (
            <span className="text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-surface text-text-tertiary">
              {statusLabel[action.status]}
            </span>
          )}
          {expanded
            ? <ChevronUp className="h-3.5 w-3.5 text-text-tertiary" />
            : <ChevronDown className="h-3.5 w-3.5 text-text-tertiary" />}
        </div>
      </button>

      {/* ── Expanded detail ────────────────────────────────────────── */}
      {expanded && (
        <div className="border-t border-border/40 px-4 py-3 space-y-3">

          {/* What this means */}
          <p className="text-xs text-text-secondary leading-relaxed">{context}</p>

          {/* Engine reason */}
          {reason && (
            <div className="rounded-md bg-surface-elevated/50 border border-border/30 px-3 py-2">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary mb-1">Why</p>
              <p className="text-xs text-text-secondary">{reason}</p>
            </div>
          )}

          {/* Signal snapshot */}
          {action.signal_snapshot && Object.keys(action.signal_snapshot).length > 0 && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary mb-1.5">Signal data</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1">
                {Object.entries(action.signal_snapshot).map(([key, val]) =>
                  val !== null && val !== undefined && (
                    <div key={key} className="flex items-center gap-1.5 text-[10px]">
                      <span className="text-text-tertiary">{key.replace(/_/g, ' ')}:</span>
                      <span className="font-mono font-semibold text-text-secondary">
                        {typeof val === 'number' ? val.toFixed(2) : String(val)}
                      </span>
                    </div>
                  )
                )}
              </div>
            </div>
          )}

          {/* Date */}
          <p className="text-[10px] text-text-tertiary">
            Generated {new Date(action.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
            {action.trigger_cycle ? ` · ${action.trigger_cycle.replace(/_/g, ' ')}` : ''}
          </p>

          {/* Actions */}
          {action.status === 'pending' && onDone && onDismiss && (
            <div className="flex items-center gap-2 pt-1 border-t border-border/30">
              <Button
                size="sm"
                onClick={(e) => { e.stopPropagation(); onDone() }}
                disabled={isUpdating}
                className="h-7 text-xs"
              >
                I&apos;ve done this
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={(e) => { e.stopPropagation(); onDismiss() }}
                disabled={isUpdating}
                className="h-7 text-xs text-text-tertiary"
              >
                Dismiss
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
