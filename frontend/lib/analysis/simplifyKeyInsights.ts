import type { TakeawayItem } from '@/components/results/KeyTakeaways'

// Substrings present in backend error fallback strings — checked against raw strings
// before any transformation. Specific enough to avoid false positives (e.g. "analysis
// pipeline" not just "pipeline"). No dependency on exact dash character encoding.
const RAW_ERROR_PATTERNS = [
  'error parsing synthesis',
  'analysis pipeline failed',
  'please rerun the analysis',
  'error in synthesis',
  'analysis pipeline error',
  'synthesis generation failed',
  'retry required before making investment',
]

function isRawErrorString(text: string): boolean {
  const lower = text.toLowerCase()
  return RAW_ERROR_PATTERNS.some(p => lower.includes(p))
}

/**
 * Transforms verbose key insights and risk factors into simplified,
 * scannable bullet points with headline/context/metric structure.
 */
export function simplifyKeyInsights(
  rawInsights: string[],
  rawRisks: string[]
): { strengths: TakeawayItem[]; concerns: TakeawayItem[] } {
  const strengths = rawInsights
    .filter(s => !isRawErrorString(s))
    .slice(0, 5)
    .map((insight) => transformToSimpleBullet(insight, 'strength'))
  const concerns = rawRisks
    .filter(r => !isRawErrorString(r))
    .slice(0, 5)
    .map((risk) => transformToSimpleBullet(risk, 'concern'))

  return { strengths, concerns }
}

function transformToSimpleBullet(text: string, type: 'strength' | 'concern'): TakeawayItem {
  // Parse verbose text into headline + context + metric
  // Handle formats like: "Title: description (metric) additional context"

  const parts = extractKeyParts(text)

  return {
    headline: simplifyHeadline(parts.topic, type),
    context: simplifyContext(parts.detail),
    metric: parts.metric,
  }
}

function extractKeyParts(text: string): { topic: string; detail: string; metric?: string } {
  // Try to split on colon for "Topic: Details" format
  const colonSplit = text.split(':')

  let topic = ''
  let detail = ''
  let metric: string | undefined

  if (colonSplit.length >= 2) {
    topic = colonSplit[0].trim()
    detail = colonSplit.slice(1).join(':').trim()
  } else {
    // No colon, use first sentence as topic, rest as detail
    const sentences = text.split('. ')
    topic = sentences[0]
    detail = sentences.slice(1).join('. ')
  }

  // Extract metrics (numbers with %, $, or multiplier suffix)
  // Exclude X/10 scores — those are internal signal scores, shown in dedicated components
  const metricMatch = text.match(/(\d+\.?\d*%|\$\d+\.?\d*[KMB]?|\d+\.?\d*x)/g)
  if (metricMatch && metricMatch.length > 0) {
    // Pick the most prominent metric
    metric = metricMatch[0]
  }

  return { topic, detail, metric }
}

function simplifyHeadline(text: string, type: 'strength' | 'concern'): string {
  // Remove jargon, keep it punchy

  // Common jargon mappings
  const jargonMap: Record<string, string> = {
    'Fundamental-Technical Divergence': 'Business strong, stock weak',
    'Technical-Fundamental Divergence': 'Stock strong, business weak',
    'AI Investment Paradox': 'AI spending not yet paying off',
    'Capital Expenditure': 'Heavy spending',
    'Oversold Bounce Setup': 'Technically oversold',
    'Valuation-Growth Paradox': 'Growing fast, priced high',
    'Valuation Premium': 'Premium valuation',
    'Margin Compression': 'Shrinking margins',
    'Revenue Deceleration': 'Slowing growth',
    'Earnings Momentum': 'Strong earnings',
    'Financial Health': 'Rock-solid balance sheet',
    'Operating Leverage': 'Efficient operations',
    'Competitive Moat': 'Strong competitive edge',
    'Market Share Gains': 'Winning market share',
    'Pricing Power': 'Can raise prices',
  }

  // Check for direct mappings first
  const simplifiedText = jargonMap[text] || text

  return simplifiedText
}

function simplifyContext(text: string): string {
  // Remove complex terminology

  let simplified = text
    .replace(/death cross formation/gi, 'bearish technical signal')
    .replace(/golden cross formation/gi, 'bullish technical signal')
    .replace(/POC level/gi, 'key price level')
    .replace(/lower Bollinger Band/gi, 'support level')
    .replace(/upper Bollinger Band/gi, 'resistance level')
    .replace(/RSI oversold/gi, 'technically oversold')
    .replace(/RSI overbought/gi, 'technically overbought')
    .replace(/institutional accumulation/gi, 'big investors buying')
    .replace(/institutional distribution/gi, 'big investors selling')
    .replace(/insider buying/gi, 'executives buying')
    .replace(/insider selling/gi, 'executives selling')
    .replace(/positive free cash flow/gi, 'generating cash')
    .replace(/negative free cash flow/gi, 'burning cash')

  return simplified
}

/**
 * Legacy fallback: If called with simple string arrays (old format),
 * convert them to the new structure
 */
export function legacyInsightsToTakeaways(
  insights: string[],
  risks: string[]
): { strengths: TakeawayItem[]; concerns: TakeawayItem[] } {
  return simplifyKeyInsights(insights, risks)
}
