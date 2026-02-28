'use client'

// Sticky command bar — shown at the top of every report page.
// Contains: ticker · price · timestamp (left) and mode toggle · watchlist (right).
// Everything else (EV, allocation, conviction) lives in the scrollable content.

import { AddToWatchlistButton } from '@/components/dashboard/AddToWatchlistButton'
import { ModeToggle, type ReportMode } from '@/components/results/ModeToggle'
import { formatDateTime } from '@/lib/utils/formatting'

interface ReportCommandBarProps {
  ticker: string
  price: number | null
  timestamp: string
  runId: string
  companyName?: string
  mode: ReportMode
  onModeChange: (m: ReportMode) => void
  isReadingMode?: boolean
  onToggleReadingMode?: () => void
}

export function ReportCommandBar({
  ticker,
  price,
  timestamp,
  runId,
  companyName,
  mode,
  onModeChange,
  isReadingMode,
  onToggleReadingMode,
}: ReportCommandBarProps) {
  return (
    <div
      className="sticky top-14 z-40 h-16 w-full border-b border-border/50 shadow-sm"
      style={{ background: 'rgb(var(--bg-rgb) / 0.98)' }}
    >
      <div className="container mx-auto px-4 h-full">
        <div className="max-w-6xl mx-auto h-full flex items-center justify-between gap-4">

          {/* Left — ticker · price · timestamp */}
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-sm font-bold font-mono text-text-primary tracking-widest uppercase flex-shrink-0">
              {ticker}
            </span>
            {price !== null && (
              <>
                <span className="text-border/50 select-none flex-shrink-0">|</span>
                <span className="text-sm font-semibold font-mono text-text-primary flex-shrink-0">
                  ${price.toFixed(2)}
                </span>
              </>
            )}
            <span className="text-[11px] text-text-tertiary/60 font-mono truncate hidden sm:block">
              {formatDateTime(timestamp)}
            </span>
          </div>

          {/* Right — mode toggle · watchlist */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <ModeToggle mode={mode} onChange={onModeChange} />
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
