'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { WeekAction } from '@/types/api'

const OUTCOME_LABEL: Record<string, string> = {
  not_placed: 'authorised, not placed',
  exited: 'exited',
  passed_on: 'considered, passed',
}

function ActionRow({ a }: { a: WeekAction }) {
  return (
    <div className="border-b last:border-b-0 py-2.5">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <span className="font-mono font-semibold">{a.ticker}</span>
        {a.slug && <Badge variant="secondary" className="text-[0.65rem]">{a.slug}</Badge>}
        {a.role && <Badge variant="secondary" className="text-[0.65rem]">{a.role.replace('_', ' ')}</Badge>}
        {a.conviction != null && (
          <span className="font-mono text-xs text-muted-foreground">conviction {a.conviction.toFixed(2)}</span>
        )}
        <span className="ml-auto text-[0.65rem] uppercase tracking-wider font-semibold text-muted-foreground">
          {OUTCOME_LABEL[a.outcome] ?? a.outcome}
        </span>
      </div>
      {a.reason && <p className="mt-1 text-sm text-muted-foreground max-w-[70ch]">{a.reason}</p>}
      {a.reconsider_if && (
        <p className="mt-1 text-sm text-muted-foreground max-w-[70ch]">
          <span className="uppercase text-[0.62rem] tracking-wider font-semibold text-primary mr-2">
            Would change our mind
          </span>
          {a.reconsider_if}
        </p>
      )}
    </div>
  )
}

export function DecisionsSection({ actions }: { actions: WeekAction[] }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">
          Decided, not held
        </CardTitle>
      </CardHeader>
      <CardContent>
        {actions.length === 0 ? (
          <p className="text-sm italic text-muted-foreground">
            Nothing recorded. Candidates the memo declined appear here from the first run after the passed-on field shipped.
          </p>
        ) : (
          actions.map((a, i) => <ActionRow key={`${a.ticker}-${i}`} a={a} />)
        )}
      </CardContent>
    </Card>
  )
}
