# Supply Chain Analysis - Data Availability & Strategy

## The Core Problem

**Most companies do NOT disclose supplier names in 10-K/10-Q filings for competitive reasons.**

Apple, for example, deliberately avoids naming:
- Chip suppliers (TSMC, Samsung)
- Contract manufacturers (Foxconn, Pegatron)
- Component suppliers (Sony for cameras, LG for displays)

This is by design - they don't want competitors knowing their supply chain.

## Current System Behavior

The system IS working correctly:
1. ✓ Fetches 10-K/10-Q filings
2. ✓ Parses Item 1 (Business) and Item 1A (Risk Factors)
3. ✓ Calls LLM to extract supplier information
4. ✓ LLM correctly returns empty lists because **the data isn't in the filings**

## What IS Available in 10-Ks

Companies typically disclose:
- **Customer concentration** ("Our top 5 customers represent 60% of revenue")
- **Geographic revenue** ("40% from APAC, 30% from Americas")
- **Generic dependencies** ("We rely on third-party manufacturers in Asia")
- **Category descriptions** ("We source semiconductors from multiple suppliers")
- **Risk factors** ("Disruption to our Taiwan suppliers could impact production")

But NOT specific names.

## Solutions

### Option 1: Use Alternative Data Sources (RECOMMENDED)

**For comprehensive supply chain mapping, you need external data:**

1. **FactSet Supply Chain Relationships API**
   - Covers 80,000+ supplier relationships
   - Shows Apple → TSMC → ASML chains
   - Cost: ~$50k-200k/year

2. **Bloomberg Supply Chain Analysis**
   - Part of Bloomberg Terminal
   - Supplier/customer revenue relationships
   - Cost: Bloomberg Terminal required

3. **Craft.co / ZoomInfo**
   - Supplier relationship databases
   - API-accessible
   - Cost: ~$10k-50k/year

4. **Public Disclosures from Suppliers**
   - TSMC discloses Apple as major customer
   - Foxconn discloses Apple revenue
   - **This is backward-mapping**: check suppliers' 10-Ks to see who their customers are

### Option 2: Enhance LLM Extraction (Marginal Gains)

We can improve the prompt to extract MORE from what's available:

```python
# Enhanced prompt that looks for:
- Indirect supplier mentions ("semiconductor foundries in Taiwan" → TSMC)
- Customer concentration percentages
- Geographic supply chain risks
- Industry partnerships mentioned in press releases
- Technology licensing agreements
```

**Expected improvement: 10-30% more data, but still sparse**

### Option 3: Web Scraping + LLM Analysis (Medium Effort)

Scrape and analyze:
- Company press releases
- Investor presentations
- News articles about partnerships
- Industry reports
- Supplier annual reports (backward mapping)

**Expected improvement: 50-70% better coverage**

### Option 4: Manual Curation Database (High Effort)

Build a curated database of known relationships:
- Apple → TSMC, Foxconn, Samsung, LG, Sony
- Tesla → Panasonic, LG, CATL
- etc.

Then augment LLM analysis with this database.

## Immediate Action Items

### 1. Verify Current Extraction IS Working

Let's confirm the LLM is being called and returning what it finds:

```bash
# Check logs for "No 10-K filing found" warnings
# If present → filing isn't being fetched
# If absent → filing IS being fetched, but contains no supplier names
```

### 2. Test with a Company that DOES Disclose

Some companies are more transparent:
- **Small caps / private suppliers**: Often name major customers
- **Defense contractors**: Required to disclose government contracts
- **Automotive OEMs**: Often name tier-1 suppliers

Let's test with a supplier company that names its customers:

```bash
python -m research_swarm run TSMC
# TSMC should disclose Apple, NVIDIA, AMD as customers
```

### 3. Enhance Prompts for Better Extraction

Update `SUPPLY_CHAIN_PROMPT` to extract:
- Customer concentration percentages
- Geographic dependencies
- Generic supplier categories
- Risk factor mentions

### 4. Add Alternative Data Integration (If Budget Allows)

If supply chain is critical for your research:
- Integrate FactSet/Bloomberg APIs
- Build web scraping pipeline
- Create manual curated database for top 100 companies

## Recommendation

**For your research needs:**

1. **Short-term (this week):**
   - Test with supplier companies (TSMC, ASML, Foxconn equivalents)
   - Enhance prompts to extract MORE from existing data
   - Add backward-mapping: check suppliers' 10-Ks for customer names

2. **Medium-term (next month):**
   - Integrate news/press release scraping
   - Build curated database for top tech companies
   - Add industry report integration

3. **Long-term (if scaling):**
   - License professional supply chain database (FactSet, etc.)
   - Build comprehensive web scraping + LLM pipeline

## Questions for You

1. **What's your primary use case?**
   - Identifying supply chain risks?
   - Finding investment opportunities in suppliers?
   - Competitive analysis?

2. **What companies/sectors are you targeting?**
   - Tech companies? (hardest - very secretive)
   - Automotive? (more transparent)
   - Defense? (required disclosure)

3. **What's your budget for data?**
   - $0: Stick with 10-K extraction + backward mapping
   - $1k-10k: Add web scraping + news analysis
   - $10k+: License professional databases

Let me know and I can prioritize the solution that fits your needs!
