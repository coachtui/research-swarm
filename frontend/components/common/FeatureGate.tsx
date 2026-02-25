'use client'

import type { ReactNode } from 'react'
import { useEntitlements } from '@/lib/hooks/useEntitlements'

interface FeatureGateProps {
  /**
   * Backend feature flag string — e.g. "feature.report.signal_metrics".
   * Use the FEAT_* constants defined in api/lib/entitlements.py for naming
   * consistency between backend and frontend.
   */
  flag: string
  /** Rendered when the server confirms access to this flag. */
  children: ReactNode
  /**
   * Rendered when the user lacks access.
   * Defaults to null (renders nothing).
   */
  fallback?: ReactNode
}

/**
 * FeatureGate — renders children only when the server confirms the user
 * has access to the given feature flag.
 *
 * Unlike TierGate (which uses client-side tier comparison), FeatureGate uses
 * the server-computed entitlements response so admin override and Stripe
 * inactive-status downgrade are always respected without duplicating
 * that logic on the client.
 *
 * Renders nothing (null) while loading to avoid flash-of-content.
 *
 * @example
 *   <FeatureGate
 *     flag="feature.report.signal_metrics"
 *     fallback={<p>Upgrade to Investor to view signal metrics.</p>}
 *   >
 *     <SignalMetricsPanel />
 *   </FeatureGate>
 */
export function FeatureGate({ flag, children, fallback = null }: FeatureGateProps) {
  const { data: entitlements, isLoading } = useEntitlements()

  // Render nothing while entitlements load to prevent content flash
  if (isLoading || !entitlements) return null

  const granted = entitlements.features[flag] ?? false
  return granted ? <>{children}</> : <>{fallback}</>
}
