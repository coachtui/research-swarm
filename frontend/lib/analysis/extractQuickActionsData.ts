export interface QuickActionsData {
  ticker: string
  current_price: number
  rating: string
  key_levels: {
    ideal_entry?: number
    stop_loss?: number
    resistance?: number
    support?: number
  }
  next_catalyst?: string
}

export function extractQuickActionsData(data: any, ticker: string): QuickActionsData {
  // Extract current price from decision_intelligence first
  const current_price = data.decision_intelligence?.current_price ||
                       data.current_price ||
                       data.price ||
                       data.market_data?.current_price ||
                       100 // Fallback to avoid 0

  // Extract rating
  const rating = data.decision_intelligence?.rating ||
                data.rating ||
                'HOLD'

  // Extract key levels from recommended_strategy (new structure)
  const recommendedStrategy = data.decision_intelligence?.recommended_strategy
  const tradeSetup = data.decision_intelligence?.enhanced_trade_setup || data.trade_setup || {}

  const key_levels = {
    ideal_entry: recommendedStrategy?.entry?.ideal_zone?.low ||
                recommendedStrategy?.entry?.ideal_zone?.high ||
                tradeSetup.conservative_entry ||
                tradeSetup.entry_zone?.ideal ||
                tradeSetup.entry_price ||
                undefined,
    stop_loss: recommendedStrategy?.exit?.stop_loss ||
              tradeSetup.conservative_stop ||
              tradeSetup.stop_loss ||
              undefined,
    resistance: recommendedStrategy?.exit?.target_1 ||
               tradeSetup.targets?.conservative ||
               tradeSetup.resistance ||
               undefined,
    support: tradeSetup.support ||
            tradeSetup.entry_zone?.floor ||
            recommendedStrategy?.entry?.ideal_zone?.low ||
            undefined
  }

  // Extract next catalyst
  let next_catalyst: string | undefined
  if (data.catalysts?.upcoming?.[0]) {
    const nextCat = data.catalysts.upcoming[0]
    next_catalyst = nextCat.title || nextCat.event
  } else if (data.earnings?.next_report_date) {
    next_catalyst = `Q${data.earnings.next_quarter || '?'} earnings (${formatDate(data.earnings.next_report_date)})`
  }

  return {
    ticker,
    current_price,
    rating,
    key_levels,
    next_catalyst
  }
}

function formatDate(dateStr: string | Date): string {
  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  } catch {
    return 'upcoming'
  }
}
