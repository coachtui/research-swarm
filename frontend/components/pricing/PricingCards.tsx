'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { CheckCircle2 } from 'lucide-react'
import { apiClient } from '@/lib/api/client'

export function PricingCards() {
  const { isSignedIn, getToken } = useAuth()
  const router = useRouter()
  const [loading, setLoading] = useState<string | null>(null)

  const handleSubscribe = async (plan: 'pro' | 'premium') => {
    if (!isSignedIn) {
      router.push('/sign-up')
      return
    }

    const priceId = plan === 'pro'
      ? process.env.NEXT_PUBLIC_STRIPE_PRO_PRICE_ID
      : process.env.NEXT_PUBLIC_STRIPE_PREMIUM_PRICE_ID

    if (!priceId) {
      console.error('Stripe price ID not configured')
      return
    }

    try {
      setLoading(plan)
      const token = await getToken()
      if (token) {
        apiClient.setAuthToken(token)
      }

      const { checkout_url } = await apiClient.createCheckoutSession(priceId)
      window.location.href = checkout_url
    } catch (error) {
      console.error('Error creating checkout session:', error)
      alert('Failed to start checkout. Please try again.')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
      {/* Pro Plan */}
      <div className="p-8 rounded-xl bg-primary/5 border-2 border-primary relative">
        <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 px-4 py-1 bg-primary text-white text-sm font-semibold rounded-full">
          Most Popular
        </div>
        <h3 className="text-2xl font-semibold text-text-primary mb-2">Pro</h3>
        <div className="mb-6">
          <span className="text-4xl font-bold text-text-primary">$19.99</span>
          <span className="text-text-secondary">/month</span>
        </div>
        <ul className="space-y-3 mb-8">
          <li className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            <span className="text-text-secondary"><strong>10 reports per month</strong> (~$2/report)</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            <span className="text-text-secondary">Full institutional-quality analysis</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            <span className="text-text-secondary">Moat score + signal breakdown</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            <span className="text-text-secondary">Investment thesis + risks</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            <span className="text-text-secondary">PDF export & report history</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            <span className="text-text-secondary">Watchlist tracking</span>
          </li>
        </ul>
        <Button
          className="w-full"
          onClick={() => handleSubscribe('pro')}
          disabled={loading === 'pro'}
        >
          {loading === 'pro' ? 'Loading...' : 'Start Pro Plan'}
        </Button>
      </div>

      {/* Premium Plan */}
      <div className="p-8 rounded-xl bg-background border border-surface-elevated">
        <h3 className="text-2xl font-semibold text-text-primary mb-2">Premium</h3>
        <div className="mb-6">
          <span className="text-4xl font-bold text-text-primary">$49.99</span>
          <span className="text-text-secondary">/month</span>
        </div>
        <ul className="space-y-3 mb-8">
          <li className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            <span className="text-text-secondary"><strong>30 reports per month</strong> (~$1.67/report)</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            <span className="text-text-secondary">Everything in Pro, plus:</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            <span className="text-text-secondary">Priority analysis queue</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            <span className="text-text-secondary">Email alerts for watchlist updates</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            <span className="text-text-secondary">Advanced analytics & insights</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            <span className="text-text-secondary">API access (coming soon)</span>
          </li>
        </ul>
        <Button
          variant="outline"
          className="w-full"
          onClick={() => handleSubscribe('premium')}
          disabled={loading === 'premium'}
        >
          {loading === 'premium' ? 'Loading...' : 'Start Premium Plan'}
        </Button>
      </div>
    </div>
  )
}
