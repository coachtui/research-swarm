import { useState, useCallback } from 'react'
import { apiClient } from '@/lib/api/client'
import type { OpportunityDistributionResponse } from '@/types/api'

/**
 * useOpportunityDistribution — manual-trigger hook for the admin distribution panel.
 *
 * Does NOT auto-fetch on mount. Call `run()` to load the distribution.
 * Results are kept in local state; the backend caches by snapshot bucket
 * so repeated calls within the same day are nearly instant.
 */
export function useOpportunityDistribution() {
  const [data, setData] = useState<OpportunityDistributionResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const run = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await apiClient.getOpportunityDistribution()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load distribution'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { data, isLoading, error, run }
}
