'use client'

import { Card, CardContent } from '@/components/ui/card'
import type { TriggerItem } from '@/types/api'

interface BottomLineProps {
  upgradeTriggers?: TriggerItem[] | null
  downgradeTriggers?: TriggerItem[] | null
}

export function BottomLine({
  upgradeTriggers,
  downgradeTriggers,
}: BottomLineProps) {
  // Only show if we have triggers
  if (!upgradeTriggers?.length && !downgradeTriggers?.length) return null

  return (
    <section className="rating-triggers mt-8">
      <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
        <span>📊</span> What Would Change This Rating?
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Upgrade Triggers */}
        {upgradeTriggers && upgradeTriggers.length > 0 && (
          <Card className="border-success/30 bg-success/5">
            <CardContent className="pt-6">
              <h4 className="font-semibold text-lg mb-4 flex items-center gap-2">
                <span className="text-success text-xl">↗</span>
                Upgrade to BUY if...
              </h4>
              <div className="space-y-3">
                {upgradeTriggers.slice(0, 5).map((trigger, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      disabled
                      className="mt-1 rounded border-gray-300"
                    />
                    <p className="text-sm leading-relaxed text-text-secondary">
                      <span className="font-medium">{trigger.metric}:</span> {trigger.threshold}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Downgrade Triggers */}
        {downgradeTriggers && downgradeTriggers.length > 0 && (
          <Card className="border-error/30 bg-error/5">
            <CardContent className="pt-6">
              <h4 className="font-semibold text-lg mb-4 flex items-center gap-2">
                <span className="text-error text-xl">↘</span>
                Downgrade to SELL if...
              </h4>
              <div className="space-y-3">
                {downgradeTriggers.slice(0, 5).map((trigger, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      disabled
                      className="mt-1 rounded border-gray-300"
                    />
                    <p className="text-sm leading-relaxed text-text-secondary">
                      <span className="font-medium">{trigger.metric}:</span> {trigger.threshold}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </section>
  )
}
