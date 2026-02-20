'use client'

import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, Settings } from 'lucide-react'
import { TradeSetup } from './TradeSetup'
import { PortfolioContext } from './PortfolioContext'
import type { EnhancedTradeSetup, RecommendedStrategy, ConvictionPosition, SignalBreakdown, FairValueCalibration } from '@/types/api'

const STORAGE_KEY = 'dvrg_execution_layer_expanded'

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

type ActiveTab = 'sizing' | 'setup'

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
  const [activeTab, setActiveTab] = useState<ActiveTab>('sizing')

  // Persist expanded state
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'true') setExpanded(true)
  }, [])

  const toggle = () => {
    const next = !expanded
    setExpanded(next)
    localStorage.setItem(STORAGE_KEY, String(next))
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
          <span className="text-xs text-text-tertiary">— For active traders &amp; position sizing</span>
        </div>
        {expanded
          ? <ChevronUp className="h-4 w-4 text-text-tertiary flex-shrink-0" />
          : <ChevronDown className="h-4 w-4 text-text-tertiary flex-shrink-0" />
        }
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-border">
          {/* Tab bar */}
          <div className="flex border-b border-border px-5 bg-surface">
            <button
              onClick={() => setActiveTab('sizing')}
              className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
                activeTab === 'sizing'
                  ? 'border-primary text-text-primary'
                  : 'border-transparent text-text-tertiary hover:text-text-secondary'
              }`}
            >
              Position Sizing
            </button>
            {enhancedTradeSetup && (
              <button
                onClick={() => setActiveTab('setup')}
                className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
                  activeTab === 'setup'
                    ? 'border-primary text-text-primary'
                    : 'border-transparent text-text-tertiary hover:text-text-secondary'
                }`}
              >
                Entry / Exit Setup
              </button>
            )}
          </div>

          <div className="p-5">
            {activeTab === 'sizing' && (
              <PortfolioContext
                ticker={ticker}
                rating={rating}
                moatScore={moatScore}
                financialHealthScore={financialHealthScore}
                sector={sector}
                currentPrice={currentPrice}
                convictionPosition={convictionPosition}
              />
            )}
            {activeTab === 'setup' && enhancedTradeSetup && (
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
            )}
          </div>
        </div>
      )}
    </div>
  )
}
