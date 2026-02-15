'use client'

import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { ConvictionStatement, DecisionFramework, TriggerItem } from '@/types/api'

interface BottomLineProps {
  conviction?: ConvictionStatement | null
  framework?: DecisionFramework | null
  upgradeTriggers?: TriggerItem[] | null
  downgradeTriggers?: TriggerItem[] | null
}

export function BottomLine({
  conviction,
  framework,
  upgradeTriggers,
  downgradeTriggers,
}: BottomLineProps) {
  const [selectedTab, setSelectedTab] = useState<'own' | 'dont' | 'trade'>('own')

  if (!conviction && !framework) return null

  return (
    <section className="bottom-line">
      <h2 className="text-2xl font-bold mb-4">✨ The Bottom Line</h2>

      {/* Summary */}
      {conviction && (
        <Card className="mb-6 bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 mb-3">
              <Badge variant="default" className="text-sm">
                {conviction.conviction_level} Conviction
              </Badge>
            </div>
            <p className="text-base leading-relaxed text-text-primary">{conviction.bottom_line}</p>
          </CardContent>
        </Card>
      )}

      {/* Action Plan Tabs */}
      {framework && (
        <Card className="mb-6">
          <CardContent className="pt-6">
            <h3 className="font-semibold text-lg mb-4">📋 Your Action Plan</h3>

            <div className="flex gap-2 mb-6 border-b border-surface-elevated">
              {[
                { key: 'own' as const, label: 'If You Own It' },
                { key: 'dont' as const, label: "If You Don't" },
                { key: 'trade' as const, label: 'If You Trade' },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setSelectedTab(tab.key)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    selectedTab === tab.key
                      ? 'border-primary text-primary'
                      : 'border-transparent text-text-tertiary hover:text-text-primary'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="min-h-24">
              {selectedTab === 'own' && (
                <div className="space-y-3">
                  <p className="text-sm leading-relaxed text-text-secondary">
                    {framework.current_holders.detail}
                  </p>
                  {framework.current_holders.conditions.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs font-medium text-text-tertiary mb-2">Conditions:</p>
                      <ul className="space-y-1">
                        {framework.current_holders.conditions.map((condition, i) => (
                          <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
                            <span className="text-primary mt-1">•</span>
                            {condition}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              {selectedTab === 'dont' && (
                <div className="space-y-3">
                  <p className="text-sm leading-relaxed text-text-secondary">
                    {framework.new_buyers.detail}
                  </p>
                  {framework.new_buyers.caveat && (
                    <p className="text-sm text-warning italic mt-2">⚠️ {framework.new_buyers.caveat}</p>
                  )}
                </div>
              )}
              {selectedTab === 'trade' && (
                <div className="space-y-3">
                  <p className="text-sm leading-relaxed text-text-secondary">
                    Look for tactical entries on pullbacks to support levels or breakouts above
                    resistance. Use tight stops and scale in/out of positions based on technical
                    signals.
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Best Suited For */}
      {conviction?.best_suited_for && (
        <Card className="mb-6">
          <CardContent className="pt-6">
            <h3 className="font-semibold text-lg mb-4">👤 Best Suited For</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-text-tertiary uppercase tracking-wide mb-1">
                  Investor Type
                </p>
                <p className="text-sm font-medium text-text-primary">
                  {conviction.best_suited_for.investor_type}
                </p>
              </div>
              <div>
                <p className="text-xs text-text-tertiary uppercase tracking-wide mb-1">
                  Risk Tolerance
                </p>
                <p className="text-sm font-medium text-text-primary">
                  {conviction.best_suited_for.risk_tolerance}
                </p>
              </div>
              <div>
                <p className="text-xs text-text-tertiary uppercase tracking-wide mb-1">
                  Time Horizon
                </p>
                <p className="text-sm font-medium text-text-primary">
                  {conviction.best_suited_for.time_horizon}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Upgrade/Downgrade Triggers */}
      {(upgradeTriggers?.length || downgradeTriggers?.length) ? (
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
      ) : null}
    </section>
  )
}
