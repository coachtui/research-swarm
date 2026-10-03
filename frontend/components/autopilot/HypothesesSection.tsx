'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { formatDay } from '@/lib/utils/formatting'
import type { WeekHypothesis } from '@/types/api'

/** The monthly pass's forward hypotheses: what it thinks binds next. These
 * were journaled and never shown; the pass now has to graduate, restate or
 * kill each one, so the list is the engine's open research agenda. */
export function HypothesesSection({ hypotheses }: { hypotheses: WeekHypothesis[] }) {
  if (hypotheses.length === 0) return null
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs uppercase tracking-wider text-text-secondary">
          Open hypotheses — what the engine thinks binds next
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col">
        {hypotheses.map((h, i) => (
          <div key={`${h.hypothesis}-${i}`} className="py-2.5 border-b border-hairline last:border-b-0">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <p className="text-sm text-text-primary max-w-[75ch]">{h.hypothesis}</p>
              {h.first_seen && (
                <span className="ml-auto font-mono text-xs text-text-tertiary shrink-0">
                  since {formatDay(h.first_seen)}
                </span>
              )}
            </div>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-secondary">
              {h.candidates.length > 0 && (
                <span>
                  <span className="uppercase tracking-wider text-[0.6rem] font-semibold text-text-tertiary mr-1.5">candidates</span>
                  <span className="font-mono">{h.candidates.join(' ')}</span>
                </span>
              )}
              {h.leading_indicators.length > 0 && (
                <span className="max-w-[70ch]">
                  <span className="uppercase tracking-wider text-[0.6rem] font-semibold text-text-tertiary mr-1.5">watch</span>
                  {h.leading_indicators.join(' · ')}
                </span>
              )}
              {h.falsification && (
                <span className="max-w-[70ch]">
                  <span className="uppercase tracking-wider text-[0.6rem] font-semibold text-text-tertiary mr-1.5">dies if</span>
                  {h.falsification}
                </span>
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
