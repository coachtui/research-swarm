import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type { UserInfo } from '@/types/api'

/**
 * Fetch and cache the current authenticated user.
 * Stale for 10 minutes — tier changes are infrequent.
 */
export function useCurrentUser() {
  return useQuery<UserInfo>({
    queryKey: ['currentUser'],
    queryFn: () => apiClient.getCurrentUser(),
    staleTime: 1000 * 60 * 10,
    retry: 1,
  })
}
