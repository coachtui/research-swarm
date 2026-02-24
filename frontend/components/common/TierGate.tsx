'use client'

import Link from 'next/link'
import { Lock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { type Feature, type Tier, canAccessFeature, FEATURE_GATE_COPY, TIER_LABELS } from '@/lib/entitlements'

interface TierGateProps {
  /** The capability being gated. */
  feature: Feature
  /** User's current subscription tier. */
  userTier: Tier | string | null | undefined
  /** Admins always bypass gates. */
  isAdmin?: boolean
  /** Content rendered when user has access. */
  children: React.ReactNode
}

/**
 * TierGate — wraps a results-page section with an upgrade prompt when the
 * user's tier does not meet the required level.
 *
 * Design intent:
 * - Locked state feels like a *preview of expansion*, not a hard wall.
 * - Copy emphasises decision capability gained, not features withheld.
 * - Higher tiers feel like unlocking a new professional layer.
 */
export function TierGate({ feature, userTier, isAdmin = false, children }: TierGateProps) {
  // Admins always have full access
  const hasAccess = isAdmin || canAccessFeature(feature, userTier)

  if (hasAccess) return <>{children}</>

  const copy = FEATURE_GATE_COPY[feature]
  const tierLabel = TIER_LABELS[copy.requiredTier]

  // Tier badge color: investor → default (teal), trader → warning (amber)
  const badgeVariant = copy.requiredTier === 'trader' ? 'warning' : 'default'

  return (
    <div className="relative rounded-lg border border-border bg-surface overflow-hidden">
      {/* Ambient gradient — suggests content exists behind */}
      <div
        className="absolute inset-0 pointer-events-none"
        aria-hidden
        style={{
          background:
            'linear-gradient(180deg, transparent 0%, var(--surface) 70%)',
        }}
      />

      {/* Blurred content silhouette — visual hint of depth */}
      <div className="h-20 opacity-[0.06] blur-[3px] bg-gradient-to-b from-surface-elevated to-transparent" />

      {/* Gate card */}
      <div className="relative px-6 py-5 flex flex-col gap-4">
        {/* Header row */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="flex-shrink-0 flex items-center justify-center w-7 h-7 rounded-md bg-surface-elevated border border-border-subtle">
              <Lock className="w-3.5 h-3.5 text-text-tertiary" />
            </div>
            <div>
              <p className="text-sm font-semibold text-text-primary leading-tight">
                {copy.title}
              </p>
              <p className="text-xs text-text-tertiary mt-0.5 leading-snug">
                {copy.description}
              </p>
            </div>
          </div>
          <Badge variant={badgeVariant} className="flex-shrink-0 mt-0.5">
            {tierLabel}
          </Badge>
        </div>

        {/* Bullet list */}
        <ul className="space-y-1.5 pl-1">
          {copy.bullets.map((bullet) => (
            <li key={bullet} className="flex items-start gap-2 text-xs text-text-secondary">
              <span className="mt-1 flex-shrink-0 w-1 h-1 rounded-full bg-text-tertiary" />
              {bullet}
            </li>
          ))}
        </ul>

        {/* CTA */}
        <div className="flex items-center gap-3 pt-1">
          <Link href="/#pricing">
            <Button size="sm" variant="primary">
              Upgrade to {tierLabel}
            </Button>
          </Link>
          <span className="text-[11px] text-text-tertiary">
            Unlocks {copy.bullets.length} additional capabilities
          </span>
        </div>
      </div>
    </div>
  )
}
