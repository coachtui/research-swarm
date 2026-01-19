# Research Swarm - User Guide

## Table of Contents
1. [Quick Start (5 minutes)](#quick-start)
2. [CLI Commands Overview](#cli-commands)
3. [Running Manual Analysis](#running-manual-analysis)
4. [Interpreting Reports](#interpreting-reports)
5. [Customizing Stock Universe](#customizing-stock-universe)
6. [Email Notifications](#email-notifications)
7. [Cost Management](#cost-management)
8. [Common Workflows](#common-workflows)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

Get up and running in 5 minutes.

### Prerequisites
- **Python 3.10+** (3.11.9 recommended)
- macOS or Linux
- API keys (Anthropic Claude, NewsAPI, Financial Modeling Prep)

### Installation

1. **Set up Python 3.11.9 with pyenv**:
   ```bash
   # Install pyenv if not already installed
   brew install pyenv

   # Install Python 3.11.9
   pyenv install 3.11.9
   pyenv local 3.11.9

   # Verify version
   eval "$(pyenv init -)"
   python --version  # Should show Python 3.11.9
   ```

2. **Clone and install dependencies**:
   ```bash
   git clone <repo-url> research-swarm
   cd research-swarm
   pip install -r requirements.txt
   pip install -e .
   ```

3. **Configure API keys**:
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys:
   # ANTHROPIC_API_KEY=sk-ant-...
   # NEWS_API_KEY=...
   # FMP_API_KEY=...
   ```

4. **Run your first analysis**:
   ```bash
   # Activate pyenv (IMPORTANT - do this every session)
   eval "$(pyenv init -)"

   # Analyze a single stock
   python -m research_swarm run AAPL

   # Check the results
   python -m research_swarm history
   ```

**Success**: You should see AAPL analysis complete with a moat score.

---

## CLI Commands Overview

Research Swarm provides 8 main commands:

### `run` - Execute Stock Analysis
Analyze one or more stocks, generate moat scores and investment theses.

```bash
# Single stock
python -m research_swarm run AAPL

# Multiple stocks
python -m research_swarm run AAPL NVDA MSFT

# From watchlist file
python -m research_swarm run --from-file watchlist.txt

# Custom parameters
python -m research_swarm run AAPL --fiscal-year 2024 --news-days 30
```

### `report` - Generate Reports
Create PDF and Markdown reports from completed runs.

```bash
# Generate report for latest run
python -m research_swarm report <run_id>

# PDF only
python -m research_swarm report <run_id> --format pdf

# Custom output directory
python -m research_swarm report <run_id> --output-dir ./my-reports

# Top 5 picks only
python -m research_swarm report <run_id> --top-picks 5
```

### `history` - View Past Runs
Browse previous analysis runs and their results.

```bash
# List all runs
python -m research_swarm history

# Last 10 runs
python -m research_swarm history --limit 10

# Export to markdown
python -m research_swarm history --export history.md
```

### `resume` - Resume Interrupted Run
Continue a paused or failed run from where it left off.

```bash
# List resumable runs
python -m research_swarm resume --list

# Resume specific run
python -m research_swarm resume <run_id>
```

### `estimate` - Cost Estimation
Estimate API costs before running analysis.

```bash
# Estimate cost for stocks
python -m research_swarm estimate AAPL NVDA MSFT

# From file
python -m research_swarm estimate --from-file watchlist.txt
```

### `cache` - Cache Management
Manage the API response cache.

```bash
# View cache statistics
python -m research_swarm cache stats

# Clear expired entries
python -m research_swarm cache clear

# Clear all entries (requires confirmation)
python -m research_swarm cache clear --all

# Force clear without confirmation
python -m research_swarm cache clear --all --force
```

### `cost` - Cost Tracking
Monitor API spending and budget utilization.

```bash
# Current month cost report
python -m research_swarm cost

# Specific month
python -m research_swarm cost --month 2026-01

# 6-month trend
python -m research_swarm cost --trend 6

# Full dashboard (recommended)
python -m research_swarm cost --dashboard
```

### `schedule` - Automation Management
Set up bi-weekly automated runs (macOS only).

```bash
# Install launchd job
python -m research_swarm schedule install

# Check status
python -m research_swarm schedule status

# Uninstall
python -m research_swarm schedule uninstall
```

---

## Running Manual Analysis

### Single Stock Analysis

The simplest way to analyze a company:

```bash
python -m research_swarm run AAPL
```

**What happens**:
1. Fundamentalist agent fetches 10-K from SEC Edgar
2. News Hound agent fetches recent news (30 days default)
3. Quant agent fetches market data from Yahoo Finance
4. Manager synthesizes findings and calculates moat score
5. Results saved to SQLite persistence DB

**Time**: Approximately 60-90 seconds per stock
**Cost**: Approximately $0.037 per stock (after Phase 11 optimization)

### Batch Analysis

Analyze multiple stocks in sequence:

```bash
python -m research_swarm run AAPL NVDA MSFT GOOGL AMZN
```

**Features**:
- Per-stock error isolation (one failure doesn't crash entire run)
- Automatic retry with exponential backoff (3 attempts per stock)
- Resume capability if interrupted
- Cost tracking per stock and per agent

### Using a Watchlist File

Create `watchlist.txt`:
```
AAPL
NVDA
MSFT
GOOGL
AMZN
```

Run with file:
```bash
python -m research_swarm run --from-file watchlist.txt
```

**Tip**: Use sector-specific watchlists (e.g., `semiconductors.txt`, `cloud.txt`)

### Custom Parameters

```bash
# Analyze specific fiscal year
python -m research_swarm run AAPL --fiscal-year 2023

# Look back 60 days for news
python -m research_swarm run AAPL --news-days 60

# Both parameters
python -m research_swarm run AAPL --fiscal-year 2023 --news-days 60
```

---

## Interpreting Reports

After a successful run, generate a report:

```bash
python -m research_swarm report <run_id>
```

Reports are generated in `data/reports/<run_id>/`:
- `executive_summary.md` - Markdown version
- `executive_summary.pdf` - PDF version with charts

### Report Sections

#### 1. Executive Summary
- Top N picks (default: 3)
- Investment thesis for each pick
- Key insights and catalysts
- Risk factors

**Example**:
```
## Top Picks

### 1. NVDA - Moat Score: 8.7 🟢
**Thesis**: Strong position in AI chip market with expanding data center revenue...
**Key Insights**:
- Financial health: 9.2 (exceptional margins)
- Sentiment: 8.5 (positive AI growth narrative)
- Technical: 8.0 (strong uptrend)
- Supply chain: 9.0 (critical tier-1 supplier)
```

#### 2. Moat Score Breakdown

Moat scores are weighted averages of 4 components:
- **Financial Health (30%)**: Balance sheet strength, profitability, growth
- **Sentiment (20%)**: News sentiment, catalysts, market perception
- **Technical (20%)**: Price trends, momentum, relative strength
- **Supply Chain (30%)**: Position in supply chain, diversification, dependencies

**Interpretation**:
- **8.0-10.0**: Strong moat, watchlist candidate 🟢
- **6.0-7.9**: Moderate moat, worth monitoring 🟡
- **4.0-5.9**: Weak moat, proceed with caution 🟠
- **0.0-3.9**: Very weak moat, high risk 🔴

#### 3. Supply Chain Visualizations

Network graphs show:
- **Nodes**: Companies in the supply chain
- **Edges**: Supplier/customer relationships
- **Colors**: Node type (tier-1, tier-2, target company)
- **Hidden dependencies**: Shared suppliers across multiple tier-1s

**Example**: NVDA → TSMC → ASML → Nittobo Glass (fiber optic components)

#### 4. Watchlist Candidates

Companies with moat score ≥ 8.0 are automatically added to the watchlist.

**Criteria**:
- Strong fundamentals (financial health ≥ 7.0)
- Positive catalysts or favorable sentiment
- Solid technical trends
- Strategic supply chain position

#### 5. Cost Summary

Tracks API costs for the run:
- Total cost (should be approximately $0.73 for 20 stocks)
- Cost per stock
- Cost by agent (fundamentalist, news_hound, quant, manager)
- Budget utilization percentage

**Warning signs**:
- Cost per stock > $0.10 (investigate caching)
- Total cost > $2.00 for 20 stocks (check agent models)

---

## Customizing Stock Universe

### Editing the Watchlist

The default watchlist is at `data/watchlist.txt`:

```bash
# Edit watchlist
nano data/watchlist.txt

# Add your stocks (one per line)
AAPL
NVDA
MSFT
```

### Sector-Specific Lists

Create multiple watchlists:

```bash
# Semiconductors
echo -e "NVDA\nAMD\nTSM\nASML\nLRCX" > semiconductors.txt

# Cloud infrastructure
echo -e "AMZN\nMSFT\nGOOGL\nORCL\nCRM" > cloud.txt

# Run specific list
python -m research_swarm run --from-file semiconductors.txt
```

### Finding New Stocks

**Supply chain discovery**:
1. Run analysis on a known company (e.g., NVDA)
2. Review supply chain visualization in report
3. Identify interesting tier-1 and tier-2 suppliers
4. Add them to your watchlist
5. Run analysis on new discoveries

**Example workflow**:
```bash
# Start with NVDA
python -m research_swarm run NVDA

# Generate report
python -m research_swarm report <run_id>

# Review supply chain section, find TSMC, ASML
# Add to watchlist
echo "TSM" >> watchlist.txt
echo "ASML" >> watchlist.txt

# Analyze new stocks
python -m research_swarm run TSM ASML
```

---

## Email Notifications

Research Swarm can send email notifications for:
- High-priority stocks (moat score ≥ 9)
- Cost alerts (monthly budget > $180)
- Job failures

### SMTP Configuration (Gmail)

Edit `.env`:
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
NOTIFICATION_EMAIL=your-email@gmail.com
```

**Gmail setup**:
1. Go to Google Account Settings → Security
2. Enable 2-Step Verification
3. Generate App Password
4. Use App Password in `.env` file

### SendGrid Configuration (Alternative)

Edit `.env`:
```bash
SENDGRID_API_KEY=SG.xxx...
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
NOTIFICATION_EMAIL=your-email@gmail.com
```

### Testing Email

```bash
python -m research_swarm notify --test
```

You should receive a test email within 1-2 minutes.

---

## Cost Management

### Understanding Costs

**Cost breakdown** (per stock, after Phase 11 optimization):
- Fundamentalist: approximately $0.010 (Haiku extraction + Sonnet analysis)
- News Hound: approximately $0.010 (Haiku filtering + Sonnet sentiment)
- Quant: approximately $0.005 (Haiku + Sonnet, minimal LLM use)
- Manager: approximately $0.012 (Sonnet synthesis + thesis)
- **Total**: approximately $0.037 per stock

**Monthly budget**: $200
- Bi-weekly run (20 stocks): approximately $0.73
- Monthly cost (2 runs): approximately $1.46
- **Utilization**: <1% of budget ✅

### Monitoring Costs

```bash
# View cost dashboard
python -m research_swarm cost --dashboard
```

**Dashboard shows**:
- Monthly spend and budget remaining
- Cost by agent (helps identify optimization opportunities)
- 3-month trend (spot unusual spikes)
- Budget utilization percentage

### Cost Optimization Tips

1. **Use cache aggressively**:
   - 10-Ks cached for 90 days
   - News cached for 7 days
   - Market data cached for 24 hours
   - Check cache stats: `python -m research_swarm cache stats`

2. **Batch efficiently**:
   - Run stocks in one batch (shares cache)
   - Avoid running same stock multiple times per day

3. **Monitor agent costs**:
   - If scorers show high cost, verify they're using Haiku (not Sonnet)
   - Check `research_swarm/agents/*/scorer.py` for model names

4. **Set up cost alerts**:
   - Email alerts trigger at $180/month threshold
   - Review dashboard bi-weekly

---

## Common Workflows

### Bi-Weekly Research Workflow

**Automated** (recommended):
```bash
# Set up automation
python -m research_swarm schedule install

# Verify it's running
python -m research_swarm schedule status

# Check logs
tail -f ~/Library/Logs/research_swarm/stdout.log
```

**Manual**:
```bash
# Monday morning routine (every 2 weeks)
eval "$(pyenv init -)"

# Run analysis
python -m research_swarm run --from-file watchlist.txt

# Generate report
RUN_ID=$(python -m research_swarm history --limit 1 | grep "Run ID")
python -m research_swarm report $RUN_ID

# Review report
open data/reports/$RUN_ID/executive_summary.pdf

# Check costs
python -m research_swarm cost --dashboard
```

### Adding a New Stock

```bash
# 1. Add to watchlist
echo "TSLA" >> watchlist.txt

# 2. Analyze
python -m research_swarm run TSLA

# 3. Generate quick report
RUN_ID=$(python -m research_swarm history --limit 1 | grep "Run ID")
python -m research_swarm report $RUN_ID

# 4. Review moat score
# If moat ≥ 8.0, consider adding to portfolio watchlist
```

### Quarterly Deep Dive

```bash
# Update cache (clear old data)
python -m research_swarm cache clear

# Run full analysis
python -m research_swarm run --from-file watchlist.txt

# Generate comprehensive report
python -m research_swarm report <run_id> --top-picks 10

# Review supply chain changes (compare to last quarter)
diff data/reports/<last_quarter_run>/executive_summary.md \
     data/reports/<this_quarter_run>/executive_summary.md
```

---

## Troubleshooting

### Issue: "unsupported operand type(s) for |"

**Cause**: Python version < 3.10

**Solution**:
```bash
eval "$(pyenv init -)"
python --version  # Must show 3.11.9
```

Add to `~/.bashrc` or `~/.zshrc`:
```bash
eval "$(pyenv init -)"
```

### Issue: High API costs

**Diagnosis**:
```bash
python -m research_swarm cost --dashboard
```

Look at "Cost by Agent" section. If any agent is > 40% of total, investigate.

**Solutions**:
- Verify scorers use Haiku: `grep "haiku" research_swarm/agents/*/scorer.py`
- Check cache: `python -m research_swarm cache stats`
- Reduce batch size or frequency

### Issue: No email notifications

**Test**:
```bash
python -m research_swarm notify --test
```

**Common fixes**:
- Gmail: Enable App Passwords, use app password (not account password)
- SendGrid: Verify API key is valid
- Check `.env` file has correct values

See [docs/troubleshooting.md](troubleshooting.md) for more issues.

---

## Next Steps

- **Architecture**: Read [architecture.md](architecture.md) to understand how agents work
- **Maintenance**: See [maintenance.md](maintenance.md) for routine procedures
- **API Reference**: Check [api-reference.md](api-reference.md) for programmatic usage
- **Examples**: Browse [examples.md](examples.md) for more command examples

---

**Questions?** See [faq.md](faq.md) or check the troubleshooting guide.
