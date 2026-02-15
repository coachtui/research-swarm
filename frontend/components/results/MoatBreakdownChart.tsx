'use client'

import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from 'recharts'

interface MoatBreakdownProps {
  breakdown: {
    earnings_momentum: number
    financial_health: number
    valuation: number
    technical_strength: number
    sentiment_catalysts: number
  }
}

export function MoatBreakdownChart({ breakdown }: MoatBreakdownProps) {
  const data = [
    {
      name: 'Earnings Momentum',
      score: breakdown.earnings_momentum,
      fullName: 'Earnings Momentum',
    },
    {
      name: 'Financial Health',
      score: breakdown.financial_health,
      fullName: 'Financial Health',
    },
    {
      name: 'Valuation',
      score: breakdown.valuation,
      fullName: 'Valuation',
    },
    {
      name: 'Technical Strength',
      score: breakdown.technical_strength,
      fullName: 'Technical/Momentum',
    },
    {
      name: 'Sentiment',
      score: breakdown.sentiment_catalysts,
      fullName: 'Sentiment/Catalysts',
    },
  ]

  const getColor = (score: number) => {
    if (score >= 7.0) return '#10B981' // success
    if (score >= 4.0) return '#F59E0B' // warning
    return '#EF4444' // error
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-text-primary">Score Breakdown</h3>
        <span className="text-sm text-text-secondary">v2.0 Formula</span>
      </div>

      {/* Desktop: Recharts */}
      <div className="hidden md:block">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 120, bottom: 5 }}>
            <XAxis type="number" domain={[0, 10]} stroke="#6B7280" />
            <YAxis dataKey="fullName" type="category" stroke="#6B7280" tick={{ fill: '#9CA3AF' }} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1A1F2E',
                border: '1px solid #252B3D',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#FFFFFF' }}
              itemStyle={{ color: '#9CA3AF' }}
            />
            <Bar dataKey="score" radius={[0, 8, 8, 0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getColor(entry.score)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Mobile: Custom bars */}
      <div className="md:hidden space-y-3">
        {data.map((item, i) => (
          <div key={i} className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-text-secondary">{item.fullName}</span>
              <span className="font-semibold" style={{ color: getColor(item.score) }}>
                {item.score.toFixed(1)}
              </span>
            </div>
            <div className="h-3 bg-surface-elevated rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${(item.score / 10) * 100}%`,
                  backgroundColor: getColor(item.score),
                }}
              ></div>
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 text-xs text-text-tertiary pt-2">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-success"></div>
          <span>Strong (≥7.0)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-warning"></div>
          <span>Moderate (4.0-6.9)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-error"></div>
          <span>Weak (&lt;4.0)</span>
        </div>
      </div>
    </div>
  )
}
