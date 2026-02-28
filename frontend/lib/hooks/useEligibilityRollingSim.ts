import { useState, useCallback } from 'react'
import { apiClient } from '@/lib/api/client'
import type { EligibilityRollingSimResponse } from '@/types/api'

/**
 * useEligibilityRollingSim — manual-trigger hook for the admin rolling simulation.
 *
 * Does NOT auto-fetch on mount. Call `run()` to trigger the simulation.
 * Results are kept in local state; the backend caches per snapshot bucket (24h).
 */
export function useEligibilityRollingSim() {
  const [data, setData] = useState<EligibilityRollingSimResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const run = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await apiClient.getEligibilityRollingSim()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Rolling simulation failed'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { data, isLoading, error, run }
}
