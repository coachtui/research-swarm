'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { formatDate } from '@/lib/utils/formatting'
import type { ThemeConstituent, ThemeHistoryPoint } from '@/types/api'

/**
 * One ranked theme, expandable to the names behind it.
 *
 * The badge used to say "rotating in" with no date for weeks on end, and the
 * row was not clickable, so the owner could not see which companies a theme
 * even contained. The flag is a 1-month-vs-3-month rank state, so it is dated
 * from the first consecutive outlook in which it held.
 */

export const STAGE_TONE: Record<string, string> = {
  pre_consensus: 'bg-teal-100 text-teal-900 dark:bg-teal-950 dark:text-teal-200',
  catching_on: 'bg-green-100 text-green-900 dark:bg-green-950 dark:text-green-200',
  crowded: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200',
  priced: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200',
}

export function StageChip({ stage }: { stage: string | null | undefined }) {
  if (!stage) return null
  return (
    <span
      className={`text-[0.62rem] uppercase tracking-wider px-1.5 py-0.5 rounded shrink-0 ${
        STAGE_TONE[stage] ?? 'bg-surface-elevated text-text-secondary'
      }`}
    >
      {stage.replace(/_/g, ' ')}
    </span>
  )
}

export function flagLabel(
  flag: 'into' | 'out_of' | null | undefined,
  since: string | null | undefined,
  weeks: number | null | undefined,
): string | null {
  if (!flag) return null
  const verb = flag === 'into' ? 'rotating in' : 'rotating out'
  if (!since) return verb
  const span = weeks && weeks > 1 ? ` · ${weeks} wks` : ''
  return `${verb} since ${formatDate(since)}${span}`
}

export function ThemeSparkline({ points }: { points: ThemeHistoryPoint[] }) {
  if (points.length < 2) return null
  const scores = points.map((p) => p.score)
  const min = Math.min(...scores)
  const max = Math.max(...scores)
  const span = max - min || 1
  const coords = points
    .map((p, i) => `${(i / (points.length - 1)) * 60},${18 - ((p.score - min) / span) * 16}`)
    .join(' ')
  return (
    <svg width="60" height="20" className="text-primary shrink-0" aria-hidden="true">
      <polyline points={coords} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

export interface ThemeRowProps {
  rank: number | null
  slug: string
  name: string
  stage?: string | null
  rankChange?: number | null
  score?: number | null
  flag?: 'into' | 'out_of' | null
  since?: string | null
  weeks?: number | null
  constituents: ThemeConstituent[]
  history?: ThemeHistoryPoint[]
  /** Collapsed content rendered above the constituents when open (e.g. thesis). */
  thesis?: string | null
}

export function ThemeRow(t: ThemeRowProps) {
  const [open, setOpen] = useState(false)
  const held = t.constituents.filter((c) => c.held).length
  const label = flagLabel(t.flag, t.since, t.weeks)
  const panelId = `theme-${t.slug}`
  return (
    <div className="border-b border-hairline last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={panelId}
        className="w-full py-2.5 text-left flex flex-wrap items-center gap-x-3 gap-y-1 text-sm"
      >
        <span className="text-text-tertiary w-5 shrink-0 tabular-nums">{t.rank ?? '–'}</span>
        <span className="text-text-primary font-medium">{t.name}</span>
        <StageChip stage={t.stage} />
        <span className="text-text-tertiary text-xs shrink-0">
          {t.constituents.length} names{held > 0 ? ` · ${held} held` : ''}
        </span>
        {label && (
          <Badge variant={t.flag === 'into' ? 'success' : 'error'} className="text-[0.65rem]">
            {label}
          </Badge>
        )}
        <span className="ml-auto flex items-center gap-3 shrink-0">
          {t.history && <ThemeSparkline points={t.history} />}
          {t.score != null && (
            <span className="font-mono tabular-nums text-text-secondary text-xs">
              {t.score >= 0 ? '+' : ''}
              {t.score.toFixed(4)}
            </span>
          )}
          <span className="text-text-tertiary text-xs" aria-hidden="true">{open ? '▾' : '▸'}</span>
        </span>
      </button>
      {open && (
        <div id={panelId} className="pb-3 pl-8 flex flex-col gap-2">
          {t.thesis && <p className="text-sm text-text-secondary max-w-[75ch]">{t.thesis}</p>}
          {t.constituents.length === 0 ? (
            <p className="text-sm italic text-text-tertiary">No active constituents.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {t.constituents.map((c) => (
                <li key={c.ticker} className="flex flex-wrap items-baseline gap-x-2 text-sm">
                  <span className={`font-mono font-semibold ${c.held ? 'text-primary' : 'text-text-primary'}`}>
                    {c.ticker}
                  </span>
                  {c.held && <Badge variant="secondary" className="text-[0.6rem]">held</Badge>}
                  {c.confidence != null && (
                    <span className="font-mono text-xs text-text-tertiary tabular-nums">
                      {c.confidence.toFixed(2)}
                    </span>
                  )}
                  <span className="text-text-secondary text-xs max-w-[70ch]">{c.exposure}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
