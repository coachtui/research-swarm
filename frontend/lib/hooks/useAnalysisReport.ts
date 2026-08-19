'use client'

// Phase D: fetch the persisted AnalysisReport for a completed run.
// The report is built once at write time and served verbatim — this hook
// performs no derivation. Null (pre-Phase-C runs, or tier without access)
// means callers fall back to full_output-derived rendering.

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type { AnalysisReport } from '@/types/report'

export function useAnalysisReport(runId: string | null, enabled: boolean = true) {
  return useQuery<AnalysisReport | null>({
    queryKey: ['analysis-report', runId || ''],
    queryFn: () => {
      if (!runId) return Promise.resolve(null)
      return apiClient.getAnalysisReport(runId)
    },
    enabled: !!runId && enabled,
    staleTime: 1000 * 60 * 10, // the report is immutable once written
    gcTime: 1000 * 60 * 30,
  })
}
