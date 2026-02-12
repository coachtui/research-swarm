# RESEARCH-SWARM MASTER PLAN
## AI-Powered Equity Research Platform

**Last Updated:** February 12, 2026  
**Status:** Pre-Revenue, Building MVP  
**Goal:** Launch SaaS product generating institutional-quality equity research

---

# TABLE OF CONTENTS

1. [Vision & Mission](#vision--mission)
2. [Product Overview](#product-overview)
3. [Technical Architecture](#technical-architecture)
4. [Analysis Framework](#analysis-framework)
5. [Data Sources & Costs](#data-sources--costs)
6. [Monetization Strategy](#monetization-strategy)
7. [Implementation Roadmap](#implementation-roadmap)
8. [Current Status](#current-status)
9. [Next Actions](#next-actions)
10. [Success Metrics](#success-metrics)

---

# VISION & MISSION

## Vision
Democratize institutional-quality equity research by making AI-powered analysis accessible to retail investors at 1/100th the cost of Bloomberg or FactSet.

## Mission
Build an AI research platform that detects signal divergences and contrarian opportunities before they become obvious to the market - finding hidden value through systematic analysis of fundamentals, sentiment, and smart money activity.

## Core Value Proposition
> "See what institutional money is doing, not just what headlines say"

**Key Differentiator:** Signal divergence detection
- Example: MSFT news bearish (4.31/10) but institutions bullish (7.50/10)
- This contrarian intelligence is worth $149/mo to active investors

---

# PRODUCT OVERVIEW

## What We Build
AI-powered equity research reports comparable to Zacks Investment Research, but with enhanced sentiment analysis and divergence detection.

## Target Customer
**Primary:** Active retail investors and traders
- Managing $50K-500K portfolios
- Make 10-50 trades/year
- Currently pay for Seeking Alpha, Morningstar, or individual research
- Value contrarian signals and smart money tracking

**Secondary:** Small RIAs and family offices
- Need research coverage for client portfolios
- Can't afford Bloomberg ($24K/year)
- Want systematic, unbiased analysis

## Core Features

### 1. Comprehensive Stock Analysis
- **Overall Moat Score:** 0-10 weighted composite
- **VGM Style Classification:** Value/Growth/Momentum/Quality grades (A-F)
- **Enhanced Moat Analysis:** 8 competitive advantage sources
- **Financial Health:** Deep fundamental analysis
- **Valuation:** Peer-relative metrics
- **Technical Analysis:** Entry/exit signals
- **Sentiment Signals:** 5-component breakdown

### 2. Signal Divergence Detection ⭐ (KEY DIFFERENTIATOR)
```
News Sentiment:         4.3/10 🔴 (Market narrative: bearish)
Institutional Activity: 7.5/10 🟢 (Reality: smart money accumulating)

⚠️ DIVERGENCE DETECTED: Contrarian opportunity
```

### 3. Actionable Intelligence
- 12-month price targets (Bull/Base/Bear scenarios)
- Entry/exit zones with specific prices
- Stop loss recommendations
- Position sizing guidance
- Risk/reward ratios

### 4. Track Record Validation
- Historical signal performance
- "Called MSFT at $350, now $425 (+21%)"
- Win rates by signal type
- Builds credibility over time

---

# TECHNICAL ARCHITECTURE

## System Design: 4-Agent Swarm

```
User Request (Ticker: AAPL)
    ↓
┌─────────────────────────────────────────┐
│   MANAGER AGENT (Claude Sonnet 4)      │
│   - Orchestrates workflow               │
│   - Synthesizes final rating            │
│   - Generates report                    │
└─────────────────────────────────────────┘
    ↓
    ├─→ FUNDAMENTALIST AGENT (Claude Sonnet 4)
    │   ├─ Financial statement analysis
    │   ├─ VGM style classification
    │   ├─ Enhanced moat evaluation (8 sources)
    │   ├─ Peer comparison
    │   └─ Valuation analysis
    │
    ├─→ NEWS HOUND AGENT (Claude Sonnet 4)
    │   ├─ News sentiment analysis
    │   ├─ Analyst consensus tracking
    │   ├─ Institutional ownership analysis
    │   ├─ Insider transaction tracking
    │   ├─ Management quality assessment
    │   ├─ Short interest analysis
    │   └─ Upcoming catalyst identification
    │
    ├─→ QUANT AGENT (Claude Haiku 3.5)
    │   ├─ Technical indicator analysis
    │   ├─ Trend identification
    │   ├─ Support/resistance levels
    │   ├─ Entry/exit signal generation
    │   └─ Risk metrics calculation
    │
    └─→ SIGNAL ANALYZER (Claude Haiku 3.5)
        ├─ 5-component sentiment breakdown
        ├─ Signal divergence detection
        └─ Contrarian opportunity identification
    ↓
Database (Neon Postgres)
    ↓
Report Generation (PDF/Web)
```

## Technology Stack

### Backend
- **Framework:** FastAPI (Python 3.11)
- **Database:** Neon Postgres (serverless)
- **ORM:** SQLAlchemy + Alembic
- **AI:** Anthropic Claude API
  - Sonnet 4: Analysis agents (high reasoning)
  - Haiku 3.5: Data extraction (cost optimization)

### Data Layer
- **Primary:** Yahoo Finance (yfinance) - FREE
- **Backup:** Alpha Vantage, Polygon.io
- **Future:** FMP Professional (when revenue justifies $199/mo)

### Deployment
- **API:** Vercel (serverless functions)
- **Database:** Neon (serverless Postgres)
- **Background Jobs:** Future - Inngest/BullMQ
- **Auth:** Future - Clerk ($25/mo after validation)

### Frontend (Future)
- **Framework:** Next.js 14
- **UI:** Tailwind CSS + shadcn/ui
- **Deployment:** Vercel

---

# ANALYSIS FRAMEWORK

## Overall Moat Score (0-10)

**Weighted Components:**
```
Earnings Momentum (25%)     - Zacks-style estimate analysis
Financial Health (25%)      - Balance sheet, profitability, growth
Valuation (20%)            - Peer-relative, growth-adjusted
Technical/Momentum (15%)   - Price action, trend strength
Sentiment (15%)            - 5-component signal breakdown
```

**Formula:**
```python
overall_moat_score = (
    earnings_momentum * 0.25 +
    financial_health * 0.25 +
    valuation * 0.20 +
    technical * 0.15 +
    sentiment * 0.15
)
```

## VGM Style Classification

**Four Scores (A-F grades):**

### Value Score
- P/E vs sector average
- PEG ratio
- Price-to-Book
- Dividend yield
- Free cash flow yield

### Growth Score
- Revenue growth (1yr, 3yr, 5yr)
- EPS growth vs sector
- Margin expansion
- Growth consistency
- Addressable market size

### Momentum Score
- Price performance (YTD, 1yr)
- Earnings surprises (last 4 quarters)
- Estimate revisions trend
- Relative strength vs S&P 500

### Quality Score
- ROIC (Return on Invested Capital)
- Gross/Operating/Net margins
- Balance sheet strength (debt/equity)
- Free cash flow generation
- Earnings quality

**Output:**
```
Value Score:     B
Growth Score:    A
Momentum Score:  A
Quality Score:   A

VGM Composite:   A
Best Fit For:    Growth & Quality investors
```

## Enhanced Moat Analysis (8 Sources)

**For each moat source, evaluate:**

| Moat Source | Strength | Durability | Trend |
|-------------|----------|------------|-------|
| 1. Brand Power | Strong/Moderate/Weak/None | High/Medium/Low | Widening/Stable/Narrowing |
| 2. Network Effects | Strong/Moderate/Weak/None | High/Medium/Low | Widening/Stable/Narrowing |
| 3. Switching Costs | Strong/Moderate/Weak/None | High/Medium/Low | Widening/Stable/Narrowing |
| 4. Cost Advantages | Strong/Moderate/Weak/None | High/Medium/Low | Widening/Stable/Narrowing |
| 5. Intangible Assets | Strong/Moderate/Weak/None | High/Medium/Low | Widening/Stable/Narrowing |
| 6. Efficient Scale | Strong/Moderate/Weak/None | High/Medium/Low | Widening/Stable/Narrowing |
| 7. Regulatory Protection | Strong/Moderate/Weak/None | High/Medium/Low | Widening/Stable/Narrowing |
| 8. Distribution Network | Strong/Moderate/Weak/None | High/Medium/Low | Widening/Stable/Narrowing |

**Overall Moat Width:** Wide / Moderate / Narrow / None

**Example:**
```
Apple (AAPL) Moat Analysis:

Brand Power:         Strong    High    Widening
Network Effects:     Strong    High    Stable
Switching Costs:     Strong    High    Widening
Cost Advantages:     Moderate  Medium  Stable
Intangible Assets:   Strong    High    Widening
Efficient Scale:     Weak      Low     N/A
Regulatory:          Weak      Low     N/A
Distribution:        Moderate  Medium  Stable

Overall Moat Width: WIDE
```

## Sentiment Signal Breakdown (5 Components)

**Each scored 0-10:**

### 1. News Sentiment
- Recent news coverage (90 days)
- Tone analysis (positive/neutral/negative)
- Volume and velocity of coverage
- Media source credibility

### 2. Earnings Momentum
- Estimate revisions (consensus changes)
- Earnings surprise history (last 4 quarters)
- Beat/miss patterns
- Guidance changes

### 3. Analyst Consensus
- Recommendation distribution (Buy/Hold/Sell)
- Target price vs current price
- Recent upgrades/downgrades
- Analyst count and coverage quality

### 4. Institutional Activity
- Ownership percentage and trend
- Top holder changes (13F filings)
- Smart money accumulation/distribution
- Institutional ownership concentration

### 5. Insider Transactions
- Net buying/selling (6 months)
- Transaction size and frequency
- Insider ownership percentage
- Sentiment (bullish/neutral/bearish)

**Output:**
```
Overall Sentiment: 6.2/10

Component Signals:
• News Sentiment:         7.3/10 🟢
• Earnings Momentum:      8.5/10 🟢
• Analyst Consensus:      7.5/10 🟢
• Institutional Activity: 4.0/10 🔴
• Insider Transactions:   3.5/10 🔴

⚠️ SIGNAL DIVERGENCE DETECTED:
News and analysts bullish, but smart money (institutions + insiders) 
selling. Exercise caution - potential near-term weakness despite 
positive narrative.
```

## Final Rating Scale

```
STRONG BUY (8.5-10.0)
├─ Multiple strong moats
├─ All signals align bullish
├─ Undervalued with catalyst
├─ Clear entry opportunity
└─ High conviction

BUY (7.0-8.4)
├─ Solid fundamentals
├─ Positive outlook
├─ Minor concerns noted
├─ Good risk/reward
└─ Medium-high conviction

HOLD (5.0-6.9)
├─ Mixed signals
├─ Fair valuation
├─ No clear catalyst
├─ Wait for better entry
└─ Medium conviction

SELL (3.0-4.9)
├─ Deteriorating fundamentals
├─ Overvalued
├─ Negative trends
├─ Better opportunities elsewhere
└─ Medium-high conviction

STRONG SELL (0-2.9)
├─ Broken investment thesis
├─ Major risks identified
├─ Eroding competitive position
├─ Exit recommended
└─ High conviction
```

## Price Target Framework

**Three Scenarios with Probabilities:**

### Bull Case
- Optimistic assumptions
- Best-case multiple expansion
- Strong execution
- Probability: 25-35%

### Base Case
- Conservative assumptions
- Current multiples maintained
- Expected execution
- Probability: 40-50%

### Bear Case
- Pessimistic assumptions
- Multiple contraction
- Weak execution or headwinds
- Probability: 20-30%

**Expected Value:**
```
Expected Price = (Bull × P_bull) + (Base × P_base) + (Bear × P_bear)

Example:
Bull:  $150 × 30% = $45.00
Base:  $120 × 50% = $60.00
Bear:  $90  × 20% = $18.00
──────────────────────────
Expected Value:     $123.00
```

---

# DATA SOURCES & COSTS

## Current: Yahoo Finance (FREE) ✅

**What We Get:**
- ✅ Financial statements (annual + quarterly)
- ✅ Balance sheet, income statement, cash flow
- ✅ Key metrics (P/E, PEG, margins, ROIC, etc.)
- ✅ Analyst recommendations (consensus)
- ✅ Earnings estimates (consensus forward EPS)
- ✅ Earnings surprise history
- ✅ Institutional ownership (top holders)
- ✅ Insider transactions
- ✅ Short interest metrics
- ✅ Historical prices (OHLCV)
- ✅ Beta, volatility, 52-week range
- ✅ Dividends, splits

**What We're Missing:**
- ❌ Individual analyst estimate revisions (only consensus)
- ❌ Institutional position changes (QoQ flow)
- ❌ Earnings call transcripts
- ❌ Real-time data (15-20 min delay)

**Analysis Quality:** 90% of what paid services provide

**Monthly Cost:** $0

---

## Future: Financial Modeling Prep (WHEN REVENUE JUSTIFIES)

**Upgrade Trigger:** $1,000/mo MRR (Monthly Recurring Revenue)

**FMP Professional:** $199/mo

**Additional Data:**
- ✅ Individual analyst estimates + revisions
- ✅ Institutional 13F position changes (QoQ)
- ✅ Earnings call transcripts
- ✅ More comprehensive fundamental data
- ✅ Better international coverage

**Improvement:** 10-15% better analysis quality

**ROI Calculation:**
- Cost: $199/mo
- Need: 2 additional Pro subscribers ($149/mo each)
- Break-even: ~1.5 incremental subs

---

## Data Flow Architecture

```python
# data_provider.py

import yfinance as yf

class YahooFinanceProvider:
    """Free, unlimited data provider"""
    
    def get_complete_data(self, ticker: str) -> dict:
        stock = yf.Ticker(ticker)
        
        return {
            'fundamentals': {
                'financials': stock.financials,
                'balance_sheet': stock.balance_sheet,
                'cash_flow': stock.cashflow,
                'metrics': stock.info,  # P/E, margins, etc.
            },
            'estimates': {
                'earnings': stock.earnings_estimate,
                'revenue': stock.revenue_estimate,
                'history': stock.earnings_history,
            },
            'sentiment': {
                'analysts': stock.recommendations,
                'institutions': stock.institutional_holders,
                'insiders': stock.insider_transactions,
                'short_interest': stock.info['shortPercentOfFloat'],
            },
            'technical': {
                'prices': stock.history(period='2y'),
                'beta': stock.info['beta'],
            }
        }
```

---

# MONETIZATION STRATEGY

## Tiered Pricing Model

### FREE TIER (Lead Generation)
**Price:** $0/mo

**Included:**
- ✅ Overall moat score (e.g., "7.2/10")
- ✅ Final rating (Strong Buy/Buy/Hold/Sell)
- ✅ 12-month price target
- ✅ One-paragraph executive summary
- ❌ Full analysis details
- ❌ Entry strategy
- ❌ Signal breakdown

**Purpose:** Capture emails, demonstrate value, drive upgrades

---

### BASIC TIER
**Price:** $49-79/mo

**Included:**
- ✅ Everything from Free
- ✅ Full 2,500-word research report (all 4 agents)
- ✅ Moat score breakdown (5 components)
- ✅ VGM style classification
- ✅ Competitive moat analysis (8 sources)
- ✅ Financial health deep dive
- ✅ Peer comparison tables
- ✅ Key risks and catalysts
- ✅ Price target methodology
- ✅ 5 reports per month
- ❌ Entry/exit strategy
- ❌ Signal divergence alerts
- ❌ Historical tracking

**Target Customer:** Passive investors, buy-and-hold

---

### PRO TIER ⭐ (MONEY TIER)
**Price:** $99-149/mo

**Included:**
- ✅ Everything from Basic
- ✅ **15 reports per month**
- ✅ **Recommended Entry Zone:** $X - $Y
- ✅ **Ideal Entry Trigger** (pullback to support / breakout)
- ✅ **Stop Loss Price** (max risk %)
- ✅ **Take Profit Targets** (T1: sell X%, T2: sell remaining)
- ✅ **Risk/Reward Ratio** (e.g., 4.1:1)
- ✅ **Bull/Base/Bear Scenarios** with probabilities
- ✅ **Position Sizing Recommendation** (% of portfolio)
- ✅ **Signal Divergence Analysis**
- ✅ **Sentiment Signal Breakdown** (5 components)
- ❌ Real-time alerts
- ❌ API access

**Target Customer:** Active traders, swing traders

**Key Value:** Entry/exit prices worth $149/mo - one good entry vs bad entry can make $500+ difference on a $10K position

---

### ENTERPRISE TIER
**Price:** $249-299/mo

**Included:**
- ✅ Everything from Pro
- ✅ **Unlimited reports**
- ✅ **Real-time Price Alerts** (when stocks hit buy zones)
- ✅ **Rating Change Notifications** (post-earnings updates)
- ✅ **Portfolio-Level Recommendations** (best risk/reward across watchlist)
- ✅ **Quarterly Re-rating** (automatic post-earnings)
- ✅ **API Access** (for algorithmic traders)
- ✅ **Priority Coverage Requests**
- ✅ **White-label reports** (for RIAs)

**Target Customer:** RIAs, family offices, professional traders

---

## Revenue Projections

### Year 1 (Conservative)
```
Q1 (Months 1-3): Pay-Per-Report Validation
├─ 30 reports @ $39 = $1,170
├─ Goal: Validate quality, build testimonials
└─ Costs: $200 (API + hosting)

Q2-Q4 (Months 4-12): Tiered Subscriptions
├─ 10 Basic @ $79/mo = $790/mo
├─ 3 Pro @ $149/mo = $447/mo
├─ 0 Enterprise
└─ Monthly: $1,237/mo × 9 months = $11,133

Year 1 Total Revenue: ~$12,300
Year 1 Costs: ~$2,640 (API $200/mo)
Year 1 Net Profit: ~$9,660
```

### Year 2 (Growth)
```
Basic:      50 @ $79/mo = $3,950/mo
Pro:        25 @ $149/mo = $3,725/mo
Enterprise: 5 @ $299/mo = $1,495/mo

Monthly Revenue: $9,170/mo
Annual Revenue: $110,040/year

Costs:
├─ API & Data: $400/mo ($4,800/year)
├─ Infrastructure: $100/mo ($1,200/year)
├─ Marketing: $200/mo ($2,400/year)
└─ Total: $8,400/year

Net Profit: $101,640/year
Margin: 92%
```

---

## Unit Economics

### Gross Margin
```
Revenue per Pro Sub: $149/mo
COGS per Sub: ~$8/mo (API costs)

Gross Margin: 95%
```

### Customer Acquisition Cost (CAC)
```
Channel: Content marketing + SEO
CAC Target: $50-100 per customer
Payback: <1 month for Pro tier
```

### Lifetime Value (LTV)
```
Pro Tier:
├─ ARPU: $149/mo
├─ Churn: 5% monthly (target)
├─ Lifetime: 20 months
└─ LTV: $2,980

LTV:CAC Ratio: 30:1 (excellent)
```

### Conversion Funnel
```
1,000 Free users (content marketing)
    ↓ 5% convert
50 Basic @ $79 = $3,950/mo
    ↓ 30% upgrade
15 Pro @ $149 = $2,235/mo
    ↓ 20% upgrade
3 Enterprise @ $299 = $897/mo

Total MRR: $7,082/mo = $84,984/year
```

---

## Go-to-Market Strategy

### Phase 1: Pay-Per-Report (Months 1-3)
**Goal:** Validate quality before complex billing

**Execution:**
- Simple landing page (Carrd $19/year)
- Stripe payment integration
- Price: $29-39 per report
- Goal: 10-20 paid reports/month

**Marketing:**
- Post sample reports on Reddit (r/investing, r/stocks)
- Twitter thread with NVDA divergence example
- "AI found institutions buying MSFT while news was bearish"

---

### Phase 2: Freemium + Subscriptions (Months 4-6)
**Goal:** Recurring revenue, build customer base

**Execution:**
- FREE: 1 report/month, basic scoring only
- BASIC ($79/mo): 5 reports/month, full analysis
- PRO ($149/mo): 15 reports/month, entry strategy

**Marketing:**
- Weekly "Top Pick" email (free)
- Track record: "Called 3 stocks that beat S&P 500"
- Testimonials from pay-per-report customers

---

### Phase 3: Enterprise (Months 7-12)
**Goal:** High-value customers, white-label

**Execution:**
- ENTERPRISE ($299/mo): Unlimited reports, API access
- Target: Small RIAs, family offices
- White-label: RIAs can brand reports for clients

**Marketing:**
- LinkedIn outreach to RIAs
- "Institutional research for 1/10th Bloomberg cost"
- Case study: "RIA saved $20K/year switching from Morningstar"

---

### Phase 4: Platform Play (Year 2+)
**Additional Revenue Streams:**

1. **Issuer-Paid Coverage** ($5K-15K per company)
   - Companies pay for research coverage
   - Full disclosure required
   - Must maintain editorial independence

2. **Data Licensing** (API to aggregators)
   - Sell moat scores, ratings to other platforms
   - Bloomberg competitor feeds

3. **Affiliate Trading** (broker referrals)
   - Partner with Interactive Brokers, Schwab
   - Earn commission on trades from reports

---

## Competitive Positioning

### Market Map
```
High Price ($10K-25K/year)
├─ Bloomberg Terminal
├─ FactSet
└─ S&P Capital IQ

Mid Price ($200-500/year)
├─ Morningstar Premium ($249/year)
├─ Seeking Alpha Premium ($299/year)
└─ Zacks Premium ($249/year)

Low Price ($0-100/year)
├─ Yahoo Finance (free)
├─ Google Finance (free)
└─ Finviz (free)

OUR POSITION: $79-299/mo ($948-3,588/year)
├─ Above: Free tools
├─ Below: Institutional platforms
└─ Sweet spot: "AI-powered institutional research at retail prices"
```

### Competitive Advantages

**vs Morningstar/Seeking Alpha:**
- ✅ Signal divergence detection (they don't have)
- ✅ 5-component sentiment breakdown (more granular)
- ✅ Entry/exit strategy with specific prices (actionable)
- ✅ AI-powered, always up-to-date (their reports age)

**vs Zacks:**
- ✅ Enhanced moat analysis (8 sources vs their basic moat)
- ✅ VGM scores PLUS quality score
- ✅ Smart money divergence tracking (they lack institutional flow)
- ❌ They have better earnings revision data (for now)

**vs Bloomberg/FactSet:**
- ✅ 100x cheaper
- ✅ Easier to use
- ✅ AI-powered insights (they're mostly raw data)
- ❌ They have more comprehensive data
- ❌ They have real-time data

---

# IMPLEMENTATION ROADMAP

## Phase 1: MVP Launch (Weeks 1-4) ✅ IN PROGRESS

### Week 1: Core Analysis Engine
**Status:** ✅ COMPLETE

**Deliverables:**
- [x] 4-agent architecture (Fundamentalist, News Hound, Quant, Manager)
- [x] Yahoo Finance data integration
- [x] Pydantic models with proper defaults
- [x] Signal divergence detection
- [x] Database schema (5 tables in Neon)
- [x] Cost tracking

**Testing:**
- [x] AAPL analysis (6.99/10)
- [x] NVDA analysis (6.98/10, institutional 9.0/10)
- [x] DIS analysis (4.99/10, divergence detected)
- [x] MSFT analysis (5.36/10, contrarian signal)
- [x] TSM analysis (5.97/10, ADR handling)

---

### Week 2: API & Deployment ⚠️ IN PROGRESS
**Status:** Backend built, deployment blocked

**Current Issues:**
- ❌ Vercel deployment failing (Pydantic v1 migration needed)
- ❌ UV package manager conflicts
- ✅ FastAPI routes defined
- ✅ Database connected

**Immediate Tasks:**
1. Migrate to Pydantic v1 (avoid Rust compilation on Vercel)
2. Deploy API to Vercel
3. Test via Swagger UI (https://your-app.vercel.app/docs)
4. Verify end-to-end flow

**Success Criteria:**
- [ ] API deployed and accessible
- [ ] POST /api/analyze works with real analysis
- [ ] GET /api/runs retrieves from database
- [ ] <4 minute analysis time
- [ ] <$0.40 cost per analysis

---

### Week 3: Report Generation ⚠️ NEXT PRIORITY
**Status:** Old template exists, needs complete overhaul

**Current Problem:**
- Report generator uses OLD template
- Missing all new analysis sections:
  - ❌ VGM Style Classification
  - ❌ Enhanced Moat Analysis (8 sources)
  - ❌ Sentiment Signal Breakdown
  - ❌ Signal Divergence Detection
  - ❌ Management Quality Assessment
  - ❌ Short Interest Analysis
  - ❌ Upcoming Catalysts
  - ❌ Price Scenarios (Bull/Base/Bear)

**Tasks:**
1. Update report template with all new sections
2. Create formatting functions (tables, charts)
3. Test report generation on 5 tickers
4. Generate PDF + web-viewable versions
5. Ensure all scores display correctly

**Success Criteria:**
- [ ] Report shows VGM scores
- [ ] Report shows moat breakdown table
- [ ] Report shows sentiment signal analysis
- [ ] Report highlights divergences when present
- [ ] Professional appearance (ready to sell)

---

### Week 4: Frontend + Launch
**Status:** Not started

**Minimal Frontend (2 hours):**
```
1. Landing page
   ├─ Hero: "AI-powered equity research"
   ├─ Sample report (AAPL or NVDA)
   ├─ Pricing table (Free/Basic/Pro)
   └─ Email capture

2. Analysis request page
   ├─ Ticker input form
   ├─ Submit → API call
   └─ Loading state (4 min wait)

3. Results page
   ├─ Display moat score, rating
   ├─ Key highlights
   ├─ Link to full PDF report
   └─ CTA: "Upgrade for entry strategy"
```

**Launch Checklist:**
- [ ] Deploy frontend to Vercel
- [ ] Connect to API
- [ ] Test full user flow
- [ ] Set up Stripe (pay-per-report)
- [ ] Prepare 3 sample reports (AAPL, NVDA, TSLA)
- [ ] Write launch post for Reddit/Twitter

---

## Phase 2: Validation & Iteration (Months 2-3)

### Goals
- Get 10-20 paid reports ($300-800 revenue)
- Collect feedback on report quality
- Identify most valuable features
- Build testimonials

### Marketing Activities
- Post on Reddit weekly (different subs)
- Twitter threads showing divergence examples
- Email sequence for free users
- Track which reports sell (sectors, market cap)

### Product Improvements
- Add most-requested features
- Improve prompt quality based on feedback
- Build report library (50+ pre-generated reports)
- Add email delivery of reports

---

## Phase 3: Subscriptions (Months 4-6)

### Launch Tiers
- FREE: 1 report/month
- BASIC: $79/mo (5 reports)
- PRO: $149/mo (15 reports + entry strategy)

### Infrastructure
- Add Clerk authentication ($25/mo)
- Implement usage tracking
- Add payment portal (Stripe Customer Portal)
- Email automation (welcome, usage alerts, upgrades)

### Goal
- 10 Basic subscribers ($790/mo)
- 3 Pro subscribers ($447/mo)
- MRR: $1,237/mo

---

## Phase 4: Scale (Months 7-12)

### Product
- Enterprise tier ($299/mo)
- API access for traders
- Real-time alerts (Inngest background jobs)
- Portfolio view (track multiple stocks)
- Mobile app (React Native)

### Marketing
- Content marketing (SEO blog)
- YouTube (educational content + product demos)
- Partnerships with finance YouTubers
- LinkedIn for RIA outreach

### Goal
- 50 Basic ($3,950/mo)
- 25 Pro ($3,725/mo)
- 5 Enterprise ($1,495/mo)
- MRR: $9,170/mo

---

## Phase 5: Enterprise (Year 2)

### Upgrade to Premium Data
- Add FMP Professional ($199/mo)
- Improve earnings momentum tracking
- Institutional flow analysis
- Earnings call transcripts

### Enterprise Features
- White-label reports for RIAs
- Custom coverage requests
- Dedicated account management
- SLA guarantees

### Goal
- 100+ subscribers
- $15K-20K MRR
- Break even on premium data

---

# CURRENT STATUS

## ✅ What's Working

### Backend Analysis (95% Complete)
- [x] 4-agent architecture functional
- [x] Yahoo Finance data integration
- [x] Signal divergence detection validated
- [x] Database storing all runs and scores
- [x] Cost tracking ($0.30-0.40 per analysis)
- [x] Performance acceptable (3-4 minutes)

### Analysis Quality (Validated)
- [x] NVDA: Correctly identified strong institutional conviction (9.0/10)
- [x] DIS: Detected news/analyst divergence (4.6 vs 7.5)
- [x] MSFT: Found contrarian signal (news 4.31, institutions 7.50)
- [x] Works across sectors (tech, entertainment, energy, ADRs)

### Database Schema
```
✅ users (id, email, subscription_tier)
✅ analysis_runs (id, ticker, status, scores, cost)
✅ fundamentalist_analyses (financial_data, vgm_scores, moat_analysis)
✅ news_hound_analyses (sentiment_data, signals, catalysts)
✅ quant_analyses (technical_data, entry_exit_levels)
```

---

## ⚠️ In Progress

### Deployment (Blocked)
- ❌ Vercel deployment failing (Pydantic Rust compilation)
- ⏳ Need to migrate to Pydantic v1
- ⏳ API routes defined but not deployed

### Report Templates (Critical Gap)
- ❌ Current template uses OLD format
- ❌ Missing all new analysis sections
- ⏳ Need complete rewrite to display:
  - VGM scores
  - Enhanced moat
  - Signal breakdown
  - Divergence alerts
  - All new sections

---

## ❌ Not Started

### Frontend
- [ ] Landing page
- [ ] Analysis request form
- [ ] Results display
- [ ] User dashboard

### Authentication
- [ ] Clerk integration
- [ ] User accounts
- [ ] Subscription management

### Payments
- [ ] Stripe integration
- [ ] Pay-per-report flow
- [ ] Subscription billing

### Marketing
- [ ] Sample reports published
- [ ] Reddit/Twitter presence
- [ ] Email capture
- [ ] Content marketing

---

# NEXT ACTIONS

## Immediate (This Week)

### Priority 1: Fix Vercel Deployment (CRITICAL)
**Prompt for Claude Code:**
```
Migrate to Pydantic v1 to fix Vercel deployment.

Current error: Pydantic v2 requires Rust compilation which fails on Vercel.

Tasks:
1. Update requirements.txt to pydantic==1.10.14
2. Remove pydantic-settings (use python-dotenv instead)
3. Update code:
   - model_validate() → parse_obj()
   - model_dump() → dict()
   - model_validate_json() → parse_raw()
4. Test deployment to Vercel
5. Verify API works in production
```

**Time:** 30-60 minutes  
**Success:** API deployed and accessible at https://your-app.vercel.app

---

### Priority 2: Update Report Templates (CRITICAL)
**Prompt for Claude Code:**
```
Update report generator to display all new analysis sections.

Current problem: Report shows old format, missing:
- VGM Style Classification
- Enhanced Moat Analysis (8 sources)
- Sentiment Signal Breakdown (5 components)
- Signal Divergence Detection
- Management Quality Assessment
- Short Interest Analysis
- Upcoming Catalysts
- Price Scenarios (Bull/Base/Bear)

Tasks:
1. Find report template file (likely reports/template.py or reports/generator.py)
2. Add all missing sections with proper formatting
3. Update data flow to pull from agent outputs
4. Test on AAPL, NVDA, DIS
5. Generate professional PDF

Reference: /home/claude/equity_research_swarm_master_prompt.md for section structures
```

**Time:** 4-6 hours  
**Success:** Report displays all analysis sections correctly

---

### Priority 3: Generate Sample Reports (Marketing)
**After templates are fixed:**

1. Generate 5 high-quality reports:
   - AAPL (mega-cap tech)
   - NVDA (high-growth AI)
   - DIS (struggling blue-chip with divergence)
   - JPM (financials)
   - XOM (energy/cyclical)

2. Redact/watermark free tier reports

3. Post to Reddit/Twitter with headline findings:
   - "AI detected institutions accumulating MSFT while news turned bearish"
   - "Signal divergence in DIS: Market pessimistic, analysts optimistic"

**Time:** 2-3 hours  
**Success:** 5 professional reports ready to share

---

## This Month (Weeks 2-4)

### Week 2: Deploy + Test
- [ ] Fix Vercel deployment
- [ ] Test API end-to-end
- [ ] Verify database storage
- [ ] Test cost tracking

### Week 3: Reports + Marketing
- [ ] Update report templates
- [ ] Generate 20 sample reports
- [ ] Post 1st sample report on Reddit
- [ ] Start email collection

### Week 4: Basic Frontend
- [ ] Simple landing page
- [ ] Report request form
- [ ] Results display
- [ ] Stripe pay-per-report

---

## Next Quarter (Months 2-3)

### Month 2: Validation
- Get 10+ paid reports
- Collect feedback
- Iterate on quality
- Build testimonials
- Track which sectors sell best

### Month 3: Subscriptions
- Add Clerk auth
- Launch Basic + Pro tiers
- Email automation
- Goal: 5-10 subscribers

---

# SUCCESS METRICS

## Technical Metrics

### Performance
- **Analysis Time:** <4 minutes (target: 3-4 min) ✅
- **Cost per Analysis:** <$0.50 (current: $0.30-0.40) ✅
- **Uptime:** >99.5%
- **Error Rate:** <1%

### Quality
- **Signal Divergence Detection:** Working ✅
- **Institutional Sentiment Accuracy:** Validated (NVDA 9.0) ✅
- **Cross-Sector Performance:** Tested (tech/entertainment/energy) ✅
- **ADR Handling:** Works (TSM validated) ✅

---

## Business Metrics

### Month 1-3 (Pay-Per-Report)
- **Goal:** 10-20 paid reports
- **Revenue Target:** $300-800
- **Success:** Validate quality, build testimonials

### Month 4-6 (Subscriptions Launch)
- **Goal:** 10 Basic + 3 Pro subscribers
- **MRR Target:** $1,200/mo
- **Success:** Recurring revenue established

### Month 7-12 (Scale)
- **Goal:** 50 Basic + 25 Pro + 5 Enterprise
- **MRR Target:** $9,000/mo
- **Success:** Sustainable business model

### Year 2
- **Goal:** 200+ subscribers
- **MRR Target:** $20,000/mo
- **Success:** Upgrade to premium data, hire help

---

## Product-Market Fit Signals

### Early Indicators (Watch For)
- [ ] 20%+ conversion from free to paid
- [ ] <5% monthly churn
- [ ] Users asking for annual plans
- [ ] Organic word-of-mouth growth
- [ ] Enterprise inquiries (RIAs, family offices)

### Strong PMF
- [ ] 40%+ of users say "very disappointed" without product
- [ ] CAC payback <3 months
- [ ] LTV:CAC ratio >3:1
- [ ] Users creating content about product
- [ ] Unsolicited press/media coverage

---

# CONSTRAINTS & ASSUMPTIONS

## Constraints

### Time
- Solo founder with day job (EquipmentAI Inspector)
- ~10-15 hours/week available for research-swarm
- Must automate everything possible

### Budget
- Monthly API budget: ~$200
- No budget for paid marketing initially
- Bootstrap until revenue justifies spend

### Technical
- No Rust compiler on Vercel (hence Pydantic v1)
- 4-minute Vercel function timeout limit
- Free tier data sources (Yahoo Finance)

---

## Assumptions

### Market
- Retail investors will pay for AI research
- Divergence detection is valuable enough to charge for
- $79-149/mo is acceptable price point
- Market size: 10M+ active investors in US

### Product
- Yahoo Finance data is sufficient for MVP
- 90% quality vs premium data is good enough
- Users value actionable intelligence over perfect data
- Entry/exit prices justify Pro tier premium

### Competition
- Morningstar/Zacks won't add divergence detection quickly
- Bloomberg/FactSet ignore retail market
- AI research is novel enough to capture attention

---

# DECISION LOG

## Key Decisions Made

### Data Source: Yahoo Finance (Not FMP)
**Decision:** Use free Yahoo Finance for MVP  
**Rationale:** 90% quality, $0 cost, validates product before paying $199/mo  
**Date:** Feb 11, 2026  
**Review:** After $1,000/mo MRR

### Moat Scoring: Remove Supply Chain Analysis
**Decision:** Replace "Supply Chain (30%)" with "Earnings Momentum (25%)"  
**Rationale:** Supply chain = vulnerabilities, not advantages. Earnings momentum is Zacks' proven edge  
**Date:** Feb 11, 2026

### Deployment: Vercel Serverless (Not VPS)
**Decision:** Deploy on Vercel, not self-hosted VPS  
**Rationale:** Zero ops, auto-scaling, $10-30/mo vs hours managing servers  
**Date:** Feb 11, 2026

### Authentication: Deploy with Mock Auth First
**Decision:** Launch with mock auth, add Clerk after validation  
**Rationale:** Validate infrastructure works before adding auth complexity  
**Date:** Feb 12, 2026

### Pydantic Version: Downgrade to v1
**Decision:** Use Pydantic v1.10.14 instead of v2  
**Rationale:** v2 requires Rust compilation which fails on Vercel  
**Date:** Feb 12, 2026

### Report Priority: Templates Before Features
**Decision:** Fix report templates before adding Quant enhancements  
**Rationale:** 80% of analysis done but invisible to users without proper templates  
**Date:** Feb 12, 2026

---

# RESOURCES

## Key Documents
- `/home/claude/equity_research_swarm_master_prompt.md` - Complete agent prompts
- `/home/claude/migration_to_yahoo_finance.md` - Data migration guide
- `/home/claude/master-plan.md` - This document

## Critical Files
```
research-swarm/
├── research_swarm/
│   ├── agents/
│   │   ├── fundamentalist/
│   │   │   ├── analyzer.py (TTM analysis)
│   │   │   ├── models.py (Pydantic schemas)
│   │   │   └── prompts.py (LLM prompts)
│   │   ├── news_hound/
│   │   ├── quant/
│   │   └── manager/
│   ├── database/
│   │   ├── models.py (SQLAlchemy)
│   │   └── connection.py
│   └── data_provider.py (Yahoo Finance)
├── api/
│   ├── routes/
│   │   ├── analyze.py
│   │   └── runs.py
│   └── main.py
├── reports/
│   ├── generator.py (NEEDS UPDATE)
│   └── template.py (NEEDS UPDATE)
└── requirements.txt
```

## External Services
- **Database:** Neon (https://neon.tech)
- **Deployment:** Vercel (https://vercel.com)
- **AI:** Anthropic Claude (https://console.anthropic.com)
- **Payments:** Stripe (https://stripe.com) - future
- **Auth:** Clerk (https://clerk.com) - future

## Learning Resources
- Zacks Investment Research methodology
- Hamilton Helmer "7 Powers" (moat analysis)
- Morningstar moat methodology
- Warren Buffett letters (competitive advantages)

---

# APPENDIX

## Glossary

**ADR (American Depositary Receipt):** Foreign company stock trading on US exchanges

**Moat:** Sustainable competitive advantage (Warren Buffett term)

**VGM Scores:** Value/Growth/Momentum classification system (Zacks methodology)

**Signal Divergence:** When different indicators (news vs institutions) disagree - creates contrarian opportunities

**TTM (Trailing Twelve Months):** Last 12 months of financial data

**13F Filing:** Quarterly report of institutional holdings >$100M AUM

**LLM (Large Language Model):** AI like Claude that generates analysis

**MRR (Monthly Recurring Revenue):** Predictable subscription income

**CAC (Customer Acquisition Cost):** Cost to acquire one customer

**LTV (Lifetime Value):** Total revenue from one customer

**Churn:** % of customers who cancel per month

---

## Contact & Support

**Project Owner:** Tui  
**Status:** Pre-revenue MVP  
**Last Updated:** February 12, 2026

**For Questions:**
- Technical issues → Claude Code
- Product strategy → Reference this master plan
- Market validation → Test with real users

---

## Version History

**v1.0** - February 12, 2026
- Initial comprehensive master plan
- Consolidated all prior discussions
- Defined complete strategy and roadmap
- Documented current status and blockers

---

**END OF MASTER PLAN**

*This document is the single source of truth for the research-swarm project. Update it as decisions are made and progress occurs.*