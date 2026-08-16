'use client'

// Verdict Header — the headline answer to "what's the call?".
// Renders the reconciled rating, the manager's key insights, and the full
// synthesis narrative. Before this component, the report never displayed the
// rating anywhere, and synthesis_narrative / key_insights (the most expensive
// LLM outputs in the pipeline) were never rendered at all.

import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

interface VerdictHeaderProps {
  rating?: string | null
  moatScore?: number | null
  summary?: string | null
  keyInsights?: string[] | null
  synthesisNarrative?: string | null
}

const RATING_STYLES: Record<string, { badge: string; label: string }> = {
  'STRONG BUY': { badge: 'bg-success/15 text-success border-success/40', label: 'Strong Buy' },
  BUY: { badge: 'bg-success/10 text-success border-success/30', label: 'Buy' },
  HOLD: { badge: 'bg-surface-elevated/60 text-text-primary border-border/60', label: 'Hold' },
  SELL: { badge: 'bg-error/10 text-error border-error/30', label: 'Sell' },
  'STRONG SELL': { badge: 'bg-error/15 text-error border-error/40', label: 'Strong Sell' },
}

export function VerdictHeader({
  rating,
  moatScore,
  summary,
  keyInsights,
  synthesisNarrative,
}: VerdictHeaderProps) {
  const [showNarrative, setShowNarrative] = useState(false)

  const normalized = (rating || '').trim().toUpperCase()
  const style = RATING_STYLES[normalized]
  const insights = (keyInsights || []).filter(Boolean).slice(0, 5)

  // Nothing meaningful to show — render nothing rather than an empty shell
  if (!style && !summary && insights.length === 0 && !synthesisNarrative) return null

  return (
    <div className="rounded-xl border border-border/60 bg-surface/40 overflow-hidden">
      <div className="px-5 py-4 space-y-3">
        {/* Rating badge + score */}
        <div className="flex items-center gap-3 flex-wrap">
          {style ? (
            <span
              className={`inline-flex items-center rounded-lg border px-3 py-1.5 text-base font-bold tracking-wide ${style.badge}`}
            >
              {style.label}
            </span>
          ) : (
            <span className="inline-flex items-center rounded-lg border border-border/60 bg-surface-elevated/40 px-3 py-1.5 text-base font-bold text-text-tertiary">
              No Rating
            </span>
          )}
          {moatScore !== null && moatScore !== undefined && (
            <span className="text-sm text-text-secondary font-mono tabular-nums">
              Overall score {moatScore.toFixed(1)}/10
            </span>
          )}
        </div>

        {/* One-line summary */}
        {summary && (
          <p className="text-sm text-text-primary leading-relaxed">{summary}</p>
        )}

        {/* Key insights */}
        {insights.length > 0 && (
          <ul className="space-y-1.5">
            {insights.map((insight, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-primary/60" />
                <span>{insight}</span>
              </li>
            ))}
          </ul>
        )}

        {/* Full synthesis narrative, collapsed by default */}
        {synthesisNarrative && (
          <div className="border-t border-border/40 pt-2">
            <button
              type="button"
              onClick={() => setShowNarrative(s => !s)}
              className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-tertiary hover:text-text-secondary transition-colors"
            >
              {showNarrative ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              Full synthesis
            </button>
            {showNarrative && (
              <p className="mt-2 text-sm text-text-secondary leading-relaxed whitespace-pre-line">
                {synthesisNarrative}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
