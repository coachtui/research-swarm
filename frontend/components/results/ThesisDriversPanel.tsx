'use client'

import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react'
import type { TriggerItem, TranchBreakCondition } from '@/types/api'

/**
 * ThesisDriversPanel — Section II: Structural Thesis.
 *
 * Displays:
 *   - Structural drivers (from upgrade_triggers)
 *   - Break conditions with threshold-based classification
 *     (aligned with engine logic: growth collapse / capital destruction / structural break)
 */
export function ThesisDriversPanel({
  upgradeTriggers,
  downgradeTriggers,
  thesisBreakConditions,
}: {
  upgradeTriggers?: TriggerItem[] | null
  downgradeTriggers?: TriggerItem[] | null
  thesisBreakConditions?: TranchBreakCondition[] | null
}) {
  const hasDrivers = upgradeTriggers && upgradeTriggers.length > 0
  const hasBreaks = (downgradeTriggers && downgradeTriggers.length > 0) ||
                    (thesisBreakConditions && thesisBreakConditions.length > 0)

  if (!hasDrivers && !hasBreaks) return null

  return (
    <div className="space-y-4">
      {/* ── Structural Drivers ───────────────────────────────────────── */}
      {hasDrivers && (
        <div>
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Structural Drivers
          </h4>
          <div className="space-y-1.5">
            {upgradeTriggers!.map((trigger, i) => (
              <div key={i} className="flex items-start gap-2 rounded-lg bg-surface-elevated/50 px-3 py-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-success mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-xs font-medium text-text-primary">{trigger.metric}</p>
                  {trigger.action && (
                    <p className="text-[10px] text-text-tertiary mt-0.5">{trigger.action}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Break Conditions (from tranche_plan) ─────────────────────── */}
      {thesisBreakConditions && thesisBreakConditions.length > 0 && (
        <div>
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Break Conditions
          </h4>
          <div className="space-y-1.5">
            {thesisBreakConditions.map((cond, i) => (
              <div
                key={i}
                className={`flex items-start gap-2 rounded-lg px-3 py-2 ${
                  cond.active
                    ? 'bg-error/10 border border-error/30'
                    : 'bg-surface-elevated/50'
                }`}
              >
                {cond.active
                  ? <XCircle className="h-3.5 w-3.5 text-error mt-0.5 flex-shrink-0" />
                  : <AlertTriangle className="h-3.5 w-3.5 text-warning mt-0.5 flex-shrink-0" />
                }
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-text-primary">{cond.label}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[10px] text-text-tertiary">
                      Threshold: <span className="font-mono">{cond.threshold}</span>
                    </span>
                    <span className="text-[10px] text-text-tertiary">
                      Current: <span className={`font-mono font-semibold ${cond.active ? 'text-error' : 'text-text-secondary'}`}>
                        {cond.current}
                      </span>
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Downgrade Triggers (fallback if no structured break conditions) */}
      {(!thesisBreakConditions || thesisBreakConditions.length === 0) && downgradeTriggers && downgradeTriggers.length > 0 && (
        <div>
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Break Conditions
          </h4>
          <div className="space-y-1.5">
            {downgradeTriggers.map((trigger, i) => (
              <div key={i} className="flex items-start gap-2 rounded-lg bg-surface-elevated/50 px-3 py-2">
                <AlertTriangle className="h-3.5 w-3.5 text-warning mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-xs font-medium text-text-primary">{trigger.metric}</p>
                  {trigger.action && (
                    <p className="text-[10px] text-text-tertiary mt-0.5">{trigger.action}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
