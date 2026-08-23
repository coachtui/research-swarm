'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useAdminMetrics, useAdminCosts } from '@/lib/hooks/useAdmin'
import { AdminMetrics } from '@/components/admin/AdminMetrics'
import { AdminCostSummary } from '@/components/admin/AdminCostSummary'
import { AdminUserTable } from '@/components/admin/AdminUserTable'
import { AdminAnalysisTable } from '@/components/admin/AdminAnalysisTable'
import { AdminRevenueCharts } from '@/components/admin/AdminRevenueCharts'
import { MarketOutlookPanel } from '@/components/autopilot/MarketOutlookPanel'
import { EngineJournalPanel } from '@/components/autopilot/EngineJournalPanel'
import { WeeklyBatchPanel } from '@/components/autopilot/WeeklyBatchPanel'
import { WeekPanel } from '@/components/autopilot/WeekPanel'
import { WatchlistView } from '@/components/dashboard/WatchlistView'
import { StructuralDeploymentUpdate } from '@/components/deployment/StructuralDeploymentUpdate'
import { PortfolioOverview } from '@/components/portfolio/PortfolioOverview'
import { PortfolioSeedForm } from '@/components/portfolio/PortfolioSeedForm'
import { QuarterliesPanel } from '@/components/autopilot/QuarterliesPanel'
import { ActionsTab } from '@/components/portfolio/ActionsTab'
import { HoldingsTab } from '@/components/portfolio/HoldingsTab'
import { usePortfolio } from '@/lib/hooks/usePortfolio'
import { Shield, AlertCircle } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { apiClient } from '@/lib/api/client'

export default function AdminPage() {
  const { getToken } = useAuth()
  const [tokenReady, setTokenReady] = useState(false)

  // Register token getter so each request gets a fresh Clerk token (auto-refreshed)
  useEffect(() => {
    apiClient.setTokenGetter(getToken)
    setTokenReady(true)
  }, [getToken])

  // Wait for token to be set before rendering admin hooks
  if (!tokenReady) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-text-secondary">Loading...</div>
      </div>
    )
  }

  return <AdminContent />
}

function AdminContent() {
  const { data: metrics, isLoading, error } = useAdminMetrics()
  const { data: costs, isLoading: costsLoading } = useAdminCosts()
  const { data: portfolioData } = usePortfolio()
  const portfolio = portfolioData?.portfolios?.[0] || null

  // Access denied if not admin
  if (error && (error as any).status === 403) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Card className="max-w-md mx-auto">
          <CardContent className="pt-6 text-center space-y-4">
            <AlertCircle className="h-12 w-12 text-error mx-auto" />
            <h2 className="text-xl font-semibold text-text-primary">
              Access Denied
            </h2>
            <p className="text-text-secondary">
              You do not have permission to access the admin dashboard.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-surface-elevated bg-surface">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center gap-3">
            <Shield className="h-6 w-6 text-primary" />
            <div>
              <h1 className="text-xl sm:text-3xl font-bold text-text-primary">Admin Dashboard</h1>
              <p className="text-sm text-text-secondary mt-1">
                Platform management and user administration
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="container mx-auto px-4 py-8">
        <Tabs defaultValue="metrics" className="space-y-6">
          <TabsList>
            <TabsTrigger value="week">This Week</TabsTrigger>
            <TabsTrigger value="metrics">Metrics</TabsTrigger>
            <TabsTrigger value="revenue">Revenue</TabsTrigger>
            <TabsTrigger value="outlook">Outlook</TabsTrigger>
            <TabsTrigger value="quarterlies">Quarterlies</TabsTrigger>
            <TabsTrigger value="users">Users</TabsTrigger>
            <TabsTrigger value="analyses">Analyses</TabsTrigger>
            <TabsTrigger value="watchlist">Watchlist</TabsTrigger>
            <TabsTrigger value="deployment">Deployment</TabsTrigger>
            <TabsTrigger value="portfolio">Portfolio</TabsTrigger>
          </TabsList>

          <TabsContent value="week">
            <WeekPanel />
          </TabsContent>

          <TabsContent value="metrics">
            <div className="space-y-6">
              <AdminMetrics metrics={metrics} isLoading={isLoading} />
              <AdminCostSummary costs={costs} isLoading={costsLoading} />
            </div>
          </TabsContent>

          <TabsContent value="revenue">
            <AdminRevenueCharts />
          </TabsContent>

          <TabsContent value="outlook">
            <Tabs defaultValue="sunday" className="space-y-4">
              <TabsList>
                <TabsTrigger value="sunday">Sunday Outlook</TabsTrigger>
                <TabsTrigger value="monday">Monday Batch</TabsTrigger>
              </TabsList>
              <TabsContent value="sunday">
                <div className="space-y-6">
                  <MarketOutlookPanel />
                  <EngineJournalPanel />
                </div>
              </TabsContent>
              <TabsContent value="monday">
                <WeeklyBatchPanel />
              </TabsContent>
            </Tabs>
          </TabsContent>

          <TabsContent value="quarterlies">
            <QuarterliesPanel />
          </TabsContent>

          <TabsContent value="users">
            <AdminUserTable />
          </TabsContent>

          <TabsContent value="analyses">
            <AdminAnalysisTable />
          </TabsContent>

          <TabsContent value="watchlist">
            <WatchlistView />
          </TabsContent>

          <TabsContent value="deployment">
            <StructuralDeploymentUpdate adminMode />
          </TabsContent>

          <TabsContent value="portfolio">
            <Tabs defaultValue="overview" className="space-y-4">
              <TabsList>
                <TabsTrigger value="overview">Portfolio</TabsTrigger>
                <TabsTrigger value="actions">Actions</TabsTrigger>
                <TabsTrigger value="holdings">
                  Holdings {portfolio ? `(${portfolio.position_count})` : ''}
                </TabsTrigger>
              </TabsList>
              <TabsContent value="overview">
                {portfolio
                  ? <PortfolioOverview portfolioId={portfolio.id} userTier="trader" />
                  : <PortfolioSeedForm />}
              </TabsContent>
              <TabsContent value="actions">
                {portfolio
                  ? <ActionsTab portfolioId={portfolio.id} />
                  : <div className="text-center py-12 text-sm text-text-tertiary">Create a portfolio first.</div>}
              </TabsContent>
              <TabsContent value="holdings">
                {portfolio
                  ? <HoldingsTab portfolioId={portfolio.id} />
                  : <div className="text-center py-12 text-sm text-text-tertiary">Create a portfolio first.</div>}
              </TabsContent>
            </Tabs>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
