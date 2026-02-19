'use client'

import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { TrendingUp, TrendingDown, Minus, Calendar } from 'lucide-react'
import type { NewsItem } from './WhatsNew'
import type { UpcomingEvent } from './WatchCalendar'

interface RecentDevelopmentsProps {
  recentItems: NewsItem[]
  upcomingEvents: UpcomingEvent[]
}

export function RecentDevelopments({ recentItems, upcomingEvents }: RecentDevelopmentsProps) {
  const hasRecent = recentItems && recentItems.length > 0
  const hasUpcoming = upcomingEvents && upcomingEvents.length > 0

  if (!hasRecent && !hasUpcoming) return null

  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-5">
        <Calendar className="h-5 w-5 text-primary" />
        <h3 className="text-lg font-semibold">Recent Developments</h3>
        <span className="text-xs text-muted-foreground ml-1">· Events that could affect this rating</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left: Recent news */}
        {hasRecent && (
          <div>
            <p className="text-xs font-medium text-text-tertiary uppercase tracking-wide mb-3">Recent</p>
            <div className="space-y-2">
              {recentItems.map((item, i) => (
                <div key={i} className="flex items-start gap-2.5">
                  <div className="flex-shrink-0 mt-0.5">
                    {item.impact === 'positive' && (
                      <div className="h-5 w-5 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                        <TrendingUp className="h-3 w-3 text-green-600 dark:text-green-400" />
                      </div>
                    )}
                    {item.impact === 'negative' && (
                      <div className="h-5 w-5 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                        <TrendingDown className="h-3 w-3 text-red-600 dark:text-red-400" />
                      </div>
                    )}
                    {item.impact === 'neutral' && (
                      <div className="h-5 w-5 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                        <Minus className="h-3 w-3 text-gray-500" />
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="text-xs text-muted-foreground">{item.date}</span>
                      {item.source && (
                        <span className="text-xs text-muted-foreground">· {item.source}</span>
                      )}
                    </div>
                    <p className="text-sm font-medium leading-snug">{item.title}</p>
                    {item.description && (
                      <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{item.description}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Right: Upcoming events */}
        {hasUpcoming && (
          <div>
            <p className="text-xs font-medium text-text-tertiary uppercase tracking-wide mb-3">Upcoming</p>
            <div className="space-y-2">
              {upcomingEvents.map((event, i) => (
                <div key={i} className="flex items-start gap-3 p-3 rounded-lg border border-border">
                  {/* Date chip */}
                  <div className="flex-shrink-0 text-center min-w-[44px]">
                    <div className="text-lg font-bold text-primary leading-none">
                      {formatDay(event.date)}
                    </div>
                    <div className="text-xs text-muted-foreground uppercase">
                      {formatMonth(event.date)}
                    </div>
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-sm font-medium">{event.event}</span>
                      <Badge
                        variant={
                          event.importance === 'high' ? 'error' :
                          event.importance === 'medium' ? 'default' :
                          'secondary'
                        }
                        className="text-xs"
                      >
                        {event.importance === 'high' ? 'High' :
                         event.importance === 'medium' ? 'Medium' : 'Low'}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Watch: {event.what_to_watch}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}

function formatDay(dateStr: string): string {
  const date = new Date(dateStr)
  return isNaN(date.getTime()) ? '—' : date.getDate().toString()
}

function formatMonth(dateStr: string): string {
  const date = new Date(dateStr)
  return isNaN(date.getTime()) ? '' : date.toLocaleDateString('en-US', { month: 'short' })
}
