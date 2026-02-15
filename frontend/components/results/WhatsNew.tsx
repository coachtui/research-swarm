import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Newspaper, TrendingUp, TrendingDown, Minus } from 'lucide-react'

export interface NewsItem {
  date: string          // e.g., "Feb 12"
  title: string
  impact: 'positive' | 'negative' | 'neutral'
  description: string
  source?: string       // Optional: "Bloomberg", "CNBC", etc.
}

interface WhatsNewProps {
  items: NewsItem[]
}

export function WhatsNew({ items }: WhatsNewProps) {
  if (!items || items.length === 0) return null

  return (
    <Card className="p-6 mt-6">
      <div className="flex items-center gap-2 mb-4">
        <Newspaper className="h-5 w-5 text-primary" />
        <h3 className="text-xl font-bold">What's New This Week</h3>
        <span className="text-xs text-muted-foreground ml-2">
          • Recent developments affecting this stock
        </span>
      </div>

      <div className="space-y-3">
        {items.map((item, i) => (
          <div
            key={i}
            className="flex items-start gap-3 p-3 rounded-lg bg-accent/30 hover:bg-accent/50 transition-colors"
          >
            {/* Impact Icon */}
            <div className="flex-shrink-0 mt-1">
              {item.impact === 'positive' && (
                <div className="h-6 w-6 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                  <TrendingUp className="h-4 w-4 text-green-600 dark:text-green-400" />
                </div>
              )}
              {item.impact === 'negative' && (
                <div className="h-6 w-6 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                  <TrendingDown className="h-4 w-4 text-red-600 dark:text-red-400" />
                </div>
              )}
              {item.impact === 'neutral' && (
                <div className="h-6 w-6 rounded-full bg-gray-100 dark:bg-gray-900/30 flex items-center justify-center">
                  <Minus className="h-4 w-4 text-gray-600 dark:text-gray-400" />
                </div>
              )}
            </div>

            {/* Content */}
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-medium text-muted-foreground">
                  {item.date}
                </span>
                <Badge
                  variant={
                    item.impact === 'positive' ? 'default' :
                    item.impact === 'negative' ? 'destructive' :
                    'outline'
                  }
                  className="text-xs"
                >
                  {item.impact === 'positive' ? 'Bullish' :
                   item.impact === 'negative' ? 'Bearish' :
                   'Neutral'}
                </Badge>
                {item.source && (
                  <span className="text-xs text-muted-foreground">
                    • {item.source}
                  </span>
                )}
              </div>
              <p className="font-medium text-sm mb-1">{item.title}</p>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {item.description}
              </p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
