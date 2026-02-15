'use client'

import { Card, CardContent } from '@/components/ui/card'
import { ArrowUp, ArrowDown, TrendingUp } from 'lucide-react'

export interface Trigger {
  condition: string
  threshold?: string
  metric?: string
  specificTrigger?: string
}

interface RatingTriggersProps {
  upgrade_triggers: Trigger[]
  downgrade_triggers: Trigger[]
  current_rating: string
}

export function RatingTriggers({
  upgrade_triggers,
  downgrade_triggers,
  current_rating,
}: RatingTriggersProps) {
  // Determine target ratings based on current rating
  const upgradeTarget = current_rating === 'HOLD' ? 'BUY' : current_rating === 'BUY' ? 'STRONG BUY' : 'BUY'
  const downgradeTarget = current_rating === 'HOLD' ? 'SELL' : current_rating === 'BUY' ? 'HOLD' : 'STRONG SELL'

  if (!upgrade_triggers.length && !downgrade_triggers.length) {
    return null
  }

  return (
    <div className="rating-triggers mt-6">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <TrendingUp className="h-5 w-5" />
        What Would Change This Rating?
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Upgrade Triggers */}
        {upgrade_triggers.length > 0 && (
          <Card className="p-6 border-2 border-success/30 bg-success/5">
            <div className="flex items-center gap-2 mb-4">
              <div className="h-8 w-8 rounded-full bg-success/10 flex items-center justify-center">
                <ArrowUp className="h-5 w-5 text-success" />
              </div>
              <h4 className="font-semibold">Upgrade to {upgradeTarget} if...</h4>
            </div>

            <div className="space-y-3">
              {upgrade_triggers.map((trigger, i) => (
                <div key={i} className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    disabled
                    className="mt-1 rounded border-success h-4 w-4"
                  />
                  <div className="flex-1">
                    <p className="text-sm leading-relaxed">{trigger.condition}</p>
                    {trigger.specificTrigger && (
                      <p className="text-xs text-success/80 mt-1 ml-4 italic">
                        → Specific trigger: {trigger.specificTrigger}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Downgrade Triggers */}
        {downgrade_triggers.length > 0 && (
          <Card className="p-6 border-2 border-error/30 bg-error/5">
            <div className="flex items-center gap-2 mb-4">
              <div className="h-8 w-8 rounded-full bg-error/10 flex items-center justify-center">
                <ArrowDown className="h-5 w-5 text-error" />
              </div>
              <h4 className="font-semibold">Downgrade to {downgradeTarget} if...</h4>
            </div>

            <div className="space-y-3">
              {downgrade_triggers.map((trigger, i) => (
                <div key={i} className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    disabled
                    className="mt-1 rounded border-error h-4 w-4"
                  />
                  <div className="flex-1">
                    <p className="text-sm leading-relaxed">{trigger.condition}</p>
                    {trigger.specificTrigger && (
                      <p className="text-xs text-error/80 mt-1 ml-4 italic">
                        → Specific trigger: {trigger.specificTrigger}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
