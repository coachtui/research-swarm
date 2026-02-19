'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { DashboardHeader } from '@/components/dashboard/DashboardHeader'
import { WatchlistView } from '@/components/dashboard/WatchlistView'
import { AnalysisHistoryView } from '@/components/dashboard/AnalysisHistoryView'
import { useQuota } from '@/lib/hooks/useQuota'
import { apiClient } from '@/lib/api/client'

export default function DashboardPage() {
  const router = useRouter()
  const { getToken } = useAuth()
  const [tokenReady, setTokenReady] = useState(false)

  // Set auth token and check admin status
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        // Register token getter so every API request gets a fresh Clerk token
        apiClient.setTokenGetter(getToken)

        // Check if user is admin and redirect
        const user = await apiClient.getCurrentUser()

        if (user.is_admin) {
          router.replace('/admin')
          return
        }

        setTokenReady(true)
      } catch (error) {
        console.error('Failed to initialize auth:', error)
        setTokenReady(true) // Still render dashboard even if check fails
      }
    }

    initializeAuth()
  }, [getToken, router])

  // Wait for token to be set before rendering dashboard
  if (!tokenReady) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-text-secondary">Loading...</div>
      </div>
    )
  }

  return <DashboardContent />
}

function DashboardContent() {
  const { data: quota, isLoading: quotaLoading } = useQuota()

  return (
    <div className="min-h-screen bg-background">
      <DashboardHeader quota={quota} isLoading={quotaLoading} />

      <main className="container mx-auto px-4 py-8">
        <Tabs defaultValue="watchlist" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3 lg:w-[400px]">
            <TabsTrigger value="watchlist">
              Watchlist {quota && `(${quota.watchlist_count})`}
            </TabsTrigger>
            <TabsTrigger value="history">
              History
            </TabsTrigger>
            <TabsTrigger value="analyze">
              Analyze
            </TabsTrigger>
          </TabsList>

          <TabsContent value="watchlist">
            <WatchlistView />
          </TabsContent>

          <TabsContent value="history">
            <AnalysisHistoryView />
          </TabsContent>

          <TabsContent value="analyze">
            <div className="rounded-lg border border-surface-elevated bg-surface p-8 text-center">
              <p className="text-text-secondary mb-4">
                Quick analyze form coming soon
              </p>
              <p className="text-sm text-text-tertiary">
                For now, visit <a href="/analyze" className="text-primary hover:underline">/analyze</a>
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
