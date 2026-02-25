'use client'

import { useState } from 'react'
import Link from 'next/link'
import { FileDown, Lock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useCurrentUser } from '@/lib/hooks/useCurrentUser'
import { canAccessFeature } from '@/lib/entitlements'

interface DownloadPDFButtonProps {
  runId: string
  /**
   * One or more ticker symbols — used for the local filename fallback.
   * Pass all tickers for a multi-stock run so the filename is descriptive.
   */
  tickers: string | string[]
}

/**
 * DownloadPDFButton
 *
 * Renders one of three states based on the user's subscription tier:
 *
 *   Starter   → Disabled "Export PDF" button with lock icon + upgrade link
 *               (clicking navigates to /#pricing rather than calling the API)
 *
 *   Investor  → Enabled "Download PDF" button (core sections, no trade table)
 *
 *   Trader    → Enabled "Download PDF" button (full report inc. trade setup)
 *
 * Entitlement is determined client-side from the cached /api/auth/me response.
 * The backend enforces the same check independently; a 403 from the API shows
 * an upgrade CTA toast rather than a generic error.
 */
export function DownloadPDFButton({ runId, tickers }: DownloadPDFButtonProps) {
  const [isLoading, setIsLoading] = useState(false)
  const { data: user, isLoading: userLoading } = useCurrentUser()

  const hasAccess = user
    ? (user.is_admin || canAccessFeature('export_pdf', user.tier))
    : false

  // Build a descriptive local filename from the provided tickers
  const tickerList = Array.isArray(tickers) ? tickers : [tickers]
  const tickerLabel = tickerList.slice(0, 3).join('_') + (tickerList.length > 3 ? `_+${tickerList.length - 3}` : '')
  const localFilename = `report_${tickerLabel}_${runId.slice(0, 8)}.pdf`

  const handleDownload = async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`/api/proxy/runs/${runId}/report/pdf`)

      // Backend returned 403 — show upgrade CTA regardless of client-side check
      if (response.status === 403) {
        const body = await response.json().catch(() => ({}))
        if (body?.code === 'NOT_ENTITLED') {
          window.location.href = '/#pricing'
          return
        }
        throw new Error('Access denied')
      }

      if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'PDF generation failed' }))
        throw new Error(error.detail?.message || error.detail || error.error || 'Failed to generate PDF')
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = localFilename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Failed to download PDF. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  // ── Still loading user data — render a neutral skeleton button ────────────
  if (userLoading) {
    return (
      <Button size="sm" disabled className="opacity-50">
        <FileDown className="w-4 h-4 mr-1.5" />
        PDF
      </Button>
    )
  }

  // ── Starter tier or unauthenticated — show locked upgrade prompt ──────────
  if (!hasAccess) {
    return (
      <Link href="/#pricing">
        <Button
          size="sm"
          variant="outline"
          className="border-border text-text-secondary hover:border-[#00D9B5] hover:text-[#00D9B5] transition-colors"
          title="Upgrade to Investor to export PDFs"
        >
          <Lock className="w-3.5 h-3.5 mr-1.5 text-text-tertiary" />
          PDF
          <span className="ml-1.5 text-[10px] font-semibold uppercase tracking-wide bg-surface-elevated text-text-tertiary px-1 py-0.5 rounded">
            Investor
          </span>
        </Button>
      </Link>
    )
  }

  // ── Investor / Trader — enabled download ───────────────────────────────────
  return (
    <Button
      onClick={handleDownload}
      disabled={isLoading}
      size="sm"
    >
      {isLoading ? (
        <>
          <svg
            className="w-4 h-4 mr-1.5 animate-spin"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Generating…
        </>
      ) : (
        <>
          <FileDown className="w-4 h-4 mr-1.5" />
          PDF Report
        </>
      )}
    </Button>
  )
}
