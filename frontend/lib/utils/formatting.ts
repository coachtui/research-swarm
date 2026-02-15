// Utility functions for formatting data in DVRG frontend

/**
 * Format moat score to grade (A+, B, C, etc.)
 */
export function scoreToGrade(score: number): string {
  if (score >= 9.0) return 'A+'
  if (score >= 8.0) return 'A'
  if (score >= 7.0) return 'A-'
  if (score >= 6.0) return 'B+'
  if (score >= 5.0) return 'B'
  if (score >= 4.0) return 'B-'
  if (score >= 3.0) return 'C'
  return 'D'
}

/**
 * Format score to rating (Strong Buy, Buy, Hold, Sell, Strong Sell)
 */
export function scoreToRating(score: number): string {
  if (score >= 8.5) return 'Strong Buy'
  if (score >= 7.0) return 'Buy'
  if (score >= 5.0) return 'Hold'
  if (score >= 3.0) return 'Sell'
  return 'Strong Sell'
}

/**
 * Get color class for score (for Tailwind)
 */
export function scoreToColor(score: number): string {
  if (score >= 7.0) return 'text-success'
  if (score >= 4.0) return 'text-warning'
  return 'text-error'
}

/**
 * Get background color class for score
 */
export function scoreToBgColor(score: number): string {
  if (score >= 7.0) return 'bg-success/10 border-success/20'
  if (score >= 4.0) return 'bg-warning/10 border-warning/20'
  return 'bg-error/10 border-error/20'
}

/**
 * Format currency (USD)
 */
export function formatCurrency(amount: number, decimals = 2): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(amount)
}

/**
 * Format date to readable string
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(d)
}

/**
 * Format date with time
 */
export function formatDateTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(d)
}

/**
 * Format elapsed time (seconds to human readable)
 */
export function formatElapsedTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60

  if (minutes > 0) {
    return `${minutes}m ${secs}s`
  }
  return `${secs}s`
}

/**
 * Format remaining time estimate
 */
export function formatRemainingTime(
  estimatedMinutes: number,
  elapsedSeconds: number
): string {
  const totalSeconds = estimatedMinutes * 60
  const remaining = Math.max(0, totalSeconds - elapsedSeconds)
  return formatElapsedTime(remaining)
}

/**
 * Format percentage
 */
export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`
}

/**
 * Format large numbers (1.2M, 5.3K, etc.)
 */
export function formatCompactNumber(num: number): string {
  if (num >= 1_000_000_000) {
    return `${(num / 1_000_000_000).toFixed(1)}B`
  }
  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`
  }
  if (num >= 1_000) {
    return `${(num / 1_000).toFixed(1)}K`
  }
  return num.toString()
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

/**
 * Validate ticker format (1-10 uppercase letters)
 */
export function isValidTicker(ticker: string): boolean {
  return /^[A-Z]{1,10}$/.test(ticker)
}

/**
 * Format ticker to uppercase
 */
export function formatTicker(ticker: string): string {
  return ticker.trim().toUpperCase()
}
