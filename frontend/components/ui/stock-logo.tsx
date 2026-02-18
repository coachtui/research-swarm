'use client'

import { cn } from '@/lib/utils/cn'

interface StockLogoProps {
  ticker: string
  companyName?: string | null
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizeClasses = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-12 w-12 text-base',
}

/**
 * Stock logo component with fallback to ticker initial
 * Uses Parqet Logo API (same as results page)
 */
export function StockLogo({ ticker, companyName, size = 'md', className }: StockLogoProps) {
  const initial = ticker.charAt(0).toUpperCase()
  const logoUrl = `https://assets.parqet.com/logos/symbol/${ticker.toUpperCase()}`

  return (
    <div
      className={cn(
        'relative rounded-md bg-surface-elevated border border-border-subtle overflow-hidden flex-shrink-0',
        sizeClasses[size],
        className
      )}
      title={companyName || ticker}
    >
      <img
        src={logoUrl}
        alt={`${ticker} logo`}
        className="w-full h-full object-contain p-1.5"
        onError={(e) => {
          // Fallback to ticker initial if logo fails
          const target = e.target as HTMLImageElement
          target.style.display = 'none'
          const fallback = target.nextElementSibling as HTMLDivElement
          if (fallback) fallback.style.display = 'flex'
        }}
      />
      <div className="absolute inset-0 items-center justify-center bg-surface-elevated text-text-secondary font-bold hidden">
        {initial}
      </div>
    </div>
  )
}
