'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { apiClient } from '@/lib/api/client'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ResultsContent } from '@/components/results/ResultsContent'

interface ResultsPageProps {
  params: { run_id: string }
}

export default function ResultsPage({ params }: ResultsPageProps) {
  const { run_id } = params
  const { getToken } = useAuth()
  const [tokenReady, setTokenReady] = useState(false)

  useEffect(() => {
    apiClient.setTokenGetter(getToken)
    setTokenReady(true)
  }, [getToken])

  if (!tokenReady) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  return <ResultsContent runId={run_id} />
}
