'use client'

import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Target } from 'lucide-react'

interface KeyLevels {
  ideal_entry?: number
  stop_loss?: number
  resistance?: number
  support?: number
}

interface ConvictionPosition {
  conviction_level: string
  recommended_pct: number
  max_pct: number
  dollar_per_100k: number
  rationale?: string
}

interface QuickActionsProps {
  ticker: string
  current_price: number
  rating: string
  key_levels: KeyLevels
  next_catalyst?: string
  conviction_position?: ConvictionPosition | null
}

export function QuickActions({
  ticker,
  current_price,
  rating,
  key_levels,
  next_catalyst,
  conviction_position
}: QuickActionsProps) {
  const isBuy = rating.includes('BUY')
  const isHold = rating === 'HOLD'
  const isSell = rating === 'SELL'

  return (
    <Card className="p-6 mt-8">
      <div className="flex items-center gap-2 mb-4">
        <Target className="h-5 w-5 text-primary" />
        <h3 className="text-xl font-bold">Quick Actions</h3>
        <span className="text-xs text-muted-foreground ml-2">
          • Specific next steps based on your situation
        </span>
      </div>

      <Tabs defaultValue="buying" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="buying">Thinking of Buying</TabsTrigger>
          <TabsTrigger value="holding">Currently Holding</TabsTrigger>
          <TabsTrigger value="trading">Active Trading</TabsTrigger>
        </TabsList>

        {/* Buying Tab */}
        <TabsContent value="buying" className="mt-4">
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground mb-4">
              Based on the <strong>{rating}</strong> rating, here's what to do:
            </p>

            {isBuy && typeof key_levels.ideal_entry === 'number' && current_price > 0 && (
              <>
                <ActionCheckbox
                  label={`Start building position at current price ($${current_price.toFixed(2)})`}
                  description="Good risk/reward at current levels"
                />
                <ActionCheckbox
                  label={`Add more on dips to $${key_levels.ideal_entry.toFixed(2)}`}
                  description="Even better entry point if stock pulls back"
                />
              </>
            )}

            {isHold && current_price > 0 && (
              <>
                <ActionCheckbox
                  label={`Set price alert at $${(typeof key_levels.ideal_entry === 'number' ? key_levels.ideal_entry : current_price * 0.9).toFixed(2)}`}
                  description="You'll be notified when stock reaches better entry point"
                />
                <ActionCheckbox
                  label={`Set price alert at $${(current_price * 1.05).toFixed(2)} (avoid zone)`}
                  description="Don't buy if price goes above this level (too expensive)"
                />
                <ActionCheckbox
                  label="Watch for insider buying signal"
                  description="If company insiders start buying, that's a positive signal"
                />
              </>
            )}

            {isSell && (
              <>
                <ActionCheckbox
                  label="Avoid initiating new positions"
                  description="Current risk/reward is unfavorable"
                />
                <ActionCheckbox
                  label="Wait for rating upgrade before considering entry"
                  description="Let the picture clear up before committing capital"
                />
              </>
            )}

            {next_catalyst && (
              <ActionCheckbox
                label={`Review again after ${next_catalyst}`}
                description="Wait to see how this event plays out before committing capital"
              />
            )}

            {/* Position Sizing - Based on Conviction */}
            {conviction_position && (
              <div className="mt-6 p-4 bg-primary/5 border border-primary/20 rounded-lg">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs font-semibold text-primary">
                    💰 Position Sizing ({conviction_position.conviction_level} Conviction)
                  </p>
                  <span className="text-xs font-bold text-primary">
                    {conviction_position.recommended_pct}% Recommended
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs mb-3">
                  <div>
                    <span className="text-muted-foreground">$10K portfolio:</span>
                    <span className="ml-2 font-semibold">
                      ${((conviction_position.dollar_per_100k / 100000) * 10000).toLocaleString(undefined, {maximumFractionDigits: 0})}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">$50K portfolio:</span>
                    <span className="ml-2 font-semibold">
                      ${((conviction_position.dollar_per_100k / 100000) * 50000).toLocaleString(undefined, {maximumFractionDigits: 0})}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">$100K portfolio:</span>
                    <span className="ml-2 font-semibold">
                      ${conviction_position.dollar_per_100k.toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">$500K portfolio:</span>
                    <span className="ml-2 font-semibold">
                      ${((conviction_position.dollar_per_100k / 100000) * 500000).toLocaleString(undefined, {maximumFractionDigits: 0})}
                    </span>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground italic border-t border-primary/10 pt-2">
                  Max position: {conviction_position.max_pct}% (risk-adjusted cap)
                </p>
              </div>
            )}
          </div>
        </TabsContent>

        {/* Holding Tab */}
        <TabsContent value="holding" className="mt-4">
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground mb-4">
              Protect your position and know when to adjust:
            </p>

            {typeof key_levels.stop_loss === 'number' && current_price > 0 && (
              <ActionCheckbox
                label={`Set stop loss at $${key_levels.stop_loss.toFixed(2)}`}
                description={`Protect against major losses if stock breaks down (-${((current_price - key_levels.stop_loss) / current_price * 100).toFixed(1)}%)`}
              />
            )}

            {current_price > 0 && (
              <ActionCheckbox
                label={`Consider taking partial profits above $${(current_price * 1.15).toFixed(2)}`}
                description="Lock in gains if stock rallies significantly (+15%)"
              />
            )}

            <ActionCheckbox
              label="Monitor quarterly earnings reports"
              description="Watch for any negative surprises or guidance cuts"
            />

            <ActionCheckbox
              label="Check for rating changes monthly"
              description="Come back to DVRG to see if our rating has changed"
            />
          </div>
        </TabsContent>

        {/* Trading Tab */}
        <TabsContent value="trading" className="mt-4">
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground mb-4">
              For active traders managing positions:
            </p>

            {typeof key_levels.ideal_entry === 'number' && (
              <ActionCheckbox
                label={`Entry: $${key_levels.ideal_entry.toFixed(2)} (on pullback)`}
                description="Best risk/reward entry point"
              />
            )}

            {typeof key_levels.stop_loss === 'number' && current_price > 0 && (
              <ActionCheckbox
                label={`Stop: $${key_levels.stop_loss.toFixed(2)} (-${((current_price - key_levels.stop_loss) / current_price * 100).toFixed(1)}%)`}
                description="Exit if this level breaks"
              />
            )}

            {typeof key_levels.resistance === 'number' && current_price > 0 && (
              <ActionCheckbox
                label={`Target: $${key_levels.resistance.toFixed(2)} (+${((key_levels.resistance - current_price) / current_price * 100).toFixed(1)}%)`}
                description="Take profits at resistance"
              />
            )}

            <ActionCheckbox
              label="Watch volume on breakouts"
              description="Need 2x average volume for confirmation"
            />
          </div>
        </TabsContent>
      </Tabs>
    </Card>
  )
}

function ActionCheckbox({ label, description }: { label: string; description: string }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-accent/30 hover:bg-accent/50 transition-colors">
      <Checkbox className="mt-1" />
      <div className="flex-1">
        <p className="text-sm font-medium leading-tight">{label}</p>
        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
          {description}
        </p>
      </div>
    </div>
  )
}
