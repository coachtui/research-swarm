'use client'

import { AlertTriangle } from 'lucide-react'

/**
 * ActionDisclaimer — shown on every action card and at top of actions feed.
 *
 * "This is a model-generated action based on your selected mandate.
 *  Execution decisions remain yours."
 */
export function ActionDisclaimer() {
  return (
    <div className="flex items-start gap-2.5 rounded-lg bg-warning/5 border border-warning/20 px-3.5 py-2.5">
      <AlertTriangle className="h-3.5 w-3.5 text-warning mt-0.5 flex-shrink-0" />
      <p className="text-[11px] text-text-secondary leading-relaxed">
        Model-generated actions based on your selected mandate. Execution decisions remain yours.
      </p>
    </div>
  )
}
