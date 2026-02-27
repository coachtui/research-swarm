'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { DashboardHeader } from '@/components/dashboard/DashboardHeader'
import { WatchlistView } from '@/components/dashboard/WatchlistView'
import { AnalysisHistoryView } from '@/components/dashboard/AnalysisHistoryView'
import { StructuralDeploymentUpdate } from '@/components/deployment/StructuralDeploymentUpdate'
import { useQuota } from '@/lib/hooks/useQuota'
import { useEntitlements } from '@/lib/hooks/useEntitlements'
import { apiClient } from '@/lib/api/client'
import { TickerSearchForm } from '@/components/analyze/TickerSearchForm'
import { UserInfo } from '@/types/api'
import { Lock, TrendingUp } from 'lucide-react'

export default function DashboardPage() {
  const router = useRouter()
  const { getToken } = useAuth()
  const [tokenReady, setTokenReady] = useState(false)
  const [currentUser, setCurrentUser] = useState<UserInfo | null>(null)

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        apiClient.setTokenGetter(getToken)
        const user = await apiClient.getCurrentUser()

        if (user.is_admin) {
          router.replace('/admin')
          return
        }

        setCurrentUser(user)
        setTokenReady(true)
      } catch (error) {
        console.error('Failed to initialize auth:', error)
        setTokenReady(true)
      }
    }

    initializeAuth()
  }, [getToken, router])

  if (!tokenReady) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-text-secondary">Loading...</div>
      </div>
    )
  }

  return <DashboardContent currentUser={currentUser} />
}

function NoSubscriptionPanel() {
  const router = useRouter()
  return (
    <div className="max-w-2xl mx-auto mt-8">
      <div className="rounded-lg border border-border bg-surface p-8 text-center space-y-4">
        <div className="flex justify-center">
          <div className="rounded-full bg-surface-elevated p-3">
            <Lock className="h-6 w-6 text-text-secondary" />
          </div>
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Subscription Required</h3>
          <p className="text-sm text-text-secondary mt-1">
            Purchase a plan to start running institutional-quality stock analyses.
          </p>
        </div>
        <button
          onClick={() => router.push('/#pricing-tiers')}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-white rounded-button text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <TrendingUp className="h-4 w-4" />
          View Plans
        </button>
      </div>
    </div>
  )
}

function DashboardContent({ currentUser }: { currentUser: UserInfo | null }) {
  const { data: quota, isLoading: quotaLoading } = useQuota()
  const { data: entitlements } = useEntitlements()

  const PAID_STATUSES = ['active', 'trialing']
  const hasSubscription = currentUser
    ? (currentUser.is_admin || PAID_STATUSES.includes(currentUser.stripe_subscription_status ?? ''))
    : false

  // Show Deployment tab for Investor+ users (and locked preview for others)
  const showDeploymentTab = entitlements != null

  return (
    <div className="min-h-screen bg-background">
      <DashboardHeader quota={quota} isLoading={quotaLoading} />

      <main className="page-container py-8">
        <Tabs defaultValue="watchlist" className="space-y-0">
          <TabsList>
            <TabsTrigger value="watchlist">
              Watchlist {quota && `(${quota.watchlist_count})`}
            </TabsTrigger>
            <TabsTrigger value="history">
              History
            </TabsTrigger>
            <TabsTrigger value="analyze">
              {hasSubscription ? 'Analyze' : 'Analyze 🔒'}
            </TabsTrigger>
            {showDeploymentTab && (
              <TabsTrigger value="deployment">
                {entitlements?.features['feature.deployment.structural_update']
                  ? 'Deployment'
                  : 'Deployment 🔒'}
              </TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="watchlist">
            <WatchlistView />
          </TabsContent>

          <TabsContent value="history">
            <AnalysisHistoryView />
          </TabsContent>

          <TabsContent value="analyze">
            {hasSubscription ? <TickerSearchForm /> : <NoSubscriptionPanel />}
          </TabsContent>

          {showDeploymentTab && (
            <TabsContent value="deployment">
              <StructuralDeploymentUpdate />
            </TabsContent>
          )}
        </Tabs>
      </main>
    </div>
  )
}
