import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type { EntitlementsResponse } from '@/types/api'

/**
 * useEntitlements — fetches server-resolved feature flags and quota limits.
 *
 * Cached for 5 minutes (staleTime). The backend endpoint is stateless and
 * derives entitlements from the JWT user object — no extra DB hit.
 *
 * Returns the same shape as EntitlementsResponse:
 *   { tier, active, features: { [flag]: boolean }, limits: { ... } }
 *
 * Usage:
 *   const { data: ents } = useEntitlements()
 *   if (ents?.features['feature.report.signal_metrics']) { ... }
 */
export function useEntitlements() {
  return useQuery<EntitlementsResponse>({
    queryKey: ['entitlements'],
    queryFn: () => apiClient.getEntitlements(),
    staleTime: 1000 * 60 * 5,  // 5 min — matches /api/auth/me half-life
    retry: 1,
  })
}
