import type { TriggerItem } from '@/types/api'

interface WatchForSummaryProps {
  upgradeTriggers?: TriggerItem[] | null
  downgradeTriggers?: TriggerItem[] | null
}

/**
 * Condensed "Watch For" box surfaced immediately after the main recommendation.
 * Shows the top 2 upgrade and top 2 downgrade triggers so users see the key
 * catalysts before scrolling through the full analysis.
 *
 * The full trigger list is still available in the Analyst Verdict section.
 */
export function WatchForSummary({ upgradeTriggers, downgradeTriggers }: WatchForSummaryProps) {
  const topUpgrades = (upgradeTriggers ?? []).slice(0, 2)
  const topDowngrades = (downgradeTriggers ?? []).slice(0, 2)

  if (topUpgrades.length === 0 && topDowngrades.length === 0) return null

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm font-semibold text-text-primary">Watch For</span>
        <span className="text-[10px] text-text-tertiary bg-surface-elevated px-2 py-0.5 rounded border border-border uppercase tracking-wide">
          Key catalysts that change this rating
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {topUpgrades.length > 0 && (
          <div>
            <p className="text-[10px] text-success uppercase tracking-wide font-semibold mb-1.5">
              Upgrade triggers
            </p>
            <ul className="space-y-1.5">
              {topUpgrades.map((t, i) => (
                <li key={i} className="flex items-start gap-1.5 text-xs text-text-secondary">
                  <span className="text-success mt-0.5 shrink-0">↑</span>
                  <span>
                    <span className="font-medium text-text-primary">{t.metric}: </span>
                    {t.threshold}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {topDowngrades.length > 0 && (
          <div>
            <p className="text-[10px] text-error uppercase tracking-wide font-semibold mb-1.5">
              Downgrade triggers
            </p>
            <ul className="space-y-1.5">
              {topDowngrades.map((t, i) => (
                <li key={i} className="flex items-start gap-1.5 text-xs text-text-secondary">
                  <span className="text-error mt-0.5 shrink-0">↓</span>
                  <span>
                    <span className="font-medium text-text-primary">{t.metric}: </span>
                    {t.threshold}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <p className="text-[10px] text-text-tertiary mt-3 italic">
        Full trigger list with timeframes and impact in the Analyst Verdict section below.
      </p>
    </div>
  )
}
