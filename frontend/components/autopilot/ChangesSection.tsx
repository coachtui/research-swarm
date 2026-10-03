'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatDate } from '@/lib/utils/formatting'
import type { WeekChange } from '@/types/api'

const KIND_LABEL: Record<string, string> = {
  membership: 'names',
  theme: 'theme',
  hypothesis: 'hypothesis',
  veto: 'veto',
  failure: 'failure',
  validation: 'validation',
}

const SEVERITY_DOT: Record<string, string> = {
  info: 'bg-text-tertiary',
  warning: 'bg-warning',
  critical: 'bg-error',
}

/** What moved in the engine's state this week: new or removed names, themes
 * activated or retired, hypotheses journaled, vetoes, failures. Dated, so a
 * change that happened this Sunday is distinguishable from one in August. */
export function ChangesSection({ changes }: { changes: WeekChange[] }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs uppercase tracking-wider text-text-secondary">
          What changed this week
        </CardTitle>
      </CardHeader>
      <CardContent>
        {changes.length === 0 ? (
          <p className="text-sm italic text-text-secondary">
            Nothing changed. Same themes, same names, no vetoes, no failures.
          </p>
        ) : (
          <ul className="flex flex-col">
            {changes.map((c, i) => (
              <li
                key={`${c.date}-${i}`}
                className="py-2 border-b border-hairline last:border-b-0 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm"
              >
                <span className="font-mono text-xs text-text-tertiary tabular-nums w-16 shrink-0">
                  {formatDate(c.date)}
                </span>
                <span className={`h-2 w-2 rounded-full shrink-0 self-center ${SEVERITY_DOT[c.severity] ?? SEVERITY_DOT.info}`} />
                <Badge variant="secondary" className="text-[0.62rem]">{KIND_LABEL[c.kind] ?? c.kind}</Badge>
                <span className="text-text-primary">{c.title}</span>
                {c.detail && <span className="text-text-secondary max-w-[70ch]">{c.detail}</span>}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
