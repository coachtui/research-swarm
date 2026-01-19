# Bottleneck Investment Strategy Guide

## Overview

Your research-swarm system now identifies **critical supply chain bottlenecks** - companies that large tech giants depend on with no viable alternatives. This is the core of your investment thesis.

## The Investment Thesis

**Find the irreplaceable suppliers** that powerful companies cannot function without. These bottlenecks have:
- **Pricing power**: Can raise prices without losing customers
- **High switching costs**: Customers can't easily replace them
- **Moat protection**: Years of R&D or infrastructure advantage
- **Revenue visibility**: Long-term contracts with major customers

## How the System Works

### 1. Enhanced 10-K Extraction

The system now looks for **indirect clues** even when companies don't name suppliers:

**Apple 10-K might say:**
- "We rely on third-party foundries in Taiwan for chip manufacturing"
  → System infers: **TSMC dependency**

- "Single-source suppliers for critical components"
  → System flags: **High bottleneck risk**

- "Contract manufacturers primarily in China"
  → System infers: **Foxconn-type assembly partners**

### 2. Curated Knowledge Base

The system has a database of **known critical relationships**:

```python
# Example: Apple's supply chain
AAPL → depends on:
  - TSM (TSMC): sole-source for advanced chips → EXTREME bottleneck
  - ASML: TSM's sole EUV supplier → ABSOLUTE monopoly
  - Foxconn: primary assembly → HIGH risk
  - AVGO (Broadcom): RF components → MEDIUM risk
```

### 3. Bottleneck Tiers

The system classifies suppliers into investment tiers:

#### **Tier 0: Absolute Monopolies** (Highest conviction)
- **ASML**: ONLY company making EUV lithography machines
  - Every advanced chip maker (TSMC, Intel, Samsung) MUST buy from them
  - 10+ year technology lead, NO alternatives
  - Investment thesis: **Strongest moat in all of tech**

- **Synopsys/Cadence (EDA duopoly)**:
  - Every chip designer MUST use their software
  - Switching cost = impossible (years of workflow integration)
  - Investment thesis: **Recurring revenue from entire semiconductor industry**

#### **Tier 1: Critical Bottlenecks** (High conviction)
- **TSMC (TSM)**: Dominant advanced node manufacturer
  - Apple, NVIDIA, AMD depend on them for cutting-edge chips
  - 2-5 year lead over Samsung, Intel struggling to catch up
  - Investment thesis: **AI boom beneficiary, irreplaceable in near-term**

- **SK Hynix**: Critical HBM3 memory supplier
  - NVIDIA depends on them for H100/H200 GPUs
  - Limited alternatives (Samsung ramping but behind)
  - Investment thesis: **AI memory bottleneck, pricing power**

#### **Tier 2: Major Suppliers** (Moderate conviction)
- **Applied Materials (AMAT)**: Semiconductor equipment
- **Lam Research (LRCX)**: Etching equipment
- **Broadcom (AVGO)**: RF components

Good businesses but have viable competitors.

#### **Tier 3: Moderate Suppliers** (Low conviction)
- **Samsung displays**: Multiple alternatives exist
- **LG Display**: Commoditizing market

## Using the System

### Step 1: Analyze Large Tech Companies

Run analysis on big tech to map their dependencies:

```bash
# Analyze Apple
python -m research_swarm run AAPL

# Check the supply chain section in the report
python -m research_swarm report <run_id>
```

**What you'll see:**
- Suppliers identified from 10-K + knowledge base
- Bottleneck risk ratings (extreme/high/medium/low)
- Critical dependency paths
- Supply chain resilience score

### Step 2: Analyze the Bottleneck Suppliers

Now analyze the suppliers themselves:

```bash
# Analyze TSMC
python -m research_swarm run TSM

# You'll see:
# - Who their customers are (Apple, NVIDIA, AMD)
# - Revenue concentration (Apple = ~25% of revenue)
# - Their own suppliers (ASML, Applied Materials)
# - Bottleneck analysis: "Tier 1 Critical"
```

### Step 3: Go Deeper - Tier 2 Bottlenecks

Analyze the suppliers of suppliers:

```bash
# TSMC depends on ASML for EUV machines
python -m research_swarm run ASML

# You'll discover:
# - ASML is Tier 0 (absolute monopoly)
# - Depends on Zeiss (private) for optics
# - Customers: TSMC (30%), Samsung (20%), Intel (15%)
# - This is the ULTIMATE bottleneck
```

### Step 4: Build Your Investment Thesis

**Example bottleneck opportunity identified:**

1. **Run**: `python -m research_swarm run AAPL`
   - Discovers: Apple sole-sourced to TSMC for chips

2. **Run**: `python -m research_swarm run TSM`
   - Discovers: TSMC sole-sourced to ASML for EUV equipment
   - Revenue concentration: TSMC is 30-35% of ASML's EUV revenue

3. **Run**: `python -m research_swarm run ASML`
   - Discovers: Absolute monopoly, no alternatives exist
   - Customers: Every advanced chipmaker globally
   - **Investment Thesis**: ASML is the ultimate bottleneck in the entire semiconductor supply chain

## Investment Scoring System

The system scores companies on **supply chain position**:

### As a CUSTOMER (Company you're analyzing)
- **Low Score (0-3)**: Heavy dependence on bottleneck suppliers
  - Example: Apple (depends on TSMC, no alternatives)
  - **Risk**: Supply disruption could halt production
  - **Implication**: Consider the supplier instead

- **High Score (7-10)**: Diversified supply chain
  - Multiple alternatives for each component
  - **Lower risk** but also signals commodity market

### As a SUPPLIER (Bottleneck opportunity)
- **Score 9-10**: Tier 0 absolute monopoly (ASML, Synopsys)
- **Score 7-9**: Tier 1 critical bottleneck (TSMC, SK Hynix)
- **Score 5-7**: Tier 2 major supplier (AMAT, LRCX)
- **Score 3-5**: Tier 3 moderate supplier (many alternatives)

## Real-World Examples

### Example 1: NVIDIA's HBM Bottleneck (2024-2025)

```
NVDA → depends on → SK Hynix for HBM3

Analysis shows:
- SK Hynix: 80%+ market share in HBM3
- Samsung ramping but 6-12 months behind
- Micron entering but small volumes

Investment opportunity: SK Hynix (000660.KS)
- Pricing power as NVIDIA scales AI production
- Revenue visibility (long-term contracts)
- Limited near-term competition
```

### Example 2: The ASML Chain

```
AAPL → TSM → ASML → Zeiss (private)
NVDA → TSM → ASML → Zeiss (private)
INTC → ASML → Zeiss (private)

Every advanced chip flows through ASML.

Investment thesis: ASML is the ultimate picks-and-shovels play
- Every AI/compute company eventually depends on them
- 10+ year R&D moat, impossible to replicate
- Pricing power as demand for advanced chips grows
```

### Example 3: EDA Software Duopoly

```
Every chip designer → SNPS or CDNS

Analysis shows:
- Synopsys/Cadence control 70%+ of EDA market
- Switching cost = millions of dollars, years of retraining
- Recurring revenue model (annual licenses)
- Every new chip design = more revenue

Investment thesis: Software toll booth on semiconductor industry
- Growth tied to chip design activity (growing with AI)
- Extremely high margins (software business)
- Pricing power (critical to customers, small % of their costs)
```

## Updating the Knowledge Base

As you discover new relationships, update the database:

**File**: `research_swarm/data/supply_chain_db.json`

Add new companies and relationships:

```json
{
  "TSLA": {
    "suppliers": [
      {
        "name": "Panasonic",
        "ticker": "PCRFY",
        "category": "batteries",
        "criticality": "critical",
        "description": "Major battery cell supplier",
        "dependency_level": "major",
        "bottleneck_risk": "high",
        "source": "Tesla partnerships"
      }
    ]
  }
}
```

## Workflow for Research

### Daily Routine:
1. **Monitor large cap tech** (AAPL, MSFT, GOOGL, NVDA, META)
2. **Run quarterly analyses** to track dependency changes
3. **Identify new bottlenecks** as tech evolves

### When You Find a Bottleneck:
1. **Verify the dependency** (check both sides)
2. **Assess the moat** (can it be disrupted?)
3. **Check customer concentration** (diversified or risky?)
4. **Analyze financials** (margins, growth, cash flow)
5. **Build position** if thesis holds

### Red Flags to Watch:
- **Customer concentration >40%** = single customer risk
- **New entrants** = moat being challenged
- **Vertical integration** = customers building in-house (Apple makes own chips now)
- **Geographic risk** = Taiwan, China dependencies

## Next Steps

1. **Run the fixed system**:
   ```bash
   python -m research_swarm run AAPL
   python -m research_swarm report <run_id>
   ```

2. **Check the supply chain section** - should now show:
   - Suppliers from 10-K + knowledge base
   - Bottleneck risk ratings
   - Critical paths

3. **Expand the database**:
   - Add more companies you're interested in
   - Add automotive supply chains (Tesla, GM, Ford)
   - Add cloud infrastructure (hyperscalers depend on NVDA, AMD)

4. **Build your watchlist** of bottleneck suppliers:
   - Tier 0: ASML, SNPS, CDNS
   - Tier 1: TSM, SK Hynix, NVDA (is itself a bottleneck for AI)
   - Tier 2: AMAT, LRCX, AVGO

## The Power of This Approach

Traditional analysis looks at:
- Revenue growth
- Margins
- P/E ratios

**Bottleneck analysis adds:**
- **Structural position** in the supply chain
- **Switching costs** and moat durability
- **Pricing power** from irreplaceability
- **Long-term visibility** from dependencies

This is how you find the next ASML before everyone else realizes it's irreplaceable.

## Questions to Guide Your Research

For every company you analyze, ask:

1. **Who can't live without this company?**
   - If the answer is "big tech giants", you found a bottleneck

2. **What happens if this company raises prices 20%?**
   - If customers have no choice but to pay, that's pricing power

3. **How long would it take a competitor to replicate this?**
   - If the answer is "5+ years", that's a moat

4. **Is demand growing faster than supply?**
   - If yes + bottleneck = pricing power expansion

5. **Are customers trying to vertical integrate?**
   - If yes, the moat might be weakening

---

**Your goal**: Build a portfolio of irreplaceable suppliers that large companies depend on. Let the giants grow, and you own their critical dependencies.
