# Phase 12 Handoff: Documentation & Maintenance

**Status**: Ready for Implementation
**Created**: 2026-01-18
**Plan File**: [plans/current-phase.md](plans/current-phase.md)
**Previous Phase**: Phase 11 - Optimization & Cost Control (264 tests passing)

---

## Phase 12 Objectives

1. Create comprehensive user guide for running and customizing the system
2. Document system architecture with diagrams and workflows
3. Write maintenance procedures for long-term sustainability
4. Create handoff checklist for future developers
5. Address Python version requirement documentation
6. Create troubleshooting guide for common issues

**Success Criteria**: Someone with basic Python knowledge can run the system and maintain it with 30 minutes of onboarding

---

## Current Project Status

**Phases 1-11 Complete**:
- ✅ 264 total tests passing (233 unit + 31 optimization tests)
- ✅ 54% code coverage
- ✅ 92% cost reduction achieved (Haiku 3.5 optimization)
- ✅ $0.73 per bi-weekly run (99% under budget)
- ✅ Complete automation with email notifications
- ✅ Professional PDF reports with charts

**Python Version Issue**:
- Shell defaults to Anaconda Python 3.9.13
- Project requires Python 3.10+ for `|` union type syntax
- Must use `eval "$(pyenv init -)"` before running commands

---

## Session 12.1: User Guide & Quick Start

**Duration**: 2-3 hours
**Goal**: Enable new users to run the system within 30 minutes

### Task 1.1: Create Documentation Directory

```bash
mkdir -p docs
touch docs/README.md
touch docs/user-guide.md
touch docs/architecture.md
touch docs/maintenance.md
touch docs/troubleshooting.md
touch docs/api-reference.md
touch docs/examples.md
touch docs/faq.md
touch docs/handoff-checklist.md
```

### Task 1.2: Write `docs/user-guide.md`

**Target**: 1,500+ words

**Structure**:

```markdown
# Research Swarm - User Guide

## Table of Contents
1. [Quick Start (5 minutes)](#quick-start)
2. [CLI Commands Overview](#cli-commands)
3. [Running Manual Analysis](#running-manual-analysis)
4. [Interpreting Reports](#interpreting-reports)
5. [Customizing Stock Universe](#customizing-stock-universe)
6. [Email Notifications](#email-notifications)
7. [Cost Management](#cost-management)

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

### `auto` - Run Automation Manually
Execute the automated workflow manually (for testing).

```bash
# Dry run (no actual execution)
python -m research_swarm auto --dry-run

# Run with watchlist
python -m research_swarm auto --tickers-file watchlist.txt
```

### `notify` - Test Notifications
Test email notification configuration.

```bash
# Send test email
python -m research_swarm notify --test
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

**Time**: ~60-90 seconds per stock
**Cost**: ~$0.037 per stock (after Phase 11 optimization)

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
- Total cost (should be ~$0.73 for 20 stocks)
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
- Fundamentalist: ~$0.010 (Haiku extraction + Sonnet analysis)
- News Hound: ~$0.010 (Haiku filtering + Sonnet sentiment)
- Quant: ~$0.005 (Haiku + Sonnet, minimal LLM use)
- Manager: ~$0.012 (Sonnet synthesis + thesis)
- **Total**: ~$0.037 per stock

**Monthly budget**: $200
- Bi-weekly run (20 stocks): ~$0.73
- Monthly cost (2 runs): ~$1.46
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
```

### Task 1.3: Update `README.md`

**File**: `README.md`

Update the root README with a better quick start and links to documentation.

**Add after project description**:

```markdown
## Quick Start

Get started in 5 minutes:

```bash
# Prerequisites: Python 3.10+, pyenv
eval "$(pyenv init -)"

# Install
pip install -r requirements.txt
pip install -e .

# Configure (add API keys)
cp .env.example .env
nano .env

# Run first analysis
python -m research_swarm run AAPL

# View results
python -m research_swarm history
```

**Success**: AAPL analysis completes with moat score.

📚 **[Full User Guide →](docs/user-guide.md)**

---

## System Requirements

- **Python**: 3.10+ (3.11.9 recommended)
- **OS**: macOS or Linux
- **RAM**: 2GB minimum
- **Disk**: 500MB for cache and persistence

⚠️ **Important**: Use `eval "$(pyenv init -)"` to activate Python 3.11.9. Shell may default to Python 3.9 which will cause errors.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│           Research Swarm System             │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────┐    ┌──────────────┐      │
│  │ Fundamentalist│    │  News Hound  │      │
│  │    Agent      │    │    Agent     │      │
│  │  (Financial)  │    │  (Sentiment) │      │
│  └───────┬───────┘    └───────┬──────┘      │
│          │                    │             │
│          └────────┬───────────┘             │
│                   ▼                         │
│           ┌──────────────┐                  │
│           │    Manager   │                  │
│           │    Agent     │                  │
│           │ (Synthesis)  │                  │
│           └───────┬──────┘                  │
│                   │                         │
│          ┌────────┴─────────┐               │
│          ▼                  ▼               │
│  ┌──────────────┐    ┌──────────────┐      │
│  │    Quant     │    │   Reports    │      │
│  │    Agent     │    │  (PDF/MD)    │      │
│  │  (Technical) │    │              │      │
│  └──────────────┘    └──────────────┘      │
│                                             │
└─────────────────────────────────────────────┘
```

**Learn more**: [Architecture Documentation →](docs/architecture.md)

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `run` | Analyze stocks and generate moat scores |
| `report` | Generate PDF/Markdown reports |
| `history` | View past analysis runs |
| `resume` | Resume interrupted runs |
| `estimate` | Estimate API costs |
| `cache` | Manage API cache |
| `cost` | View cost dashboard |
| `schedule` | Set up automation (macOS) |
| `auto` | Run automation manually |
| `notify` | Test email notifications |

**Full CLI guide**: [User Guide →](docs/user-guide.md)

---

## Documentation

- 📖 [User Guide](docs/user-guide.md) - Quick start, CLI commands, workflows
- 🏗️ [Architecture](docs/architecture.md) - System design, agents, data flow
- 🔧 [Maintenance](docs/maintenance.md) - Routine procedures, updates
- 🐛 [Troubleshooting](docs/troubleshooting.md) - Common issues and solutions
- 📚 [API Reference](docs/api-reference.md) - Programmatic usage
- 💡 [Examples](docs/examples.md) - Command examples and walkthroughs
- ❓ [FAQ](docs/faq.md) - Frequently asked questions

---

## Cost Transparency

**Per-stock cost** (after Phase 11 optimization): ~$0.037
- Fundamentalist: $0.010
- News Hound: $0.010
- Quant: $0.005
- Manager: $0.012

**Monthly cost** (2 bi-weekly runs, 20 stocks each): ~$1.46

**Budget**: $200/month (99% under budget ✅)

Monitor costs: `python -m research_swarm cost --dashboard`

---

## Project Status

- ✅ **Phases 1-11 Complete** (264 tests passing)
- ✅ **Cost Optimized** (92% reduction, Haiku 3.5 for scorers)
- ✅ **Fully Automated** (bi-weekly email reports)
- ✅ **Production Ready** ($0.73 per run, 54% test coverage)

**Latest**: Phase 11 - Cost optimization complete (2026-01-18)

---

## Contributing

This is a personal project but documentation improvements are welcome.

---

## License

MIT License - See [LICENSE](LICENSE) for details.
```

### Task 1.4: Create `docs/examples.md`

**File**: `docs/examples.md`

**Target**: 600 words

**Content**:

```markdown
# Research Swarm - Examples

Real-world command examples and expected outputs.

---

## Example 1: Single Stock Analysis

**Scenario**: Quick analysis of Apple (AAPL)

```bash
$ python -m research_swarm run AAPL

[2026-01-18 10:00:00] INFO: Starting analysis for AAPL
[2026-01-18 10:00:15] INFO: Fundamentalist agent complete (health: 8.2)
[2026-01-18 10:00:30] INFO: News Hound agent complete (sentiment: 7.5)
[2026-01-18 10:00:40] INFO: Quant agent complete (technical: 7.8, supply: 7.2)
[2026-01-18 10:00:55] INFO: Manager synthesis complete (moat: 7.8)
[2026-01-18 10:01:00] SUCCESS: Analysis complete for AAPL

Run ID: run_20260118_100000
Moat Score: 7.8 🟡
Watchlist: No (threshold: 8.0)
Cost: $0.037
```

**Interpretation**:
- AAPL has a **moderate moat** (7.8)
- Not quite watchlist-worthy (needs ≥8.0)
- Cost is on target (~$0.037 per stock)

---

## Example 2: Batch Analysis with Watchlist

**Scenario**: Analyze semiconductor stocks

```bash
# Create watchlist
$ cat > semiconductors.txt << EOF
NVDA
AMD
TSM
ASML
LRCX
EOF

# Run analysis
$ python -m research_swarm run --from-file semiconductors.txt

[2026-01-18 10:05:00] INFO: Starting batch run: 5 stocks
[2026-01-18 10:06:30] SUCCESS: NVDA complete (moat: 8.7) 🟢
[2026-01-18 10:08:00] SUCCESS: AMD complete (moat: 7.9) 🟡
[2026-01-18 10:09:30] SUCCESS: TSM complete (moat: 8.5) 🟢
[2026-01-18 10:11:00] SUCCESS: ASML complete (moat: 8.9) 🟢
[2026-01-18 10:12:30] SUCCESS: LRCX complete (moat: 7.6) 🟡

Run ID: run_20260118_100500
Completed: 5/5
Watchlist candidates: 3 (NVDA, TSM, ASML)
Total cost: $0.185
Duration: 7m 30s
```

**Interpretation**:
- 3 watchlist candidates (moat ≥8.0)
- Total cost: $0.185 (on target: 5 × $0.037)
- Duration: ~90 seconds per stock

---

## Example 3: Generate Report

**Scenario**: Create PDF report for latest run

```bash
# Get latest run ID
$ python -m research_swarm history --limit 1
Run ID: run_20260118_100500
Date: 2026-01-18 10:05:00
Stocks: 5 (NVDA, AMD, TSM, ASML, LRCX)
Status: COMPLETED
Watchlist: 3 stocks

# Generate report
$ python -m research_swarm report run_20260118_100500

[2026-01-18 10:15:00] INFO: Generating report for run_20260118_100500
[2026-01-18 10:15:05] INFO: Rendering markdown...
[2026-01-18 10:15:08] INFO: Generating charts...
[2026-01-18 10:15:12] INFO: Creating PDF...
[2026-01-18 10:15:20] SUCCESS: Report generated

Output:
  - data/reports/run_20260118_100500/executive_summary.md
  - data/reports/run_20260118_100500/executive_summary.pdf
  - data/reports/run_20260118_100500/moat_breakdown.png
  - data/reports/run_20260118_100500/supply_chain_NVDA.png

# Open PDF
$ open data/reports/run_20260118_100500/executive_summary.pdf
```

---

## Example 4: Cost Dashboard

**Scenario**: Review monthly costs and budget utilization

```bash
$ python -m research_swarm cost --dashboard

==================================================
       RESEARCH SWARM COST DASHBOARD
==================================================

--- 2026-01 Summary ---
Total Spend:     $1.11
Budget:          $200.00
Remaining:       $198.89
Utilization:     0.6%
Runs:            2
Stocks Analyzed: 30

--- Cost by Agent ---
  fundamentalist  $0.300 (27.0%)
  news_hound     $0.330 (29.7%)
  manager        $0.360 (32.4%)
  quant          $0.120 (10.8%)

--- 3-Month Trend ---
  2025-11: $  0.95 [#                   ] OK
  2025-12: $  1.08 [#                   ] OK
  2026-01: $  1.11 [#                   ] OK
```

**Interpretation**:
- **Under budget**: 0.6% utilization (excellent)
- **Agent costs**: Manager highest (synthesis + thesis), Quant lowest
- **Trend**: Stable, no concerning spikes
- **Projected annual cost**: ~$13 (99.5% under $200/month budget)

---

## Example 5: Cache Management

**Scenario**: Check cache size and clear expired entries

```bash
$ python -m research_swarm cache stats

=== Cache Statistics ===
Database:        /Users/tui/research-swarm/data/cache/api_cache.db
Size:            2.4 MB
Total Entries:   147
Valid Entries:   132
Expired Entries: 15

# Clear expired entries
$ python -m research_swarm cache clear

[2026-01-18 10:20:00] SUCCESS: Cleared 15 expired cache entries
```

**When to use**:
- Monthly maintenance (clear expired entries)
- After major data updates (clear all: `cache clear --all --force`)
- High cache size (>100 MB)

---

## Example 6: Resume Interrupted Run

**Scenario**: Power loss during batch analysis, resume from last completed stock

```bash
# Check resumable runs
$ python -m research_swarm resume --list

Resumable Runs:
  run_20260118_103000 - 3/10 completed (AAPL, NVDA, MSFT done)
  run_20260117_150000 - 18/20 completed (GOOGL, AMZN failed)

# Resume specific run
$ python -m research_swarm resume run_20260118_103000

[2026-01-18 10:35:00] INFO: Resuming run_20260118_103000
[2026-01-18 10:35:00] INFO: Already completed: AAPL, NVDA, MSFT
[2026-01-18 10:35:00] INFO: Resuming from: GOOGL
[2026-01-18 10:36:30] SUCCESS: GOOGL complete (moat: 8.1) 🟢
[2026-01-18 10:38:00] SUCCESS: AMZN complete (moat: 7.9) 🟡
...
[2026-01-18 10:50:00] SUCCESS: Run complete: 10/10 stocks
```

---

## Example 7: Estimate Costs Before Running

**Scenario**: Check if batch analysis fits budget

```bash
$ python -m research_swarm estimate AAPL NVDA MSFT GOOGL AMZN

Cost Estimate:
  Stocks: 5
  Per Stock: $0.037
  Total: $0.185

Budget: $200.00
This run: 0.09% of monthly budget ✅

Proceed? [y/N]: y
```

---

## Example 8: Custom Fiscal Year and News Window

**Scenario**: Analyze TSLA using 2023 10-K and 60 days of news

```bash
$ python -m research_swarm run TSLA --fiscal-year 2023 --news-days 60

[2026-01-18 11:00:00] INFO: Fetching TSLA 10-K for fiscal year 2023...
[2026-01-18 11:00:15] INFO: Fetching news (last 60 days)...
[2026-01-18 11:01:45] SUCCESS: TSLA complete (moat: 7.4)

Run ID: run_20260118_110000
Fiscal Year: 2023
News Window: 60 days
Moat Score: 7.4 🟡
```

**Use case**: Compare year-over-year changes by running same stock with different fiscal years.

---

## Example 9: Automation (Bi-weekly Runs)

**Scenario**: Set up automated bi-weekly analysis (macOS)

```bash
# Install schedule
$ python -m research_swarm schedule install

[2026-01-18 11:10:00] INFO: Creating launchd plist...
[2026-01-18 11:10:01] INFO: Installing to ~/Library/LaunchAgents/
[2026-01-18 11:10:02] SUCCESS: Schedule installed

Schedule: Every other Monday at 6:00 AM
Watchlist: data/watchlist.txt
Logs: ~/Library/Logs/research_swarm/

# Check status
$ python -m research_swarm schedule status

Status: ✅ INSTALLED
Next Run: 2026-01-20 06:00:00
Last Run: 2026-01-13 06:00:00 (SUCCESS)
Watchlist: 20 stocks

# View logs
$ tail -f ~/Library/Logs/research_swarm/stdout.log
```

---

## Example 10: Test Email Notifications

**Scenario**: Verify email configuration before automation

```bash
$ python -m research_swarm notify --test

[2026-01-18 11:15:00] INFO: Sending test email...
[2026-01-18 11:15:03] SUCCESS: Test email sent

To: your-email@gmail.com
Subject: Research Swarm - Test Notification
Status: DELIVERED ✅

Check your inbox!
```

---

## More Examples

See [User Guide](user-guide.md) for more workflows and use cases.
```

---

## Session 12.2: Architecture Documentation

**Duration**: 2-3 hours
**Goal**: Document system architecture and design decisions

### Task 2.1: Write `docs/architecture.md`

**File**: `docs/architecture.md`

**Target**: 2,000+ words

**Structure**: See [full outline in plans/current-phase.md](plans/current-phase.md#session-122-architecture-documentation-2-3-hours)

**Key sections**:
1. System Overview (architecture diagram)
2. Agent Responsibilities (4 agents + manager)
3. Orchestration Layer (batch workflow, persistence, retry logic)
4. Data Pipeline (caching, rate limiting, API clients)
5. Report Generation (templates, charts, PDF)
6. Automation System (scheduler, notifier, cost monitor)
7. Design Decisions (LangGraph vs CrewAI, SQLite vs PostgreSQL, etc.)

**Include ASCII diagrams** for:
- High-level system architecture
- LangGraph state flow (per agent)
- Data flow (APIs → Cache → Agents → Persistence)
- Orchestration sequence

### Task 2.2: Write `docs/api-reference.md`

**File**: `docs/api-reference.md`

**Target**: 800 words

**Content**: Document all public API functions

**Structure**:
```markdown
# Research Swarm - API Reference

## Agents

### Fundamentalist Agent

```python
from research_swarm.agents import analyze_fundamentals

result = analyze_fundamentals(
    ticker: str,
    fiscal_year: int = None
) -> FundamentalistOutput
```

**Parameters**:
- `ticker` (str): Stock ticker symbol
- `fiscal_year` (int, optional): Fiscal year for 10-K filing

**Returns**: `FundamentalistOutput`
- `financial_health_score` (float): 0-10 score
- `metrics` (FinancialMetricsOutput): Revenue, margins, ratios
- `supply_chain` (SupplyChainOutput): Customers, suppliers
- `analysis` (str): Qualitative analysis narrative

### News Hound Agent

```python
from research_swarm.agents import analyze_company_news

result = analyze_company_news(
    ticker: str,
    days_back: int = 30
) -> NewsHoundOutput
```

### Quant Agent

```python
from research_swarm.agents import analyze_quant

result = analyze_quant(
    ticker: str,
    fundamentalist_output: FundamentalistOutput
) -> QuantOutput
```

### Manager Agent

```python
from research_swarm.agents import analyze_swarm

result = analyze_swarm(
    ticker: str,
    fiscal_year: int = None,
    news_days_back: int = 30
) -> ManagerOutput
```

## Orchestration

### Run Batch Analysis

```python
from research_swarm.orchestration import run_batch

result = run_batch(
    tickers: List[str],
    fiscal_year: int = None,
    news_days_back: int = 30,
    max_retries: int = 3,
    run_name: str = None
) -> SwarmRun
```

### Resume Run

```python
from research_swarm.orchestration import resume_run

result = resume_run(
    run_id: str
) -> SwarmRun
```

## Reports

### Generate Report

```python
from research_swarm.reports import generate_report

result = generate_report(
    run_id: str,
    output_dir: str = "data/reports",
    report_type: str = "both",  # "markdown", "pdf", or "both"
    include_charts: bool = True,
    top_picks: int = 3
) -> ReportOutput
```

## Persistence

### Get Run History

```python
from research_swarm.orchestration import PersistenceManager

persistence = PersistenceManager()
runs = persistence.get_all_runs(limit=10)
```

### Get Monthly Costs

```python
costs = persistence.get_monthly_costs(year=2026, month=1)
```

## Automation

### Run Automation

```python
from research_swarm.automation import run_automation, AutomationConfig

config = AutomationConfig(
    run_name="Weekly Analysis",
    max_retries=3,
    generate_report=True,
    send_email=True
)

result = run_automation(
    tickers=["AAPL", "NVDA", "MSFT"],
    config=config
)
```

## Data Clients

### SEC Edgar Client

```python
from research_swarm.data import SECClient

sec = SECClient()
filing_text = sec.get_10k(ticker="AAPL", fiscal_year=2024)
```

### News API Client

```python
from research_swarm.data import NewsClient

news = NewsClient()
articles = news.get_company_news(ticker="AAPL", days_back=30)
```

### Market Data Client

```python
from research_swarm.data import MarketDataClient

market = MarketDataClient()
price_data = market.get_price_history(ticker="AAPL", period="1y")
```

## Cache

### Manage Cache

```python
from research_swarm.data import cache

# Get stats
stats = cache.stats()

# Clear expired
count = cache.clear_expired()

# Get cached value
value = cache.get(key="sec_10k_AAPL_2024")

# Set cached value
cache.set(key="sec_10k_AAPL_2024", value=data, ttl_hours=2160)
```
```

---

## Session 12.3: Maintenance & Troubleshooting

**Duration**: 2-3 hours
**Goal**: Enable long-term maintenance and debugging

### Task 3.1: Write `docs/maintenance.md`

**File**: `docs/maintenance.md`

**Target**: 1,500 words

**Sections**: See [full outline in plans/current-phase.md](plans/current-phase.md#session-123-maintenance--troubleshooting-2-3-hours)

1. Routine Maintenance (quarterly/monthly/bi-weekly tasks)
2. API Key Rotation
3. Cache Management
4. Cost Monitoring
5. Database Cleanup
6. Dependency Updates
7. Adding New Data Sources
8. Modifying Moat Scoring
9. Extending Agents

### Task 3.2: Write `docs/troubleshooting.md`

**File**: `docs/troubleshooting.md`

**Target**: 1,000 words

**Cover 8+ common issues**:
1. Python version error (| union syntax)
2. API rate limit exceeded
3. Cost spike above $50
4. Report generation fails
5. Email notifications not working
6. Schedule not running
7. Supply chain graph incomplete
8. High memory usage

**Format**:
```markdown
## Issue: [Problem Description]

**Symptoms**: What the user sees
**Cause**: Why it happens
**Solution**: Step-by-step fix
**Prevention**: How to avoid in future
```

### Task 3.3: Write `docs/handoff-checklist.md`

**File**: `docs/handoff-checklist.md`

**Target**: 200 words

```markdown
# Research Swarm - Handoff Checklist

Use this checklist when delegating the system to a new developer.

## Pre-Handoff (Current Owner)

- [ ] Ensure all tests passing: `pytest -m "not integration"`
- [ ] Verify schedule is installed: `python -m research_swarm schedule status`
- [ ] Export API keys securely (1Password, encrypted file, etc.)
- [ ] Document any custom modifications
- [ ] Create backup of persistence DB: `cp data/persistence.db data/persistence.backup.db`
- [ ] Generate final cost report: `python -m research_swarm cost --dashboard`

## During Handoff

- [ ] Transfer API keys via secure channel
- [ ] Grant repository access (GitHub, GitLab, etc.)
- [ ] Share `.env` file securely
- [ ] Walk through architecture: [architecture.md](architecture.md)
- [ ] Demonstrate CLI commands
- [ ] Show where logs are stored
- [ ] Review cost monitoring procedures

## Post-Handoff (New Owner)

- [ ] Clone repository
- [ ] Set up Python 3.11.9 with pyenv
- [ ] Install dependencies: `pip install -r requirements.txt && pip install -e .`
- [ ] Configure `.env` with API keys
- [ ] Run first test: `python -m research_swarm run AAPL`
- [ ] Generate report: `python -m research_swarm report <run_id>`
- [ ] Test email: `python -m research_swarm notify --test`
- [ ] Install schedule: `python -m research_swarm schedule install`
- [ ] Verify schedule works: Check logs after next scheduled run
- [ ] Run full test suite: `eval "$(pyenv init -)" && pytest -m "not integration"`
- [ ] Read all documentation in `docs/`

## Validation

- [ ] New owner can run analysis independently
- [ ] New owner understands cost monitoring
- [ ] New owner knows how to troubleshoot common issues
- [ ] New owner has access to all resources

## Timeline

- **Handoff session**: 60-90 minutes
- **New owner independent**: Within 30 minutes after handoff

**Success**: New owner runs first analysis without help.
```

### Task 3.4: Add Python Version Check to CLI

**File**: `research_swarm/__main__.py`

**Add after imports** (around line 20):

```python
# Python version check
import sys

def check_python_version():
    """Ensure Python 3.10+ is being used."""
    if sys.version_info < (3, 10):
        logger.error(
            f"Python 3.10+ required, but using {sys.version_info.major}.{sys.version_info.minor}"
        )
        logger.error("Solution: Use pyenv to switch to Python 3.11.9:")
        logger.error('  eval "$(pyenv init -)"')
        logger.error("  python --version  # Should show 3.11.9")
        sys.exit(1)

# Call at start of main()
def main():
    """Main CLI entry point."""
    check_python_version()

    # ... rest of main() function
```

---

## Session 12.4: Final Polish & Validation

**Duration**: 1-2 hours
**Goal**: Validate completeness and test 30-minute onboarding

### Task 4.1: Write `docs/faq.md`

**File**: `docs/faq.md`

**Target**: 500 words

```markdown
# Research Swarm - Frequently Asked Questions

## General

### When should I run the system?

**Recommended**: Bi-weekly (every other Monday morning).

This gives you:
- Fresh quarterly filings (10-Ks, 10-Qs)
- Recent news (30-day window)
- Updated technical indicators
- Cost efficiency ($0.73 per run)

You can also run:
- **Weekly**: For fast-moving sectors (tech, biotech)
- **Monthly**: For stable watchlists
- **On-demand**: When specific news breaks

### How do I interpret moat scores?

**Moat scores** (0-10) represent competitive advantage:

- **8.0-10.0** 🟢: Strong moat, watchlist candidate
  - Durable competitive advantage
  - Strong financials, positive sentiment
  - Strategic supply chain position

- **6.0-7.9** 🟡: Moderate moat, monitor
  - Some competitive advantages
  - Decent fundamentals, neutral sentiment
  - Worth watching for entry points

- **4.0-5.9** 🟠: Weak moat, caution
  - Limited competitive advantages
  - Mixed signals across agents
  - Higher risk

- **0.0-3.9** 🔴: Very weak moat, avoid
  - No clear competitive advantages
  - Poor fundamentals or negative sentiment
  - High supply chain risk

**Components**:
- Financial Health (30%): Balance sheet, profitability, growth
- Sentiment (20%): News, catalysts, market perception
- Technical (20%): Price trends, momentum, relative strength
- Supply Chain (30%): Position, diversification, dependencies

### What's a good watchlist size?

**Recommended**: 15-25 stocks

- **Too few (<10)**: Not diversified, higher risk
- **Sweet spot (15-25)**: Diverse, manageable cost (~$0.73/run)
- **Too many (>50)**: Expensive, hard to track

**Tip**: Start with 10-15 core stocks, add 5-10 supply chain discoveries.

### How do I add new stocks?

**Method 1**: Manual addition
```bash
echo "TSLA" >> watchlist.txt
python -m research_swarm run TSLA
```

**Method 2**: Supply chain discovery
1. Run analysis on known company (e.g., NVDA)
2. Review supply chain visualization in report
3. Identify interesting tier-1/tier-2 suppliers
4. Add to watchlist: `echo "TSMC" >> watchlist.txt`
5. Analyze: `python -m research_swarm run TSMC`

**Method 3**: Sector research
```bash
# Create sector watchlist
cat > semiconductors.txt << EOF
NVDA
AMD
TSM
ASML
LRCX
EOF

python -m research_swarm run --from-file semiconductors.txt
```

## Technical

### How do I change email settings?

Edit `.env` file:

**For Gmail**:
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Not account password!
NOTIFICATION_EMAIL=your-email@gmail.com
```

**For SendGrid**:
```bash
SENDGRID_API_KEY=SG.xxx...
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
NOTIFICATION_EMAIL=your-email@gmail.com
```

Test: `python -m research_swarm notify --test`

### What if costs spike unexpectedly?

**Diagnosis**:
```bash
python -m research_swarm cost --dashboard
```

**Look for**:
- Total spend > $2.00 for 20 stocks
- Any agent > 40% of total cost
- Month-over-month increase > 50%

**Common causes**:
1. **Scorers using Sonnet** (should be Haiku)
   - Check: `grep "model=" research_swarm/agents/*/scorer.py`
   - Should see: `claude-3-5-haiku-20241022`

2. **Cache miss** (fetching same data multiple times)
   - Check: `python -m research_swarm cache stats`
   - Clear and retry: `cache clear && run ...`

3. **Large batch without caching**
   - Solution: Run smaller batches or space them out

**Prevention**:
- Monitor bi-weekly: `cost --dashboard`
- Use cache: Check `cache stats` monthly
- Set up cost alerts (automatic at $180/month)

### How do I backup my data?

**Backup**:
```bash
# Create backup directory
mkdir -p backups

# Backup persistence DB
cp data/persistence.db backups/persistence-$(date +%Y%m%d).db

# Backup cache
cp data/cache/api_cache.db backups/cache-$(date +%Y%m%d).db

# Backup reports (optional)
tar -czf backups/reports-$(date +%Y%m%d).tar.gz data/reports/
```

**Restore**:
```bash
# Restore persistence
cp backups/persistence-20260118.db data/persistence.db

# Restore cache
cp backups/cache-20260118.db data/cache/api_cache.db
```

**Automated backup** (add to crontab):
```bash
# Backup every Sunday at 2 AM
0 2 * * 0 cd /path/to/research-swarm && ./scripts/backup.sh
```

### Why does my shell show Python 3.9 even after installing 3.11?

**Cause**: Shell defaults to Anaconda Python 3.9.

**Solution**: Use pyenv to activate Python 3.11.9:
```bash
eval "$(pyenv init -)"
python --version  # Should now show 3.11.9
```

**Permanent fix**: Add to `~/.bashrc` or `~/.zshrc`:
```bash
# Add at end of file
eval "$(pyenv init -)"
```

Then restart shell or run: `source ~/.bashrc`

## Advanced

### Can I run this in production for real trading?

**No.** Research Swarm is designed for:
- **Research and analysis** (bi-weekly thesis reports)
- **Idea generation** (finding hidden supply chain opportunities)
- **Educational purposes** (understanding multi-agent systems)

It is **NOT**:
- A real-time trading system
- Investment advice (always do your own due diligence)
- A replacement for professional financial advisors

**Use responsibly**: Moat scores are starting points for research, not buy/sell signals.

### Can I add new agents?

Yes! See [maintenance.md](maintenance.md#section-5-extending-agents) for detailed instructions.

**High-level process**:
1. Create `research_swarm/agents/new_agent/` directory
2. Implement 6 core modules (state, models, prompts, analyzer, scorer, graph)
3. Export from `agents/__init__.py`
4. Update manager orchestration to call new agent
5. Adjust moat scoring formula to include new agent's output
6. Write comprehensive tests

**Time estimate**: 4-6 hours for a new agent

### Can I use a different LLM provider?

Currently, Research Swarm uses **Anthropic Claude** (Haiku 3.5 and Sonnet 3.5).

**To switch**:
1. Replace `ChatAnthropic` with new provider in all agent files
2. Update pricing in `orchestration/cost_tracker.py`
3. Test thoroughly (prompts may need adjustment)

**Recommended alternatives**:
- OpenAI GPT-4 (similar quality, higher cost)
- OpenAI GPT-3.5-turbo (lower cost, reduced quality)
- Local models (Llama 3, Mixtral) - untested

**Note**: Prompts are optimized for Claude's style. You may need to adjust.

---

**More questions?** See [User Guide](user-guide.md) or [Troubleshooting](troubleshooting.md).
```

### Task 4.2: Create `CHANGELOG.md`

**File**: `CHANGELOG.md` (root directory)

**Target**: 400 words

```markdown
# Changelog

All notable changes to Research Swarm will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Phase 11] - 2026-01-18

### Added - Cost Optimization & Dashboard
- **Cache CLI commands**: `cache stats`, `cache clear`, `cache clear --all`
- **Cost dashboard**: `cost --dashboard` shows monthly summary, per-agent breakdown, 3-month trend
- **Per-agent cost tracking**: Cost breakdown by agent (fundamentalist, news_hound, quant, manager)
- **Automatic cache cleanup**: Clears expired entries on startup

### Changed
- **Switched scorers to Haiku 3.5**: 92% cost reduction ($0.24 → $0.032 per run)
- **Updated analyzers to Sonnet 3.5**: Latest model versions
- **Cost per bi-weekly run**: $9.14 → $0.73 (92% reduction)

### Tests
- 31 new tests added (12 cache + 12 model + 7 dashboard)
- 264 total tests passing (233 unit + 31 optimization)

---

## [Phase 10] - 2026-01-18

### Added - Testing & Validation
- 71 new tests across 5 test files
- Registered pytest markers (integration, slow)
- Comprehensive test coverage for all agents

### Fixed
- Test assertion bugs (incorrect expected values)
- Pydantic schema mismatches in test fixtures
- Added missing `@pytest.mark.integration` markers

### Tests
- 233 unit tests passing (1 skipped)
- 54% code coverage achieved

---

## [Phase 9] - 2026-01-17

### Added - Scheduling & Automation
- **Automation module**: Bi-weekly scheduling with launchd (macOS)
- **Email notifications**: SMTP and SendGrid support
- **Cost monitoring**: Budget alerts at $180 threshold
- **Priority alerts**: High moat stocks (≥9) trigger email notifications
- **CLI commands**: `schedule install/status/uninstall`, `auto`, `notify --test`

### Tests
- 24 tests added (100% passing)

---

## [Phase 8] - 2026-01-17

### Added - Report Generation
- **PDF reports**: Professional reports with WeasyPrint
- **Markdown reports**: Jinja2 templates (5 modular sections)
- **Charts**: Moat breakdown, supply chain graphs (matplotlib + NetworkX)
- **CLI command**: `report <run_id>`

### Tests
- 43 tests added (100% passing)

---

## [Phase 7] - 2026-01-17

### Added - Orchestration & Workflow
- **Batch orchestration**: Run multiple stocks in sequence
- **SQLite persistence**: 3 tables (swarm_runs, stock_results, cost_log)
- **Resume capability**: Continue from any failed stock
- **Retry logic**: Exponential backoff (3 attempts per stock)
- **Cost tracking**: Per-stock and per-agent granularity
- **CLI commands**: `run`, `resume`, `history`, `estimate`

### Changed
- **Python version**: Upgraded from 3.9.13 to 3.11.9 (yfinance compatibility)

### Tests
- 25 tests added (20 unit + 5 integration, 100% passing)

---

## [Phase 6] - 2026-01-17

### Added - Manager Agent
- **Manager Agent**: Orchestrates all 3 specialist agents
- **Moat scoring**: Weighted formula (30/20/20/30)
- **Thesis generation**: Investment recommendations (buy/hold/avoid)
- **Watchlist**: Automatic identification of moat ≥8 stocks

### Tests
- Unit tests for manager agent

---

## [Phase 5] - 2026-01-17

### Added - Quant Agent
- **Quant Agent**: Technical analysis + supply chain mapping
- **Technical indicators**: SMA 50/200, RSI, volume, relative strength
- **Supply chain graphs**: Multi-tier NetworkX graphs
- **Hidden dependencies**: Identifies shared tier-2 suppliers

### Tests
- 13 tests added (10 unit + 3 integration)

---

## [Phase 4] - 2026-01-17

### Added - News Hound Agent
- **News Hound Agent**: Sentiment analysis + catalyst detection
- **NewsAPI integration**: 7-day caching, 100 requests/day limit
- **9 catalyst categories**: M&A, regulatory, partnerships, etc.
- **4-dimension sentiment**: Tone, catalyst, market perception, forward-looking

### Tests
- 11 tests added (7 unit + 4 integration)

---

## [Phase 3] - 2026-01-17

### Added - Fundamentalist Agent
- **Fundamentalist Agent**: Financial statement analysis
- **SEC Edgar integration**: Fetches 10-K filings (90-day cache)
- **5-dimension scoring**: Profitability, growth, balance sheet, cash flow, supply chain
- **LangGraph workflow**: 6-node sequential pipeline

### Tests
- 5 unit tests added

---

## [Phase 2] - 2026-01-17

### Added - Data Pipeline
- **SQLite caching**: TTL-based cache (10-Ks: 90 days, news: 7 days)
- **SEC Edgar client**: Free CIK lookup + 10-K retrieval
- **Financial Modeling Prep client**: Free tier (250 calls/day)
- **Rate limiter**: Token bucket algorithm
- **Market data client**: Yahoo Finance via yfinance

### Tests
- 4 integration tests added

---

## [Phase 1] - 2026-01-17

### Added - Foundation
- **Project scaffolding**: Python 3.9+ with venv
- **LangGraph integration**: Agent framework
- **Configuration management**: .env system
- **Logging**: Loguru (console + file)
- **CLI entry point**: `python -m research_swarm`

### Tests
- Basic validation tests

---

## Upcoming

### [Phase 12] - Documentation & Maintenance
- Comprehensive user guide
- Architecture documentation
- Maintenance procedures
- Troubleshooting guide
- API reference
- FAQ and handoff checklist
```

### Task 4.3: Add `docs/README.md`

**File**: `docs/README.md`

```markdown
# Research Swarm - Documentation

Welcome to the Research Swarm documentation!

---

## Getting Started

- 📖 **[User Guide](user-guide.md)** - Start here! Quick start, CLI commands, workflows
- 💡 **[Examples](examples.md)** - Real command examples with expected outputs

---

## Understanding the System

- 🏗️ **[Architecture](architecture.md)** - System design, agents, data flow
- 📚 **[API Reference](api-reference.md)** - Programmatic usage

---

## Running & Maintaining

- 🔧 **[Maintenance](maintenance.md)** - Routine procedures, updates, extensions
- 🐛 **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
- ❓ **[FAQ](faq.md)** - Frequently asked questions

---

## For New Developers

- 📋 **[Handoff Checklist](handoff-checklist.md)** - Onboarding guide for new team members

---

## Quick Links

**Installation**: See [User Guide - Quick Start](user-guide.md#quick-start)

**Common Commands**:
```bash
# Run analysis
python -m research_swarm run AAPL

# Generate report
python -m research_swarm report <run_id>

# Cost dashboard
python -m research_swarm cost --dashboard

# Help
python -m research_swarm --help
```

**Python Version**: 3.10+ required (3.11.9 recommended)

```bash
eval "$(pyenv init -)"
python --version  # Should show 3.11.9
```

---

## Project Status

- ✅ Phases 1-11 Complete (264 tests passing)
- ✅ Cost Optimized (92% reduction, $0.73/run)
- ✅ Fully Automated (bi-weekly reports)
- ✅ Production Ready

**Latest**: Phase 11 - Cost optimization (2026-01-18)

---

## Need Help?

1. Check [FAQ](faq.md) for common questions
2. See [Troubleshooting](troubleshooting.md) for error solutions
3. Review [User Guide](user-guide.md) for detailed instructions

---

**Project Repository**: [GitHub](https://github.com/your-repo/research-swarm)
**License**: MIT
```

### Task 4.4: Validate 30-Minute Onboarding

**Test the quick start**:

1. Fresh terminal session (no pyenv activated)
2. Follow `docs/user-guide.md` Quick Start section
3. Time yourself
4. Note any friction points
5. Update documentation to address issues

**Success**: Complete first analysis in <30 minutes without external help.

### Task 4.5: Update `plans/master-plan.md`

**File**: `plans/master-plan.md`

Mark Phase 12 as complete and add statistics:

```markdown
### **Phase 12: Documentation & Maintenance** ✅ COMPLETE
**Duration**: 3-4 sessions (completed 2026-01-18)
**Goal**: Ensure long-term sustainability

- User guide (1,500+ words)
- Architecture documentation (2,000+ words)
- Maintenance procedures (1,500+ words)
- Troubleshooting guide (1,000+ words)
- API reference (800 words)
- Examples (600 words)
- FAQ (500 words)
- Handoff checklist (200 words)
- CHANGELOG.md
- Python version check added to CLI

**Success Criteria**: ✅ New user can run system in <30 minutes

**Files Created**: 9 documentation files (~8,500 words total)
**Files Modified**: 2 (README.md, __main__.py)

---

## Project Complete! 🎉

All 12 phases complete (2026-01-18):
- **Tests**: 264 passing (54% coverage)
- **Cost**: $0.73 per bi-weekly run (99% under $200 budget)
- **Documentation**: 8,500+ words
- **Lines of code**: ~15,000
- **Development time**: ~3 weeks (part-time)
```

---

## Success Criteria

### Must Have
- [ ] New user can run first analysis in <30 minutes (validated)
- [ ] All CLI commands documented with examples
- [ ] Architecture diagrams for all 4 agents + orchestration
- [ ] Troubleshooting covers 8+ common issues
- [ ] Maintenance procedures for API keys, cache, costs
- [ ] Handoff checklist validated
- [ ] Python version check added to CLI
- [ ] 8,500+ words of documentation created

### Nice to Have
- [ ] Mermaid diagrams for workflows
- [ ] Screenshots in user guide (optional)

---

## Files to Create

| File | Size (est.) | Description |
|------|-------------|-------------|
| docs/user-guide.md | 1,500 words | Quick start, CLI, customization |
| docs/architecture.md | 2,000 words | System design, agents, workflows |
| docs/maintenance.md | 1,500 words | Routine procedures, updates |
| docs/troubleshooting.md | 1,000 words | Common issues + solutions |
| docs/api-reference.md | 800 words | Public API functions |
| docs/examples.md | 600 words | Command examples |
| docs/faq.md | 500 words | Frequently asked questions |
| docs/handoff-checklist.md | 200 words | Onboarding checklist |
| docs/README.md | 300 words | Documentation overview |
| CHANGELOG.md | 400 words | Version history |
| **TOTAL** | **~8,800 words** | Complete documentation |

## Files to Modify

| File | Change | Lines (est.) |
|------|--------|--------------|
| README.md | Better quick start, links to docs/ | +100 |
| research_swarm/__main__.py | Add Python version check | +15 |

---

## Verification Commands

```bash
# Check Python version
eval "$(pyenv init -)" && python --version

# Verify CLI help works
python -m research_swarm --help
python -m research_swarm run --help
python -m research_swarm report --help
python -m research_swarm schedule --help
python -m research_swarm cache --help
python -m research_swarm cost --help

# Validate 30-minute onboarding
time ./docs/quick-start.sh  # Should be <30 min

# Check documentation links (no broken links)
cd docs && grep -r "](/" *.md | grep -v "http"
```

---

## Cost Target

| Component | Cost |
|-----------|------|
| API calls | $0.00 (no LLM calls) |
| Development time | 8-10 hours |

**Phase 12 has zero API costs - pure documentation work.**

---

## Phase 12 Timeline

| Session | Duration | Deliverable |
|---------|----------|-------------|
| 12.1 | 2-3 hours | User guide + quick start + examples |
| 12.2 | 2-3 hours | Architecture + API reference |
| 12.3 | 2-3 hours | Maintenance + troubleshooting + handoff |
| 12.4 | 1-2 hours | FAQ + CHANGELOG + validation |
| **Total** | **7-11 hours** | **8,800 words of docs** |

---

## Handoff Complete

Phase 12 is ready for implementation. All documentation templates and outlines are provided above.

**Next steps**:
1. Create `docs/` directory
2. Write documentation files following templates above
3. Update README.md and __main__.py
4. Validate 30-minute onboarding
5. Mark Phase 12 complete in master-plan.md

**Success**: Research Swarm system fully documented and maintainable! 🎉

---

**Created**: 2026-01-18
**Phase**: 12 - Documentation & Maintenance
**Developer**: CTO Architect Agent
**Status**: Ready for Implementation 🚀
