/**
 * Plans — single source of truth for all subscription tiers.
 *
 * This file owns:
 *   - Stripe price IDs (read from env at build time)
 *   - Monthly analysis quotas
 *   - Marketing bullets rendered on the pricing cards
 *   - Feature gates (maps to canAccessFeature() in entitlements.ts)
 *
 * Backend entitlement enforcement is in api/lib/entitlement_config.py.
 * These frontend Feature flags gate UI panels; the backend independently
 * gates API endpoints — never rely on frontend flags for access control.
 *
 * PDF export decision: gated at Investor+ (not listed for Starter).
 * Downgrade policy: entitlements maintained until current period end.
 */

import type { Feature } from '@/lib/entitlements'

export type PlanKey = 'starter' | 'investor' | 'trader'

export interface Plan {
  key: PlanKey
  name: string
  /** Stripe recurring price ID — used to create Checkout sessions. */
  stripePriceId: string
  displayPrice: string
  pricePerMonth: number
  analysesPerMonth: number
  pricePerAnalysis: string
  description: string
  popular: boolean
  /** Marketing bullets rendered in the pricing card, in display order. */
  bullets: string[]
  /**
   * Frontend feature gates unlocked by this tier.
   * Evaluated by canAccessFeature() in entitlements.ts.
   * Higher tiers include all lower-tier features.
   */
  unlockedFeatures: Feature[]
}

// ── Tier definitions ──────────────────────────────────────────────────────────

export const PLANS: Record<PlanKey, Plan> = {
  starter: {
    key: 'starter',
    name: 'Starter',
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_STARTER_PRICE_ID!,
    displayPrice: '$19.99',
    pricePerMonth: 19.99,
    analysesPerMonth: 5,
    pricePerAnalysis: '$4.00',
    description: 'Core report + clear verdict + watchlist tracking',
    popular: false,
    bullets: [
      '5 analyses / month',
      'Full moat score + signal breakdown',
      'Fair value snapshot & price targets',
      'Investment summary + strategic catalysts',
      'Clear buy / hold / avoid verdict',
      'Unlimited watchlist tracking',
    ],
    // No locked features beyond core — all core report panels are visible.
    unlockedFeatures: [],
  },

  investor: {
    key: 'investor',
    name: 'Investor',
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_INVESTOR_PRICE_ID!,
    displayPrice: '$39.99',
    pricePerMonth: 39.99,
    analysesPerMonth: 15,
    pricePerAnalysis: '$2.67',
    description: 'Full signal metrics, probabilistic engine + PDF export',
    popular: true,
    bullets: [
      '15 analyses / month',
      'Everything in Starter',
      'Probabilistic EV engine + scenario weights',
      'Stop probability & confidence calibration',
      'Full investment thesis + analyst verdict',
      'Stability & noise diagnostics',
      'Historical pattern framing',
      'PDF report export',
    ],
    unlockedFeatures: [
      'historical_patterns',
      'institutional_risk',
      'probabilistic_engine',
      'analyst_verdict',
    ],
  },

  trader: {
    key: 'trader',
    name: 'Trader',
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_TRADER_PRICE_ID!,
    displayPrice: '$99.99',
    pricePerMonth: 99.99,
    analysesPerMonth: 50,
    pricePerAnalysis: '$2.00',
    description: 'Full engine console, trade setup + allocation infrastructure',
    popular: false,
    bullets: [
      '50 analyses / month',
      'Everything in Investor',
      'Dynamic position sizing engine',
      'Portfolio risk & factor exposure',
      'Tactical entry / exit setup',
      'Full engine console + advanced appendix',
      'PDF report export',
    ],
    unlockedFeatures: [
      'historical_patterns',
      'institutional_risk',
      'probabilistic_engine',
      'analyst_verdict',
      'execution_layer',
    ],
  },
}

/** Ordered list of plans for rendering (Starter → Investor → Trader). */
export const PLAN_LIST: Plan[] = [PLANS.starter, PLANS.investor, PLANS.trader]
