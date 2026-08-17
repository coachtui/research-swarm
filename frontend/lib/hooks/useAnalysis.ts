'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type { AnalyzeRequest, RunResponse } from '@/types/api'

// Query keys factory
export const analysisKeys = {
  all: ['analyses'] as const,
  lists: () => [...analysisKeys.all, 'list'] as const,
  list: (filters: string) => [...analysisKeys.lists(), filters] as const,
  details: () => [...analysisKeys.all, 'detail'] as const,
  detail: (id: string) => [...analysisKeys.details(), id] as const,
}

/**
 * Hook to fetch and poll a single analysis by run_id
 * Automatically polls every 5s if status is not completed/failed
 */
export function useAnalysis(runId: string | null) {
  return useQuery({
    queryKey: analysisKeys.detail(runId || ''),
    queryFn: () => {
      if (!runId) throw new Error('No run ID provided')
      return apiClient.getAnalysis(runId)
    },
    enabled: !!runId,
    refetchInterval: (query) => {
      // Poll every 5s if status is queued or running
      const status = query.state.data?.status
      if (status === 'queued' || status === 'running') {
        return 5000 // 5 seconds
      }
      // Defensive: a run can briefly report "completed" with no results while
      // the result row is still being written. Latching onto that snapshot
      // strands the user on "No Results Available" forever, because polling
      // has already stopped. The write ordering in save_analysis_result now
      // closes that window, but keep polling here too — an empty completed
      // run is never a valid terminal state, and this costs one extra request
      // in the rare case it happens.
      if (status === 'completed' && !(query.state.data?.results?.length)) {
        return 2000
      }
      // Stop polling when completed with results, or failed
      return false
    },
    staleTime: 0, // Always refetch on mount
    gcTime: 1000 * 60 * 10, // Keep in cache for 10 minutes
  })
}

/**
 * Hook to fetch analysis history with pagination
 */
export function useAnalysisHistory(
  limit = 20,
  offset = 0,
  status?: string
) {
  const filters = JSON.stringify({ limit, offset, status })

  return useQuery({
    queryKey: analysisKeys.list(filters),
    queryFn: () => apiClient.getAnalysisHistory(limit, offset, status),
    staleTime: 1000 * 30, // 30 seconds
  })
}

/**
 * Mutation hook to submit a new analysis request
 */
export function useSubmitAnalysis() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: AnalyzeRequest) => apiClient.analyzeStock(request),
    onSuccess: (data) => {
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: analysisKeys.all })

      // Optimistically set the data for the new run
      queryClient.setQueryData<RunResponse>(
        analysisKeys.detail(data.run_id),
        {
          id: data.run_id,
          status: data.status,
          tickers: [data.ticker],
          total_cost_usd: 0,
          created_at: data.created_at,
          completed_at: null,
          results: data.result ? [data.result] : [],
        }
      )
    },
  })
}

/**
 * Hook to delete an analysis
 */
export function useDeleteAnalysis() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (runId: string) => apiClient.deleteAnalysis(runId),
    onSuccess: (_, runId) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: analysisKeys.detail(runId) })
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: analysisKeys.lists() })
    },
  })
}
