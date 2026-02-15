import { UpcomingEvent } from '@/components/results/WatchCalendar'

export function extractWatchCalendar(data: any): UpcomingEvent[] {
  const events: UpcomingEvent[] = []
  const today = new Date()
  const thirtyDaysOut = new Date(today.getTime() + 30 * 24 * 60 * 60 * 1000)

  // Helper to check if date is in range
  const isInRange = (dateStr: string | Date): boolean => {
    try {
      const date = new Date(dateStr)
      return date >= today && date <= thirtyDaysOut
    } catch {
      return false
    }
  }

  // Upcoming earnings
  if (data.earnings?.next_report_date && isInRange(data.earnings.next_report_date)) {
    events.push({
      date: data.earnings.next_report_date,
      event: `Q${data.earnings.next_quarter || '?'} ${data.earnings.fiscal_year || ''} Earnings Report`,
      importance: 'high',
      what_to_watch: 'Revenue growth, EPS beat/miss, guidance for next quarter',
      potential_impact: 'Could move stock 5-10% on earnings surprise or guidance change'
    } as UpcomingEvent)
  }

  // Upcoming catalysts
  if (data.catalysts?.upcoming) {
    events.push(...data.catalysts.upcoming
      .filter((c: any) => isInRange(c.date))
      .map((c: any) => ({
        date: c.date,
        event: c.title,
        importance: c.importance || 'medium',
        what_to_watch: c.description || c.what_to_watch,
        potential_impact: c.impact || c.potential_impact
      } as UpcomingEvent))
    )
  }

  // Regulatory events
  if (data.regulatory?.upcoming_events) {
    events.push(...data.regulatory.upcoming_events
      .filter((e: any) => isInRange(e.date))
      .map((e: any) => ({
        date: e.date,
        event: e.title,
        importance: 'high',
        what_to_watch: `Ruling outcome on ${e.topic || 'regulatory matter'}`,
        potential_impact: e.potential_impact || 'Could significantly impact stock valuation'
      } as UpcomingEvent))
    )
  }

  // Product launches
  if (data.product_roadmap?.upcoming) {
    events.push(...data.product_roadmap.upcoming
      .filter((p: any) => isInRange(p.launch_date || p.date))
      .map((p: any) => ({
        date: p.launch_date || p.date,
        event: `${p.product_name} Launch`,
        importance: p.importance || 'medium',
        what_to_watch: p.key_features || 'Product reception, competitive positioning',
        potential_impact: 'Could boost revenue if well-received'
      } as UpcomingEvent))
    )
  }

  // Ex-dividend date
  if (data.dividend?.ex_date && isInRange(data.dividend.ex_date)) {
    events.push({
      date: data.dividend.ex_date,
      event: `Ex-Dividend Date ($${data.dividend.amount || '?'}/share)`,
      importance: 'low',
      what_to_watch: 'Buy before this date to receive dividend',
      potential_impact: 'Stock typically drops by dividend amount on ex-date'
    } as UpcomingEvent)
  }

  // Analyst days / investor presentations
  if (data.events?.upcoming) {
    events.push(...data.events.upcoming
      .filter((e: any) => isInRange(e.date) && e.type?.includes('investor'))
      .map((e: any) => ({
        date: e.date,
        event: e.title || 'Investor Presentation',
        importance: 'medium',
        what_to_watch: 'New guidance, strategic initiatives, management commentary',
        potential_impact: 'Can provide insight into company direction'
      } as UpcomingEvent))
    )
  }

  // Sort by date and limit to 5 events
  return events
    .filter(event => event.date && event.event)
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
    .slice(0, 5)
}
