'use client'

import { useEffect, useState } from 'react'
import { formatElapsedTime, formatRemainingTime } from '@/lib/utils/formatting'

interface LoadingSpinnerProps {
  estimatedMinutes?: number
  startTime?: string
  currentStep?: string
}

export function LoadingSpinner({
  estimatedMinutes = 4,
  startTime,
  currentStep = 'Initializing...',
}: LoadingSpinnerProps) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!startTime) return

    const start = new Date(startTime).getTime()
    const interval = setInterval(() => {
      const now = Date.now()
      const diff = Math.floor((now - start) / 1000)
      setElapsed(diff)
    }, 1000)

    return () => clearInterval(interval)
  }, [startTime])

  const progress = Math.min((elapsed / (estimatedMinutes * 60)) * 100, 95)
  const remaining = formatRemainingTime(estimatedMinutes, elapsed)

  return (
    <div className="flex flex-col items-center justify-center space-y-6 py-12">
      {/* Spinner */}
      <div className="relative">
        <div className="w-20 h-20 border-4 border-surface-elevated rounded-full"></div>
        <div className="absolute top-0 left-0 w-20 h-20 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
        <div className="absolute top-0 left-0 w-20 h-20 flex items-center justify-center">
          <div className="w-12 h-12 bg-primary/20 rounded-full animate-pulse"></div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full max-w-md space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-text-secondary">{formatElapsedTime(elapsed)} elapsed</span>
          <span className="text-text-secondary">~{remaining} remaining</span>
        </div>
        <div className="h-2 bg-surface-elevated rounded-full overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
        <div className="text-center text-sm text-text-tertiary">
          {progress.toFixed(0)}% complete
        </div>
      </div>

      {/* Status */}
      <div className="text-center space-y-2">
        <p className="text-lg text-text-primary font-medium">{currentStep}</p>
        <p className="text-sm text-text-secondary max-w-md">
          We're analyzing 13+ data sources including SEC filings, news sentiment,
          institutional holdings, and technical indicators.
        </p>
      </div>

      {/* Steps */}
      <div className="space-y-2 text-sm max-w-md w-full">
        {[
          { label: 'Analyzing SEC filings & financials', done: elapsed > 60 },
          { label: 'Processing news & sentiment (13 sources)', done: elapsed > 120 },
          { label: 'Running technical analysis', done: elapsed > 180 },
          { label: 'Synthesizing insights & scoring', done: elapsed > 210 },
        ].map((step, i) => (
          <div key={i} className="flex items-center space-x-2">
            {step.done ? (
              <span className="text-primary">✓</span>
            ) : elapsed > i * 60 ? (
              <span className="text-primary animate-pulse">⏳</span>
            ) : (
              <span className="text-text-tertiary">○</span>
            )}
            <span className={step.done ? 'text-text-secondary line-through' : 'text-text-secondary'}>
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {/* Disclaimer */}
      <p className="text-xs text-text-tertiary text-center max-w-md">
        Analysis typically takes 3-5 minutes. This page will automatically update when complete.
      </p>
    </div>
  )
}
