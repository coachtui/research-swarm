# Parallel Agent Execution

## Summary

The Research Swarm agent workflow has been refactored to run the three research agents (Fundamentalist, News Hound, and Quant) **in parallel** instead of sequentially. This significantly reduces total analysis time.

## Architecture Changes

### Before (Sequential - ~270s total)
```
fetch_swarm_data (1s)
    ↓
call_fundamentalist (~90s)
    ↓
call_news_hound (~90s)
    ↓
call_quant (~90s)
    ↓
synthesize_findings
    ↓
calculate_moat_score
    ↓
generate_thesis
```

### After (Parallel - ~90s for agents)
```
                            ┌→ call_fundamentalist (~90s) ─┐
fetch_swarm_data (1s) ──┼→ call_news_hound (~90s) ──────┤→ check_agents_complete
                            └→ call_quant (~90s) ──────────┘
                                                              ↓
                                                     synthesize_findings
                                                              ↓
                                                     calculate_moat_score
                                                              ↓
                                                     generate_thesis
```

## Performance Impact

**Expected time savings**: ~180 seconds per analysis (67% reduction in agent execution time)

- **Before**: Data fetch (1s) + Fund (90s) + News (90s) + Quant (90s) = ~271s
- **After**: Data fetch (1s) + max(Fund, News, Quant) = ~91s
- **Total savings**: ~180 seconds per stock analysis

## Implementation Details

### Key Changes

1. **Removed sequential dependencies** in agent nodes:
   - `call_news_hound_node`: Removed check for fundamentalist errors
   - `call_quant_node`: Removed check for previous agent errors

2. **Added synchronization node** (`check_agents_complete_node`):
   - Waits for all three agents to complete
   - Validates all outputs exist
   - Checks for any agent errors
   - Proceeds to synthesis only if all agents succeeded

3. **Updated graph structure** in `build_manager_graph()`:
   - Fan-out: `fetch_swarm_data` → all three agents in parallel
   - Fan-in: all three agents → `check_agents_complete`
   - Sequential: `check_agents_complete` → synthesis → scoring → thesis

### Node Numbering

- Node 0: `fetch_swarm_data` - Pre-fetch all data
- Node 1: `call_fundamentalist` - **Parallel**
- Node 2: `call_news_hound` - **Parallel**
- Node 3: `call_quant` - **Parallel**
- Node 4: `check_agents_complete` - **New synchronization point**
- Node 5: `synthesize_findings`
- Node 6: `calculate_moat_score`
- Node 7: `generate_thesis`

## Compatibility Notes

### Why This Works

All three agents are independent and only require:
- Ticker symbol
- Pre-fetched data from `shared_swarm_data`
- Their specific parameters (quarters, news_days_back, etc.)

### Previous Dependencies (Now Removed)

1. **Quant → Fundamentalist supply chain data**:
   - Supply chain analysis is currently disabled (`supply_chain_depth=0`)
   - If re-enabled, would need to run Quant after Fundamentalist sequentially

2. **Error propagation**:
   - Previously: Each agent checked if previous agents failed
   - Now: All agents run independently, errors checked at sync point

## Testing

Run the test script to verify graph compilation:

```bash
python test_parallel_graph.py
```

Expected output:
```
✓ Graph compiled successfully!
✓ Graph type: <class 'langgraph.graph.state.CompiledStateGraph'>
✓ Parallel agent execution enabled
```

## Future Considerations

If you need to re-enable supply chain analysis with Fundamentalist dependencies:

1. Keep Fundamentalist and News Hound in parallel
2. Run Quant sequentially after Fundamentalist completes
3. Update graph to: `fundamentalist → quant`, `news_hound → check`, `quant → check`

This would still provide ~90s savings (News Hound runs in parallel with Fund+Quant).
