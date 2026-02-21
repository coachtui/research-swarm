'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useRouter } from 'next/navigation'
import { CheckCircle2, Zap, AlertTriangle, X } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import type { QuotaData } from '@/types/api'

const STARTER_PRICE_ID = process.env.NEXT_PUBLIC_STRIPE_STARTER_PRICE_ID!
const INVESTOR_PRICE_ID = process.env.NEXT_PUBLIC_STRIPE_INVESTOR_PRICE_ID!
const TRADER_PRICE_ID = process.env.NEXT_PUBLIC_STRIPE_TRADER_PRICE_ID!

interface PricingCardsProps {
  quota?: QuotaData
}

interface BoostWarningModalProps {
  daysRemaining: number
  billingPeriodEnd: string
  onContinue: () => void
  onUpgrade: () => void
  onCancel: () => void
}

function BoostWarningModal({ daysRemaining, billingPeriodEnd, onContinue, onUpgrade, onCancel }: BoostWarningModalProps) {
  const expiryDate = billingPeriodEnd
    ? new Date(billingPeriodEnd).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
    : 'end of billing period'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-surface border border-surface-elevated rounded-xl p-6 max-w-md mx-4 shadow-2xl">
        <div className="flex items-start gap-3 mb-4">
          <AlertTriangle className="h-5 w-5 text-warning mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <h3 className="font-semibold text-text-primary text-lg">
              Billing period ends in {daysRemaining} day{daysRemaining !== 1 ? 's' : ''}
            </h3>
            <p className="text-sm text-text-secondary mt-1">
              Unused analyses expire on {expiryDate}. This Boost adds 5 analyses to your current
              period only — they won&apos;t roll over.
            </p>
          </div>
          <button onClick={onCancel} className="text-text-tertiary hover:text-text-primary flex-shrink-0">
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="text-sm text-text-secondary mb-5">
          Consider upgrading to a higher tier for more analyses every month instead.
        </p>

        <div className="flex flex-col gap-2">
          <button
            onClick={onContinue}
            className="w-full py-2.5 px-4 bg-primary text-white rounded-lg font-medium text-sm hover:bg-primary/90 transition-colors"
          >
            Continue with Boost ($9.99)
          </button>
          <button
            onClick={onUpgrade}
            className="w-full py-2.5 px-4 border border-surface-elevated text-text-primary rounded-lg font-medium text-sm hover:bg-surface-elevated transition-colors"
          >
            Upgrade Plan Instead
          </button>
          <button
            onClick={onCancel}
            className="w-full py-2.5 px-4 text-text-tertiary rounded-lg text-sm hover:text-text-secondary transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

export function PricingCards({ quota }: PricingCardsProps) {
  const { isSignedIn } = useAuth()
  const router = useRouter()
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null)
  const [boostLoading, setBoostLoading] = useState(false)
  const [showBoostWarning, setShowBoostWarning] = useState(false)
  const [boostCheckoutUrl, setBoostCheckoutUrl] = useState<string | null>(null)
  const [boostDaysRemaining, setBoostDaysRemaining] = useState(0)

  const handleSubscribe = async (priceId: string, planName: string) => {
    if (!isSignedIn) {
      router.push('/sign-up')
      return
    }
    setLoadingPlan(planName)
    try {
      const { checkout_url } = await apiClient.createCheckoutSession(priceId)
      window.location.href = checkout_url
    } catch (err) {
      console.error('Checkout error:', err)
    } finally {
      setLoadingPlan(null)
    }
  }

  const handleBoost = async () => {
    setBoostLoading(true)
    try {
      const result = await apiClient.createBoostSession()
      if (result.warn_expiry) {
        setBoostDaysRemaining(result.days_remaining ?? 0)
        setBoostCheckoutUrl(result.checkout_url)
        setShowBoostWarning(true)
      } else {
        window.location.href = result.checkout_url
      }
    } catch (err) {
      console.error('Boost error:', err)
    } finally {
      setBoostLoading(false)
    }
  }

  const handleBoostWarningContinue = () => {
    if (boostCheckoutUrl) window.location.href = boostCheckoutUrl
    setShowBoostWarning(false)
  }

  const handleBoostWarningUpgrade = () => {
    setShowBoostWarning(false)
    document.getElementById('pricing-tiers')?.scrollIntoView({ behavior: 'smooth' })
  }

  const plans = [
    {
      name: 'Starter',
      price: '$19.99',
      analyses: 5,
      priceId: STARTER_PRICE_ID,
      description: 'For investors getting started with AI research',
      perReport: '$4.00',
      popular: false,
    },
    {
      name: 'Investor',
      price: '$39.99',
      analyses: 15,
      priceId: INVESTOR_PRICE_ID,
      description: 'For active investors who analyze regularly',
      perReport: '$2.67',
      popular: true,
    },
    {
      name: 'Trader',
      price: '$99.99',
      analyses: 50,
      priceId: TRADER_PRICE_ID,
      description: 'For professional traders and power users',
      perReport: '$2.00',
      popular: false,
    },
  ]

  const features = [
    'Institutional-quality analysis',
    'Moat score + signal breakdown',
    'Structured investment thesis',
    'Strategic catalysts analysis',
    'PDF report export',
    'Unlimited watchlist tracking',
  ]

  return (
    <div id="pricing-tiers">
      {showBoostWarning && (
        <BoostWarningModal
          daysRemaining={boostDaysRemaining}
          billingPeriodEnd={quota?.billing_period_end ?? ''}
          onContinue={handleBoostWarningContinue}
          onUpgrade={handleBoostWarningUpgrade}
          onCancel={() => setShowBoostWarning(false)}
        />
      )}

      <p className="text-center text-sm text-text-secondary mb-8">
        All tiers receive identical analysis quality — only quantity per month differs.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
        {plans.map((plan) => (
          <div
            key={plan.name}
            className={`relative rounded-xl border p-6 flex flex-col ${
              plan.popular
                ? 'border-primary bg-primary/5 shadow-lg shadow-primary/10'
                : 'border-surface-elevated bg-surface'
            }`}
          >
            {plan.popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="bg-primary text-white text-xs font-semibold px-3 py-1 rounded-full">
                  Most Popular
                </span>
              </div>
            )}

            <div className="mb-5">
              <h3 className="text-lg font-bold text-text-primary">{plan.name}</h3>
              <p className="text-sm text-text-secondary mt-1">{plan.description}</p>
              <div className="mt-4">
                <span className="text-4xl font-bold text-text-primary">{plan.price}</span>
                <span className="text-text-secondary text-sm ml-1">/month</span>
              </div>
              <p className="text-xs text-text-tertiary mt-1">
                {plan.analyses} analyses · ~{plan.perReport}/report
              </p>
            </div>

            <ul className="space-y-2.5 mb-6 flex-1">
              {features.map((feature) => (
                <li key={feature} className="flex items-center gap-2 text-sm text-text-secondary">
                  <CheckCircle2 className="h-4 w-4 text-success flex-shrink-0" />
                  {feature}
                </li>
              ))}
              <li className="flex items-center gap-2 text-sm font-medium text-text-primary">
                <CheckCircle2 className="h-4 w-4 text-primary flex-shrink-0" />
                {plan.analyses} analyses/month
              </li>
            </ul>

            <button
              onClick={() => handleSubscribe(plan.priceId, plan.name)}
              disabled={loadingPlan !== null}
              className={`w-full py-2.5 rounded-lg font-semibold text-sm transition-colors ${
                plan.popular
                  ? 'bg-primary text-white hover:bg-primary/90'
                  : 'border border-primary text-primary hover:bg-primary/5'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {loadingPlan === plan.name ? 'Redirecting...' : `Get ${plan.name}`}
            </button>
          </div>
        ))}
      </div>

      {/* Boost section — only shown to eligible paid subscribers */}
      {quota?.boost_eligible && (
        <div className="mt-10 max-w-lg mx-auto">
          <div className="rounded-xl border border-surface-elevated bg-surface p-6">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-warning/10 rounded-lg flex-shrink-0">
                <Zap className="h-5 w-5 text-warning" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-text-primary">Need more analyses this month?</h3>
                <p className="text-sm text-text-secondary mt-1">
                  Add 5 analyses to your current billing period for a one-time $9.99. For existing
                  customers only — unused analyses expire at period end.
                </p>
                {quota.boost_analyses_added > 0 && (
                  <p className="text-xs text-warning mt-2">
                    You already have {quota.boost_analyses_added} boost analyses active this period.
                  </p>
                )}
                {quota.days_remaining < 7 && (
                  <p className="text-xs text-text-tertiary mt-2">
                    ⚠️ Only {quota.days_remaining} day{quota.days_remaining !== 1 ? 's' : ''} left in your billing period.
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={handleBoost}
              disabled={boostLoading}
              className="mt-4 w-full py-2.5 px-4 bg-warning/10 border border-warning/30 text-warning hover:bg-warning/20 rounded-lg font-semibold text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {boostLoading ? 'Loading...' : 'Buy Boost — $9.99 (adds 5 analyses)'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
