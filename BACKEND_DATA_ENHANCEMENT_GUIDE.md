# Backend Data Enhancement Guide
## Supporting New Frontend QA Improvements

This guide shows how to enhance backend data structures to fully support the new frontend improvements.

---

## 1. Enhanced Rating Triggers with Specific Thresholds

### Current Structure:
```python
# research_swarm/reports/models.py
class Trigger(BaseModel):
    condition: str
    threshold: Optional[str] = None
    metric: Optional[str] = None
```

### Enhanced Structure:
```python
class Trigger(BaseModel):
    condition: str  # "Insider Activity turns positive (shows market confidence)"
    threshold: Optional[str] = None
    metric: Optional[str] = None
    specific_trigger: Optional[str] = None  # "2+ C-suite executives buy >$500K in next 30 days"
```

### Implementation Example:
```python
# research_swarm/reports/decision_intelligence_calculator.py

def generate_specific_upgrade_triggers(
    ticker: str,
    current_price: float,
    signal_breakdown: SignalBreakdown,
    technical_data: dict
) -> list[Trigger]:
    """Generate upgrade triggers with specific quantifiable thresholds."""

    triggers = []

    # 1. Insider Activity trigger
    if signal_breakdown.insider_score < 5.0:
        triggers.append(Trigger(
            condition="Insider Activity turns positive (shows market confidence)",
            threshold="Score > 6.0",
            metric="Insider Activity Score",
            specific_trigger="2+ C-suite executives buy >$500K in next 30 days"
        ))

    # 2. Technical momentum trigger
    if signal_breakdown.technical_strength < 6.0:
        macd_threshold = technical_data.get('macd_signal', 0) * 1.05
        triggers.append(Trigger(
            condition="Technical momentum improves (ends downtrend)",
            threshold="MACD > signal line",
            metric="MACD",
            specific_trigger=f"MACD crosses positive + volume >150% of 20-day avg"
        ))

    # 3. Valuation trigger
    if signal_breakdown.valuation_score < 6.0:
        fair_value_low = current_price * 0.88  # 12% pullback
        fair_value_high = current_price * 0.95  # 5% pullback
        triggers.append(Trigger(
            condition="Price pulls back to fair value range",
            threshold=f"${fair_value_low:.2f} - ${fair_value_high:.2f}",
            metric="Stock Price",
            specific_trigger=f"Close below ${fair_value_high:.2f} for 3+ consecutive days"
        ))

    # 4. Earnings beat trigger
    next_earnings = estimate_next_earnings_date(ticker)
    triggers.append(Trigger(
        condition="Earnings beat with raised guidance",
        threshold=">10% beat vs consensus",
        metric="EPS",
        specific_trigger=f"Earnings beat >10% with raised guidance (Next: ~{next_earnings})"
    ))

    return triggers


def generate_specific_downgrade_triggers(
    ticker: str,
    current_price: float,
    signal_breakdown: SignalBreakdown,
    stop_loss_price: float
) -> list[Trigger]:
    """Generate downgrade triggers with specific quantifiable thresholds."""

    triggers = []

    # 1. Technical breakdown
    triggers.append(Trigger(
        condition="Price breaks critical support level",
        threshold=f"${stop_loss_price:.2f}",
        metric="Stock Price",
        specific_trigger=f"Close below ${stop_loss_price:.2f} on high volume (>2x avg)"
    ))

    # 2. Insider selling
    if signal_breakdown.insider_score < 7.0:
        triggers.append(Trigger(
            condition="Insider selling accelerates",
            threshold="3+ executives in 2 weeks",
            metric="Insider Transactions",
            specific_trigger="3+ C-suite insiders sell >$1M each within 2 weeks"
        ))

    # 3. Earnings miss
    triggers.append(Trigger(
        condition="Earnings miss with lowered guidance",
        threshold=">5% miss vs consensus",
        metric="EPS",
        specific_trigger="Q1 earnings miss >5% AND guidance cut >10%"
        ))

    # 4. Institutional exodus
    if signal_breakdown.institutional_score > 5.0:
        triggers.append(Trigger(
            condition="Major institutional selling",
            threshold=">15% ownership decline",
            metric="Institutional Ownership",
            specific_trigger="Top 3 holders reduce positions by >15% in one quarter"
        ))

    return triggers
```

---

## 2. Recent News for Signal Divergence Section

### New Structure:
```python
# frontend/components/results/SignalDivergenceSection.tsx expects:
recentNews = [
    {
        "date": "Feb 12",
        "headline": "Morgan Stanley upgrades to Overweight, $210 target",
        "source": "Morgan Stanley"  # Optional
    }
]
```

### Backend Implementation:
```python
# research_swarm/reports/decision_intelligence_calculator.py

def extract_recent_news(
    news_hound_output: NewsHoundOutput,
    max_items: int = 3
) -> list[dict]:
    """Extract top 3 most recent/relevant news headlines."""

    if not news_hound_output or not news_hound_output.news_items:
        return []

    recent_news = []

    # Sort by date (most recent first) or sentiment impact
    sorted_news = sorted(
        news_hound_output.news_items,
        key=lambda x: (x.published_date, abs(x.sentiment_score - 5.0)),
        reverse=True
    )

    for item in sorted_news[:max_items]:
        # Format date as "Feb 12" or "2 days ago"
        date_str = format_relative_date(item.published_date)

        recent_news.append({
            "date": date_str,
            "headline": item.headline[:100],  # Truncate if too long
            "source": item.source
        })

    return recent_news


def format_relative_date(date_str: str) -> str:
    """Convert ISO date to relative format."""
    from datetime import datetime, timedelta

    try:
        date = datetime.fromisoformat(date_str)
        now = datetime.now()
        delta = now - date

        if delta.days == 0:
            return "Today"
        elif delta.days == 1:
            return "Yesterday"
        elif delta.days < 7:
            return f"{delta.days} days ago"
        else:
            return date.strftime("%b %d")
    except:
        return "Recent"
```

### Add to DecisionIntelligence:
```python
# research_swarm/reports/models.py

class DecisionIntelligence(BaseModel):
    # ... existing fields
    recent_news: Optional[list[dict]] = None  # NEW FIELD
    next_earnings_date: Optional[str] = None  # NEW FIELD
```

### Populate in Generator:
```python
# research_swarm/reports/decision_intelligence_calculator.py

def calculate_decision_intelligence(...) -> DecisionIntelligence:
    # ... existing logic

    return DecisionIntelligence(
        # ... existing fields
        recent_news=extract_recent_news(manager_output.news_hound_output),
        next_earnings_date=estimate_next_earnings_date(ticker),
    )
```

---

## 3. Next Earnings Date Estimation

### Implementation:
```python
# research_swarm/reports/decision_intelligence_calculator.py

def estimate_next_earnings_date(ticker: str) -> str:
    """
    Estimate next earnings date based on:
    1. SEC filings pattern (10-Q/10-K due dates)
    2. Historical earnings dates
    3. Fiscal quarter calendar
    """
    from datetime import datetime, timedelta

    # Most companies report quarterly
    # Q1: Late April/Early May
    # Q2: Late July/Early August
    # Q3: Late October/Early November
    # Q4: Late January/Early February

    now = datetime.now()
    month = now.month

    # Simple heuristic based on current month
    if 1 <= month <= 3:
        return "Late April"
    elif 4 <= month <= 6:
        return "Late July"
    elif 7 <= month <= 9:
        return "Late October"
    else:
        return "Late January"

    # TODO: Enhance with:
    # - Parse earnings_calendar from fundamentalist_output
    # - Query Yahoo Finance/Alpha Vantage earnings calendar API
    # - Extract from 10-K/10-Q filing patterns
```

### Better Implementation (with API):
```python
import requests
from datetime import datetime

def get_next_earnings_date_from_api(ticker: str) -> Optional[str]:
    """Fetch actual next earnings date from financial data API."""

    try:
        # Option 1: Yahoo Finance (free)
        url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
        params = {
            "modules": "calendarEvents"
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        earnings_date = data["quoteSummary"]["result"][0]["calendarEvents"]["earnings"]["earningsDate"][0]["fmt"]
        return earnings_date

    except Exception as e:
        # Fallback to estimation
        return estimate_next_earnings_date(ticker)
```

---

## 4. Sector/Industry Fields

### Add to ManagerOutput:
```python
# research_swarm/agents/manager/models.py

class ManagerOutput(BaseModel):
    # ... existing fields
    sector: Optional[str] = None  # "Technology"
    industry: Optional[str] = None  # "Semiconductors"
    market_cap_category: Optional[str] = None  # "Large Cap"
```

### Extract from Fundamentalist:
```python
# research_swarm/agents/fundamentalist/graph.py

def extract_company_profile(state: FundamentalistState) -> dict:
    """Extract sector/industry from company profile."""

    profile = state.get("company_profile", {})

    return {
        "sector": profile.get("sector", "Unknown"),
        "industry": profile.get("industry", "Unknown"),
        "market_cap_category": categorize_market_cap(profile.get("market_cap", 0))
    }


def categorize_market_cap(market_cap: float) -> str:
    """Categorize market cap into investment buckets."""
    if market_cap >= 200_000_000_000:  # $200B+
        return "Mega Cap"
    elif market_cap >= 10_000_000_000:  # $10B+
        return "Large Cap"
    elif market_cap >= 2_000_000_000:  # $2B+
        return "Mid Cap"
    elif market_cap >= 300_000_000:  # $300M+
        return "Small Cap"
    else:
        return "Micro Cap"
```

---

## 5. Integration Checklist

### Phase 1: Minimal (Optional but Recommended)
- [ ] Add `specific_trigger` field to Trigger model
- [ ] Implement basic trigger generation with thresholds
- [ ] Test that existing triggers still work

### Phase 2: Enhanced News (High Value)
- [ ] Add `recent_news` field to DecisionIntelligence
- [ ] Extract top 3 news from news_hound_output
- [ ] Format dates as relative ("2 days ago")

### Phase 3: Earnings & Sector (Medium Value)
- [ ] Add `next_earnings_date` to DecisionIntelligence
- [ ] Implement earnings date estimation or API lookup
- [ ] Add sector/industry to ManagerOutput
- [ ] Extract from fundamentalist company profile

### Phase 4: Full Enhancement (Nice to Have)
- [ ] Connect to Yahoo Finance/Alpha Vantage for live earnings dates
- [ ] Add historical divergence statistics
- [ ] Track which signals are more reliable per sector

---

## 6. Example Full Response

### Before (Current):
```json
{
  "upgrade_triggers": [
    {
      "condition": "Insider Activity turns positive",
      "threshold": "> 6.0",
      "metric": "Insider Score"
    }
  ]
}
```

### After (Enhanced):
```json
{
  "upgrade_triggers": [
    {
      "condition": "Insider Activity turns positive (shows market confidence)",
      "threshold": "> 6.0",
      "metric": "Insider Score",
      "specific_trigger": "2+ C-suite executives buy >$500K in next 30 days"
    }
  ],
  "recent_news": [
    {
      "date": "Feb 12",
      "headline": "Morgan Stanley upgrades to Overweight, $210 target",
      "source": "Morgan Stanley"
    },
    {
      "date": "Feb 10",
      "headline": "Insider sale: CFO sold $2.1M shares (routine)",
      "source": "SEC Form 4"
    }
  ],
  "next_earnings_date": "Late April",
  "sector": "Technology",
  "industry": "Semiconductors"
}
```

---

## Testing

### Test Cases:
1. **Trigger Generation:** Ensure specific_trigger is populated for all conditions
2. **News Extraction:** Verify top 3 most relevant/recent headlines
3. **Earnings Date:** Confirm estimation falls in correct quarter
4. **Sector Classification:** Check sector/industry from fundamentalist
5. **Backward Compatibility:** Ensure old responses still work without new fields

---

## Performance Considerations

- News extraction: O(n log n) sort, negligible for <100 items
- Earnings date API: Add 100-200ms latency, use caching
- Specific trigger generation: Pure logic, no external calls
- Overall impact: <1% additional analysis time

---

**Priority:** Medium (enhances UX significantly but not blocking)
**Effort:** 2-4 hours for full implementation
**Risk:** Low (all fields are optional, backward compatible)
