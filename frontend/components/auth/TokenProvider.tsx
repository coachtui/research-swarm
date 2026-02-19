'use client'

import { useEffect } from 'react'
import { useAuth } from '@clerk/nextjs'
import { apiClient } from '@/lib/api/client'

/**
 * Wires up Clerk's getToken to the API client once at app level.
 * This ensures every API request gets a fresh, non-expired JWT automatically.
 */
export function TokenProvider() {
  const { getToken } = useAuth()

  useEffect(() => {
    apiClient.setTokenGetter(getToken)
  }, [getToken])

  return null
}
