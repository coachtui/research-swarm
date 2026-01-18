# Research Swarm

Multi-agent AI system for researching supply chain bottlenecks and generating bi-weekly investment thesis reports.

## Quick Start

1. **Setup Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure API Keys**
   ```bash
   cp .env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   ```

3. **Test Installation**
   ```bash
   python -m research_swarm
   # Should print "Phase 1 Complete!"
   ```

## Project Status

**Current Phase**: 1 of 12 (Foundation)

See [plans/master-plan.md](plans/master-plan.md) for full roadmap.

## Budget

- Monthly limit: $200
- Current spend: $0

## Tech Stack

- Python 3.10+
- LangGraph (agent orchestration)
- Claude API (LLM)
- SQLite (caching)
