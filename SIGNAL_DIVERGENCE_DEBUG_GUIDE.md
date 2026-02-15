# Signal Divergence Fix - Complete Debugging Guide

## Current Status

✅ **Backend Code is Correct** - The signal divergence calculator exists and is being called
✅ **Frontend Component Works** - The UI renders correctly
✅ **Data Flow is Wired** - Manager → News Hound → Signal Calculator → API → Frontend
❌ **Problem**: All signals show 5.0 (neutral) instead of real scores

---

## Root Cause Analysis

The signal_divergence calculator defaults to **5.0** when data is missing:

```python
# research_swarm/agents/manager/signal_divergence.py
def _extract_news_score(news_hound_output: Dict[str, Any]) -> float:
    return float(news_hound_output.get("sentiment_score", 5.0))  # ← defaults to 5.0

def _extract_earnings_score(news_hound_output: Dict[str, Any]) -> float:
    earnings_data = news_hound_output.get("earnings_estimates")
    if not earnings_data or not isinstance(earnings_data, dict):
        return 5.0  # ← defaults to 5.0
    # ... rest of logic

# Same pattern for:
# - _extract_analyst_score()
# - _extract_institutional_score()
# - _extract_insider_score()
```

**All signals returning 5.0 means the news_hound_output is missing these fields:**
- ❌ `sentiment_score`
- ❌ `earnings_estimates`
- ❌ `analyst_consensus`
- ❌ `institutional_activity`
- ❌ `insider_activity`

---

## Why Are These Fields Missing?

The News Hound agent has nodes that fetch this data, but they're **failing silently**:

```python
# research_swarm/agents/news_hound/graph.py (line 320-323)
try:
    result, tokens = analyzer.analyze_earnings_estimates(...)
    state["earnings_estimates"] = result
except Exception as e:
    logger.error(f"Error in earnings estimates node: {e}")
    state["earnings_estimates"] = None  # ← Sets to None on error
```

**Common failure reasons:**
1. **API Key Missing/Invalid** - Market data client needs valid API keys
2. **Rate Limiting** - Too many requests to data provider
3. **Network Errors** - Timeout or connection issues
4. **Data Not Available** - Some tickers don't have analyst coverage
5. **LLM Analysis Failure** - Error in the analyzer.analyze_* methods

---

## Step 1: Check Your Frontend Data

I've added a debug component to your results page. Run your next analysis and look for the yellow debug box:

```typescript
// Added to: frontend/app/results/[run_id]/page.tsx
<DataDebugger data={full_output} label="Signal Data Debug" />
```

### What to Look For:

**✅ Good State:**
```
🐛 DEBUG: Signal Data Debug
Signal Breakdown: ✓ EXISTS
  News Score: 8.8
  Earnings Score: 7.5
  Analyst Score: 6.2
  Institutional Score: 7.5
  Insider Score: 2.5
  Has Divergence: YES
  Status: Smart Money Caution

News Hound Output: ✓ EXISTS
  sentiment_score: 8.8
  earnings_estimates: ✓ present
  analyst_consensus: ✓ present
  institutional_activity: ✓ present
  insider_activity: ✓ present
```

**❌ Bad State (Current):**
```
🐛 DEBUG: Signal Data Debug
Signal Breakdown: ✓ EXISTS
  News Score: 5.0
  Earnings Score: 5.0
  Analyst Score: 5.0
  Institutional Score: 5.0
  Insider Score: 5.0
  Has Divergence: NO
  Status: All Signals Aligned

News Hound Output: ✓ EXISTS
  sentiment_score: 5.0
  earnings_estimates: ✗ missing
  analyst_consensus: ✗ missing
  institutional_activity: ✗ missing
  insider_activity: ✗ missing
```

---

## Step 2: Check Backend Logs

Run a fresh analysis and watch the logs for these lines:

### Expected Success Flow:

```bash
[Node 5] Analyzing earnings estimates for NVDA
✓ Earnings estimates analyzed

[Node 6] Analyzing analyst consensus for NVDA
✓ Analyst consensus analyzed

[Node 7] Analyzing institutional activity for NVDA
✓ Institutional activity analyzed

[Node 8] Analyzing insider activity for NVDA
✓ Insider activity analyzed

✓ Signal divergence: Smart Money Caution (σ=2.45)
```

### Error Indicators:

```bash
Error in earnings estimates node: KeyError: 'recommendations'
Error in analyst consensus node: HTTPError: 429 Too Many Requests
Error in institutional activity node: TimeoutError
Error in insider activity node: AttributeError: 'NoneType' object has no attribute 'get'
```

---

## Step 3: Verify API Keys & Configuration

The News Hound nodes depend on `market_data_client` which needs API keys:

```python
# research_swarm/data/market_data_client.py
# Check if these are configured:
- FINNHUB_API_KEY
- FINANCIAL_MODELING_PREP_API_KEY (or similar)
```

### Quick Test:

```python
# Run this in a Python shell
from research_swarm.data.market_data_client import market_data_client

# Test each endpoint
earnings = market_data_client.get_earnings_estimates("NVDA")
print(f"Earnings data: {earnings is not None}")

recommendations = market_data_client.get_analyst_recommendations("NVDA")
print(f"Analyst data: {recommendations is not None}")

institutional = market_data_client.get_institutional_holders("NVDA")
print(f"Institutional data: {institutional is not None}")

insider = market_data_client.get_insider_transactions("NVDA")
print(f"Insider data: {insider is not None}")
```

**Expected output:**
```
Earnings data: True
Analyst data: True
Institutional data: True
Insider data: True
```

---

## Step 4: Check Analyzer Methods

The LLM-based analyzers might be failing:

```python
# research_swarm/agents/news_hound/analyzer.py
# These methods must return (Dict, int) - (result, tokens_used)

analyzer.analyze_earnings_estimates(...)  # → (Dict, int)
analyzer.analyze_analyst_consensus(...)   # → (Dict, int)
analyzer.analyze_institutional_activity(...)  # → (Dict, int)
analyzer.analyze_insider_activity(...)    # → (Dict, int)
```

Add debug logging to see what they're returning:

```python
# In analyze_earnings_estimates_node()
result, tokens = analyzer.analyze_earnings_estimates(...)
print(f"DEBUG: earnings result = {result}")  # Should be a dict, not None
```

---

## Step 5: Temporary Workaround (Mock Data)

If you need to test the frontend UI while fixing the backend, you can inject mock data:

```python
# research_swarm/agents/manager/signal_divergence.py
# At the top of calculate_signal_divergence()

def calculate_signal_divergence(...) -> Optional[Dict[str, Any]]:
    # TEMPORARY: Force mock data for testing
    return {
        "overall_score": 6.5,
        "news_score": 8.8,
        "earnings_score": 7.5,
        "analyst_score": 7.5,
        "institutional_score": 7.5,
        "insider_score": 2.5,
        "news_interpretation": "🟢 Bullish News Sentiment",
        "earnings_interpretation": "🟢 Bullish Earnings Revisions",
        "analyst_interpretation": "🟢 Bullish Analyst Ratings",
        "institutional_interpretation": "🟢 Bullish Institutional",
        "insider_interpretation": "🔴 Bearish Insider",
        "alignment_status": "Smart Money Caution",
        "has_divergence": True,
        "divergence_explanation": "Headlines bullish but insiders selling",
        "divergence_recommendation": "Exercise caution - wait for insider buying",
        "direction_consensus": "Mixed",
    }
```

---

## Step 6: Expected Data Structures

For reference, here's what each field should contain:

### earnings_estimates (EarningsEstimateRevision model)
```python
{
    "net_revision_direction": "positive",  # or "neutral", "negative", "strongly positive", "strongly negative"
    "magnitude": 0.15,  # Percentage change in estimates
    "recent_changes": ["Upgraded by JP Morgan", "Raised estimates by 5%"],
    "interpretation": "Earnings estimates trending higher"
}
```

### analyst_consensus (AnalystConsensus model)
```python
{
    "consensus_rating": "buy",  # or "strong buy", "hold", "sell", "strong sell"
    "rating_momentum": "improving",  # or "stable", "deteriorating"
    "buy_count": 15,
    "hold_count": 3,
    "sell_count": 1,
    "average_price_target": 150.00,
    "interpretation": "Strong analyst support with rising targets"
}
```

### institutional_activity (InstitutionalActivity model)
```python
{
    "trend": "accumulation",  # or "stable", "distribution"
    "institutional_sentiment": "bullish",  # or "neutral", "bearish", "strongly bullish"
    "net_flow_usd": 50_000_000,  # Net buying/selling in USD
    "top_holders": ["Vanguard", "BlackRock", "State Street"],
    "interpretation": "Institutions are increasing positions"
}
```

### insider_activity (InsiderActivity model)
```python
{
    "insider_sentiment": "bearish",  # or "neutral", "bullish"
    "net_value_usd": -2_500_000,  # Negative = net selling
    "recent_transactions": ["CEO sold $1M", "CFO sold $1.5M"],
    "interpretation": "Insiders selling shares"
}
```

---

## Quick Fix Checklist

- [ ] Run a new analysis and check the DataDebugger output
- [ ] Check backend logs for "Error in ... node" messages
- [ ] Verify API keys are configured for market_data_client
- [ ] Test market_data_client methods independently
- [ ] Add debug logging to analyzer methods
- [ ] Check if the ticker has analyst coverage (some small caps don't)
- [ ] Verify LLM API key (Claude) is valid and has quota

---

## Success Criteria

You'll know it's fixed when:

1. ✅ DataDebugger shows all 5 signals with **different scores** (not all 5.0)
2. ✅ DataDebugger shows **"earnings_estimates: ✓ present"** for all 4 fields
3. ✅ Signal bars display in **different colors** (green/red/gray mix)
4. ✅ Divergence status is **NOT "All Signals Aligned"** (unless truly aligned)
5. ✅ Backend logs show **"✓ Signal divergence: [Status]"** with a meaningful status

---

## Need More Help?

If the issue persists:

1. **Share the DataDebugger output** - Screenshot or copy the debug box
2. **Share backend logs** - The "Error in ... node" messages
3. **Share ticker tested** - Some tickers have more data than others
4. **Test with NVDA first** - Large cap with guaranteed analyst coverage

The debug component will tell us exactly where the data is breaking down.
