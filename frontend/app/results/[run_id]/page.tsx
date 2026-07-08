'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useSearchParams } from 'next/navigation'
import { apiClient } from '@/lib/api/client'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ResultsContent } from '@/components/results/ResultsContent'
import { ReusedReportBanner } from '@/components/results/ReusedReportBanner'

interface ResultsPageProps {
  params: { run_id: string }
}

export default function ResultsPage({ params }: ResultsPageProps) {
  const { run_id } = params
  const { getToken } = useAuth()
  const searchParams = useSearchParams()
  const [tokenReady, setTokenReady] = useState(false)

  const reused = searchParams.get('reused') === '1'
  const reusedAsOf = searchParams.get('as_of')
  const reusedTicker = searchParams.get('ticker')

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

  return (
    <>
      {reused && reusedAsOf && reusedTicker && (
        <div className="max-w-6xl mx-auto px-4 pt-4">
          <ReusedReportBanner ticker={reusedTicker} asOf={reusedAsOf} />
        </div>
      )}
      <ResultsContent runId={run_id} />
    </>
  )
}
