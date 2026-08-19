'use client'

// Verdict Header — the headline answer to "what's the call?".
// Renders the reconciled rating, the one-line summary, and the manager's key
// insights — the 15-second read. The long synthesis narrative lives in the
// Investment Thesis section (it is the raw draft the structured thesis is
// rewritten from, so showing it here read as a second telling of the thesis).

interface VerdictHeaderProps {
  rating?: string | null
  moatScore?: number | null
  summary?: string | null
  keyInsights?: string[] | null
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
}: VerdictHeaderProps) {
  const normalized = (rating || '').trim().toUpperCase()
  const style = RATING_STYLES[normalized]
  const insights = (keyInsights || []).filter(Boolean).slice(0, 5)

  // Nothing meaningful to show — render nothing rather than an empty shell
  if (!style && !summary && insights.length === 0) return null

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

      </div>
    </div>
  )
}
