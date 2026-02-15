import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Calendar } from 'lucide-react'

export interface UpcomingEvent {
  date: string          // ISO format or display format
  event: string
  importance: 'high' | 'medium' | 'low'
  what_to_watch: string
  potential_impact?: string
}

interface WatchCalendarProps {
  events: UpcomingEvent[]
}

export function WatchCalendar({ events }: WatchCalendarProps) {
  if (!events || events.length === 0) return null

  return (
    <Card className="p-6 mt-6">
      <div className="flex items-center gap-2 mb-4">
        <Calendar className="h-5 w-5 text-primary" />
        <h3 className="text-xl font-bold">What to Watch Next 30 Days</h3>
        <span className="text-xs text-muted-foreground ml-2">
          • Events that could change this rating
        </span>
      </div>

      <div className="space-y-3">
        {events.map((event, i) => (
          <div
            key={i}
            className="flex items-start gap-4 p-4 rounded-lg border border-border hover:border-primary/50 transition-colors"
          >
            {/* Date Display */}
            <div className="flex-shrink-0 text-center min-w-[60px]">
              <div className="text-2xl font-bold text-primary">
                {formatDay(event.date)}
              </div>
              <div className="text-xs text-muted-foreground uppercase">
                {formatMonth(event.date)}
              </div>
            </div>

            {/* Event Details */}
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className="font-semibold text-sm">{event.event}</span>
                <Badge
                  variant={
                    event.importance === 'high' ? 'error' :
                    event.importance === 'medium' ? 'default' :
                    'secondary'
                  }
                  className="text-xs"
                >
                  {event.importance === 'high' ? 'High Impact' :
                   event.importance === 'medium' ? 'Medium Impact' :
                   'Low Impact'}
                </Badge>
              </div>

              <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                <span className="font-medium">📌 Watch for:</span>
                {event.what_to_watch}
              </p>

              {event.potential_impact && (
                <p className="text-xs text-muted-foreground italic">
                  Potential impact: {event.potential_impact}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-border">
        <p className="text-xs text-muted-foreground">
          💡 <strong>Tip:</strong> Set price alerts or calendar reminders for high-impact events
        </p>
      </div>
    </Card>
  )
}

function formatDay(dateStr: string): string {
  const date = new Date(dateStr)
  return date.getDate().toString()
}

function formatMonth(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short' })
}
