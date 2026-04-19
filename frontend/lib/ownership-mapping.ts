/**
 * Ownership Label Mapping — UI display layer translation.
 *
 * Maps backend ratings (BUY/HOLD/SELL) and engine states to the
 * Compounder Ownership vocabulary. Backend computation is unchanged;
 * only the frontend display changes.
 */

import type { PortfolioPosition, EngineAction, EngineActionType } from '@/types/api'

// ── Ownership Status ────────────────────────────────────────────────────────

export type OwnershipStatus = 'Core Compounder' | 'Watch' | 'Disqualified' | 'Eligible' | 'Not Eligible'

export function mapToOwnershipStatus(
  rating: string | null | undefined,
  initiationStatus: string | null | undefined,
  position: PortfolioPosition | null | undefined,
): { status: OwnershipStatus; color: string } {
  // If position exists in portfolio, use position.ownership_status
  if (position) {
    switch (position.ownership_status) {
      case 'core_compounder':
        return { status: 'Core Compounder', color: 'text-success' }
      case 'watch':
        return { status: 'Watch', color: 'text-warning' }
      case 'disqualified':
        return { status: 'Disqualified', color: 'text-error' }
    }
  }

  // Fallback: derive from initiation_decision
  if (initiationStatus === 'INITIATE') return { status: 'Eligible', color: 'text-success' }
  if (initiationStatus === 'WATCHLIST') return { status: 'Watch', color: 'text-warning' }
  return { status: 'Not Eligible', color: 'text-text-tertiary' }
}

// ── Thesis State ────────────────────────────────────────────────────────────

export type ThesisState = 'Intact' | 'Monitoring' | 'Broken'

export function mapToThesisState(
  position: PortfolioPosition | null | undefined,
): { state: ThesisState; color: string } {
  if (!position) return { state: 'Intact', color: 'text-text-secondary' }

  switch (position.thesis_state) {
    case 'intact':
      return { state: 'Intact', color: 'text-success' }
    case 'monitoring':
      return { state: 'Monitoring', color: 'text-warning' }
    case 'broken':
      return { state: 'Broken', color: 'text-error' }
    default:
      return { state: 'Intact', color: 'text-text-secondary' }
  }
}

// ── Action Label ────────────────────────────────────────────────────────────

const ACTION_LABELS: Record<EngineActionType, string> = {
  INITIATE: 'Initiate',
  ADD_TIER_20: 'Add +2%',
  ADD_TIER_30: 'Add +4%',
  ADD_TIER_40: 'Add +6%',
  ADD_TIER_50: 'Add +8%',
  TRIM_EUPHORIA: 'Trim (Euphoria)',
  TRIM_CAP: 'Trim (Cap)',
  TRIM_THESIS: 'Trim (Integrity)',
  EXIT_THESIS: 'Exit',
  REPLACE: 'Replace',
  HOLD: 'Hold',
}

const ACTION_COLORS: Record<EngineActionType, string> = {
  INITIATE: 'text-success',
  ADD_TIER_20: 'text-success',
  ADD_TIER_30: 'text-success',
  ADD_TIER_40: 'text-success',
  ADD_TIER_50: 'text-success',
  TRIM_EUPHORIA: 'text-warning',
  TRIM_CAP: 'text-warning',
  TRIM_THESIS: 'text-error',
  EXIT_THESIS: 'text-error',
  REPLACE: 'text-primary',
  HOLD: 'text-text-secondary',
}

export function mapToActionLabel(
  pendingAction: EngineAction | null | undefined,
): { label: string; color: string } {
  if (!pendingAction) return { label: 'No Action Pending', color: 'text-text-tertiary' }
  const type = pendingAction.action_type as EngineActionType
  return {
    label: ACTION_LABELS[type] || pendingAction.action_type,
    color: ACTION_COLORS[type] || 'text-text-secondary',
  }
}

export function formatActionType(actionType: EngineActionType | string): string {
  return ACTION_LABELS[actionType as EngineActionType] || actionType
}

export function getActionColor(actionType: EngineActionType | string): string {
  return ACTION_COLORS[actionType as EngineActionType] || 'text-text-secondary'
}

// ── Weight formatting ───────────────────────────────────────────────────────

export function formatWeight(weight: number): string {
  return `${(weight * 100).toFixed(1)}%`
}

export function formatWeightDelta(delta: number): string {
  const sign = delta >= 0 ? '+' : ''
  return `${sign}${(delta * 100).toFixed(1)}%`
}
