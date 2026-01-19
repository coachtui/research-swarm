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
- Cost is on target (approximately $0.037 per stock)

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
- Duration: approximately 90 seconds per stock

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
- **Projected annual cost**: approximately $13 (99.5% under $200/month budget)

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
