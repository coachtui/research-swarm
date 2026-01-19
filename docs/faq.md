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
- **Sweet spot (15-25)**: Diverse, manageable cost (approximately $0.73/run)
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

---

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

---

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

### How can I modify the moat scoring weights?

**File**: `research_swarm/agents/manager/scorer.py`

**Current formula**:
```python
moat_score = (0.30 × financial_health) +
             (0.20 × sentiment) +
             (0.20 × technical) +
             (0.30 × supply_chain)
```

**Change weights**:
```python
weights = {
    "financial_health": 0.25,  # Modify here
    "sentiment": 0.15,
    "technical": 0.15,
    "supply_chain": 0.45,  # Increased importance
}
```

**Important**: Weights must sum to 1.0.

**Update tests**:
```python
# tests/test_manager.py
def test_moat_scoring_new_weights():
    score = calculate_moat_score(
        financial_health=8.0,
        sentiment=7.0,
        technical=6.0,
        supply_chain=9.0
    )
    expected = 0.25*8.0 + 0.15*7.0 + 0.15*6.0 + 0.45*9.0
    assert abs(score - expected) < 0.01
```

See [maintenance.md](maintenance.md#modifying-moat-scoring) for full guide.

### What APIs does the system use?

**Free APIs**:
- **SEC Edgar**: 10-K filings (no key needed)
- **Yahoo Finance**: Price data via yfinance (no key needed)

**Free Tier APIs** (require key but $0 cost):
- **NewsAPI**: 100 requests/day
- **Financial Modeling Prep**: 250 requests/day

**Paid API**:
- **Anthropic Claude**: Pay-as-you-go (approximately $1.50/month for bi-weekly runs)

**Total cost**: Approximately $1.50/month (99% under $200 budget)

### Can I schedule runs at different intervals?

Yes! Edit the schedule configuration:

```bash
# Weekly runs
python -m research_swarm schedule install --frequency weekly --day 0 --hour 6

# Monthly runs
python -m research_swarm schedule install --frequency monthly --day 1 --hour 6

# Bi-weekly (default)
python -m research_swarm schedule install --frequency bi_weekly --day 0 --hour 6
```

**Custom schedules**: Edit launchd plist directly:
```bash
nano ~/Library/LaunchAgents/com.research_swarm.bi_weekly.plist
```

### How do I export data for external analysis?

**Export run history**:
```bash
python -m research_swarm history --export history.md
```

**Query database directly**:
```bash
sqlite3 data/persistence.db

# Get all moat scores
SELECT ticker, moat_score, thesis
FROM stock_results
ORDER BY moat_score DESC;

# Export to CSV
.mode csv
.output moat_scores.csv
SELECT ticker, moat_score, financial_health, sentiment, technical, supply_chain
FROM stock_results
WHERE moat_score >= 8.0;
.quit
```

**Programmatic access**:
```python
from research_swarm.orchestration import PersistenceManager

pm = PersistenceManager()
runs = pm.get_all_runs(limit=10)

for run in runs:
    for ticker, result in run.stock_results.items():
        print(f"{ticker}: {result.moat_score}")
```

See [api-reference.md](api-reference.md) for full API.

---

**More questions?** See [User Guide](user-guide.md) or [Troubleshooting](troubleshooting.md).
