import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'

export const analysisHistoryKeys = {
  all: ['analysis-history'] as const,
  lists: () => [...analysisHistoryKeys.all, 'list'] as const,
  list: (limit?: number, offset?: number, status?: string) =>
    [...analysisHistoryKeys.lists(), limit, offset, status] as const,
  detail: (runId: string) => [...analysisHistoryKeys.all, 'detail', runId] as const,
}

/**
 * Fetch user's analysis history (list of runs)
 */
export function useAnalysisHistory(limit = 20, offset = 0, status?: string) {
  return useQuery({
    queryKey: analysisHistoryKeys.list(limit, offset, status),
    queryFn: () => apiClient.getRuns(limit, offset, status),
    staleTime: 1000 * 60, // 1 minute
  })
}

/**
 * Fetch details of a specific run
 */
export function useRunDetail(runId: string) {
  return useQuery({
    queryKey: analysisHistoryKeys.detail(runId),
    queryFn: () => apiClient.getRun(runId),
    staleTime: 1000 * 60 * 5, // 5 minutes
    enabled: !!runId,
  })
}
