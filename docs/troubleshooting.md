# Research Swarm - Troubleshooting Guide

Solutions for common issues and error messages.

---

## Table of Contents
1. [Python Version Errors](#issue-1-python-version-errors)
2. [API Rate Limit Exceeded](#issue-2-api-rate-limit-exceeded)
3. [Cost Spike Above Expected](#issue-3-cost-spike-above-expected)
4. [Report Generation Fails](#issue-4-report-generation-fails)
5. [Email Notifications Not Working](#issue-5-email-notifications-not-working)
6. [Schedule Not Running](#issue-6-schedule-not-running)
7. [Supply Chain Graph Incomplete](#issue-7-supply-chain-graph-incomplete)
8. [High Memory Usage](#issue-8-high-memory-usage)
9. [Cache Database Locked](#issue-9-cache-database-locked)
10. [Debugging Tips](#debugging-tips)

---

## Issue 1: Python Version Errors

### Symptoms

```
TypeError: unsupported operand type(s) for |: 'type' and 'type'
```

or

```
SyntaxError: invalid syntax (using | for type unions)
```

### Cause

Python version < 3.10 doesn't support `|` union syntax for type hints.

The shell may default to Anaconda Python 3.9.13 even after installing Python 3.11.9.

### Solution

**Activate pyenv Python 3.11.9**:

```bash
# Verify current version
python --version
# If showing 3.9.x, activate pyenv

# Activate pyenv
eval "$(pyenv init -)"

# Verify again
python --version
# Should show: Python 3.11.9
```

**Make it permanent**:

Add to `~/.bashrc` or `~/.zshrc`:
```bash
# Add at the end of the file
eval "$(pyenv init -)"
```

Then restart your shell:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

### Prevention

- Always run `eval "$(pyenv init -)"` before using Research Swarm
- Add pyenv init to shell startup file
- Check Python version: `python --version` (should be 3.11.9)

---

## Issue 2: API Rate Limit Exceeded

### Symptoms

```
HTTP 429: Too Many Requests
APIError: Rate limit exceeded
Analysis failed for AAPL: Rate limit error
```

### Cause

Too many requests to an API in a short time:
- NewsAPI: 100 requests/day limit (free tier)
- SEC Edgar: 10 requests/second guideline
- FMP: 250 requests/day limit (free tier)

Cache miss can cause redundant API calls.

### Solution

**1. Wait for rate limit reset**:
- NewsAPI: Resets at midnight UTC
- FMP: Resets after 24 hours
- SEC Edgar: Usually brief, wait 1-2 minutes

**2. Check cache hit rate**:
```bash
python -m research_swarm cache stats

# If hit rate is low, cache may need refresh
python -m research_swarm cache clear
```

**3. Reduce batch size**:
```bash
# Instead of 50 stocks at once
python -m research_swarm run --from-file watchlist.txt

# Split into smaller batches
head -10 watchlist.txt | python -m research_swarm run --from-file /dev/stdin
```

**4. Stagger runs**:
```bash
# Don't run multiple analyses in same hour
# Space them out across days
```

### Prevention

- Use cache aggressively (default TTLs are optimized)
- Avoid running same stock multiple times per day
- Monitor cache stats monthly: `cache stats`
- Stay within free tier limits:
  - NewsAPI: Max 100 stocks per day
  - FMP: Max 250 stocks per day

---

## Issue 3: Cost Spike Above Expected

### Symptoms

```
Monthly cost: $15 (expected: $1.50)
Cost per stock: $0.25 (expected: $0.037)
```

### Diagnosis

**Check cost dashboard**:
```bash
python -m research_swarm cost --dashboard
```

Look for:
- Total spend > $5/month
- Any agent > 40% of total cost
- Unusual month-over-month increase

### Common Causes & Solutions

**Cause 1: Scorers using Sonnet instead of Haiku**

**Check**:
```bash
grep "claude-3-5-haiku" research_swarm/agents/*/scorer.py
```

Should see haiku in all scorer files. If you see "sonnet", that's the problem.

**Fix**:
```python
# research_swarm/agents/*/scorer.py
# Change from:
llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")

# To:
llm = ChatAnthropic(model="claude-3-5-haiku-20241022")
```

**Cause 2: Cache miss causing redundant API calls**

**Check**:
```bash
python -m research_swarm cache stats
```

Low hit rate indicates cache problems.

**Fix**:
```bash
# Clear and rebuild cache
python -m research_swarm cache clear --all --force

# Run analysis again (will rebuild cache)
python -m research_swarm run AAPL
```

**Cause 3: Large batch without caching**

Running 100+ stocks without warm cache.

**Fix**:
- Run in smaller batches (10-20 stocks)
- Let cache build up over time
- Avoid clearing cache before large runs

### Prevention

- Review dashboard bi-weekly: `cost --dashboard`
- Verify Haiku usage after code changes: `grep haiku */scorer.py`
- Monitor cache hit rate: `cache stats`
- Set up budget alerts (automatic at $180/month)

---

## Issue 4: Report Generation Fails

### Symptoms

```
WeasyPrint error: Failed to load PDF
FileNotFoundError: No such file or directory
OSError: cannot load library 'gobject-2.0'
```

### Common Causes & Solutions

**Cause 1: WeasyPrint not installed**

**Check**:
```bash
python -c "import weasyprint"
```

**Fix**:
```bash
pip install weasyprint
```

**Cause 2: Missing system dependencies (macOS)**

**Fix**:
```bash
brew install pango gdk-pixbuf libffi
```

**Cause 3: Missing fonts**

WeasyPrint requires system fonts for PDF generation.

**Fix (macOS)**:
```bash
# Install fonts via Homebrew
brew install --cask font-arial
brew install --cask font-helvetica
```

**Cause 4: Bad data in run**

Run completed with errors, report generation fails.

**Check**:
```bash
python -m research_swarm history --limit 1
```

Look for run status: Should be "COMPLETED", not "FAILED" or "PARTIAL".

**Fix**:
```bash
# Resume incomplete run
python -m research_swarm resume <run_id>

# Then generate report
python -m research_swarm report <run_id>
```

### Prevention

- Verify WeasyPrint installation after setup: `python -c "import weasyprint"`
- Install system dependencies during initial setup
- Check run status before generating reports: `history`

---

## Issue 5: Email Notifications Not Working

### Symptoms

No emails received after automated runs or test notifications.

### Diagnosis

**Test email configuration**:
```bash
python -m research_swarm notify --test
```

Check for errors in output.

### Common Causes & Solutions

**Cause 1: Incorrect SMTP credentials**

**Gmail users**: Must use App Password, not account password.

**Fix**:
1. Go to Google Account → Security
2. Enable 2-Step Verification
3. Generate App Password
4. Update `.env`:
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # 16-character app password
NOTIFICATION_EMAIL=your-email@gmail.com
```

**Cause 2: Gmail "Less secure apps" disabled**

Gmail deprecated less secure app access. Must use App Passwords.

**Fix**: Follow Cause 1 solution (App Passwords).

**Cause 3: SendGrid API key expired or invalid**

**Check**:
```bash
# Test SendGrid key
curl -X POST https://api.sendgrid.com/v3/mail/send \
  -H "Authorization: Bearer $SENDGRID_API_KEY" \
  -H "Content-Type: application/json"
```

**Fix**:
1. Log into SendGrid dashboard
2. Generate new API key
3. Update `.env`:
```bash
SENDGRID_API_KEY=SG.new_key_here
```

**Cause 4: Firewall blocking SMTP**

**Check**:
```bash
# Test SMTP connection
telnet smtp.gmail.com 587
```

Should connect. If connection fails, firewall may be blocking.

**Fix**:
- Check firewall settings
- Try alternative port (465 for SSL)
- Contact network administrator

### Prevention

- Test email after initial setup: `notify --test`
- Use App Passwords for Gmail (more reliable)
- Keep API keys in password manager
- Test email configuration after any changes

---

## Issue 6: Schedule Not Running

### Symptoms

No automated runs happening, even though schedule is installed.

### Diagnosis

**Check launchd status** (macOS):
```bash
launchctl list | grep research_swarm
```

Should show process. If not listed, schedule not installed.

**Check logs**:
```bash
tail -50 ~/Library/Logs/research_swarm/stdout.log
tail -50 ~/Library/Logs/research_swarm/stderr.log
```

Look for errors.

### Common Causes & Solutions

**Cause 1: Schedule not installed**

**Fix**:
```bash
python -m research_swarm schedule install
```

Verify:
```bash
python -m research_swarm schedule status
```

**Cause 2: Python environment not accessible to launchd**

launchd runs in different environment than terminal.

**Fix**:

Edit plist file to use full path:
```bash
nano ~/Library/LaunchAgents/com.research_swarm.bi_weekly.plist
```

Update `<key>ProgramArguments</key>` section:
```xml
<key>ProgramArguments</key>
<array>
    <string>/Users/YOUR_USER/.pyenv/versions/3.11.9/bin/python</string>
    <string>-m</string>
    <string>research_swarm</string>
    <string>auto</string>
</array>
```

Reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.research_swarm.bi_weekly.plist
launchctl load ~/Library/LaunchAgents/com.research_swarm.bi_weekly.plist
```

**Cause 3: Permissions on script**

launchd can't execute script due to permissions.

**Fix**:
```bash
chmod +x /path/to/research-swarm/run_automation.sh
```

**Cause 4: .env file not readable by launchd**

Environment variables not loaded.

**Fix**:

Use absolute path in .env:
```bash
# In automation script
source /Users/YOUR_USER/research-swarm/.env
```

Or embed keys in plist (less secure):
```xml
<key>EnvironmentVariables</key>
<dict>
    <key>ANTHROPIC_API_KEY</key>
    <string>sk-ant-...</string>
</dict>
```

### Prevention

- Verify schedule status after installation: `schedule status`
- Check logs regularly: `tail -f ~/Library/Logs/research_swarm/stdout.log`
- Test manual automation run: `python -m research_swarm auto --dry-run`

---

## Issue 7: Supply Chain Graph Incomplete

### Symptoms

Supply chain visualizations missing tier-2 relationships.

Only showing direct suppliers (tier-1), not suppliers to suppliers (tier-2).

### Cause

Hardcoded tier-2 mappings in `quant/supply_chain.py`.

Relationships need to be manually added for new stocks.

### Solution

**Add tier-2 mappings**:

```python
# research_swarm/agents/quant/supply_chain.py

TIER_2_MAPPINGS = {
    # Existing mappings...

    # Add new mappings
    "TSMC": {
        "suppliers": ["ASML", "Applied Materials", "Lam Research"],
        "type": "semiconductor_fab"
    },
    "ASML": {
        "suppliers": ["Carl Zeiss", "Cymer"],
        "type": "lithography"
    },
}
```

**Research tier-2 relationships**:
1. Review supplier 10-Ks for their suppliers
2. Industry reports (e.g., semiconductor supply chain)
3. Company investor presentations

### Prevention

- Regularly update tier-2 mappings when analyzing new sectors
- Contribute to TIER_2_MAPPINGS dictionary
- Document sources for tier-2 relationships

---

## Issue 8: High Memory Usage

### Symptoms

```
System slowdown during batch runs
MemoryError: Unable to allocate memory
Python process using >4GB RAM
```

### Cause

- Large cache in memory
- Many stocks in memory simultaneously
- Memory leak (rare)

### Solution

**1. Clear cache**:
```bash
python -m research_swarm cache clear --all --force
```

**2. Reduce batch size**:
```bash
# Instead of 100 stocks
python -m research_swarm run --from-file large_watchlist.txt

# Run in batches of 20
head -20 large_watchlist.txt > batch1.txt
python -m research_swarm run --from-file batch1.txt
```

**3. Run stocks sequentially** (already default):

Current design already processes stocks one at a time, not in parallel.

**4. Restart Python process** (if memory leak suspected):

Between large batches, restart:
```bash
# Run first batch
python -m research_swarm run --from-file batch1.txt

# Exit Python, restart
python -m research_swarm run --from-file batch2.txt
```

### Prevention

- Monitor cache size: `cache stats` (keep <100MB)
- Clear cache monthly
- Run large batches in smaller chunks (20 stocks per run)
- Avoid running multiple instances simultaneously

---

## Issue 9: Cache Database Locked

### Symptoms

```
sqlite3.OperationalError: database is locked
Unable to write to cache
Cache operation timed out
```

### Cause

Multiple processes accessing cache simultaneously.

SQLite doesn't handle concurrent writes well.

### Solution

**1. Wait and retry**:

Error usually resolves after a few seconds.

**2. Check for zombie processes**:
```bash
ps aux | grep research_swarm
```

Kill any stuck processes:
```bash
kill <PID>
```

**3. Close database connections**:
```bash
# If using SQLite browser or other tools
# Close all connections to cache database
```

**4. Last resort - rebuild cache**:
```bash
# Backup cache
cp data/cache/api_cache.db data/cache/api_cache.backup.db

# Delete and recreate
rm data/cache/api_cache.db
python -m research_swarm run AAPL  # Will recreate cache
```

### Prevention

- Don't run multiple Research Swarm instances simultaneously
- Close SQLite browsers/tools before running analysis
- Use automation scheduler (ensures single instance)

---

## Debugging Tips

### Enable Debug Logging

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Run command
python -m research_swarm run AAPL

# Check logs
tail -f research_swarm.log
```

### Inspect Persistence Database

```bash
sqlite3 data/persistence.db

# View recent runs
SELECT run_id, status, completed_count, total_count
FROM swarm_runs
ORDER BY created_at DESC
LIMIT 5;

# View stock results
SELECT ticker, moat_score, thesis
FROM stock_results
WHERE run_id = 'run_20260118_103000';

# Exit
.exit
```

### Inspect Cache

```bash
sqlite3 data/cache/api_cache.db

# View cache keys
SELECT key, expires_at
FROM cache
ORDER BY expires_at DESC
LIMIT 10;

# Check expired entries
SELECT COUNT(*) as expired_count
FROM cache
WHERE expires_at < datetime('now');

# Exit
.exit
```

### Test Agents Individually

```python
# Test fundamentalist agent
from research_swarm.agents import analyze_fundamentals

result = analyze_fundamentals("AAPL")
print(f"Financial Health: {result.financial_health_score}")
```

### Verify API Keys

```bash
# Check .env file
cat .env | grep API_KEY

# Test Anthropic key
python -c "from langchain_anthropic import ChatAnthropic; llm = ChatAnthropic(); print(llm.invoke('Hello').content)"

# Test NewsAPI key
curl "https://newsapi.org/v2/everything?q=apple&apiKey=$NEWS_API_KEY"
```

### Profile Performance

```bash
# Time a command
time python -m research_swarm run AAPL

# Profile with cProfile
python -m cProfile -o profile.stats -m research_swarm run AAPL

# View profile
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative'); p.print_stats(20)"
```

---

## Getting Help

If issues persist:

1. **Check logs**: `tail -100 research_swarm.log`
2. **Review recent changes**: `git diff`
3. **Test environment**: `pytest -m "not integration"`
4. **Check Python version**: `python --version` (should be 3.11.9)
5. **Verify dependencies**: `pip list`

**Common log locations**:
- Application log: `./research_swarm.log`
- Automation logs: `~/Library/Logs/research_swarm/`
- System logs (macOS): `~/Library/Logs/`

---

**See Also**:
- [User Guide](user-guide.md) - CLI usage
- [Maintenance](maintenance.md) - Routine procedures
- [FAQ](faq.md) - Frequently asked questions
