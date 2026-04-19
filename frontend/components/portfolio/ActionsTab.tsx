'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp, AlertTriangle, TrendingDown, TrendingUp, Minus, RotateCcw } from 'lucide-react'
import { usePortfolioActions, useMarkAction, useResetThesis } from '@/lib/hooks/usePortfolio'
import { Button } from '@/components/ui/button'
import type { EngineAction, EngineActionType } from '@/types/api'

// ── Plain-language descriptions ──────────────────────────────────────────────

const ACTION_HEADLINE: Record<EngineActionType, (ticker: string) => string> = {
  INITIATE:      (t) => `Start a position in ${t}`,
  ADD_TIER_20:   (t) => `Add to ${t} — report supports building the position`,
  ADD_TIER_30:   (t) => `Add to ${t} — down 30%+ from its high`,
  ADD_TIER_40:   (t) => `Add to ${t} — down 40%+ from its high`,
  ADD_TIER_50:   (t) => `Add to ${t} — down 50%+ from its high`,
  TRIM_EUPHORIA: (t) => `Consider trimming ${t} — trading well above its 200-day average`,
  TRIM_CAP:      (t) => `Trim ${t} — above policy cap`,
  TRIM_THESIS:   (t) => `Reduce ${t} — thesis integrity check flagged`,
  EXIT_THESIS:   (t) => `Consider selling ${t} — thesis shows breakdown`,
  REPLACE:       (t) => `Consider replacing ${t} with a stronger compounder`,
  HOLD:          (t) => `${t} — monitoring, no action yet`,
}

const ACTION_CONTEXT: Record<EngineActionType, string> = {
  INITIATE:      'The latest report rates this stock as an INITIATE — the risk/reward and quality score support opening a starter position.',
  ADD_TIER_20:   'The report\'s tranche plan recommends building the position further. The analysis shows conditions supporting the next stage add.',
  ADD_TIER_30:   'A significant drawdown. This tier calls for a larger add if the thesis is intact.',
  ADD_TIER_40:   'A severe drawdown. High-conviction add for positions with an unbroken thesis.',
  ADD_TIER_50:   'A deep, capitulation-level drawdown. Maximum add tier.',
  TRIM_EUPHORIA: 'When a stock runs far ahead of its 200-day average it is often wise to reduce exposure and lock in gains.',
  TRIM_CAP:      'Position has grown beyond its policy cap. Trimming keeps the portfolio balanced and frees capital for other opportunities.',
  TRIM_THESIS:   'One or more integrity signals have breached their thresholds. Reducing position by 50% is a defensive response — not a full exit. Re-run a fresh report to reassess.',
  EXIT_THESIS:   'The analysis flagged a deterioration in the fundamental signals that originally justified owning this stock. This is a review prompt, not a command.',
  REPLACE:       'A better compounder candidate may exist. Consider swapping the capital.',
  HOLD:          'The position is being monitored. Either waiting for entry conditions to improve, or at the correct stage target with no action needed.',
}

const ACTION_SENTIMENT: Record<EngineActionType, 'buy' | 'sell' | 'neutral'> = {
  INITIATE:      'buy',
  ADD_TIER_20:   'buy',
  ADD_TIER_30:   'buy',
  ADD_TIER_40:   'buy',
  ADD_TIER_50:   'buy',
  TRIM_EUPHORIA: 'sell',
  TRIM_CAP:      'sell',
  TRIM_THESIS:   'sell',
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
  const resetThesis = useResetThesis()

  if (isLoading) {
    return <div className="text-sm text-text-tertiary text-center py-8">Loading recommendations...</div>
  }

  const actions = feed?.actions ?? []
  const pending = actions.filter(a => a.status === 'pending')
  const past    = actions.filter(a => a.status !== 'pending')

  // Detect when the engine has generated trims/exits on everything — likely stale signal data
  const allExits = pending.length > 0 && pending.every(
    a => a.action_type === 'EXIT_THESIS' || a.action_type === 'TRIM_THESIS'
  )

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

      {/* ── Stale-signal warning ────────────────────────────────────── */}
      {allExits && (
        <div className="rounded-lg border border-warning/30 bg-warning/5 px-4 py-3 space-y-2">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="h-3.5 w-3.5 text-warning mt-0.5 flex-shrink-0" />
            <div className="space-y-1">
              <p className="text-xs font-semibold text-text-primary">Everything showing as Exit</p>
              <p className="text-[11px] text-text-secondary leading-relaxed">
                This usually means the engine ran on analyses older than 90 days, or positions were marked broken by a previous run.
                Run fresh reports on your holdings, then re-run the engine. Or reset thesis state now to clear the flags and start clean.
              </p>
            </div>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            disabled={resetThesis.isPending}
            onClick={() => resetThesis.mutate(portfolioId)}
          >
            <RotateCcw className={`h-3 w-3 mr-1.5 ${resetThesis.isPending ? 'animate-spin' : ''}`} />
            {resetThesis.isPending ? 'Resetting…' : 'Reset thesis state'}
          </Button>
        </div>
      )}

      {/* ── Disclaimer ─────────────────────────────────────────────── */}
      {!allExits && (
        <div className="flex items-start gap-2.5 rounded-lg bg-surface-elevated/60 border border-border/40 px-3.5 py-2.5">
          <AlertTriangle className="h-3.5 w-3.5 text-text-tertiary mt-0.5 flex-shrink-0" />
          <p className="text-[11px] text-text-tertiary leading-relaxed">
            These are model-generated suggestions based on your holdings and latest research. Review before acting — all decisions are yours.
          </p>
        </div>
      )}

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

// ── Snapshot Panel ───────────────────────────────────────────────────────────

function SnapshotPanel({ snap }: { snap: Record<string, unknown> }) {
  const s = snap as {
    stage?: number
    initiation_status?: string
    initiation_rationale?: string
    max_position_pct?: number
    recommended_pct?: number
    current_position_pct?: number
    current_allocation_pct?: number
    fair_value?: number
    report_verdict?: string
    dvrg_mode?: string
    divergence_score?: number
    active_thesis_breaks?: { label: string; current: string; threshold: string }[]
    next_add_trigger_conditions?: { label: string; detail: string; met: boolean }[]
    next_add_note?: string
  }

  const rows: { label: string; value: string }[] = []

  if (s.stage != null) rows.push({ label: 'Tranche stage', value: `Stage ${s.stage} of 3` })
  if (s.initiation_status) rows.push({ label: 'Report status', value: s.initiation_status })
  if (s.report_verdict) rows.push({ label: 'Verdict', value: s.report_verdict.toUpperCase() })
  if (s.current_allocation_pct != null) rows.push({ label: 'Current allocation', value: `${s.current_allocation_pct.toFixed(1)}%` })
  if (s.current_position_pct != null) rows.push({ label: 'Stage target', value: `${s.current_position_pct.toFixed(1)}%` })
  if (s.max_position_pct != null) rows.push({ label: 'Policy cap', value: `${s.max_position_pct.toFixed(0)}%` })
  if (s.recommended_pct != null) rows.push({ label: 'Recommended weight', value: `${s.recommended_pct.toFixed(1)}%` })
  if (s.fair_value != null) rows.push({ label: 'Fair value', value: `$${s.fair_value.toFixed(2)}` })
  if (s.divergence_score != null) rows.push({ label: 'Divergence score', value: `${s.divergence_score.toFixed(1)}/10` })

  return (
    <div className="space-y-2">
      {rows.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary mb-1.5">Report data</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1">
            {rows.map(r => (
              <div key={r.label} className="flex items-center gap-1.5 text-[10px]">
                <span className="text-text-tertiary">{r.label}:</span>
                <span className="font-mono font-semibold text-text-secondary">{r.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {s.dvrg_mode && (
        <div className="rounded-md bg-surface-elevated/50 border border-border/30 px-3 py-1.5">
          <p className="text-[10px] text-text-tertiary">
            <span className="font-semibold text-text-secondary">DVRG: </span>{s.dvrg_mode}
          </p>
        </div>
      )}

      {s.active_thesis_breaks && s.active_thesis_breaks.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary mb-1">Active integrity flags</p>
          <div className="space-y-0.5">
            {s.active_thesis_breaks.map(b => (
              <div key={b.label} className="text-[10px] flex items-start gap-2">
                <span className="text-error mt-0.5">●</span>
                <span className="text-text-secondary">{b.label}: <span className="font-mono">{b.current}</span> vs threshold <span className="font-mono">{b.threshold}</span></span>
              </div>
            ))}
          </div>
        </div>
      )}

      {s.next_add_trigger_conditions && s.next_add_trigger_conditions.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary mb-1">
            Next add triggers
            {s.next_add_note ? <span className="normal-case font-normal ml-1">({s.next_add_note.replace(' — monitor thesis break conditions', '')})</span> : ''}
          </p>
          <div className="space-y-0.5">
            {s.next_add_trigger_conditions.map(c => (
              <div key={c.label} className="text-[10px] flex items-start gap-2">
                <span className={c.met ? 'text-success mt-0.5' : 'text-text-tertiary mt-0.5'}>
                  {c.met ? '✓' : '○'}
                </span>
                <span className={c.met ? 'text-success' : 'text-text-secondary'}>
                  {c.label}
                  {c.detail && <span className="text-text-tertiary ml-1">· {c.detail}</span>}
                </span>
              </div>
            ))}
          </div>
        </div>
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

          {/* Signal snapshot — structured PM data */}
          {action.signal_snapshot && <SnapshotPanel snap={action.signal_snapshot} />}

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
