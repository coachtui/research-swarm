import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type { DeploymentUpdateResponse } from '@/types/api'

/**
 * useAdminDeploymentUpdate — fetches the platform-wide Structural Deployment Update.
 *
 * Admin-only. Queries the /api/deployment/structural-update/admin endpoint which
 * aggregates across ALL users' watchlists and analyses (no per-user filter).
 * Server-side cache TTL is 24 hours; client-side stale time is 5 minutes.
 */
export function useAdminDeploymentUpdate(enabled = true) {
  return useQuery<DeploymentUpdateResponse>({
    queryKey: ['admin-deployment-update'],
    queryFn: () => apiClient.getAdminDeploymentUpdate(),
    staleTime: 1000 * 60 * 5,  // 5 min client-side; server cache is 24h
    retry: 1,
    enabled,
  })
}
