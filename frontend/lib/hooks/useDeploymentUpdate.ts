import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type { DeploymentUpdateResponse } from '@/types/api'

/**
 * useDeploymentUpdate — fetches the Structural Deployment Update report.
 *
 * Investor tier and above only. The backend enforces entitlement.
 * Server-side cache TTL is 24 hours; client-side stale time is 5 minutes.
 *
 * The hook itself does not enforce tier gating — use FeatureGate or check
 * entitlements?.features['feature.deployment.structural_update'] before rendering.
 */
export function useDeploymentUpdate(enabled = true) {
  return useQuery<DeploymentUpdateResponse>({
    queryKey: ['deployment-update'],
    queryFn: () => apiClient.getDeploymentUpdate(),
    staleTime: 1000 * 60 * 5,  // 5 min client-side; server cache is 24h
    retry: 1,
    enabled,
  })
}
