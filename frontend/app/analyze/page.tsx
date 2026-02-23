'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { apiClient } from '@/lib/api/client'
import { TickerSearchForm } from '@/components/analyze/TickerSearchForm'
import { Lock, TrendingUp } from 'lucide-react'

function NoSubscriptionPanel() {
  const router = useRouter()
  return (
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
  )
}

export default function AnalyzePage() {
  const { getToken } = useAuth()
  const [hasSubscription, setHasSubscription] = useState<boolean | null>(null)

  useEffect(() => {
    const checkSubscription = async () => {
      try {
        apiClient.setTokenGetter(getToken)
        const user = await apiClient.getCurrentUser()
        const PAID_STATUSES = ['active', 'trialing']
        setHasSubscription(PAID_STATUSES.includes(user.stripe_subscription_status ?? ''))
      } catch {
        setHasSubscription(false)
      }
    }
    checkSubscription()
  }, [getToken])

  return (
    <div className="container mx-auto px-4 py-16">
      <div className="max-w-2xl mx-auto space-y-10">

        {/* Header */}
        <div className="space-y-2">
          <p className="text-xs font-medium tracking-widest uppercase text-text-secondary">
            Research
          </p>
          <h1 className="text-2xl md:text-3xl font-bold text-text-primary tracking-tight">
            Analyze a Stock
          </h1>
          <p className="text-sm text-text-secondary leading-relaxed">
            Get institutional-quality research powered by AI. We analyze 13+ data sources
            to detect what Wall Street doesn&apos;t tell you.
          </p>
        </div>

        {/* Divider */}
        <div style={{ borderTop: '1px solid var(--border)' }} />

        {/* Search form — gated on active subscription */}
        {hasSubscription === null ? (
          <div className="h-40 flex items-center justify-center">
            <div className="text-sm text-text-secondary">Loading...</div>
          </div>
        ) : hasSubscription ? (
          <TickerSearchForm />
        ) : (
          <NoSubscriptionPanel />
        )}

        {/* Popular tickers */}
        <div className="space-y-3">
          <p className="text-xs text-text-secondary">Popular:</p>
          <div className="flex flex-wrap gap-2">
            {['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'META', 'AMZN', 'TSM'].map((ticker) => (
              <div
                key={ticker}
                className="px-3 py-1 rounded-full text-xs font-medium text-text-secondary transition-colors duration-150"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
              >
                {ticker}
              </div>
            ))}
          </div>
        </div>

        {/* Divider */}
        <div style={{ borderTop: '1px solid var(--border)' }} />

        {/* Guarantee */}
        <div
          className="rounded-card p-5 text-center space-y-1"
          style={{ background: 'var(--accent-weak)', border: '1px solid var(--accent-border)' }}
        >
          <h3 className="text-sm font-semibold text-primary">Money-Back Guarantee</h3>
          <p className="text-xs text-text-secondary">
            If your analysis fails for any reason, we&apos;ll automatically issue a full refund.
            No questions asked.
          </p>
        </div>

        {/* Trust stats */}
        <div className="grid grid-cols-2 gap-4 text-center">
          <div
            className="py-4 rounded-card"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
          >
            <div className="text-2xl font-bold text-primary font-mono">~4 min</div>
            <div className="text-xs text-text-secondary mt-1">Average analysis time</div>
          </div>
          <div
            className="py-4 rounded-card"
            style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
          >
            <div className="text-2xl font-bold text-primary font-mono">13+</div>
            <div className="text-xs text-text-secondary mt-1">Data sources analyzed</div>
          </div>
        </div>

      </div>
    </div>
  )
}
