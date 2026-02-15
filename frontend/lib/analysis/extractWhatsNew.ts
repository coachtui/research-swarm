import { NewsItem } from '@/components/results/WhatsNew'

export function extractWhatsNew(data: any): NewsItem[] {
  const items: NewsItem[] = []

  // Helper function to format dates
  const formatDate = (dateStr: string | Date): string => {
    try {
      const date = new Date(dateStr)
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    } catch {
      return 'Recent'
    }
  }

  // From recent catalysts
  if (data.catalysts?.recent) {
    items.push(...data.catalysts.recent.map((catalyst: any) => ({
      date: formatDate(catalyst.date),
      title: catalyst.title,
      impact: catalyst.sentiment > 0 ? 'positive' :
              catalyst.sentiment < 0 ? 'negative' :
              'neutral',
      description: catalyst.summary || catalyst.description,
      source: catalyst.source
    } as NewsItem)))
  }

  // From earnings
  if (data.earnings?.recent_report) {
    const earnings = data.earnings.recent_report
    items.push({
      date: formatDate(earnings.date),
      title: `Q${earnings.quarter} earnings ${earnings.beat ? 'beat' : 'missed'} expectations`,
      impact: earnings.beat ? 'positive' : 'negative',
      description: `EPS $${earnings.actual} vs $${earnings.expected} expected (${earnings.surprise_pct}% ${earnings.beat ? 'beat' : 'miss'})`,
    } as NewsItem)
  }

  // From news hound output
  if (data.news_hound_output?.recent_news) {
    items.push(...data.news_hound_output.recent_news.slice(0, 3).map((news: any) => ({
      date: formatDate(news.date || news.published_at),
      title: news.headline || news.title,
      impact: news.sentiment > 0.3 ? 'positive' :
              news.sentiment < -0.3 ? 'negative' :
              'neutral',
      description: news.summary || news.snippet,
      source: news.source
    } as NewsItem)))
  }

  // From insider activity
  if (data.insider_activity?.recent_transactions) {
    const totalValue = data.insider_activity.recent_transactions
      .reduce((sum: number, t: any) => sum + (t.value || 0), 0)

    if (Math.abs(totalValue) > 1000000) {
      items.push({
        date: formatDate(data.insider_activity.latest_date || new Date()),
        title: `Insider ${totalValue > 0 ? 'buying' : 'selling'} activity`,
        impact: totalValue > 0 ? 'positive' : 'negative',
        description: `${data.insider_activity.recent_transactions.length} executives ${totalValue > 0 ? 'bought' : 'sold'} shares totaling $${(Math.abs(totalValue) / 1000000).toFixed(1)}M`
      } as NewsItem)
    }
  }

  // From institutional activity
  if (data.institutional_activity?.recent_changes) {
    const netShares = data.institutional_activity.recent_changes
      .reduce((sum: number, change: any) => sum + (change.shares || 0), 0)

    if (Math.abs(netShares) > 100000) {
      items.push({
        date: formatDate(data.institutional_activity.latest_filing || new Date()),
        title: `Institutional ${netShares > 0 ? 'accumulation' : 'distribution'}`,
        impact: netShares > 0 ? 'positive' : 'negative',
        description: `Net ${netShares > 0 ? 'buying' : 'selling'} of ${Math.abs(netShares).toLocaleString()} shares by major funds`
      } as NewsItem)
    }
  }

  // Sort by date (most recent first) and limit to 5 items
  return items
    .filter(item => item.date && item.title)
    .slice(0, 5)
}
