import React from 'react'
import { Card } from '@/components/ui/card'
import { CheckCircle, AlertTriangle, TrendingDown } from 'lucide-react'

export interface TakeawayItem {
  headline: string      // Short, punchy (5-8 words)
  context: string       // Explanation (10-15 words)
  metric?: string       // Optional data point
}

// Utility function to bold key metrics in text
function highlightMetrics(text: string): React.ReactNode {
  // Pattern: numbers with units like %, $, x, M, B, or standalone numbers
  const metricPattern = /(\$[\d,]+\.?\d*[KMB]?|\d+\.?\d*%|\d+\.?\d*x|\d+\.?\d*[KMB]|\d{2,}%? of [\w\s-]+(?:volume|average|avg))/gi

  const parts = text.split(metricPattern)

  return parts.map((part, i) => {
    // Check if this part matches the metric pattern
    if (metricPattern.test(part)) {
      metricPattern.lastIndex = 0 // Reset regex state
      return <strong key={i} className="font-semibold text-text-primary">{part}</strong>
    }
    return part
  })
}

// Patterns that indicate a bearish signal has been framed as a strength.
// These items are analytically relevant but should not appear under "Strengths"
// as that framing creates semantic confusion.
const BEARISH_FRAMING_PATTERNS = [
  /bearish divergence/i,
  /distribution signal/i,
  /smart money.*sell/i,
  /institutional.*exit/i,
  /heavy selling/i,
  /bearish signal/i,
  /selling pressure/i,
  /net selling/i,
  /insiders.*selling/i,
  /insider.*sell/i,
]

type StrengthClass = 'STRENGTH' | 'SETUP'

function classifyStrength(item: TakeawayItem): StrengthClass {
  const combined = `${item.headline} ${item.context}`
  if (BEARISH_FRAMING_PATTERNS.some(p => p.test(combined))) return 'SETUP'
  return 'STRENGTH'
}

interface KeyTakeawaysProps {
  strengths: TakeawayItem[]
  concerns: TakeawayItem[]
}

function TakeawayList({ items, bulletColor }: { items: TakeawayItem[]; bulletColor: string }) {
  return (
    <ul className="space-y-4">
      {items.slice(0, 5).map((item, i) => (
        <li key={i} className="group">
          <div className="flex items-start gap-2">
            <span className={`${bulletColor} mt-0.5 text-lg`}>•</span>
            <div className="flex-1">
              <p className="font-medium text-sm leading-tight mb-1">
                {item.headline}
              </p>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {highlightMetrics(item.context)}
              </p>
              {item.metric && (
                <span className={`inline-block mt-1 text-xs font-mono px-2 py-0.5 rounded ${bulletColor === 'text-success' ? 'bg-success/10' : bulletColor === 'text-warning' ? 'bg-warning/10' : 'bg-primary/10'}`}>
                  {item.metric}
                </span>
              )}
            </div>
          </div>
        </li>
      ))}
    </ul>
  )
}

export function KeyTakeaways({ strengths, concerns }: KeyTakeawaysProps) {
  if ((!strengths || strengths.length === 0) && (!concerns || concerns.length === 0)) {
    return null
  }

  // Split strengths into genuine positives vs bearish-framed items
  const trueStrengths = (strengths || []).filter(s => classifyStrength(s) === 'STRENGTH')
  const setupItems = (strengths || []).filter(s => classifyStrength(s) === 'SETUP')

  return (
    <section className="key-takeaways">
      <div className="flex items-center gap-2 mb-6">
        <h2 className="text-xl font-semibold">Key Takeaways</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Genuine Strengths */}
        {trueStrengths.length > 0 && (
          <Card className="p-6 border-l-4 border-l-success bg-success/5">
            <div className="flex items-center gap-2 mb-4">
              <div className="h-8 w-8 rounded-full bg-success/10 flex items-center justify-center">
                <CheckCircle className="h-5 w-5 text-success" />
              </div>
              <h3 className="font-semibold text-lg">Strengths</h3>
            </div>
            <TakeawayList items={trueStrengths} bulletColor="text-success" />
          </Card>
        )}

        {/* Risks */}
        {concerns && concerns.length > 0 && (
          <Card className="p-6 border-l-4 border-l-warning bg-warning/5">
            <div className="flex items-center gap-2 mb-4">
              <div className="h-8 w-8 rounded-full bg-warning/10 flex items-center justify-center">
                <AlertTriangle className="h-5 w-5 text-warning" />
              </div>
              <h3 className="font-semibold text-lg">Risks</h3>
            </div>
            <TakeawayList items={concerns} bulletColor="text-warning" />
          </Card>
        )}
      </div>

      {/* Notable Signal Conditions — reclassified bearish-framed items from Strengths.
          These are analytically significant divergence/distribution signals that are
          relevant to analysis but should not be framed as investment positives. */}
      {setupItems.length > 0 && (
        <Card className="mt-6 p-6 border-l-4 border-l-primary/40 bg-primary/5">
          <div className="flex items-center gap-2 mb-1">
            <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
              <TrendingDown className="h-5 w-5 text-primary/70" />
            </div>
            <h3 className="font-semibold text-lg">Notable Signal Conditions</h3>
          </div>
          <p className="text-xs text-text-tertiary mb-4 ml-10">
            Analytically significant — these are signal observations, not investment positives
          </p>
          <TakeawayList items={setupItems} bulletColor="text-primary/60" />
        </Card>
      )}
    </section>
  )
}
