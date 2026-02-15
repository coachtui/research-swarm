# DVRG Issues & Fixes - February 14, 2026

## Issues Identified from BE Analysis

### 1. ✅ **PDF Generation Errors** (FIXED)

**Problem:**
- "unsupported format string passed to NoneType.__format__"
- "'stock' is undefined" in PDF template

**Root Cause:**
1. `conviction_generator.py` line 211: `valuation_category` could be None, causing format error
2. `pdf_report.html.j2` line 5: `stock.ticker` used outside the loop where `stock` isn't defined yet

**Fix Applied:**
```python
# conviction_generator.py line 211
cat = valuation_metrics.get("valuation_category") or "Fair"  # Ensure not None

# pdf_report.html.j2 line 5
<title>DVRG Report — {{ stocks[0].ticker if stocks else report.run_name }}</title>
```

**Status:** ✅ Fixed - PDF generation should work now

---

### 2. ⚠️ **Signal Analysis Missing Data** (PARTIAL - Need New Analysis)

**Problem:**
- Earnings Revisions: 5.0 (default - no data)
- Analyst Ratings: 5.0 (default - no data)
- Institutional: 5.0 (default - no data)
- Only News (1.5) and Insider (2.5) have real data

**Root Cause:**
Two possible reasons:
1. **Old Analysis**: BE was analyzed BEFORE the signal extraction fix (needs re-run)
2. **Missing Source Data**: News Hound didn't fetch earnings/analyst/institutional data for BE

**Fix Applied:**
- ✅ Updated all 4 extraction functions in `signal_divergence.py` to use correct Pydantic fields
- ✅ Backend restarted with fixes

**Action Required:**
1. **Run a NEW analysis for BE** (or any ticker) to test the fixed extraction
2. If still showing 5.0s, investigate why News Hound isn't fetching the data

---

### 3. ⚠️ **Data Quality Issue: "Zero Revenue"**

**Problem:**
Key insight says "Zero reported revenue combined with 10.0/10 growth score"
- This is factually wrong - BE reported earnings last week with revenue

**Root Cause:**
Two possibilities:
1. **LLM Hallucination**: Manager agent made up "zero revenue" when data was missing
2. **Data Extraction Failure**: Fundamentalist agent didn't fetch revenue properly

**Investigation Needed:**
```bash
# Check what revenue data was actually fetched
curl http://localhost:8000/api/runs/248955d9-81fe-48f1-a683-29eda3a53f0a | \
  jq '.results[0].full_output.fundamentalist_output.valuation_metrics'
```

Look for:
- `revenue` or `revenue_ttm` fields
- `growth_metrics.revenue_growth` fields

**Potential Fixes:**
1. If data is missing: Fix fundamentalist data fetching
2. If data exists but LLM ignores it: Fix manager synthesis prompt
3. Add validation: Warn when critical financial metrics are missing

---

### 4. ❌ **UI Clarity Issues** (NOT FIXED YET)

**Problem:**
Users don't understand what these mean:
- "ALL CLEAR" badge
- "All Signals Aligned" badge
- "Bearish consensus"
- "Signal Analysis" section overall

**Proposed Fixes:**

#### A. Add tooltips/info icons

**SignalDivergenceHero.tsx:**
```typescript
// Add info icon with tooltip next to "ALL CLEAR"
<Badge variant="success">
  ALL CLEAR
  <InfoIcon
    tooltip="All 5 market signals agree on direction - reduces uncertainty"
  />
</Badge>
```

**Tooltip text examples:**
- **"ALL CLEAR"**: "All 5 market signals agree on direction - reduces uncertainty"
- **"All Signals Aligned"**: "News, analyst ratings, institutions, insiders all pointing same way"
- **"Bearish consensus"**: "All signals suggest caution - smart money is selling"
- **"Signal Analysis"**: "Compares what media says vs what smart money (institutions & insiders) does"

#### B. Add explainer callout box

Add a dismissible info box above Signal Analysis:
```
💡 What is Signal Divergence?

Signal Divergence detects when different market signals disagree. For example:
- Headlines are bullish BUT insiders are selling = RED FLAG
- Headlines are bearish BUT institutions are buying = OPPORTUNITY

When all signals align (ALL CLEAR), the path forward is clearer.
When they diverge, it's a warning to dig deeper.
```

#### C. Improve "Bearish consensus" wording

Instead of just "Bearish consensus", show:
```
"Bearish consensus - All 5 signals suggest caution"
```

---

### 5. ⚠️ **Trade Target Progression** (FIXED - Need New Analysis)

**Problem:**
Conservative T2 ($295) was LOWER than T1 ($305.97)

**Root Cause:**
`decision_intelligence_calculator.py` didn't ensure T1 < T2 < T3

**Fix Applied:**
```python
# Conservative targets now progressively higher
conservative_t1 = max(conservative_t1, conservative_entry * 1.05)
conservative_t2 = max(base_target, conservative_t1 * 1.05)  # At least 5% above T1
conservative_t3 = max(bull_target, conservative_t2 * 1.10)  # At least 10% above T2

# Aggressive targets also fixed
aggressive_t1 = base_target
aggressive_t2 = max(bull_target, aggressive_t1 * 1.07)  # At least 7% above T1
aggressive_t3 = aggressive_t2 * 1.10  # 10% above T2
```

**Status:** ✅ Fixed - but requires NEW analysis to see corrected targets

---

## Action Plan

### Immediate (Do This Now):

1. **Test PDF Generation**:
   ```bash
   # In terminal, run backend:
   cd /Users/tui/Desktop/DevProjects/research-swarm
   uvicorn api.index:app --host 0.0.0.0 --port 8000 --reload

   # Try downloading PDF for BE analysis
   # Should work now (no more "stock is undefined" error)
   ```

2. **Run NEW Analysis**:
   - Pick ANY ticker (NVDA, GOOGL, MU, etc.)
   - Run a brand new analysis
   - Verify:
     - ✅ Signal scores show real data (not all 5.0s)
     - ✅ Colored bars (red/green/gray)
     - ✅ Trade targets are progressive (T1 < T2 < T3)
     - ✅ PDF downloads successfully

### Short-term (Next Session):

3. **Add UI Tooltips**:
   - Add info icons to "ALL CLEAR", "All Signals Aligned"
   - Add explainer callout box to Signal Analysis section
   - Improve badge text clarity

4. **Investigate Data Quality**:
   - Check why BE shows "zero revenue" (fetch full_output and inspect)
   - Verify why only 2/5 signals have data for BE
   - Add validation warnings for missing critical metrics

5. **Testing Checklist**:
   - [ ] PDF downloads without errors
   - [ ] All 5 signals show real scores (not 5.0 defaults)
   - [ ] Colored bars render correctly
   - [ ] Trade targets are progressive
   - [ ] "ALL CLEAR" / "Signal Divergence" badges explained
   - [ ] No "zero revenue" hallucinations

---

## Files Modified

1. ✅ `research_swarm/reports/conviction_generator.py` (line 211)
2. ✅ `research_swarm/reports/templates/pdf_report.html.j2` (line 5)
3. ✅ `research_swarm/agents/manager/signal_divergence.py` (lines 111-230)
4. ✅ `research_swarm/reports/decision_intelligence_calculator.py` (lines 218-235)

---

## Expected Results After Fixes

### Signal Analysis (NEW analysis required):
```
🎯 Signal Analysis                     [All Signals Aligned]

📰 News Sentiment        ████░░░░░░ 4.2  ⚪ Neutral
📈 Earnings Revisions    ████████░░ 7.5  🟢 Bullish  ← REAL DATA NOW
👔 Analyst Ratings       █████░░░░░ 5.0  ⚪ Neutral   ← REAL DATA NOW
🏛️ Institutional         ███░░░░░░░ 2.5  🔴 Bearish  ← REAL DATA NOW
👤 Insider Activity      ████░░░░░░ 4.0  ⚪ Neutral   ← REAL DATA NOW
```

### Trade Setup:
```
Conservative:
T1: $295 (Near-term)    ← LOWEST
T2: $310 (Base case)    ← MIDDLE
T3: $350 (Bull case)    ← HIGHEST
```

### PDF:
- ✅ Downloads successfully
- ✅ Shows ticker in title
- ✅ No format errors
