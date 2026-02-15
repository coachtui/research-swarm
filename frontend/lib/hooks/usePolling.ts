'use client'

import { useQuery } from '@tanstack/react-query'

interface PollingOptions<T> {
  queryKey: unknown[]
  queryFn: () => Promise<T>
  shouldPoll: (data: T | undefined) => boolean
  interval?: number
  enabled?: boolean
  onSuccess?: (data: T) => void
  onError?: (error: Error) => void
}

/**
 * Generic polling hook for any API endpoint
 * Polls at specified interval while shouldPoll returns true
 */
export function usePolling<T>({
  queryKey,
  queryFn,
  shouldPoll,
  interval = 5000,
  enabled = true,
  onSuccess,
  onError,
}: PollingOptions<T>) {
  return useQuery({
    queryKey,
    queryFn,
    enabled,
    refetchInterval: (query) => {
      if (shouldPoll(query.state.data)) {
        return interval
      }
      return false
    },
    refetchOnWindowFocus: true,
    staleTime: 0,
  })
}

/**
 * Hook to track elapsed time during polling
 */
export function useElapsedTime(startTime: string | null) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!startTime) {
      setElapsed(0)
      return
    }

    const start = new Date(startTime).getTime()
    const interval = setInterval(() => {
      const now = Date.now()
      const diff = Math.floor((now - start) / 1000)
      setElapsed(diff)
    }, 1000)

    return () => clearInterval(interval)
  }, [startTime])

  return elapsed
}

// Add React imports
import { useEffect, useState } from 'react'
