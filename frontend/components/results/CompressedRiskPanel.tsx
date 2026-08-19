'use client'

// Phase 4 — Risk Panel (Compressed)
// PM memo style. No paragraphs. Bullet-only. Three labelled groups.
// Max: 5 risk drivers · 3 sensitivity triggers · 2 kill-thesis conditions.

import type { TriggerItem } from '@/types/api'

interface CompressedRiskPanelProps {
  riskFactors: string[]
  downgradeTriggers?: TriggerItem[] | null
}

function extractText(item: TriggerItem): string {
  // Format as "metric: threshold → action" for the compressed display
  const parts = [item.metric, item.threshold, item.action].filter(Boolean)
  return parts.join(' — ')
}

// Trim each bullet to max ~120 chars — no paragraphs
function trimBullet(text: string, maxLen = 120): string {
  const cleaned = text.replace(/^\W+/, '').trim()
  return cleaned.length > maxLen ? cleaned.slice(0, maxLen - 1) + '…' : cleaned
}

function BulletGroup({
  title,
  items,
  color,
  prefix = '▸',
}: {
  title: string
  items: string[]
  color: string
  prefix?: string
}) {
  if (!items.length) return null
  return (
    <div>
      <p className={`text-[9px] font-bold uppercase tracking-[0.14em] mb-1.5 ${color}`}>
        {title}
      </p>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className={`text-[10px] mt-0.5 flex-shrink-0 ${color}`}>{prefix}</span>
            <span className="text-xs text-text-secondary leading-snug">{trimBullet(item)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function CompressedRiskPanel({
  riskFactors,
  downgradeTriggers,
}: CompressedRiskPanelProps) {
  // Key Risk Drivers: top 5 from risk_factors
  const keyRiskDrivers = (riskFactors ?? []).slice(0, 5)

  // Kill Thesis: first 2 downgrade triggers (most critical thesis-invalidators)
  const killThesis = (downgradeTriggers ?? [])
    .slice(0, 2)
    .map(extractText)

  // Sensitivity Triggers: the next 3 downgrade triggers — disjoint from the
  // kill-thesis group so no trigger is listed twice in the same panel
  const sensitivityTriggers = (downgradeTriggers ?? [])
    .slice(2, 5)
    .map(extractText)

  if (!keyRiskDrivers.length && !sensitivityTriggers.length && !killThesis.length) {
    return null
  }

  return (
    <div className="rounded-xl border border-border/70 bg-card overflow-hidden">

      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-border/40 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-primary tracking-tight uppercase">
          Risk Assessment
        </h2>
        <span className="text-[9px] font-mono text-text-tertiary/50 border border-border rounded px-1.5 py-0.5 uppercase tracking-wider">
          PM Memo
        </span>
      </div>

      {/* Compressed bullet groups */}
      <div className="px-5 py-4 space-y-5">

        <BulletGroup
          title="Key Risk Drivers"
          items={keyRiskDrivers}
          color="text-text-tertiary"
        />

        {sensitivityTriggers.length > 0 && (
          <BulletGroup
            title="Sensitivity Triggers"
            items={sensitivityTriggers}
            color="text-warning"
            prefix="◆"
          />
        )}

        {killThesis.length > 0 && (
          <BulletGroup
            title="Kill Thesis Conditions"
            items={killThesis}
            color="text-error"
            prefix="✕"
          />
        )}

      </div>
    </div>
  )
}
