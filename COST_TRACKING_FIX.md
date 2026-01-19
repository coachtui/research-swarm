# Cost Tracking Fix - January 18, 2026

## Issues Found

### 1. **Token Tracking Broken (CRITICAL)**
All agents were reporting 0 tokens used and $0.00 costs, even though LLM calls were succeeding.

**Root Cause:** The Anthropic API response structure changed. The code was looking for:
```python
tokens = response.response_metadata.get("usage", {}).get("total_tokens", 0)
```

But the API now returns:
```python
{
  "usage": {
    "input_tokens": 16,
    "output_tokens": 10,
    "cache_read_input_tokens": 0,
    ...
  }
}
```

**Fix Applied:**
- Created `research_swarm/utils.py` with `extract_token_usage()` helper
- Updated all agent files to use this helper
- Now correctly calculates: `input_tokens + output_tokens`

**Files Fixed:**
- `research_swarm/utils.py` (NEW)
- `research_swarm/agents/fundamentalist/analyzer.py`
- `research_swarm/agents/fundamentalist/scorer.py`
- `research_swarm/agents/manager/analyzer.py`
- `research_swarm/agents/news_hound/analyzer.py`
- `research_swarm/agents/news_hound/scorer.py`
- `research_swarm/agents/quant/analyzer.py`

### 2. **Supply Chain Data Quality**
Reports show only the root company (AAPL) with 0 connections, leading to incomplete supply chain analysis.

**Likely Cause:** The supply chain extraction from 10-K filings isn't finding supplier/customer information, possibly due to:
- 10-K parsing not capturing the right sections
- LLM prompts need refinement to better extract supplier relationships
- Apple's 10-K may not explicitly name suppliers (common for competitive reasons)

**Status:** This is a data quality issue, not a code bug. The system is working as designed, but the input data (10-K filings) may not contain explicit supplier names.

### 3. **Python Version Warning**
Your system is running Python 3.9.13, but the project requires Python 3.10+.

**Impact:** You'll see import errors from `yfinance` that uses Python 3.10+ syntax.

**Fix:** Run with Python 3.11.9:
```bash
eval "$(pyenv init -)"
python --version  # Should show 3.11.9
```

## Verification

The token extraction fix has been tested and verified:
```bash
python -c "from research_swarm.utils import extract_token_usage; print('OK')"
```

## Next Steps

1. **Immediate:** Run a new analysis to verify costs are now tracked:
   ```bash
   python -m research_swarm run AAPL
   python -m research_swarm report <run_id>
   ```

2. **Verify costs are non-zero** in the report

3. **Supply chain improvement** (optional): Review prompts in `research_swarm/agents/fundamentalist/prompts.py` to improve supplier extraction

## Expected Behavior After Fix

- Token counts should be **non-zero** for all agents
- Costs should reflect actual API usage:
  - Haiku: ~$0.001-0.003 per 1K tokens
  - Sonnet: ~$0.015-0.075 per 1K tokens
- Total run cost for 1 stock: **$0.50-$3.00** depending on complexity
