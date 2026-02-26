'use client'

import { X, TrendingUp, Mail } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { apiClient } from '@/lib/api/client'
import { PLANS, PLAN_LIST } from '@/lib/plans'
import type { EntitlementsResponse } from '@/types/api'

type PaywallReason =
  | 'CREDITS_EXHAUSTED'   // Free tier: 2/2 reports used
  | 'MONTHLY_CAP'         // Paid tier: monthly limit reached
  | 'EMAIL_REQUIRED'      // Free tier: report #2 needs verified email
  | 'DEVICE_LIMIT'        // Anti-abuse: device threshold exceeded

interface PaywallModalProps {
  reason: PaywallReason
  entitlements?: EntitlementsResponse
  onClose: () => void
}

/** Recommended tier to highlight in the plan chooser given the current situation. */
function recommendedTier(reason: PaywallReason, currentTier: string): string {
  if (reason === 'CREDITS_EXHAUSTED' || reason === 'DEVICE_LIMIT' || currentTier === 'free') {
    return 'starter'
  }
  if (currentTier === 'starter') return 'investor'
  if (currentTier === 'investor') return 'trader'
  return 'starter'
}

function usageLabel(reason: PaywallReason, ents?: EntitlementsResponse): string {
  if (!ents) return ''
  const u = ents.usage
  if (u.is_free_tier) {
    return `${u.report_credits_used ?? 2} / ${u.report_credits_total ?? 2} free reports used`
  }
  return `${u.analyses_used} / ${u.analyses_limit} reports used this month`
}

/** Email verification reminder panel — shown for EMAIL_REQUIRED reason. */
function EmailVerificationPanel({ onClose }: { onClose: () => void }) {
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)

  const handleResend = async () => {
    setSending(true)
    try {
      // Clerk exposes resend via their frontend SDK — call their endpoint
      await fetch('/api/auth/resend-verification', { method: 'POST' })
      setSent(true)
    } catch {
      // Ignore errors — user can try again
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start gap-3 p-4 rounded-lg bg-warning/10 border border-warning/20">
        <Mail className="h-5 w-5 text-warning mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-sm font-semibold text-text-primary">Email verification required</p>
          <p className="text-sm text-text-secondary mt-1">
            Your second free report requires a verified email address.
            Check your inbox for a verification link, or request a new one below.
          </p>
        </div>
      </div>

      <button
        onClick={handleResend}
        disabled={sending || sent}
        className="w-full py-2.5 px-4 bg-primary text-white rounded-lg font-medium text-sm hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {sent ? 'Verification email sent!' : sending ? 'Sending...' : 'Resend verification email'}
      </button>
      <button
        onClick={onClose}
        className="w-full py-2.5 px-4 text-text-tertiary rounded-lg text-sm hover:text-text-secondary transition-colors"
      >
        Close
      </button>
    </div>
  )
}

/** Plan chooser — rendered inside the paywall modal for upgrade path. */
function PlanChooser({
  recommendedPlanKey,
  onClose,
}: {
  recommendedPlanKey: string
  onClose: () => void
}) {
  const router = useRouter()
  const [loading, setLoading] = useState<string | null>(null)

  const handleUpgrade = async (stripePriceId: string, planKey: string) => {
    setLoading(planKey)
    try {
      const { checkout_url } = await apiClient.createCheckoutSession(stripePriceId)
      window.location.href = checkout_url
    } catch (err) {
      console.error('Checkout error:', err)
      setLoading(null)
    }
  }

  return (
    <div className="grid gap-3 mt-1">
      {PLAN_LIST.map((plan) => {
        const isRecommended = plan.key === recommendedPlanKey
        return (
          <div
            key={plan.key}
            className={`relative rounded-lg border p-4 flex items-center justify-between gap-4 transition-colors ${
              isRecommended
                ? 'border-primary bg-primary/5'
                : 'border-surface-elevated bg-surface hover:bg-surface-elevated'
            }`}
          >
            {isRecommended && (
              <span className="absolute -top-2.5 left-3 bg-primary text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide">
                Recommended
              </span>
            )}
            <div className="min-w-0">
              <p className="font-semibold text-text-primary text-sm">{plan.name}</p>
              <p className="text-xs text-text-secondary mt-0.5">
                {plan.analysesPerMonth} analyses/month · {plan.displayPrice}/mo
              </p>
            </div>
            <button
              onClick={() => handleUpgrade(plan.stripePriceId, plan.key)}
              disabled={loading !== null}
              className={`flex-shrink-0 py-2 px-4 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                isRecommended
                  ? 'bg-primary text-white hover:bg-primary/90'
                  : 'border border-primary/40 text-primary hover:bg-primary/5'
              }`}
            >
              {loading === plan.key ? 'Redirecting...' : `Upgrade to ${plan.name}`}
            </button>
          </div>
        )
      })}

      <button
        onClick={onClose}
        className="w-full py-2 px-4 text-text-tertiary rounded-lg text-sm hover:text-text-secondary transition-colors mt-1"
      >
        Not now
      </button>
    </div>
  )
}

/**
 * PaywallModal — shown when a user hits a generation limit.
 *
 * Handles four scenarios:
 *  - CREDITS_EXHAUSTED: free 2/2 reports consumed → show plan chooser
 *  - MONTHLY_CAP: paid tier monthly limit reached → show plan chooser (next tier)
 *  - EMAIL_REQUIRED: free report #2 blocked by unverified email → email CTA
 *  - DEVICE_LIMIT: anti-abuse device threshold reached → show plan chooser
 */
export function PaywallModal({ reason, entitlements, onClose }: PaywallModalProps) {
  const currentTier = entitlements?.tier ?? 'free'
  const recommended = recommendedTier(reason, currentTier)

  const title =
    reason === 'EMAIL_REQUIRED'
      ? 'Verify your email to continue'
      : 'Upgrade to generate more reports'

  const subtitle =
    reason === 'EMAIL_REQUIRED'
      ? null
      : usageLabel(reason, entitlements)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="bg-surface border border-surface-elevated rounded-xl w-full max-w-lg shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-surface-elevated">
          <div>
            <h2 className="text-lg font-bold text-text-primary">{title}</h2>
            {subtitle && (
              <p className="text-sm text-text-secondary mt-0.5">{subtitle}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-text-tertiary hover:text-text-primary transition-colors p-1 -mr-1 flex-shrink-0"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5">
          {reason === 'EMAIL_REQUIRED' ? (
            <EmailVerificationPanel onClose={onClose} />
          ) : (
            <>
              {reason === 'DEVICE_LIMIT' && (
                <p className="text-sm text-text-secondary mb-4">
                  This device has reached the free report limit. Upgrade to get
                  monthly analyses with no device restrictions.
                </p>
              )}
              <PlanChooser recommendedPlanKey={recommended} onClose={onClose} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
