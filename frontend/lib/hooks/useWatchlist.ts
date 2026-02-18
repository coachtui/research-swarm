import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type {
  WatchlistResponse,
  AddToWatchlistRequest,
  UpdateNotesRequest,
  RefreshWatchlistResponse,
  WatchlistStatsResponse,
} from '@/types/api'

// Query keys for cache invalidation
export const watchlistKeys = {
  all: ['watchlist'] as const,
  lists: () => [...watchlistKeys.all, 'list'] as const,
  stats: () => [...watchlistKeys.all, 'stats'] as const,
}

/**
 * Fetch user's watchlist
 */
export function useWatchlist() {
  return useQuery({
    queryKey: watchlistKeys.lists(),
    queryFn: () => apiClient.getWatchlist(),
    staleTime: 1000 * 60, // 1 minute
  })
}

/**
 * Fetch watchlist statistics
 */
export function useWatchlistStats() {
  return useQuery({
    queryKey: watchlistKeys.stats(),
    queryFn: () => apiClient.getWatchlistStats(),
    staleTime: 1000 * 60, // 1 minute
  })
}

/**
 * Add stock to watchlist
 */
export function useAddToWatchlist() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: AddToWatchlistRequest) =>
      apiClient.addToWatchlist(data),
    onSuccess: () => {
      // Invalidate watchlist and quota queries
      queryClient.invalidateQueries({ queryKey: watchlistKeys.all })
      queryClient.invalidateQueries({ queryKey: ['quota'] })
    },
  })
}

/**
 * Remove stock from watchlist
 */
export function useRemoveFromWatchlist() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (ticker: string) => apiClient.removeFromWatchlist(ticker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: watchlistKeys.all })
      queryClient.invalidateQueries({ queryKey: ['quota'] })
    },
  })
}

/**
 * Refresh watchlist item (run new analysis)
 */
export function useRefreshWatchlistItem() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (ticker: string) => apiClient.refreshWatchlistItem(ticker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: watchlistKeys.all })
      queryClient.invalidateQueries({ queryKey: ['quota'] })
    },
  })
}

/**
 * Update watchlist item notes
 */
export function useUpdateWatchlistNotes() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ ticker, notes }: { ticker: string; notes: string }) =>
      apiClient.updateWatchlistNotes(ticker, { notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: watchlistKeys.all })
    },
  })
}
