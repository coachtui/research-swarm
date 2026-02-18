import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type { QuotaData } from '@/types/api'

/**
 * Fetch user's current quota/usage
 */
export function useQuota() {
  return useQuery({
    queryKey: ['quota'],
    queryFn: () => apiClient.getQuota(),
    staleTime: 1000 * 60 * 5, // 5 minutes cache
    retry: 2,
  })
}

/**
 * Check if user can run another analysis
 */
export function useCanAnalyze() {
  const { data: quota } = useQuota()

  if (!quota) return { canAnalyze: false, remaining: 0 }

  const canAnalyze = quota.analyses_remaining > 0
  const remaining = quota.analyses_remaining

  return { canAnalyze, remaining }
}

/**
 * Check if user can add another watchlist stock
 */
export function useCanAddToWatchlist() {
  const { data: quota } = useQuota()

  if (!quota) return { canAdd: false, remaining: 0 }

  const canAdd = quota.watchlist_remaining > 0
  const remaining = quota.watchlist_remaining

  return { canAdd, remaining }
}
