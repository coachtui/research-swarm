'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useSubmitAnalysis } from '@/lib/hooks/useAnalysis'
import { formatTicker, isValidTicker } from '@/lib/utils/formatting'
import { getErrorMessage } from '@/lib/utils/errors'
import { apiClient } from '@/lib/api/client'

const formSchema = z.object({
  ticker: z
    .string()
    .min(1, 'Ticker is required')
    .max(10, 'Ticker must be 10 characters or less')
    .transform((val) => formatTicker(val))
    .refine((val) => isValidTicker(val), {
      message: 'Please enter a valid ticker symbol (letters only)',
    }),
  newsDaysBack: z.number().min(1).max(90).default(30),
})

type FormData = z.infer<typeof formSchema>

export function TickerSearchForm() {
  const router = useRouter()
  const { getToken } = useAuth()
  const [serverError, setServerError] = useState<string | null>(null)
  const submitAnalysis = useSubmitAnalysis()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    watch,
  } = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      ticker: '',
      newsDaysBack: 30,
    },
  })

  const ticker = watch('ticker')

  const onSubmit = async (data: FormData) => {
    setServerError(null)

    try {
      // Get auth token from Clerk and set it on API client
      const token = await getToken()
      if (!token) {
        throw new Error('Not authenticated. Please sign in.')
      }
      apiClient.setAuthToken(token)

      const response = await submitAnalysis.mutateAsync({
        ticker: data.ticker,
        news_days_back: data.newsDaysBack,
      })

      // Redirect to results page with polling
      router.push(`/results/${response.run_id}`)
    } catch (error) {
      setServerError(getErrorMessage(error))
    }
  }

  return (
    <Card className="max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle>Analyze a Stock</CardTitle>
        <CardDescription>
          Enter a ticker symbol to get institutional-quality analysis in ~4 minutes
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Ticker Input */}
          <div className="space-y-2">
            <Label htmlFor="ticker">
              Stock Ticker <span className="text-error">*</span>
            </Label>
            <Input
              id="ticker"
              placeholder="e.g., NVDA, AAPL, MSFT"
              autoComplete="off"
              autoFocus
              {...register('ticker')}
              className={`uppercase ${errors.ticker ? 'border-error focus-visible:ring-error' : ''}`}
            />
            {errors.ticker && (
              <p className="text-sm text-error">{errors.ticker.message}</p>
            )}
            <p className="text-xs text-text-tertiary">
              We support US stocks and foreign ADRs (e.g., TSM, BABA)
            </p>
          </div>

          {/* News Lookback Slider */}
          <div className="space-y-2">
            <Label htmlFor="newsDaysBack">
              News Lookback: {watch('newsDaysBack')} days
            </Label>
            <input
              id="newsDaysBack"
              type="range"
              min="1"
              max="90"
              {...register('newsDaysBack', { valueAsNumber: true })}
              className="w-full h-2 bg-surface-elevated rounded-lg appearance-none cursor-pointer accent-primary"
            />
            <div className="flex justify-between text-xs text-text-tertiary">
              <span>1 day</span>
              <span>90 days</span>
            </div>
          </div>

          {/* Server Error */}
          {serverError && (
            <div className="p-3 rounded-button bg-error/10 border border-error/20">
              <p className="text-sm text-error">{serverError}</p>
            </div>
          )}

          {/* What's Included */}
          <div className="rounded-button bg-surface-elevated p-4 space-y-2">
            <h4 className="font-semibold text-sm text-text-primary">Your analysis will include:</h4>
            <ul className="space-y-1 text-sm text-text-secondary">
              <li className="flex items-start">
                <span className="text-primary mr-2">✓</span>
                <span>Moat score breakdown (5 components)</span>
              </li>
              <li className="flex items-start">
                <span className="text-primary mr-2">✓</span>
                <span>Investment thesis & key insights</span>
              </li>
              <li className="flex items-start">
                <span className="text-primary mr-2">✓</span>
                <span>VGM score (Value/Growth/Momentum)</span>
              </li>
              <li className="flex items-start">
                <span className="text-primary mr-2">✓</span>
                <span>Price targets with scenarios (Bull/Base/Bear)</span>
              </li>
              <li className="flex items-start">
                <span className="text-primary mr-2">✓</span>
                <span>Signal divergence detection</span>
              </li>
              <li className="flex items-start">
                <span className="text-primary mr-2">✓</span>
                <span>Peer comparison & competitive position</span>
              </li>
            </ul>
          </div>

          {/* Submit Button */}
          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                Submitting...
              </>
            ) : (
              <>Analyze {ticker ? ticker.toUpperCase() : 'Stock'}</>
            )}
          </Button>

          <p className="text-xs text-center text-text-tertiary">
            Analysis typically takes 3-5 minutes
          </p>
        </form>
      </CardContent>
    </Card>
  )
}
