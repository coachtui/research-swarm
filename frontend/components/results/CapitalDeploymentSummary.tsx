'use client'

/**
 * CapitalDeploymentSummary — Section 1 (Capital Allocation Memo)
 *
 * Answers the only 4 questions that matter at first glance:
 *   1. Do I initiate?          → Status badge (INITIATE / WATCHLIST / WAIT)
 *   2. At what price?          → Entry Zone
 *   3. At what size?           → Starter % + Max %
 *   4. What breaks the thesis? → Thesis Break Trigger
 *
 * Zero model exposition. Large numeric emphasis. No research prose.
 */

import type { ConvictionPosition, RecommendedStrategy, TriggerItem } from '@/types/api'

// ── Props ─────────────────────────────────────────────────────────────────────

interface CapitalDeploymentSummaryProps {
  rating: string | null
  conviction: ConvictionPosition
  strategy?: RecommendedStrategy | null
  upgradeTriggers?: TriggerItem[] | null
  downgradeTriggers?: TriggerItem[] | null
  ticker: string
}

// ── Status derivation ─────────────────────────────────────────────────────────

type DeployStatus = 'INITIATE' | 'WATCHLIST' | 'WAIT'

function deriveStatus(rating: string | null): DeployStatus {
  const r = (rating ?? '').toUpperCase()
  if (r === 'STRONG BUY' || r === 'BUY') return 'INITIATE'
  if (r === 'SELL' || r === 'STRONG SELL') return 'WAIT'
  return 'WATCHLIST'
}

const STATUS_STYLES: Record<DeployStatus, {
  dot: string
  text: string
  bg: string
  border: string
}> = {
  INITIATE:  { dot: 'bg-success',  text: 'text-success',  bg: 'bg-success/8',  border: 'border-success/35' },
  WATCHLIST: { dot: 'bg-warning',  text: 'text-warning',  bg: 'bg-warning/8',  border: 'border-warning/35' },
  WAIT:      { dot: 'bg-error',    text: 'text-error',    bg: 'bg-error/8',    border: 'border-error/35'   },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatZone(low?: number, high?: number): string | null {
  if (!low && !high) return null
  const fmt = (n: number) =>
    `$${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`
  if (low && high) return `${fmt(low)} – ${fmt(high)}`
  return `~${fmt((low ?? high)!)}`
}

function firstTriggerText(t?: TriggerItem | null): string | null {
  if (!t) return null
  const parts = [t.metric, t.threshold].filter(Boolean)
  return parts.length ? parts.join(' — ') : null
}

function scoreDisplay(s: string): string {
  // "8.2/10" → "8.2" | "7.8" → "7.8" | "High" → "High"
  const slash = s.indexOf('/')
  return slash > 0 ? s.slice(0, slash).trim() : s.trim()
}

// ── Component ─────────────────────────────────────────────────────────────────

export function CapitalDeploymentSummary({
  rating,
  conviction,
  strategy,
  upgradeTriggers,
  downgradeTriggers,
  ticker,
}: CapitalDeploymentSummaryProps) {
  const status = deriveStatus(rating)
  const styles = STATUS_STYLES[status]

  const entryZone = strategy?.entry?.ideal_zone
    ? formatZone(strategy.entry.ideal_zone.low, strategy.entry.ideal_zone.high)
    : null

  const nextAdd     = firstTriggerText(upgradeTriggers?.[0])
  const thesisBreak = firstTriggerText(downgradeTriggers?.[0])
  const score       = scoreDisplay(conviction.conviction_score)

  return (
    <div
      className="rounded-xl border-2 bg-card overflow-hidden"
      style={{ borderColor: 'rgba(0, 217, 181, 0.22)' }}
    >
      <div className="px-6 pt-6 pb-5 space-y-5">

        {/* ── Row 1: Status badge + Initiation Score ───────────────────── */}
        <div className="flex items-center justify-between gap-4">
          {/* Status badge */}
          <div className={`inline-flex items-center gap-2.5 px-4 py-2.5 rounded-xl border-2 ${styles.bg} ${styles.border}`}>
            <span className={`w-2.5 h-2.5 rounded-full ${styles.dot} flex-shrink-0 shadow-sm`} />
            <span className={`text-xl font-bold tracking-[0.06em] ${styles.text}`}>{status}</span>
          </div>

          {/* Score */}
          <div className="text-right">
            <p className="text-[10px] text-text-tertiary uppercase tracking-wider mb-0.5">
              Initiation Score
            </p>
            <p className="text-3xl font-bold text-text-primary font-mono tabular-nums leading-none">
              {score}
            </p>
            <p className="text-[10px] text-text-tertiary mt-0.5">
              {conviction.conviction_level} conviction · {ticker}
            </p>
          </div>
        </div>

        {/* ── Row 2: Allocation numbers ─────────────────────────────────── */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl bg-surface-elevated border border-border/50 px-4 py-4 text-center">
            <p className="text-[10px] text-text-tertiary uppercase tracking-wider mb-2">
              Starter Allocation
            </p>
            <div className="flex items-baseline justify-center gap-0.5">
              <span className="text-5xl font-bold text-primary tabular-nums leading-none">
                {conviction.recommended_pct}
              </span>
              <span className="text-2xl font-semibold text-primary/60 ml-0.5">%</span>
            </div>
            <p className="text-[10px] text-text-tertiary mt-2">of portfolio</p>
          </div>

          <div className="rounded-xl bg-surface-elevated border border-border/50 px-4 py-4 text-center">
            <p className="text-[10px] text-text-tertiary uppercase tracking-wider mb-2">
              Max Allocation
            </p>
            <div className="flex items-baseline justify-center gap-0.5">
              <span className="text-5xl font-bold text-text-secondary tabular-nums leading-none">
                {conviction.max_pct}
              </span>
              <span className="text-2xl font-semibold text-text-tertiary ml-0.5">%</span>
            </div>
            <p className="text-[10px] text-text-tertiary mt-2">policy ceiling</p>
          </div>
        </div>

        {/* ── Row 3: Entry Zone ─────────────────────────────────────────── */}
        {entryZone && (
          <div className="flex items-center justify-between rounded-lg border border-border/50 bg-surface-elevated/40 px-4 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
              Entry Zone
            </p>
            <p className="text-base font-semibold text-primary font-mono">{entryZone}</p>
          </div>
        )}

        {/* ── Row 4: Triggers ───────────────────────────────────────────── */}
        {(nextAdd || thesisBreak) && (
          <div className="space-y-2">
            {nextAdd && (
              <div className="flex items-start gap-3 px-3.5 py-3 rounded-lg border border-success/25 bg-success/5">
                <span className="mt-1 w-1.5 h-1.5 rounded-full bg-success flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-success/70 mb-0.5">
                    Next Add Trigger
                  </p>
                  <p className="text-xs text-text-secondary leading-snug">{nextAdd}</p>
                </div>
              </div>
            )}

            {thesisBreak && (
              <div className="flex items-start gap-3 px-3.5 py-3 rounded-lg border border-error/25 bg-error/5">
                <span className="mt-1 w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-error/70 mb-0.5">
                    Thesis Break Trigger
                  </p>
                  <p className="text-xs text-text-secondary leading-snug">{thesisBreak}</p>
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
