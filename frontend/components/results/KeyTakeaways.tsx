import { Card, CardContent } from '@/components/ui/card'
import { CheckCircle, AlertTriangle } from 'lucide-react'

export interface TakeawayItem {
  headline: string      // Short, punchy (5-8 words)
  context: string       // Explanation (10-15 words)
  metric?: string       // Optional data point
}

interface KeyTakeawaysProps {
  strengths: TakeawayItem[]
  concerns: TakeawayItem[]
}

export function KeyTakeaways({ strengths, concerns }: KeyTakeawaysProps) {
  if ((!strengths || strengths.length === 0) && (!concerns || concerns.length === 0)) {
    return null
  }

  return (
    <section className="key-takeaways">
      <div className="flex items-center gap-2 mb-6">
        <span className="text-2xl">⚡</span>
        <h2 className="text-2xl font-bold">What You Need to Know</h2>
        <span className="text-sm text-muted-foreground ml-2">
          • The 60-second version
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Strengths */}
        {strengths && strengths.length > 0 && (
          <Card className="p-6 border-l-4 border-l-success bg-success/5">
            <div className="flex items-center gap-2 mb-4">
              <div className="h-8 w-8 rounded-full bg-success/10 flex items-center justify-center">
                <CheckCircle className="h-5 w-5 text-success" />
              </div>
              <h3 className="font-semibold text-lg">What's Working</h3>
            </div>

            <ul className="space-y-4">
              {strengths.slice(0, 5).map((strength, i) => (
                <li key={i} className="group">
                  <div className="flex items-start gap-2">
                    <span className="text-success mt-0.5 text-lg">•</span>
                    <div className="flex-1">
                      <p className="font-medium text-sm leading-tight mb-1">
                        {strength.headline}
                      </p>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {strength.context}
                      </p>
                      {strength.metric && (
                        <span className="inline-block mt-1 text-xs font-mono bg-success/10 px-2 py-0.5 rounded">
                          {strength.metric}
                        </span>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {/* Concerns */}
        {concerns && concerns.length > 0 && (
          <Card className="p-6 border-l-4 border-l-warning bg-warning/5">
            <div className="flex items-center gap-2 mb-4">
              <div className="h-8 w-8 rounded-full bg-warning/10 flex items-center justify-center">
                <AlertTriangle className="h-5 w-5 text-warning" />
              </div>
              <h3 className="font-semibold text-lg">What's Concerning</h3>
            </div>

            <ul className="space-y-4">
              {concerns.slice(0, 5).map((concern, i) => (
                <li key={i} className="group">
                  <div className="flex items-start gap-2">
                    <span className="text-warning mt-0.5 text-lg">•</span>
                    <div className="flex-1">
                      <p className="font-medium text-sm leading-tight mb-1">
                        {concern.headline}
                      </p>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {concern.context}
                      </p>
                      {concern.metric && (
                        <span className="inline-block mt-1 text-xs font-mono bg-warning/10 px-2 py-0.5 rounded">
                          {concern.metric}
                        </span>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </section>
  )
}
