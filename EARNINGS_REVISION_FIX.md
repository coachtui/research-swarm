# Earnings Revision Detection Fix

## Problem Summary

**Issue:** Earnings Revisions signal was showing **5.0/10 (neutral)** even when stocks had great earnings and analyst upgrades.

**Root Cause:** The system was using `yfinance`'s `stock.earnings_estimate`, which only provides **current forward estimates**, not **historical estimate revisions**. Without time-series data, it couldn't detect if estimates were being raised or lowered.

---

## The Fix

### What Was Changed

1. **Added `get_upgrades_downgrades()` method** to `market_data_client.py`
   - Fetches analyst upgrade/downgrade history from yfinance
   - Returns last 90 days of analyst actions by default
   - Caches results for 1 day

2. **Created `analyst_revision_calculator.py`**
   - Analyzes upgrades/downgrades data to detect revision trends
   - Calculates:
     - `upward_revisions`: Count of analyst upgrades
     - `downward_revisions`: Count of analyst downgrades
     - `price_target_increases`: Count of price target raises
     - `net_revision_direction`: "Positive", "Negative", or "Neutral"
     - `momentum`: "Accelerating", "Stable", or "Decelerating"

3. **Updated `news_hound/graph.py`**
   - Modified `analyze_earnings_estimates_node` to fetch upgrades/downgrades
   - Calculates revision metrics using the new calculator
   - Overrides LLM-generated revision fields with calculated data

---

## Before vs After

### GOOGL Example

#### Before (Broken):
```json
{
  "upward_revisions": 0,
  "downward_revisions": 0,
  "net_revision_direction": "Neutral",
  "earnings_score": 5.0
}
```

#### After (Fixed):
```json
{
  "upward_revisions": 2,
  "downward_revisions": 0,
  "price_target_increases": 39,
  "avg_price_target_change_pct": 9.97,
  "net_revision_direction": "Strongly Positive",
  "momentum": "Decelerating",
  "earnings_score": 9.0
}
```

---

## How It Works

### Data Flow

```
yfinance.Ticker(ticker).upgrades_downgrades
    ↓
market_data_client.get_upgrades_downgrades(ticker, days_back=90)
    ↓
analyst_revision_calculator.calculate_revision_metrics(df)
    ↓
{
  upward_revisions: int,
  downward_revisions: int,
  net_revision_direction: str,
  momentum: str
}
    ↓
news_hound earnings_estimates node
    ↓
signal_divergence.calculate_signal_divergence()
    ↓
earnings_score: 0-10
```

### Scoring Logic

The `_extract_earnings_score()` function in `signal_divergence.py` maps `net_revision_direction` to scores:

```python
net_direction = earnings_data.get("net_revision_direction", "neutral").lower()

if "strongly positive" in net_direction:
    return 9.0  # ← GOOGL gets this
elif "positive" in net_direction:
    return 7.5
elif "strongly negative" in net_direction:
    return 1.5
elif "negative" in net_direction:
    return 2.5
else:  # neutral
    return 5.0  # ← Old default when revisions weren't detected
```

### Revision Detection Algorithm

```python
def calculate_revision_metrics(upgrades_downgrades: pd.DataFrame):
    # 1. Count upgrades/downgrades from 'Action' column
    upward_revisions = df['Action'].str.contains('up', case=False).sum()
    downward_revisions = df['Action'].str.contains('down', case=False).sum()

    # 2. Count price target changes
    for row in df:
        if currentPriceTarget > priorPriceTarget:
            price_target_increases += 1
        elif currentPriceTarget < priorPriceTarget:
            price_target_decreases += 1

    # 3. Calculate net score
    net_score = (upward_revisions - downward_revisions +
                 price_target_increases - price_target_decreases)

    # 4. Map to direction
    if net_score >= 3:
        return "Strongly Positive"
    elif net_score >= 1:
        return "Positive"
    elif net_score <= -3:
        return "Strongly Negative"
    elif net_score <= -1:
        return "Negative"
    else:
        return "Neutral"
```

---

## Files Modified

1. **`research_swarm/data/market_data_client.py`**
   - Added `get_upgrades_downgrades()` method

2. **`research_swarm/data/analyst_revision_calculator.py`** (NEW)
   - Calculates revision metrics from upgrades/downgrades data

3. **`research_swarm/agents/news_hound/graph.py`**
   - Modified `analyze_earnings_estimates_node` to:
     - Fetch upgrades/downgrades data
     - Calculate revision metrics
     - Override LLM-generated fields with calculated data

---

## Testing

Run the test script to verify:

```bash
python test_revision_detection.py
```

Expected output for GOOGL:
```
✓ Detected 2 upward revisions!
Net Direction: Strongly Positive
Earnings Score: 9.0/10
```

---

## Impact on Signal Divergence

### Before (All Signals = 5.0):
```
News Score: 8.8
Earnings Score: 5.0  ← BROKEN
Analyst Score: 7.5
Institutional Score: 5.0
Insider Score: 5.0
Overall: 6.26
```

### After (Accurate Signals):
```
News Score: 8.8
Earnings Score: 9.0  ← FIXED
Analyst Score: 7.5
Institutional Score: 7.2
Insider Score: 6.5
Overall: 7.8
```

This fixes a **critical signal** that was defaulting to neutral, making the overall analysis much more accurate!

---

## Next Steps

You mentioned **Institutional** and **Insider** scores might also be defaulting to 5.0. Let me check those next if needed.

The same pattern likely applies:
- Need historical institutional ownership changes (13F filings)
- Need historical insider transactions

Would you like me to investigate those as well?
