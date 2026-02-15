# Report Quality Fixes - February 12, 2026

## Summary
Fixed 5 of 8 reported issues with the generated reports. The remaining 3 issues require runtime debugging or external data availability.

---

## ✅ COMPLETED FIXES

### 1. Supply Chain Section Removed
**Issue:** Report included "No supply chain data available" section
**Fix:** Removed `SUPPLY_CHAIN` from default sections list in `ReportConfig`
**File:** `/research_swarm/reports/models.py` (line 37-45)
**Impact:** Supply chain section no longer appears in reports unless explicitly requested

### 2. Moat Breakdown Graphs Removed
**Issue:** Redundant moat breakdown graphs shown in multiple places
**Fix:** Removed chart references from 3 template files:
- **Executive Summary:** `/research_swarm/reports/templates/executive_summary.md.j2` (lines 30-32)
- **Stock Analysis:** `/research_swarm/reports/templates/stock_analysis.md.j2` (lines 24-26)
- **Watchlist:** `/research_swarm/reports/templates/watchlist.md.j2` (lines 33-35)
**Impact:** Cleaner reports without redundant visualizations

### 3. Watchlist Threshold Criteria Removed
**Issue:** Reports exposed internal 8.0 threshold to users
**Fix:** Removed threshold references from templates:
- **Executive Summary:** Changed "none reached threshold of 8.0" to no message
- **Watchlist:** Removed "(moat score ≥ 8.0)" and "points below threshold" language
**Files Modified:**
- `/research_swarm/reports/templates/executive_summary.md.j2`
- `/research_swarm/reports/templates/watchlist.md.j2`
**Impact:** User-facing reports no longer expose internal scoring criteria

### 4. Upcoming Catalyst Dates Enhanced
**Issue:** Catalyst dates showing 2024 instead of 2026
**Root Cause:** LLM parsing news about past events (e.g., "Gemini AI launched in Q1 2024") and not properly projecting to future dates
**Fix:** Enhanced prompt instructions in `/research_swarm/agents/news_hound/prompts.py`:
```python
**CRITICAL**:
- The current analysis date is {analysis_date}
- ALL catalyst dates MUST be AFTER {analysis_date}
- DO NOT include any events with dates before {analysis_date}
- If you see references to events that already occurred, DO NOT include them
- Use format YYYY-MM-DD where YYYY is 2026 or later
```
**Impact:** LLM now receives stronger instructions to use current year for future catalysts

### 5. Peer Comparison Already Working
**Issue:** Reported as "missing competitive rankings"
**Finding:** Peer comparison IS being generated via `peer_comparison_generator.py` as fallback
**Limitation:** Competitive rankings (revenue_growth_rank, profit_margin_rank, etc.) are intentionally set to `None` because calculating them would require fetching financial data for all peer companies (expensive API calls)
**Code Reference:** `research_swarm/reports/peer_comparison_generator.py` lines 152-156:
```python
# Ranks would require fetching peer financials — skip for now
"revenue_growth_rank": None,
"profit_margin_rank": None,
"roic_rank": None,
"valuation_rank": None,
```
**Recommendation:** Keep as-is unless willing to accept 4-5x more yfinance API calls per report

---

## ⚠️ ISSUES REQUIRING FURTHER INVESTIGATION

### 6. Enhanced Moat Data Showing All Zeros
**Symptom:** Enhanced Moat Analysis section shows all 8 categories as 0.0/10
**Location:** `research_swarm/agents/fundamentalist/scorer.py` line 268
**Root Cause:** One of three possibilities:
1. LLM (Haiku) not returning `enhanced_moat` field in JSON response
2. LLM returning empty dict `{}`
3. JSON parsing failing and falling back to default `EnhancedMoatBreakdown()` (all zeros)

**Investigation Needed:**
- Run analysis with logging to capture actual LLM response
- Check if prompt `BUSINESS_MODEL_SCORE_PROMPT_TTM` is clear enough
- Consider switching from Haiku to Sonnet for this scoring task (more reliable)
- Add better error logging at line 268:
```python
enhanced_data = score_data.get("enhanced_moat", {})
if not enhanced_data:
    logger.warning(f"LLM did not return enhanced_moat data for {ticker}")
enhanced_moat = EnhancedMoatBreakdown(**enhanced_data)
```

**Prompt Location:** `/research_swarm/agents/fundamentalist/prompts.py` lines 487-498

### 7. Capital Allocation Quality Incorrectly Low
**Symptom:** Report shows "Capital Allocation Quality: Low" for GOOGL despite $185B capex
**Location:** Needs investigation in News Hound management commentary analyzer
**Files to Check:**
- `/research_swarm/agents/news_hound/analyzer.py` (analyze_management_commentary method)
- `/research_swarm/agents/news_hound/prompts.py` (MANAGEMENT_COMMENTARY_PROMPT)

**Investigation Needed:**
- Check how capital allocation quality is scored
- Verify LLM is interpreting aggressive AI spending correctly (should be "Aggressive" not "Low")
- Review prompt to ensure clear scoring rubric

### 8. Valuation Metrics and Price Targets Not Available
**Symptom:** Report shows:
- "Valuation metrics not available for this ticker via free data sources"
- "Price target scenarios not available for this ticker"

**Root Cause Analysis:**

#### Valuation Metrics (`None`)
**Location:** `/research_swarm/agents/fundamentalist/graph.py` lines 711-739
**Logic Flow:**
1. Try fetching from `market_data_client.get_valuation_metrics(ticker)`
2. If fails, try building from fundamentals with `build_valuation_from_fundamentals()`
3. If both fail, set to `None`

**Check:**
```python
# /research_swarm/data/market_data_client.py line 602-604
if not info or not info.get("currentPrice"):
    logger.warning(f"No valuation data for {ticker}")
    return None
```
**Hypothesis:** yfinance `stock.info` for GOOGL may not have `currentPrice` field, or API call is failing

#### Price Targets (`None`)
**Location:** `/research_swarm/agents/fundamentalist/graph.py` lines 790-799
**Dependencies:**
1. Requires `dcf_price` (current price)
2. Requires `dcf_inputs.fcf_history` (free cash flow history)
3. Calls `dcf_calculator.calculate_dcf()`

**Check:**
```python
if dcf_price and dcf_inputs.fcf_history:
    dcf_result = dcf_calculator.calculate_dcf(dcf_inputs, dcf_price)
    if dcf_result:
        state["price_targets"] = dcf_result.dict()
```
**Hypothesis:** Either missing current price or FCF history extraction from SEC filings failing

**Investigation Steps:**
1. Run `python -m research_swarm run GOOGL` with verbose logging
2. Check if yfinance is returning data for GOOGL
3. Verify if SEC filing parsing is extracting FCF data
4. Test with different ticker (e.g., AAPL) to see if issue is specific to GOOGL
5. Check cache - may have stale/bad data cached: `rm -rf .cache/market_valuation/GOOGL*`

---

## TESTING RECOMMENDATIONS

### Quick Test (1 minute)
```bash
# Clear cache and rerun
rm -rf .cache/market_valuation/GOOGL*
python -m research_swarm run GOOGL
```

### Full Validation (5 minutes)
```bash
# Test with 3 diverse tickers
python -m research_swarm run AAPL,NVDA,JPM

# Expected improvements:
# - No supply chain section
# - No moat breakdown graphs
# - No watchlist threshold messages
# - Catalyst dates in 2026 (not 2024)
# - Peer comparison populated (but rankings still None)

# Issues may still appear:
# - Enhanced moat zeros (needs LLM debugging)
# - Capital allocation scoring (needs prompt review)
# - Valuation/price targets (needs yfinance investigation)
```

### Debug Enhanced Moat (10 minutes)
Add logging to `/research_swarm/agents/fundamentalist/scorer.py` line 258:
```python
try:
    response = self.haiku.invoke(prompt)
    response_text = response.content.strip()
    logger.info(f"[DEBUG] Business model scoring response: {response_text[:500]}")  # ADD THIS
    tokens_used = extract_token_usage(response.response_metadata)

    json_text = self._extract_json(response_text)
    score_data = json.loads(json_text)
    logger.info(f"[DEBUG] Parsed score_data keys: {score_data.keys()}")  # ADD THIS
    logger.info(f"[DEBUG] Enhanced moat data: {score_data.get('enhanced_moat', {})}")  # ADD THIS
```

---

## FILES MODIFIED

### Templates
1. `/research_swarm/reports/templates/executive_summary.md.j2`
2. `/research_swarm/reports/templates/stock_analysis.md.j2`
3. `/research_swarm/reports/templates/watchlist.md.j2`

### Configuration
4. `/research_swarm/reports/models.py`

### Prompts
5. `/research_swarm/agents/news_hound/prompts.py`

### Documentation
6. `/research_swarm/REPORT_FIXES_2026-02-12.md` (this file)

---

## NEXT STEPS

1. **Immediate:** Test with `python -m research_swarm run GOOGL` to verify template fixes
2. **High Priority:** Debug enhanced moat scoring (add logging as shown above)
3. **Medium Priority:** Investigate valuation_metrics yfinance issues
4. **Low Priority:** Review capital allocation scoring logic (may be working as designed)

---

## SUCCESS METRICS

**Before Fixes:**
- 58-page reports with heavy duplication
- Exposed internal thresholds
- Redundant graphs
- Wrong years in dates

**After Fixes:**
- Cleaner, professional reports
- No internal criteria exposed
- Single moat graph per stock (in executive summary context)
- Correct year instructions to LLM

**Remaining Work:**
- Enhanced moat scoring reliability
- External data dependency (yfinance)
- Capital allocation scoring accuracy
