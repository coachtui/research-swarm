import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type {
  PlatformMetrics,
  UsersListResponse,
  AnalysesListResponse,
  UpdateTierRequest,
  CostSummary,
} from '@/types/api'

// Query keys
export const adminKeys = {
  all: ['admin'] as const,
  metrics: () => [...adminKeys.all, 'metrics'] as const,
  costs: () => [...adminKeys.all, 'costs'] as const,
  users: (limit?: number, offset?: number) => [...adminKeys.all, 'users', limit, offset] as const,
  analyses: (limit?: number, ticker?: string) => [...adminKeys.all, 'analyses', limit, ticker] as const,
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
