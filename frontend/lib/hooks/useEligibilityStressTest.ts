import { useState, useCallback } from 'react'
import { apiClient } from '@/lib/api/client'
import type { EligibilityStressTestResponse } from '@/types/api'

/**
 * useEligibilityStressTest — manual-trigger hook for the admin stress-test simulation.
 *
 * Does NOT auto-fetch on mount. Call `run()` to trigger the simulation.
 * Results are kept in local state (session-scoped); the backend caches by snapshot
 * bucket so repeated calls within the same day are nearly instant.
 */
export function useEligibilityStressTest() {
  const [data, setData] = useState<EligibilityStressTestResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const run = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await apiClient.getEligibilityStressTest()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Stress test failed'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { data, isLoading, error, run }
}
