# Signal Accuracy Fixes - Complete Summary

## Overview

Fixed critical data accuracy issues in the signal breakdown system that were causing default/incorrect scores.

---

## 🔴 Problem: Signals Defaulting to 5.0 (Neutral)

Several signals were showing **5.0/10 (neutral)** even when there was clear bullish/bearish activity:

1. **Earnings Revisions** - Showed 5.0 even after great earnings
2. **Insider Activity** - Had $0 net_value_usd even with $25M of sales

---

## ✅ Fix #1: Earnings Revisions Detection

### Issue
- Used `yfinance`'s `stock.earnings_estimate` (current estimates only)
- Couldn't detect if estimates were being raised or lowered
- Always returned `upward_revisions: 0`, `downward_revisions: 0`

### Solution
Added **analyst upgrades/downgrades tracking**:

**Files Created:**
1. `research_swarm/data/analyst_revision_calculator.py` - Calculates revision metrics from upgrades/downgrades
2. `market_data_client.get_upgrades_downgrades()` - Fetches yfinance upgrades/downgrades data

**Files Modified:**
- `research_swarm/agents/news_hound/graph.py` - Updated `analyze_earnings_estimates_node` to:
  - Fetch upgrades/downgrades data
  - Calculate revision metrics
  - Override LLM-generated values with calculated data

### Results (GOOGL Example)

| Metric | Before | After |
|--------|--------|-------|
| Upward Revisions | 0 | 2 |
| Downward Revisions | 0 | 0 |
| Price Target Increases | 0 | 39 |
| Avg PT Change | 0% | +9.97% |
| Net Direction | Neutral | **Strongly Positive** |
| **Earnings Score** | **5.0** | **9.0** ✅ |

---

## ✅ Fix #2: Insider Activity USD Values

### Issue
- LLM was calculating `net_value_usd` from formatted text
- Returned $0.00 even when clear sales existed
- Couldn't accurately detect buy/sell dollar amounts

### Solution
Added **direct USD value calculation** from yfinance data:

**Files Created:**
1. `research_swarm/data/insider_activity_calculator.py` - Calculates insider metrics from transaction data

**Files Modified:**
- `research_swarm/agents/news_hound/graph.py` - Updated `analyze_insider_activity_node` to:
  - Calculate insider metrics directly from transactions
  - Override LLM-generated USD values with calculated data
  - Use 365-day window (instead of LLM's variable window)

### Results (GOOGL Example)

| Metric | Before (LLM) | After (Calculator) |
|--------|--------------|-------------------|
| Sell Transactions | 16 | 5 (last year) |
| Sell Value USD | **$0.00** ❌ | **$24,990,801** ✅ |
| Net Value USD | **$0.00** ❌ | **-$24,990,801** ✅ |
| Sentiment | Bearish | Bearish |
| **Insider Score** | 2.5 | **2.5** ✅ |

**Note:** Sentiment was already correct, but now USD values are accurate for better transparency.

---

## 📊 Impact on Overall Signal Breakdown

### Before (GOOGL)
```
News Score: 8.8
Earnings Score: 5.0  ← BROKEN (should be 9.0)
Analyst Score: 7.5
Institutional Score: 7.5
Insider Score: 2.5  ← USD values wrong ($0 vs $25M)
────────────────
Overall: 6.26
```

### After (GOOGL)
```
News Score: 8.8
Earnings Score: 9.0  ← FIXED
Analyst Score: 7.5
Institutional Score: 7.5
Insider Score: 2.5  ← USD values accurate
────────────────
Overall: 7.0
```

**Impact:** Overall score went from 6.26 → 7.0 (more bullish, more accurate)

---

## 🧪 Testing

### Test Scripts Created

1. **`test_revision_detection.py`** - Tests earnings revision detection
   ```bash
   python test_revision_detection.py
   # Expected: Earnings Score: 9.0/10 for GOOGL
   ```

2. **`test_insider_detection.py`** - Tests insider activity calculation
   ```bash
   python test_insider_detection.py
   # Expected: Net Value: -$24,990,801 for GOOGL
   ```

---

## 📁 Files Summary

### Created (3 files)
1. `research_swarm/data/analyst_revision_calculator.py`
2. `research_swarm/data/insider_activity_calculator.py`
3. `research_swarm/data/market_data_client.py::get_upgrades_downgrades()`

### Modified (1 file)
1. `research_swarm/agents/news_hound/graph.py`
   - `analyze_earnings_estimates_node` (lines 290-323)
   - `analyze_insider_activity_node` (lines 455-493)

### Test Files (2 files)
1. `test_revision_detection.py`
2. `test_insider_detection.py`

---

## ✅ What Was Already Working

### Institutional Activity
- ✅ Sentiment detection working correctly
- ✅ Score calculation accurate (7.5 for "Bullish")
- ✅ Data from news_hound properly structured

### Analyst Ratings
- ✅ Consensus rating detection working
- ✅ Score calculation accurate
- ✅ No fix needed

### News Sentiment
- ✅ Sentiment scoring working correctly
- ✅ No fix needed

---

## 🎯 Key Improvements

1. **Accuracy**: Signals now reflect actual market data, not LLM estimation errors
2. **Transparency**: USD values are now accurate for insider activity
3. **Reliability**: Calculated metrics are deterministic (not subject to LLM variability)
4. **Performance**: Direct calculations are faster than LLM analysis

---

## 🚀 Next Steps

### Recommended
1. Run a fresh analysis on a known stock (e.g., GOOGL) to verify all signals
2. Check signal breakdown in frontend to confirm earnings score shows correctly
3. Monitor for any other signals that might need similar fixes

### Optional Enhancements
1. Add historical tracking of estimate revisions (trend over time)
2. Add insider role weighting (CEO sells > analyst sells)
3. Add institutional ownership change alerts (>5% swing)

---

## 📝 Migration Notes

**No breaking changes** - all fixes are backward compatible:
- Old data structures still work
- New fields are additions, not replacements
- LLM analysis still runs (provides context), but critical metrics are overridden

**Testing recommended:**
```bash
# Run a fresh analysis
python -m research_swarm.cli analyze GOOGL

# Check signal breakdown in results
# Earnings Score should now be 9.0 (not 5.0)
# Insider net_value_usd should be accurate (not $0)
```

---

## 🐛 Debugging Tips

If signals still show 5.0:

1. **Check data fetch**
   ```python
   from research_swarm.data.market_data_client import market_data_client

   # Test earnings
   upgrades = market_data_client.get_upgrades_downgrades("GOOGL")
   print(len(upgrades))  # Should be > 0

   # Test insider
   insider = market_data_client.get_insider_transactions("GOOGL")
   print(len(insider))  # Should be > 0
   ```

2. **Check calculators**
   ```python
   from research_swarm.data.analyst_revision_calculator import calculate_revision_metrics
   from research_swarm.data.insider_activity_calculator import calculate_insider_metrics

   # Should return non-zero values for active stocks
   ```

3. **Check news_hound output**
   ```python
   # In database, check:
   news_hound_output.earnings_estimates.upward_revisions  # Should be > 0 if there were upgrades
   news_hound_output.insider_activity.net_value_usd  # Should match calculated value
   ```
