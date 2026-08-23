import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type {
  PlatformMetrics,
  UsersListResponse,
  AnalysesListResponse,
  UpdateTierRequest,
  CostSummary,
  RevenueTimeSeries,
  MarketOutlookResponse,
  WeekResponse,
  WeeklyBatchRunSummary,
  WeeklyBatchRunDetail,
  QuarterlyReview,
} from '@/types/api'

// Query keys
export const adminKeys = {
  all: ['admin'] as const,
  metrics: () => [...adminKeys.all, 'metrics'] as const,
  costs: () => [...adminKeys.all, 'costs'] as const,
  revenue: () => [...adminKeys.all, 'revenue'] as const,
  users: (limit?: number, offset?: number) => [...adminKeys.all, 'users', limit, offset] as const,
  analyses: (limit?: number, ticker?: string) => [...adminKeys.all, 'analyses', limit, ticker] as const,
  outlook: () => [...adminKeys.all, 'outlook'] as const,
  engineReports: (type?: string) => [...adminKeys.all, 'engineReports', type ?? 'all'] as const,
  quarterlies: () => [...adminKeys.all, 'quarterlies'] as const,
  batchRuns: () => [...adminKeys.all, 'batchRuns'] as const,
  batchRunDetail: (runDate?: string) => [...adminKeys.all, 'batchRunDetail', runDate ?? 'latest'] as const,
}

/**
 * Fetch platform metrics
 */
export function useAdminMetrics() {
  return useQuery({
    queryKey: adminKeys.metrics(),
    queryFn: () => apiClient.getAdminMetrics(),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * Fetch revenue and profit timeseries
 */
export function useAdminRevenue() {
  return useQuery({
    queryKey: adminKeys.revenue(),
    queryFn: () => apiClient.getAdminRevenue(),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * Fetch cost summary (day/week/month/year)
 */
export function useAdminCosts() {
  return useQuery({
    queryKey: adminKeys.costs(),
    queryFn: () => apiClient.getCostSummary(),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * Fetch users list
 */
export function useAdminUsers(limit = 50, offset = 0) {
  return useQuery({
    queryKey: adminKeys.users(limit, offset),
    queryFn: () => apiClient.getAdminUsers(limit, offset),
    staleTime: 1000 * 60 * 2, // 2 minutes
  })
}

/**
 * Fetch analyses list
 */
export function useAdminAnalyses(limit = 100, ticker?: string) {
  return useQuery({
    queryKey: adminKeys.analyses(limit, ticker),
    queryFn: () => apiClient.getAdminAnalyses(limit, ticker),
    staleTime: 1000 * 60 * 2, // 2 minutes
  })
}

/**
 * Fetch the latest autopilot market outlook (404 until the first weekly run lands)
 */
export function useMarketOutlook() {
  return useQuery({
    queryKey: adminKeys.outlook(),
    queryFn: () => apiClient.getMarketOutlook(),
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: (failureCount, error) => (error as any)?.status === 404 ? false : failureCount < 1,
  })
}

/**
 * Engine journal feed (theme changes, failures, rebalance summaries)
 */
export function useEngineReports(type?: string) {
  return useQuery({
    queryKey: adminKeys.engineReports(type),
    queryFn: () => apiClient.getEngineReports({ type, limit: 50 }),
    staleTime: 1000 * 60 * 5,
  })
}

/**
 * Quarter-by-quarter sleeve performance, oldest first, with each quarter's
 * written review linked. Recomputed server-side from SleeveSnapshot on every
 * request, so a correction to the snapshot series shows up here immediately.
 */
export function useQuarterlies() {
  return useQuery<QuarterlyReview[]>({
    queryKey: adminKeys.quarterlies(),
    queryFn: () => apiClient.getQuarterlies(),
    staleTime: 1000 * 60 * 30,
  })
}

/**
 * History list of past Monday weekly-batch runs, newest first.
 */
export function useWeeklyBatchRuns() {
  return useQuery({
    queryKey: adminKeys.batchRuns(),
    queryFn: () => apiClient.getWeeklyBatchRuns(),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * One weekly-batch run's funnel summary + ticker rows. Omit runDate for the
 * most recent run (404 until the first Monday run lands).
 */
export function useWeeklyBatchRunDetail(runDate?: string) {
  return useQuery({
    queryKey: adminKeys.batchRunDetail(runDate),
    queryFn: () => apiClient.getWeeklyBatchRunDetail(runDate),
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: (failureCount, error) => (error as any)?.status === 404 ? false : failureCount < 1,
  })
}

/**
 * Update user tier
 */
export function useUpdateUserTier() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ userId, newTier }: { userId: string; newTier: string }) =>
      apiClient.updateUserTier(userId, { new_tier: newTier }),
    onSuccess: () => {
      // Invalidate users and metrics queries
      queryClient.invalidateQueries({ queryKey: adminKeys.all })
    },
  })
}

/**
 * This week: live broker positions and orders joined to the memo's reasoning,
 * plus what it decided and did NOT buy. Short staleTime — it reads the broker.
 */
export function useWeek(week?: string) {
  return useQuery({
    queryKey: [...adminKeys.all, 'week', week ?? 'latest'] as const,
    queryFn: () => apiClient.getWeek(week),
    staleTime: 1000 * 60, // 1 minute
  })
}
