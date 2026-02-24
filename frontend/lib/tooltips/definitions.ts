// Educational tooltip definitions for technical investment terms

export interface TooltipDefinition {
  term: string
  definition: string
  example?: string
}

export const TOOLTIP_DEFINITIONS: Record<string, TooltipDefinition> = {
  rsi: {
    term: 'RSI (Relative Strength Index)',
    definition: 'Measures momentum on a 0-100 scale. Below 30 = oversold (bounce likely), above 70 = overbought (pullback likely).',
    example: 'At 23.4, this is very oversold. Historically, stocks at this level tend to bounce 5-10% within 2 weeks.',
  },
  stochastic: {
    term: 'Stochastic Oscillator',
    definition: 'Another momentum indicator showing overbought/oversold conditions on a 0-100 scale.',
    example: 'At 4.4, this is extremely oversold - one of the lowest readings you\'ll see.',
  },
  macd: {
    term: 'MACD (Moving Average Convergence Divergence)',
    definition: 'Shows trend direction and momentum. Crossovers signal potential trend changes.',
    example: 'When MACD crosses above signal line, it\'s a bullish signal. Below = bearish.',
  },
  bollinger_bands: {
    term: 'Bollinger Bands',
    definition: 'Shows normal price range. Price near upper band = expensive, near lower band = cheap.',
    example: 'Trading at lower Bollinger Band means the stock is 2 standard deviations below average - statistically cheap.',
  },
  volume: {
    term: 'Volume',
    definition: 'Number of shares traded. High volume confirms price moves, low volume suggests weak conviction.',
    example: 'A breakout on 3x average volume is much more reliable than one on light volume.',
  },
  institutional_activity: {
    term: 'Institutional Activity',
    definition: 'Trading by large investors (hedge funds, mutual funds, pensions). They move markets with big orders.',
    example: 'When institutions accumulate 5%+ of shares in a quarter, that\'s a strong bullish signal.',
  },
  insider_activity: {
    term: 'Insider Activity',
    definition: 'Trading by company executives and board members. They know the business best - their buying/selling is a strong signal.',
    example: 'Multiple insiders buying after earnings = very bullish. They rarely buy before bad news.',
  },
  fair_value: {
    term: 'Structural Valuation Reference',
    definition: 'A long-term anchor derived from fundamental models (P/E, DCF, EV/EBITDA). Represents a structural reference point, not a "correct" price. High-quality growth stocks routinely trade above this anchor — that is a regime classification, not a valuation error.',
    example: 'If the Structural Valuation Reference is $150 and stock trades at $250, the stock operates in a Structural Premium regime — not overvalued, but priced for continued execution.',
  },
  divergence: {
    term: 'Signal Divergence',
    definition: 'When different indicators disagree. For example, analysts bullish but insiders selling. These gaps often signal hidden risks or opportunities.',
    example: 'Analysts upgrading to BUY while insiders sell = red flag. Smart money might know something.',
  },
  earnings_momentum: {
    term: 'Earnings Momentum',
    definition: 'Tracks if analysts are raising or lowering their earnings estimates. Rising estimates = bullish, falling = bearish.',
    example: '10 analysts raising estimates in past month = strong earnings momentum. Stock likely to follow.',
  },
  pe_ratio: {
    term: 'P/E Ratio (Price-to-Earnings)',
    definition: 'Price divided by earnings. Shows how expensive a stock is. Higher P/E = more expensive.',
    example: 'P/E of 15 means you pay $15 for every $1 of annual earnings. Sector average is key for comparison.',
  },
  ev_ebitda: {
    term: 'EV/EBITDA',
    definition: 'Enterprise Value to EBITDA. Better than P/E for comparing companies with different debt levels.',
    example: 'EV/EBITDA of 10 vs sector average of 15 means the stock is cheap relative to peers.',
  },
  dcf: {
    term: 'DCF (Discounted Cash Flow)',
    definition: 'Values a company by forecasting future cash flows and discounting them to today\'s dollars.',
    example: 'DCF shows intrinsic value. If DCF says $200 but stock trades at $150, that\'s 25% upside.',
  },
  support_level: {
    term: 'Support Level',
    definition: 'Price level where buying typically comes in, preventing further declines.',
    example: 'If stock bounced at $100 three times, that\'s strong support. Breaking below is bearish.',
  },
  resistance_level: {
    term: 'Resistance Level',
    definition: 'Price level where selling typically appears, preventing further gains.',
    example: 'If stock topped out at $150 multiple times, that\'s resistance. Breaking above is bullish.',
  },
  stop_loss: {
    term: 'Stop Loss',
    definition: 'Price level where you sell to limit losses if trade goes against you.',
    example: 'Buy at $100 with stop at $92 = max 8% loss. Protects capital for other opportunities.',
  },
  risk_reward: {
    term: 'Risk/Reward Ratio',
    definition: 'Compares potential upside to potential downside. Good trades have 2:1 or better.',
    example: 'Buy at $100, target $130, stop $92 = $30 upside vs $8 downside = 3.75:1 risk/reward.',
  },
  conviction: {
    term: 'Conviction Level',
    definition: 'How confident we are in the rating. Higher conviction = larger position size appropriate.',
    example: 'High conviction BUY with multiple bullish signals = consider 8-10% portfolio weight.',
  },
  moat: {
    term: 'Economic Moat',
    definition: 'Competitive advantages that protect profits from competition. Think "castle with a moat".',
    example: 'Apple\'s ecosystem lock-in is a moat. Once you buy iPhone/Mac, switching is painful.',
  },
  catalyst: {
    term: 'Catalyst',
    definition: 'Upcoming event that could significantly move the stock price.',
    example: 'FDA drug approval decision, earnings report, product launch = catalysts to watch.',
  },
}

export function getTooltip(key: keyof typeof TOOLTIP_DEFINITIONS): TooltipDefinition | undefined {
  return TOOLTIP_DEFINITIONS[key]
}
