'use client'

import type { InitiationDecision } from '@/types/api'

// ── Status config ───────────────────────────────────────────────────────────────

const STATUS_CONFIG = {
  INITIATE: {
    label: 'INITIATE',
    bg: 'bg-emerald-500/15',
    border: 'border-emerald-500/40',
    badgeBg: 'bg-emerald-500',
    badgeText: 'text-white',
    dot: 'bg-emerald-400',
    scoreColor: 'text-emerald-400',
    barColor: 'bg-emerald-500',
  },
  WATCHLIST: {
    label: 'WATCHLIST',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/35',
    badgeBg: 'bg-amber-500',
    badgeText: 'text-black',
    dot: 'bg-amber-400',
    scoreColor: 'text-amber-400',
    barColor: 'bg-amber-500',
  },
  WAIT: {
    label: 'WAIT',
    bg: 'bg-surface/50',
    border: 'border-border/60',
    badgeBg: 'bg-zinc-600',
    badgeText: 'text-white',
    dot: 'bg-zinc-400',
    scoreColor: 'text-zinc-400',
    barColor: 'bg-zinc-500',
  },
} as const

interface CapitalInitiationCardProps {
  decision: InitiationDecision
  currentPrice?: number | null
}

function fmt(n: number) {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function CapitalInitiationCard({ decision, currentPrice }: CapitalInitiationCardProps) {
  const cfg = STATUS_CONFIG[decision.status]
  const [zoneLow, zoneMid] = decision.required_entry_zone

  // Score bar width (0–100 → 0–100%)
  const scoreWidth = `${Math.round(decision.initiation_score)}%`

  // Classify score tier label
  const scoreTier =
    decision.initiation_score >= 65
      ? 'Strong'
      : decision.initiation_score >= 50
      ? 'Moderate'
      : 'Weak'

  return (
    <div
      className={`rounded-xl border ${cfg.border} ${cfg.bg} overflow-hidden`}
      role="region"
      aria-label="Capital Initiation Decision"
    >
      {/* ── Header row ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border/30">
        <div className="flex items-center gap-2.5">
          <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot} flex-shrink-0`} />
          <p className="text-[11px] font-semibold uppercase tracking-widest text-text-tertiary">
            Capital Initiation Decision
          </p>
        </div>
        {/* Status badge */}
        <span
          className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold tracking-wide ${cfg.badgeBg} ${cfg.badgeText}`}
        >
          {cfg.label}
        </span>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────────── */}
      <div className="px-5 py-4 space-y-4">

        {/* Metric grid */}
        <div className="grid grid-cols-3 gap-3">

          {/* Starter Allocation */}
          <div className="rounded-lg border border-border/40 bg-surface/40 px-3.5 py-2.5 space-y-0.5">
            <p className="text-[10px] font-medium uppercase tracking-wider text-text-tertiary">
              Starter Allocation
            </p>
            <p className="text-xl font-bold text-text-primary tabular-nums">
              {decision.starter_allocation_percent.toFixed(1)}
              <span className="text-sm font-normal text-text-secondary ml-0.5">%</span>
            </p>
            <p className="text-[10px] text-text-tertiary">of portfolio</p>
          </div>

          {/* Entry Zone */}
          <div className="rounded-lg border border-border/40 bg-surface/40 px-3.5 py-2.5 space-y-0.5">
            <p className="text-[10px] font-medium uppercase tracking-wider text-text-tertiary">
              Required Entry Zone
            </p>
            <p className="text-sm font-semibold text-text-primary tabular-nums leading-snug">
              ${fmt(zoneLow)}
              <span className="text-text-tertiary font-normal"> – </span>
              ${fmt(zoneMid)}
            </p>
            {currentPrice != null && (
              <p className="text-[10px] text-text-tertiary">
                Current ${fmt(currentPrice)}
                {currentPrice <= zoneMid ? (
                  <span className="text-emerald-400"> · in zone</span>
                ) : (
                  <span className="text-amber-400"> · above zone</span>
                )}
              </p>
            )}
          </div>

          {/* Score */}
          <div className="rounded-lg border border-border/40 bg-surface/40 px-3.5 py-2.5 space-y-0.5">
            <p className="text-[10px] font-medium uppercase tracking-wider text-text-tertiary">
              Initiation Score
            </p>
            <p className={`text-xl font-bold tabular-nums ${cfg.scoreColor}`}>
              {decision.initiation_score.toFixed(0)}
              <span className="text-sm font-normal text-text-secondary ml-0.5">/ 100</span>
            </p>
            <p className="text-[10px] text-text-tertiary">{scoreTier} signal</p>
          </div>
        </div>

        {/* Score bar */}
        <div className="space-y-1.5">
          <div className="h-1.5 w-full rounded-full bg-surface-elevated overflow-hidden">
            <div
              className={`h-full rounded-full ${cfg.barColor} transition-all duration-500`}
              style={{ width: scoreWidth }}
            />
          </div>
          {/* Threshold markers */}
          <div className="relative h-3">
            <div className="absolute left-[50%] top-0 flex flex-col items-center">
              <div className="w-px h-1.5 bg-border/60" />
              <span className="text-[9px] text-text-tertiary leading-none mt-0.5">50</span>
            </div>
            <div className="absolute left-[65%] top-0 flex flex-col items-center">
              <div className="w-px h-1.5 bg-border/60" />
              <span className="text-[9px] text-text-tertiary leading-none mt-0.5">65</span>
            </div>
          </div>
        </div>

        {/* Rationale */}
        <p className="text-[11px] text-text-secondary leading-relaxed border-t border-border/30 pt-3">
          {decision.rationale_summary}
        </p>
      </div>
    </div>
  )
}
