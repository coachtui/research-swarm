'use client'

// Sticky command bar — shown at the top of every report page.
// Contains: ticker · price · timestamp (left) and PDF export · reading-mode
// toggle · watchlist (right).
// Everything else (EV, allocation, conviction) lives in the scrollable content.

import { useState } from 'react'
import { FileText, Loader2 } from 'lucide-react'
import { AddToWatchlistButton } from '@/components/dashboard/AddToWatchlistButton'
import { StockLogo } from '@/components/ui/stock-logo'
import { formatDateTime } from '@/lib/utils/formatting'
import { apiClient } from '@/lib/api/client'

interface ReportCommandBarProps {
  ticker: string
  price: number | null
  timestamp: string
  runId: string
  companyName?: string
  dvrgMode?: string | null
}

export function ReportCommandBar({
  ticker,
  price,
  timestamp,
  runId,
  companyName,
  dvrgMode,
}: ReportCommandBarProps) {
  const hasDvrgMode = !!dvrgMode
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState(false)

  // The API has served GET /runs/{id}/report/pdf since the reports route
  // shipped — but nothing in the UI ever called it, so users had no way to
  // export or print. This button closes that last inch: fetch as a blob
  // (auth header required, so a plain <a href> cannot work in production)
  // and hand it to the browser as a download.
  const handleExportPdf = async () => {
    if (exporting) return
    setExporting(true)
    setExportError(false)
    try {
      const blob = await apiClient.downloadPdfReport(runId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `DVRG_Research_Note_${ticker}_${timestamp.slice(0, 10)}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      setExportError(true)
      setTimeout(() => setExportError(false), 4000)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div
      className={`sticky top-14 z-40 w-full border-b border-border/50 shadow-sm ${hasDvrgMode ? 'h-[5rem]' : 'h-[4.5rem]'}`}
      style={{ background: 'rgb(var(--bg-rgb) / 0.98)' }}
    >
      <div className="container mx-auto px-4 h-full">
        <div className={`max-w-6xl mx-auto ${hasDvrgMode ? 'h-[3.5rem]' : 'h-full'} flex items-center justify-between gap-4`}>

          {/* Left — logo · ticker · company · price · timestamp */}
          <div className="flex flex-col justify-center min-w-0 flex-1">
            <div className="flex items-center gap-3 min-w-0">
              <StockLogo ticker={ticker} size="md" />
              <span className="text-xl font-bold font-mono text-text-primary tracking-widest uppercase flex-shrink-0">
                {ticker}
              </span>
              {companyName && (
                <>
                  <span className="text-border/50 select-none flex-shrink-0">·</span>
                  <span className="text-sm text-text-secondary truncate hidden sm:block">
                    {companyName}
                  </span>
                </>
              )}
              {price !== null && (
                <>
                  <span className="text-border/60 select-none flex-shrink-0 text-lg">|</span>
                  <span className="text-xl font-bold font-mono text-text-primary flex-shrink-0">
                    ${price.toFixed(2)}
                  </span>
                </>
              )}
              <span className="text-[11px] text-text-tertiary/60 font-mono truncate hidden lg:block">
                {formatDateTime(timestamp)}
              </span>
            </div>
            {dvrgMode && (
              <p className="text-[10px] text-text-tertiary italic font-mono truncate hidden sm:block mt-0.5">
                DVRG Mode: {dvrgMode}
              </p>
            )}
          </div>

          {/* Right — PDF export · reading mode toggle · watchlist */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* The PDF is the product's flagship deliverable, not a utility
                export — style it as the primary action of the page. */}
            <button
              onClick={handleExportPdf}
              disabled={exporting}
              className={`flex items-center gap-1.5 text-xs font-semibold rounded-md px-3 py-1.5 transition-colors ${
                exportError
                  ? 'text-error border border-error/40'
                  : 'bg-primary text-white hover:bg-primary/90'
              } ${exporting ? 'opacity-70 cursor-wait' : ''}`}
              title="Download the full research note (PDF)"
            >
              {exporting
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <FileText className="h-3.5 w-3.5" />}
              <span className="hidden sm:inline">
                {exportError ? 'Download failed' : exporting ? 'Preparing note…' : 'Research Note'}
              </span>
              <span className="sm:hidden">PDF</span>
            </button>
            <AddToWatchlistButton
              ticker={ticker}
              companyName={companyName}
              runId={runId}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
