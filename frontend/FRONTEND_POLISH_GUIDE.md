# Frontend Polish Implementation Guide

This guide explains the new educational components added to differentiate the casual frontend (for new investors) from the professional PDF report (for seasoned investors).

## Overview of New Components

### 1. Educational Tooltips
**Location:** `components/ui/educational-tooltip.tsx`

Makes technical investment terms understandable for new investors with inline explanations.

#### Usage Example:

```tsx
import { EducationalTooltip } from '@/components/ui/educational-tooltip'
import { getTooltip } from '@/lib/tooltips/definitions'

// Simple usage with predefined definitions
const tooltip = getTooltip('rsi')
<EducationalTooltip {...tooltip}>
  RSI 23.4
</EducationalTooltip>

// Custom usage
<EducationalTooltip
  term="Custom Term"
  definition="What it means in plain English"
  example="Real-world example of the concept"
>
  Technical Jargon
</EducationalTooltip>
```

#### Adding New Tooltip Definitions:

Edit `lib/tooltips/definitions.ts`:

```typescript
export const TOOLTIP_DEFINITIONS = {
  // ... existing definitions

  new_term: {
    term: 'New Term Name',
    definition: 'Clear, simple explanation (1-2 sentences)',
    example: 'Optional: Real-world example that makes it concrete',
  },
}
```

#### Common Terms Already Defined:
- `rsi` - Relative Strength Index
- `stochastic` - Stochastic Oscillator
- `macd` - MACD indicator
- `bollinger_bands` - Bollinger Bands
- `volume` - Trading volume
- `institutional_activity` - Institutional trading
- `insider_activity` - Insider trading
- `fair_value` - Fair value estimation
- `divergence` - Signal divergence
- `earnings_momentum` - Earnings estimate changes
- `pe_ratio` - Price-to-Earnings ratio
- `ev_ebitda` - EV/EBITDA valuation
- `dcf` - Discounted Cash Flow
- `support_level` - Support levels
- `resistance_level` - Resistance levels
- `stop_loss` - Stop loss orders
- `risk_reward` - Risk/reward ratio
- `conviction` - Conviction level
- `moat` - Economic moat
- `catalyst` - Market catalysts

---

### 2. What's New This Week
**Location:** `components/results/WhatsNew.tsx`

Shows recent news, earnings, insider activity, and other developments affecting the stock.

#### Usage:

```tsx
import { WhatsNew } from '@/components/results/WhatsNew'
import { extractWhatsNew } from '@/lib/analysis/extractWhatsNew'

// In your component
const whatsNewItems = extractWhatsNew(analysisData)

<WhatsNew items={whatsNewItems} />
```

#### Data Structure:

```typescript
interface NewsItem {
  date: string          // "Feb 12"
  title: string
  impact: 'positive' | 'negative' | 'neutral'
  description: string
  source?: string       // Optional: "Bloomberg", "CNBC"
}
```

#### The extractor looks for:
- Recent catalysts
- Earnings reports
- News sentiment
- Insider transactions
- Institutional activity changes

**Placement:** After "The Verdict", before "What You Need to Know"

---

### 3. What to Watch Calendar
**Location:** `components/results/WatchCalendar.tsx`

Displays upcoming events in the next 30 days that could change the stock rating.

#### Usage:

```tsx
import { WatchCalendar } from '@/components/results/WatchCalendar'
import { extractWatchCalendar } from '@/lib/analysis/extractWatchCalendar'

const watchCalendarEvents = extractWatchCalendar(analysisData)

<WatchCalendar events={watchCalendarEvents} />
```

#### Data Structure:

```typescript
interface UpcomingEvent {
  date: string          // ISO format
  event: string
  importance: 'high' | 'medium' | 'low'
  what_to_watch: string
  potential_impact?: string
}
```

#### The extractor looks for:
- Upcoming earnings reports
- Product launches
- Regulatory events
- Ex-dividend dates
- Investor presentations

**Placement:** After "Signal Divergence Section"

---

### 4. Quick Actions Checklist
**Location:** `components/results/QuickActions.tsx`

Interactive action items based on user's situation (buying, holding, or trading).

#### Usage:

```tsx
import { QuickActions } from '@/components/results/QuickActions'
import { extractQuickActionsData } from '@/lib/analysis/extractQuickActionsData'

const quickActionsData = extractQuickActionsData(analysisData, ticker)

<QuickActions
  ticker={quickActionsData.ticker}
  current_price={quickActionsData.current_price}
  rating={quickActionsData.rating}
  key_levels={quickActionsData.key_levels}
  next_catalyst={quickActionsData.next_catalyst}
/>
```

#### Features:
- **3 Tabs:** Thinking of Buying, Currently Holding, Active Trading
- **Position Sizing:** Suggested allocation by portfolio size
- **Actionable Items:** Specific price levels and next steps

**Placement:** After "Trade Setup"

---

### 5. Professional Analysis Section
**Location:** `components/results/ProfessionalAnalysisSection.tsx`

Clearly differentiates the casual frontend from the professional PDF report.

#### Usage:

```tsx
import { ProfessionalAnalysisSection } from '@/components/results/ProfessionalAnalysisSection'

<ProfessionalAnalysisSection
  ticker="AAPL"
  onDownloadPDF={async () => {
    // Your PDF download logic
    const response = await fetch(`/api/runs/${runId}/report/pdf`)
    const blob = await response.blob()
    // ... download logic
  }}
  professionalContent={<ProfessionalAnalysisContent />} // Optional
/>
```

#### Features:
- **Side-by-side comparison** of frontend vs professional report
- **View Professional Analysis** button (opens modal)
- **Download PDF** button
- Clear messaging about different audiences

**Placement:** Replaces the old "Download PDF" button at the end

---

## How Data Flows

### Backend → Frontend → Components

```
API Response (full_output)
    ↓
Data Extraction Utilities
    ├── extractWhatsNew()
    ├── extractWatchCalendar()
    └── extractQuickActionsData()
    ↓
Component Props
    ↓
Rendered UI
```

### Example in results page:

```tsx
// Extract data
const whatsNewItems = extractWhatsNew(full_output)
const watchCalendarEvents = extractWatchCalendar(full_output)
const quickActionsData = extractQuickActionsData(full_output, ticker)

// Render components
<VerdictSummary {...verdictData} />
<WhatsNew items={whatsNewItems} />
<KeyTakeaways strengths={strengths} concerns={concerns} />
<SignalDivergenceSection breakdown={signal_breakdown} />
<WatchCalendar events={watchCalendarEvents} />
<TradeSetup setup={trade_setup} ticker={ticker} />
<QuickActions {...quickActionsData} />
```

---

## Adding Tooltips to Existing Components

### Step 1: Identify Technical Terms

Look for jargon that new investors won't understand:
- RSI, MACD, Stochastic
- P/E ratio, EV/EBITDA
- Insider activity, institutional activity
- Fair value, DCF
- Support, resistance, stop loss

### Step 2: Wrap Terms in Tooltips

**Before:**
```tsx
<p>Extreme oversold technical conditions (RSI 23.4, Stochastic 4.4)</p>
```

**After:**
```tsx
import { EducationalTooltip } from '@/components/ui/educational-tooltip'
import { getTooltip } from '@/lib/tooltips/definitions'

<p>
  Extreme oversold technical conditions (
  <EducationalTooltip {...getTooltip('rsi')}>
    RSI 23.4
  </EducationalTooltip>
  ,
  <EducationalTooltip {...getTooltip('stochastic')}>
    Stochastic 4.4
  </EducationalTooltip>
  )
</p>
```

### Step 3: Test on Mobile

Tooltips work on mobile with tap-to-show. Test that:
- Tooltip appears on hover (desktop) and tap (mobile)
- Content is readable and not too wide
- Examples make sense

---

## Styling & Theming

All components use shadcn/ui primitives and follow your existing design system:

- **Colors:** `primary`, `success`, `warning`, `destructive`
- **Text:** `muted-foreground`, `text-primary`, `text-secondary`
- **Spacing:** Consistent with existing cards and sections
- **Dark Mode:** Fully supported with `dark:` variants

---

## Testing Checklist

### Educational Tooltips
- [ ] Tooltips appear on hover (desktop)
- [ ] Tooltips appear on tap (mobile)
- [ ] All technical terms in "What's Working/Concerning" have tooltips
- [ ] Examples are helpful and accurate

### What's New This Week
- [ ] Shows 3-5 recent items
- [ ] Dates are formatted correctly
- [ ] Impact icons match sentiment (green/red/gray)
- [ ] Sources are displayed when available

### What to Watch Calendar
- [ ] Only shows events in next 30 days
- [ ] Dates are sorted chronologically
- [ ] Importance badges are accurate
- [ ] "What to watch" guidance is clear

### Quick Actions
- [ ] All 3 tabs work (Buying/Holding/Trading)
- [ ] Position sizing calculations are correct
- [ ] Checkboxes are interactive
- [ ] Price levels make sense

### Professional Analysis Section
- [ ] Comparison clearly differentiates versions
- [ ] Download PDF works
- [ ] View modal opens (if implemented)
- [ ] Messaging is clear

---

## Next Steps (Optional Enhancements)

### 1. Professional Analysis Content Components

Create formal, institutional-quality analysis components:

```tsx
// components/results/professional/
├── ProfessionalExecutiveSummary.tsx
├── ProfessionalValuation.tsx
├── ProfessionalPeerComparison.tsx
├── ProfessionalRiskFactors.tsx
└── ProfessionalTradeSetup.tsx
```

These would use:
- ❌ No conversational tone
- ✓ Formal language ("maintains competitive positioning")
- ✓ Data tables instead of visual bars
- ✓ Comprehensive methodology sections

### 2. Tooltip Analytics

Track which tooltips users interact with most:

```tsx
<EducationalTooltip
  {...tooltip}
  onOpen={() => analytics.track('tooltip_viewed', { term: 'rsi' })}
>
```

### 3. Customizable Tooltips

Allow users to toggle tooltips on/off in settings:

```tsx
const { showTooltips } = useSettings()

{showTooltips && <EducationalTooltip {...props}>{children}</EducationalTooltip>}
{!showTooltips && children}
```

---

## Support

For issues or questions:
1. Check the component source code in `frontend/components/results/`
2. Review data extraction logic in `frontend/lib/analysis/`
3. Test with different API responses to ensure robustness

All components gracefully handle missing data and return null when appropriate.
