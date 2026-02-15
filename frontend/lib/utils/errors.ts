// Error handling utilities for DVRG frontend

export const ERROR_MESSAGES = {
  // API Errors
  QUOTA_EXCEEDED: 'Monthly budget exceeded. Please upgrade to Pro for unlimited analyses.',
  ANALYSIS_FAILED: "Analysis failed. We've issued a full refund. Please try again.",
  TICKER_NOT_FOUND: 'Ticker not recognized. Please verify the symbol on Yahoo Finance.',
  NETWORK_ERROR: 'Connection lost. Please check your internet connection and try again.',
  UNAUTHORIZED: 'Please sign in to continue.',
  PAYMENT_REQUIRED: 'Payment required to continue. Complete checkout to proceed.',
  RATE_LIMIT: 'Too many requests. Please wait a moment and try again.',
  SERVER_ERROR: 'Server error. Our team has been notified. Please try again later.',
  UNKNOWN: 'Something went wrong. Our team has been notified.',

  // Validation Errors
  INVALID_TICKER: 'Please enter a valid ticker symbol (1-10 letters).',
  INVALID_EMAIL: 'Please enter a valid email address.',
  REQUIRED_FIELD: 'This field is required.',
} as const

export type ErrorCode = keyof typeof ERROR_MESSAGES

/**
 * Get user-friendly error message from API error
 */
export function getErrorMessage(error: unknown): string {
  if (!error) return ERROR_MESSAGES.UNKNOWN

  // Handle API errors with status codes
  if (typeof error === 'object' && 'status' in error) {
    const status = (error as any).status

    switch (status) {
      case 401:
        return ERROR_MESSAGES.UNAUTHORIZED
      case 402:
        return ERROR_MESSAGES.PAYMENT_REQUIRED
      case 404:
        return ERROR_MESSAGES.TICKER_NOT_FOUND
      case 429:
        return ERROR_MESSAGES.RATE_LIMIT
      case 500:
      case 502:
      case 503:
        return ERROR_MESSAGES.SERVER_ERROR
      case 0:
        return ERROR_MESSAGES.NETWORK_ERROR
    }

    // Check for specific error messages from API
    if ('message' in error) {
      const msg = (error as any).message.toLowerCase()

      if (msg.includes('quota') || msg.includes('budget')) {
        return ERROR_MESSAGES.QUOTA_EXCEEDED
      }
      if (msg.includes('ticker') || msg.includes('symbol')) {
        return ERROR_MESSAGES.TICKER_NOT_FOUND
      }
      if (msg.includes('failed') || msg.includes('error')) {
        return ERROR_MESSAGES.ANALYSIS_FAILED
      }

      // Return the API message if it's user-friendly
      return (error as any).message
    }
  }

  // Handle Error instances
  if (error instanceof Error) {
    return error.message
  }

  // Handle string errors
  if (typeof error === 'string') {
    return error
  }

  return ERROR_MESSAGES.UNKNOWN
}

/**
 * Check if error is retryable
 */
export function isRetryableError(error: unknown): boolean {
  if (typeof error === 'object' && error && 'status' in error) {
    const status = (error as any).status
    // Retry on network errors, rate limits, and server errors
    return status === 0 || status === 429 || status >= 500
  }
  return false
}

/**
 * Get suggested action for error
 */
export function getErrorAction(error: unknown): string | null {
  if (!error) return null

  if (typeof error === 'object' && 'status' in error) {
    const status = (error as any).status

    switch (status) {
      case 401:
        return 'Sign in to continue'
      case 402:
        return 'Complete checkout'
      case 404:
        return 'Verify ticker symbol'
      case 429:
        return 'Please wait a moment'
      case 0:
        return 'Check your connection'
      case 500:
      case 502:
      case 503:
        return 'Try again in a few minutes'
    }
  }

  return 'Try again'
}

/**
 * Log error to console (development) or error tracking service (production)
 */
export function logError(error: unknown, context?: Record<string, any>) {
  if (process.env.NODE_ENV === 'development') {
    console.error('[DVRG Error]', error, context)
  } else {
    // TODO: Send to error tracking service (Sentry, LogRocket, etc.)
    console.error('[DVRG Error]', error)
  }
}
