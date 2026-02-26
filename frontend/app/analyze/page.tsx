'use client'

import { useEffect, useRef } from 'react'
import { useAuth } from '@clerk/nextjs'
import { apiClient } from '@/lib/api/client'
import { TickerSearchForm } from '@/components/analyze/TickerSearchForm'

/**
 * /analyze — authenticated stock analysis entry point.
 *
 * Auth gate is enforced by middleware (unauthenticated → /sign-up).
 * This page just:
 *   1. Wires the Clerk token getter into apiClient (needed for all API calls).
 *   2. Calls POST /api/entitlements/ensure once to guarantee the user's
 *      FreeReportCredit row exists in Neon even if the Clerk webhook was slow.
 *   3. Renders TickerSearchForm, which handles credit display and paywall via
 *      useEntitlements() + the backend quota system.
 */
export default function AnalyzePage() {
  const { getToken } = useAuth()
  const ensuredRef = useRef(false)

  useEffect(() => {
    // Wire Clerk token into apiClient for all subsequent requests
    apiClient.setTokenGetter(getToken)

    // Ensure entitlement rows exist exactly once per page mount
    if (!ensuredRef.current) {
      ensuredRef.current = true
      apiClient.ensureEntitlements().catch(() => {
        // Non-fatal — report generation will still work; credits will be
        // lazily created by the quota_service on the first analyze call.
      })
    }
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

        {/* Search form — credit/quota gating handled inside the form */}
        <TickerSearchForm />

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
