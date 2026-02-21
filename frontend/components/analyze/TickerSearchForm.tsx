'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useSubmitAnalysis } from '@/lib/hooks/useAnalysis'
import { useQuota } from '@/lib/hooks/useQuota'
import { formatTicker, isValidTicker } from '@/lib/utils/formatting'
import { apiClient } from '@/lib/api/client'
import { Zap, TrendingUp } from 'lucide-react'

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

function OutOfAnalysesPanel({ boostEligible, boostAnalysesAdded, daysRemaining }: {
  boostEligible: boolean
  boostAnalysesAdded: number
  daysRemaining: number
}) {
  const router = useRouter()
  const [boostLoading, setBoostLoading] = useState(false)
  const [boostError, setBoostError] = useState<string | null>(null)

  const handleBoost = async () => {
    setBoostLoading(true)
    setBoostError(null)
    try {
      const result = await apiClient.createBoostSession()
      window.location.href = result.checkout_url
    } catch {
      setBoostError('Could not start boost purchase. Please try again.')
    } finally {
      setBoostLoading(false)
    }
  }

  return (
    <div className="rounded-lg border border-error/30 bg-error/5 p-4 space-y-3">
      <div>
        <p className="text-sm font-semibold text-text-primary">Out of Analyses</p>
        <p className="text-xs text-text-secondary mt-0.5">
          You&apos;ve used all your analyses this period.{' '}
          {daysRemaining > 0 ? `Resets in ${daysRemaining} day${daysRemaining !== 1 ? 's' : ''}.` : 'Resets soon.'}
        </p>
      </div>

      <div className="flex flex-col gap-2">
        {boostEligible && (
          <button
            onClick={handleBoost}
            disabled={boostLoading}
            className="flex items-center justify-center gap-2 w-full py-2 px-3 bg-warning/10 border border-warning/30 text-warning hover:bg-warning/20 rounded-md text-sm font-medium transition-colors disabled:opacity-50"
          >
            <Zap className="h-3.5 w-3.5" />
            {boostLoading ? 'Loading...' : 'Buy Boost — $9.99 (adds 5 analyses)'}
          </button>
        )}
        <button
          onClick={() => router.push('/#pricing-tiers')}
          className="flex items-center justify-center gap-2 w-full py-2 px-3 border border-primary/30 text-primary hover:bg-primary/5 rounded-md text-sm font-medium transition-colors"
        >
          <TrendingUp className="h-3.5 w-3.5" />
          Upgrade Plan
        </button>
      </div>

      {boostError && <p className="text-xs text-error">{boostError}</p>}

      {boostEligible && boostAnalysesAdded > 0 && (
        <p className="text-xs text-text-tertiary">
          You already have {boostAnalysesAdded} boost analyses active — they&apos;ll appear after page refresh.
        </p>
      )}
    </div>
  )
}

export function TickerSearchForm() {
  const router = useRouter()
  const [serverError, setServerError] = useState<string | null>(null)
  const [showOutOfAnalyses, setShowOutOfAnalyses] = useState(false)
  const submitAnalysis = useSubmitAnalysis()
  const { data: quota } = useQuota()

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

  // Pre-flight quota check
  const isAtLimit = quota ? quota.analyses_remaining === 0 : false

  const onSubmit = async (data: FormData) => {
    setServerError(null)
    setShowOutOfAnalyses(false)

    try {
      const response = await submitAnalysis.mutateAsync({
        ticker: data.ticker,
        news_days_back: data.newsDaysBack,
      })
      router.push(`/results/${response.run_id}`)
    } catch (error: any) {
      // 402 = quota exceeded — show boost/upgrade UI
      if (error?.status === 402) {
        setShowOutOfAnalyses(true)
      } else {
        setServerError(error?.message || 'Something went wrong. Please try again.')
      }
    }
  }

  const buttonLabel = () => {
    if (isAtLimit) return 'Out of Analyses'
    if (isSubmitting) return 'Submitting...'
    return `Analyze ${ticker ? ticker.toUpperCase() : 'Stock'}`
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

          {/* Out of Analyses — shown pre-flight (quota check) or after 402 */}
          {(isAtLimit || showOutOfAnalyses) && quota ? (
            <OutOfAnalysesPanel
              boostEligible={quota.boost_eligible ?? false}
              boostAnalysesAdded={quota.boost_analyses_added ?? 0}
              daysRemaining={quota.days_remaining ?? 0}
            />
          ) : serverError ? (
            <div className="p-3 rounded-button bg-error/10 border border-error/20">
              <p className="text-sm text-error">{serverError}</p>
            </div>
          ) : null}

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
            disabled={isSubmitting || isAtLimit}
            variant={isAtLimit ? 'outline' : 'primary'}
          >
            {isSubmitting ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-3 h-5 w-5"
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
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Submitting...
              </>
            ) : (
              buttonLabel()
            )}
          </Button>

          {/* Quota indicator — show remaining count when near limit */}
          {quota && !isAtLimit && quota.analyses_remaining <= 3 && (
            <p className="text-xs text-center text-warning">
              {quota.analyses_remaining} analysis{quota.analyses_remaining !== 1 ? 'ses' : ''} remaining this period
            </p>
          )}

          {!isAtLimit && (
            <p className="text-xs text-center text-text-tertiary">
              Analysis typically takes 3-5 minutes
            </p>
          )}
        </form>
      </CardContent>
    </Card>
  )
}
