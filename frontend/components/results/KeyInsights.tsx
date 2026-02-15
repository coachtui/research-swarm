import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface KeyInsightsProps {
  insights: string[]
}

export function KeyInsights({ insights }: KeyInsightsProps) {
  if (!insights || insights.length === 0) {
    return null
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Key Insights</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {insights.slice(0, 5).map((insight, i) => (
            <li key={i} className="flex items-start gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-semibold mt-0.5">
                {i + 1}
              </span>
              <span className="text-text-secondary leading-relaxed">{insight}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
