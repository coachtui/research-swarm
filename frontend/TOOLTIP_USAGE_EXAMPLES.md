# Educational Tooltip Usage Examples

This file shows practical examples of integrating tooltips into existing components.

## Example 1: Adding Tooltips to KeyTakeaways

**File:** `components/results/KeyTakeaways.tsx`

### Before (Plain Text):
```tsx
<p className="text-xs text-muted-foreground leading-relaxed">
  Strong institutional buying with positive insider sentiment
</p>
```

### After (With Tooltips):
```tsx
import { EducationalTooltip } from '@/components/ui/educational-tooltip'
import { getTooltip } from '@/lib/tooltips/definitions'

<p className="text-xs text-muted-foreground leading-relaxed">
  Strong{' '}
  <EducationalTooltip {...getTooltip('institutional_activity')}>
    institutional buying
  </EducationalTooltip>
  {' '}with positive{' '}
  <EducationalTooltip {...getTooltip('insider_activity')}>
    insider sentiment
  </EducationalTooltip>
</p>
```

---

## Example 2: TradeSetup Component

**File:** `components/results/TradeSetup.tsx`

### Adding Tooltips to Price Levels:

```tsx
<div className="space-y-2">
  <div className="flex justify-between items-center">
    <span className="text-sm text-muted-foreground">
      <EducationalTooltip {...getTooltip('support_level')}>
        Support
      </EducationalTooltip>
    </span>
    <span className="font-mono font-semibold">${support}</span>
  </div>

  <div className="flex justify-between items-center">
    <span className="text-sm text-muted-foreground">
      <EducationalTooltip {...getTooltip('resistance_level')}>
        Resistance
      </EducationalTooltip>
    </span>
    <span className="font-mono font-semibold">${resistance}</span>
  </div>

  <div className="flex justify-between items-center">
    <span className="text-sm text-muted-foreground">
      <EducationalTooltip {...getTooltip('stop_loss')}>
        Stop Loss
      </EducationalTooltip>
    </span>
    <span className="font-mono font-semibold">${stopLoss}</span>
  </div>
</div>
```

---

## Example 3: Signal Divergence Section

**File:** `components/results/SignalDivergenceSection.tsx`

### Adding Context to Technical Metrics:

```tsx
<div className="metric-card">
  <h4 className="text-sm font-semibold mb-2">
    <EducationalTooltip {...getTooltip('divergence')}>
      Signal Divergence
    </EducationalTooltip>
  </h4>
  <p className="text-xs">
    Analysts are bullish (upgrading to BUY) while{' '}
    <EducationalTooltip {...getTooltip('insider_activity')}>
      insiders are selling
    </EducationalTooltip>
    . This gap suggests potential hidden risks.
  </p>
</div>
```

---

## Example 4: Custom Tooltip for Stock-Specific Terms

Sometimes you need a custom tooltip that isn't in the definitions:

```tsx
<EducationalTooltip
  term="Regulation XYZ Impact"
  definition="This regulation affects how the company can operate in certain markets, potentially reducing revenue by 10-15%."
  example="Similar regulations in Europe reduced Meta's ad revenue by 12% in 2023."
>
  regulatory headwinds
</EducationalTooltip>
```

---

## Example 5: Multiple Tooltips in One Sentence

```tsx
<p className="text-sm">
  The stock is oversold on{' '}
  <EducationalTooltip {...getTooltip('rsi')}>
    RSI (23.4)
  </EducationalTooltip>
  {' '}and{' '}
  <EducationalTooltip {...getTooltip('stochastic')}>
    Stochastic (4.4)
  </EducationalTooltip>
  , suggesting a near-term bounce is likely.
</p>
```

---

## Example 6: Valuation Metrics

**File:** `components/results/ScoreBreakdownBars.tsx`

```tsx
<div className="valuation-metrics">
  <MetricRow
    label={
      <EducationalTooltip {...getTooltip('pe_ratio')}>
        P/E Ratio
      </EducationalTooltip>
    }
    value="24.5"
    comparison="vs sector avg 18.2"
  />

  <MetricRow
    label={
      <EducationalTooltip {...getTooltip('ev_ebitda')}>
        EV/EBITDA
      </EducationalTooltip>
    }
    value="12.3"
    comparison="vs sector avg 15.1"
  />

  <MetricRow
    label={
      <EducationalTooltip {...getTooltip('fair_value')}>
        Fair Value
      </EducationalTooltip>
    }
    value="$142"
    comparison="20% upside from current"
  />
</div>
```

---

## Example 7: Conditional Tooltips

Only show tooltips for new users:

```tsx
function TermWithOptionalTooltip({
  term,
  children,
  showTooltip = true
}: {
  term: keyof typeof TOOLTIP_DEFINITIONS
  children: React.ReactNode
  showTooltip?: boolean
}) {
  const tooltip = getTooltip(term)

  if (!showTooltip || !tooltip) {
    return <>{children}</>
  }

  return (
    <EducationalTooltip {...tooltip}>
      {children}
    </EducationalTooltip>
  )
}

// Usage
<TermWithOptionalTooltip term="rsi" showTooltip={user.isNewInvestor}>
  RSI 23.4
</TermWithOptionalTooltip>
```

---

## Example 8: Tooltips with Dynamic Content

```tsx
function DynamicTooltip({
  term,
  currentValue,
  context
}: {
  term: string
  currentValue: number
  context: string
}) {
  const baseTooltip = getTooltip(term)

  return (
    <EducationalTooltip
      term={baseTooltip.term}
      definition={baseTooltip.definition}
      example={`Current value: ${currentValue}. ${context}`}
    >
      {term} {currentValue}
    </EducationalTooltip>
  )
}

// Usage
<DynamicTooltip
  term="rsi"
  currentValue={23.4}
  context="Historically, stocks at this level bounce 5-10% within 2 weeks."
/>
```

---

## Best Practices

### DO:
✅ Use tooltips for technical jargon new investors won't know
✅ Keep definitions to 1-2 sentences
✅ Include concrete examples when possible
✅ Use consistent terminology (match the tooltip term to the text)
✅ Test on mobile (tooltips should work on tap)

### DON'T:
❌ Tooltip every word (only jargon, not basic terms like "price")
❌ Write long essays in tooltips (keep it concise)
❌ Nest tooltips inside other tooltips
❌ Use tooltips for critical information (they should enhance, not replace)
❌ Forget to test keyboard navigation (tooltips should be accessible)

---

## Accessibility

All tooltips are built with Radix UI and support:
- ✅ Keyboard navigation (focus + Enter)
- ✅ Screen readers (aria-describedby)
- ✅ Touch devices (tap to show/hide)
- ✅ Escape key to close

---

## Performance Notes

- Tooltips use `delayDuration={200}` to prevent accidental triggers
- TooltipProvider is scoped to each tooltip for better tree-shaking
- Definitions are loaded once from a constant object (no API calls)

---

## Adding to Your Workflow

1. **While writing content**, identify technical terms
2. **Check** if term exists in `TOOLTIP_DEFINITIONS`
3. **If exists**: Use `getTooltip(key)` and wrap term
4. **If new**: Add to definitions file first, then use
5. **Test**: Hover/tap to ensure tooltip appears and makes sense
