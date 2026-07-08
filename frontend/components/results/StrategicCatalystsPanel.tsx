'use client'

import { Rocket, CalendarClock } from 'lucide-react'
import type { ManagerOutput } from '@/types/api'

type StrategicCatalyst = NonNullable<ManagerOutput['strategic_catalysts']>[number]

interface UpcomingCatalystEvent {
  event_type?: string
  event_date?: string
  description?: string
  potential_impact?: string
  impact_direction?: string
  confidence?: number
}

/**
 * StrategicCatalystsPanel — renders the manager's forward-looking strategic
 * catalysts plus the news hound's upcoming catalyst calendar. Before this
 * panel existed, strategic_catalysts was generated and stored but never
 * shown anywhere in the report UI.
 */
export function StrategicCatalystsPanel({
  catalysts,
  upcoming,
}: {
  catalysts?: StrategicCatalyst[] | null
  upcoming?: { catalysts?: UpcomingCatalystEvent[]; next_earnings_date?: string | null } | null
}) {
  // Guard against stale calendar entries in reports generated before the
  // backend date filter existed: drop parseable dates in the past, keep
  // fuzzy timeframes like "2026-Q3".
  const today = new Date().toISOString().slice(0, 10)
  const isPast = (value?: string) => {
    const d = String(value ?? '').slice(0, 10)
    return /^\d{4}-\d{2}-\d{2}$/.test(d) && d < today
  }
  const calendar = (upcoming?.catalysts ?? []).filter(e => !isPast(e.event_date))
  const strategic = catalysts ?? []

  if (strategic.length === 0 && calendar.length === 0) return null

  const impactStyle = (impact?: string) => {
    switch ((impact || '').toUpperCase()) {
      case 'HIGH':
        return 'text-success border-success/40'
      case 'MEDIUM':
        return 'text-warning border-warning/40'
      default:
        return 'text-text-tertiary border-border'
    }
  }

  return (
    <div className="space-y-4">
      {/* ── Upcoming catalyst calendar (dated events) ─────────────────── */}
      {calendar.length > 0 && (
        <div>
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Catalyst Calendar
          </h4>
          <div className="space-y-1.5">
            {calendar.map((event, i) => (
              <div key={i} className="flex items-start gap-2 rounded-lg bg-surface-elevated/50 px-3 py-2">
                <CalendarClock className="h-3.5 w-3.5 text-text-tertiary mt-0.5 flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-xs font-medium text-text-primary">
                    <span className="font-mono text-text-secondary mr-1.5">{event.event_date}</span>
                    {event.event_type}
                  </p>
                  {event.description && (
                    <p className="text-[10px] text-text-tertiary mt-0.5">{event.description}</p>
                  )}
                </div>
                {event.potential_impact && (
                  <span className={`ml-auto flex-shrink-0 text-[9px] font-semibold uppercase border rounded px-1.5 py-0.5 ${impactStyle(event.potential_impact)}`}>
                    {event.potential_impact}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Strategic catalysts (forward-looking, speculative) ────────── */}
      {strategic.length > 0 && (
        <div>
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Strategic Catalysts
          </h4>
          <div className="space-y-1.5">
            {strategic.map((cat, i) => (
              <div key={i} className="rounded-lg bg-surface-elevated/50 px-3 py-2.5">
                <div className="flex items-start gap-2">
                  <Rocket className="h-3.5 w-3.5 text-text-tertiary mt-0.5 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <p className="text-xs font-medium text-text-primary">{cat.title}</p>
                      <span className={`text-[9px] font-semibold uppercase border rounded px-1.5 py-0.5 ${impactStyle(cat.potential_impact)}`}>
                        {cat.potential_impact}
                      </span>
                    </div>
                    <p className="text-[10px] text-text-tertiary mt-0.5">
                      {cat.category} · {cat.timeframe}
                    </p>
                    <p className="text-[11px] text-text-secondary mt-1.5 leading-relaxed">
                      {cat.description}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <p className="text-[9px] text-text-tertiary mt-2 italic">
            Forward-looking and speculative — potential upside with execution risk, not yet reflected in current financials.
          </p>
        </div>
      )}
    </div>
  )
}
