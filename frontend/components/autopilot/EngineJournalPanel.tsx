'use client'

import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useEngineReports } from '@/lib/hooks/useAdmin'
import { formatDate } from '@/lib/utils/formatting'
import type { EngineReportEntry } from '@/types/api'

const SEVERITY_DOT: Record<EngineReportEntry['severity'], string> = {
  info: 'bg-text-secondary',
  warning: 'bg-warning',
  critical: 'bg-error',
}

function EntryRow({ entry }: { entry: EngineReportEntry }) {
  const [open, setOpen] = useState(false)
  const bodyId = `journal-body-${entry.id}`
  return (
    <div className="py-2 border-b border-hairline last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={bodyId}
        className="flex w-full items-center gap-2 text-left text-sm"
      >
        <span className={`h-2 w-2 rounded-full shrink-0 ${SEVERITY_DOT[entry.severity]}`} />
        <Badge variant="secondary">{entry.type.replace(/_/g, ' ')}</Badge>
        <span className="text-text-primary truncate flex-1">{entry.title}</span>
        <span className="text-xs text-text-secondary shrink-0">
          {formatDate(entry.created_at)}
        </span>
      </button>
      {open && (
        <pre
          id={bodyId}
          className="mt-2 max-h-64 overflow-auto rounded bg-surface-elevated p-3 text-xs text-text-secondary"
        >
          {JSON.stringify(entry.body, null, 2)}
        </pre>
      )}
    </div>
  )
}

export function EngineJournalPanel() {
  const { data, isLoading, error } = useEngineReports()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Engine Journal</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-8" />
            ))}
          </div>
        )}
        {error && <p className="text-text-secondary text-sm">Failed to load journal</p>}
        {data && data.length === 0 && (
          <p className="text-text-secondary text-sm">
            Nothing yet — entries appear when the engine changes themes, rebalances, or fails.
          </p>
        )}
        {data && data.map((entry) => <EntryRow key={entry.id} entry={entry} />)}
      </CardContent>
    </Card>
  )
}
