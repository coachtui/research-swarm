'use client'

import { useEffect, useState } from 'react'
import { apiClient } from '@/lib/api/client'
import { ResultsContent } from '@/components/results/ResultsContent'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { Card, CardContent } from '@/components/ui/card'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import type { RunResponse } from '@/types/api'

export default function NvdaPreviewPage() {
  const [data, setData] = useState<RunResponse | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiClient.getPreviewNvda()
      .then(setData)
      .catch(() => setError(true))
  }, [])

  if (error) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-2xl mx-auto">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <div className="text-4xl">⚠️</div>
              <h2 className="text-xl font-semibold text-text-primary">Example Report Unavailable</h2>
              <p className="text-text-secondary">The NVDA example report is temporarily unavailable. Try running your own analysis.</p>
              <div className="pt-4">
                <Link href="/analyze"><Button>Analyze a Stock</Button></Link>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div>
      {/* Preview banner */}
      <div className="bg-surface-elevated border-b border-border text-center py-2 text-xs text-text-tertiary">
        Example Report — NVDA &nbsp;·&nbsp; This is a real analysis run shown for illustrative purposes only. Not financial advice.
      </div>
      <ResultsContent previewData={data} isPreview />
    </div>
  )
}
