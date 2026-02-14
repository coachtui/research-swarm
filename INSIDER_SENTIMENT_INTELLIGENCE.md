# Intelligent Insider Sentiment Analysis

## Problem: Naive Dollar-Amount Thresholds

The original logic used fixed USD thresholds:
```python
if net_value_usd < -1_000_000:  # $1M+ selling
    return "Bearish"
```

This treated all companies the same:
- ❌ $25M selling at **$100M company** = 25% of market cap → VERY BEARISH
- ❌ $25M selling at **$3.7T company** = 0.0007% of market cap → **IRRELEVANT**

But both got the same "Bearish" rating!

---

## Solution: Market Cap-Aware Sentiment

### 1. Scale Thresholds by Company Size

```python
# Mega-caps ($100B+): Insider trading is less significant
if market_cap >= 100_000_000_000:
    if net_value_pct < -0.05%:  # $50M+ for $100B company
        return "Bearish"

# Large-caps ($10B-100B): Moderate significance
elif market_cap >= 10_000_000_000:
    if net_value_pct < -0.1%:  # $10M+ for $10B company
        return "Bearish"

# Small/mid-caps (<$10B): Very significant
else:
    if net_value_pct < -0.5%:  # $5M+ for $1B company
        return "Bearish"
```

### 2. Add Contextual Interpretation

Beyond just the sentiment label, we provide context notes:

```python
context_notes = [
    "0.0007% of market cap ($3698.3B)",
    "Multiple executives selling with no buying activity",
    "2 scheduled 10b5-1 plan transactions (routine selling)",
    "C-level activity: 1 CEO, 2 CFO transactions"
]
```

---

## GOOGL Example: Before vs After

### Before (Naive Logic)
```
Sell Value: $24,990,801
Market Cap: Not considered
Sentiment: Bearish ❌ (> $1M threshold)
Score: 2.5/10
Interpretation: "Bearish insider activity"
```

### After (Intelligent Logic)
```
Sell Value: $24,990,801
Market Cap: $3.7T
As % of Market Cap: 0.0007%
Sentiment: Neutral ✅ (< 0.05% threshold for mega-caps)
Score: 5.0/10
Context: "0.0007% of market cap; Multiple executives selling with no buying"
Interpretation: "Routine director sales, immaterial to $3.7T company"
```

---

## Key Improvements

### 1. Market Cap Scaling
- **Mega-caps** ($100B+): Need 0.05% for bearish signal
- **Large-caps** ($10B-100B): Need 0.1% for bearish signal
- **Small/mid-caps** (<$10B): Need 0.5% for bearish signal

### 2. Context Flags
- ✅ **10b5-1 Plans**: Scheduled selling (not concerning)
- ✅ **C-Level Activity**: CEO/CFO trades more significant than directors
- ✅ **Clustered Selling**: Multiple execs selling at once (potential concern)
- ✅ **Market Cap %**: Shows actual materiality

### 3. Interpretation Notes
The `context_notes` array provides narrative context:
- "X% of market cap" - shows scale
- "Scheduled 10b5-1 transactions" - routine selling
- "C-level activity" - role weighting
- "Multiple executives selling" - pattern warning

---

## Scenarios & Interpretation

### Scenario 1: Small-Cap Founder Selling
```
Company: $500M market cap
Activity: CEO sold $5M (1% of market cap)
Sentiment: Bearish
Reasoning: 1% > 0.5% threshold for small-cap, C-level selling
```

### Scenario 2: Mega-Cap Director Routine Sales
```
Company: $3.7T market cap
Activity: Director sold $25M (0.0007% of market cap)
Sentiment: Neutral ✅
Reasoning: 0.0007% << 0.05% threshold, routine liquidity
```

### Scenario 3: Large-Cap 10b5-1 Plan
```
Company: $50B market cap
Activity: CFO sold $30M (0.06% of market cap) via 10b5-1 plan
Sentiment: Slightly Bearish (but context notes explain it's planned)
Context: "Scheduled 10b5-1 plan transactions (routine selling)"
```

### Scenario 4: Clustered C-Level Selling
```
Company: $20B market cap
Activity: CEO, CFO, COO all sold totaling $50M (0.25% of market cap)
Sentiment: Bearish
Context: "C-level activity: 1 CEO, 1 CFO; Multiple executives selling"
Reasoning: Unusual pattern, crosses 0.1% threshold, C-level involvement
```

---

## Implementation Details

### Data Captured
```python
{
    "net_value_usd": -24990801.00,
    "insider_sentiment": "Neutral",
    "market_cap_pct": -0.0007,
    "ceo_transactions": 0,
    "cfo_transactions": 0,
    "planned_10b51_transactions": 0,
    "context_notes": [
        "0.0007% of market cap ($3698.3B)",
        "Multiple executives selling with no buying activity"
    ]
}
```

### Sentiment Mapping
```python
# In signal_divergence.py
insider_data.get("insider_sentiment", "neutral").lower()

if "bullish" in sentiment or net_value > 1_000_000:
    return 7.5
elif "bearish" in sentiment or net_value < -1_000_000:
    return 2.5  # Only if truly bearish (market cap aware)
else:
    return 5.0  # Neutral for routine activity
```

---

## Future Enhancements

### 1. Historical Context
Track typical insider activity for this company:
- Is $25M/year normal for GOOGL?
- Sudden spike in selling = concern
- Consistent pattern = routine

### 2. Timing Analysis
- Selling before earnings = suspicious
- Selling after lockup expiration = normal
- Selling after major news = interpret in context

### 3. Ownership % Change
- Track total insider ownership % over time
- 10% → 9% ownership = concerning
- 5% → 5% ownership (but some selling) = neutral

### 4. Peer Comparison
- How does this compare to peer companies?
- Is Google's insider selling higher/lower than Meta, Apple, Microsoft?

---

## Testing

```bash
# Test with different market caps
python3 << 'EOF'
from research_swarm.data.insider_activity_calculator import calculate_insider_metrics
import pandas as pd

# Mock $25M selling for different market caps
transactions = pd.DataFrame([{
    'Shares': 100000,
    'Value': 25000000,
    'Text': 'Sale',
    'Position': 'Director',
    'Start Date': '2026-01-01'
}])

# Small-cap ($500M)
result = calculate_insider_metrics(transactions, market_cap=500_000_000)
print(f"$500M cap: {result['insider_sentiment']}")  # Bearish

# Mid-cap ($10B)
result = calculate_insider_metrics(transactions, market_cap=10_000_000_000)
print(f"$10B cap: {result['insider_sentiment']}")  # Neutral

# Mega-cap ($3.7T)
result = calculate_insider_metrics(transactions, market_cap=3_700_000_000_000)
print(f"$3.7T cap: {result['insider_sentiment']}")  # Neutral
EOF
```

---

## Key Takeaways

1. ✅ **Market cap context** is critical for accurate interpretation
2. ✅ **Fixed dollar thresholds** don't work across different company sizes
3. ✅ **Context matters**: 10b5-1 plans, role, timing, clustering
4. ✅ **Transparency**: Provide context_notes for user understanding

**Bottom line:** $25M of insider selling is:
- **Material** for a $100M company (25% of market cap)
- **Concerning** for a $1B company (2.5% of market cap)
- **Noteworthy** for a $10B company (0.25% of market cap)
- **Irrelevant** for a $3.7T company (0.0007% of market cap)

The intelligent algorithm now understands this distinction!
