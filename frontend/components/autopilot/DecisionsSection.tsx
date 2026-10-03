'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { WeekAction } from '@/types/api'

const OUTCOME_LABEL: Record<string, string> = {
  not_placed: 'authorised, not placed',
  placed: 'order placed',
  vetoed: 'vetoed by the entry screen',
  rejected: 'rejected',
  deferred: 'deferred',
  exited: 'exited',
  passed_on: 'considered, passed',
}

const OUTCOME_TONE: Record<string, string> = {
  vetoed: 'text-error',
  rejected: 'text-error',
  deferred: 'text-warning',
  placed: 'text-success',
}

const DEFER_REASON: Record<string, string> = {
  standing_open_order: 'an order for this name is already working',
  budget_exhausted: 'the week\'s research budget was spent before this name',
  max_positions: 'the sleeve is at its position cap',
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
        <span className={`ml-auto text-[0.65rem] uppercase tracking-wider font-semibold ${OUTCOME_TONE[a.outcome] ?? 'text-muted-foreground'}`}>
          {OUTCOME_LABEL[a.outcome] ?? a.outcome}
        </span>
      </div>
      {a.reason && (
        <p className="mt-1 text-sm text-muted-foreground max-w-[70ch]">
          {a.outcome === 'vetoed' || a.outcome === 'deferred' || a.outcome === 'rejected' ? (
            <span className="uppercase text-[0.62rem] tracking-wider font-semibold text-error mr-2">
              {a.outcome === 'deferred' ? 'Held back' : 'Why not'}
            </span>
          ) : null}
          {DEFER_REASON[a.reason] ?? a.reason}
        </p>
      )}
      {a.why_now && a.why_now !== a.reason && (
        <p className="mt-1 text-sm text-muted-foreground max-w-[70ch]">
          <span className="uppercase text-[0.62rem] tracking-wider font-semibold text-primary mr-2">
            The memo's case
          </span>
          {a.why_now}
        </p>
      )}
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

const PRIMARY_ORDER: Record<string, number> = {
  vetoed: 0, rejected: 1, placed: 2, deferred: 3, not_placed: 4, exited: 5,
}

export function DecisionsSection({ actions }: { actions: WeekAction[] }) {
  // The memo's authorised entries and what the engine did with them come
  // first; the long tail of names it considered and passed on is collapsed
  // so it stops burying the handful of decisions that moved money.
  const primary = actions
    .filter((a) => a.outcome !== 'passed_on')
    .sort((x, y) => (PRIMARY_ORDER[x.outcome] ?? 9) - (PRIMARY_ORDER[y.outcome] ?? 9))
  const passed = actions.filter((a) => a.outcome === 'passed_on')
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">
          Decided, not held — what the memo wanted and what the engine did with it
        </CardTitle>
      </CardHeader>
      <CardContent>
        {actions.length === 0 ? (
          <p className="text-sm italic text-muted-foreground">
            Nothing recorded. Candidates the memo declined appear here from the first run after the passed-on field shipped.
          </p>
        ) : primary.length === 0 ? (
          <p className="text-sm italic text-muted-foreground">
            The memo authorised no new entries this week.
          </p>
        ) : (
          primary.map((a, i) => <ActionRow key={`${a.ticker}-${i}`} a={a} />)
        )}
        {passed.length > 0 && (
          <details className="mt-3">
            <summary className="text-xs uppercase tracking-wider text-muted-foreground cursor-pointer">
              Considered and passed ({passed.length})
            </summary>
            <div className="mt-1">
              {passed.map((a, i) => <ActionRow key={`${a.ticker}-p-${i}`} a={a} />)}
            </div>
          </details>
        )}
      </CardContent>
    </Card>
  )
}
