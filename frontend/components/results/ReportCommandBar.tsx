'use client'

// Sticky command bar — shown at the top of every report page.
// Contains: ticker · price · timestamp (left) and reading-mode toggle · watchlist (right).
// Everything else (EV, allocation, conviction) lives in the scrollable content.

import { AddToWatchlistButton } from '@/components/dashboard/AddToWatchlistButton'
import { StockLogo } from '@/components/ui/stock-logo'
import { formatDateTime } from '@/lib/utils/formatting'

interface ReportCommandBarProps {
  ticker: string
  price: number | null
  timestamp: string
  runId: string
  companyName?: string
  isReadingMode?: boolean
  onToggleReadingMode?: () => void
  dvrgMode?: string | null
}

export function ReportCommandBar({
  ticker,
  price,
  timestamp,
  runId,
  companyName,
  isReadingMode,
  onToggleReadingMode,
  dvrgMode,
}: ReportCommandBarProps) {
  const hasDvrgMode = !!dvrgMode
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

          {/* Right — reading mode toggle · watchlist */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {onToggleReadingMode && (
              <button
                onClick={onToggleReadingMode}
                className={`text-[10px] font-mono border rounded px-1.5 py-0.5 transition-colors hidden sm:block ${
                  isReadingMode
                    ? 'bg-primary/10 text-primary border-primary/30'
                    : 'text-text-tertiary border-border hover:text-text-secondary'
                }`}
                title="Toggle Reading Mode (R)"
              >
                {isReadingMode ? 'EXIT' : '[R]'}
              </button>
            )}
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
