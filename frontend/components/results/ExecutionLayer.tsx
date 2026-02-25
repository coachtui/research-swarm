'use client'

import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, Settings } from 'lucide-react'
import { TradeSetup } from './TradeSetup'
import { PortfolioContext } from './PortfolioContext'
import { PositionSizingCard } from './PositionSizingCard'
import { FinalWeightResolver } from './FinalWeightResolver'
import type { EnhancedTradeSetup, RecommendedStrategy, ConvictionPosition, SignalBreakdown, FairValueCalibration } from '@/types/api'

const STORAGE_KEY = 'dvrg_execution_layer_expanded'
const VIEW_MODE_KEY = 'dvrg_execution_view_mode'

interface ExecutionLayerProps {
  ticker: string
  rating: string
  moatScore: number
  financialHealthScore?: number
  sector?: string
  currentPrice: number
  convictionPosition?: ConvictionPosition | null
  enhancedTradeSetup?: EnhancedTradeSetup | null
  strategy?: RecommendedStrategy | null
  signalBreakdown?: SignalBreakdown | null
  calibration?: FairValueCalibration | null
}

type ViewMode = 'pm' | 'trader'

export function ExecutionLayer({
  ticker,
  rating,
  moatScore,
  financialHealthScore,
  sector,
  currentPrice,
  convictionPosition,
  enhancedTradeSetup,
  strategy,
  signalBreakdown,
  calibration,
}: ExecutionLayerProps) {
  const [expanded, setExpanded] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('pm')

  useEffect(() => {
    const storedExpanded = localStorage.getItem(STORAGE_KEY)
    if (storedExpanded === 'true') setExpanded(true)

    const storedMode = localStorage.getItem(VIEW_MODE_KEY) as ViewMode | null
    if (storedMode === 'pm' || storedMode === 'trader') setViewMode(storedMode)
  }, [])

  const toggle = () => {
    const next = !expanded
    setExpanded(next)
    localStorage.setItem(STORAGE_KEY, String(next))
  }

  const setMode = (mode: ViewMode) => {
    setViewMode(mode)
    localStorage.setItem(VIEW_MODE_KEY, mode)
  }

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      {/* Collapsed header — always visible */}
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between px-5 py-4 bg-surface hover:bg-surface-elevated transition-colors text-left"
      >
        <div className="flex items-center gap-2.5">
          <Settings className="h-4 w-4 text-text-tertiary" />
          <span className="text-sm font-medium text-text-primary">Trade Setup &amp; Position Sizing</span>
          <span className="text-xs text-text-tertiary hidden sm:inline">— Execution detail</span>
        </div>
        {expanded
          ? <ChevronUp className="h-4 w-4 text-text-tertiary flex-shrink-0" />
          : <ChevronDown className="h-4 w-4 text-text-tertiary flex-shrink-0" />
        }
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-border">

          {/* ── Audience View Toggle ─────────────────────────────────────
              Portfolio Manager View: simplified allocation guidance.
              Trader / Tactical View: full asymmetry math, entry/exit setup. */}
          <div className="flex items-center justify-between px-5 py-3 bg-surface-elevated/50 border-b border-border/60">
            <span className="text-[11px] text-text-tertiary uppercase tracking-wide font-semibold">View Mode</span>
            <div className="flex items-center rounded-md border border-border overflow-hidden text-xs">
              <button
                onClick={() => setMode('pm')}
                className={`px-3 py-1.5 font-medium transition-colors ${
                  viewMode === 'pm'
                    ? 'bg-primary text-white'
                    : 'bg-surface text-text-tertiary hover:text-text-secondary'
                }`}
              >
                Portfolio Manager
              </button>
              <button
                onClick={() => setMode('trader')}
                className={`px-3 py-1.5 font-medium transition-colors border-l border-border ${
                  viewMode === 'trader'
                    ? 'bg-primary text-white'
                    : 'bg-surface text-text-tertiary hover:text-text-secondary'
                }`}
              >
                Trader / Tactical
              </button>
            </div>
          </div>

          {/* ── PM View: position sizing / allocation guidance ────────── */}
          {viewMode === 'pm' && (
            <div className="p-5 space-y-4">
              <PortfolioContext
                ticker={ticker}
                rating={rating}
                moatScore={moatScore}
                financialHealthScore={financialHealthScore}
                sector={sector}
                currentPrice={currentPrice}
                convictionPosition={convictionPosition}
                signalBreakdown={signalBreakdown}
              />
              <PositionSizingCard
                ticker={ticker}
                signalBreakdown={signalBreakdown}
                convictionPosition={convictionPosition}
              />
              <FinalWeightResolver
                ticker={ticker}
                rating={rating}
                signalBreakdown={signalBreakdown}
                convictionPosition={convictionPosition}
              />
              {enhancedTradeSetup && (
                <p className="text-[11px] text-text-tertiary italic border-t border-border/40 pt-3">
                  Switch to <span className="font-medium text-text-secondary">Trader / Tactical</span> view for detailed entry levels, stop placement, target tiers, and asymmetry analysis.
                </p>
              )}
            </div>
          )}

          {/* ── Trader View: entry/exit setup ────────────────────────── */}
          {viewMode === 'trader' && (
            <div className="p-5">
              {enhancedTradeSetup ? (
                <TradeSetup
                  setup={enhancedTradeSetup}
                  ticker={ticker}
                  strategy={strategy}
                  signalBreakdown={signalBreakdown}
                  rating={rating}
                  currentPrice={currentPrice}
                  calibration={calibration}
                  financialHealthScore={financialHealthScore}
                />
              ) : (
                <p className="text-sm text-text-tertiary italic">
                  No tactical entry/exit data available for this analysis.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
