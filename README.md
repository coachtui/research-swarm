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
   # Demonstrates cache and SEC client functionality
   ```

4. **Run Tests**
   ```bash
   pytest tests/
   ```

## Project Status

**Current Phase**: 3 of 12 (Fundamentalist Agent)

| Phase | Status |
|-------|--------|
| 1. Foundation | Complete |
| 2. Data Pipeline | Complete |
| 3. Fundamentalist Agent | In Progress |
| 4-12. Remaining Agents & Features | Planned |

See [plans/master-plan.md](plans/master-plan.md) for the full roadmap and [progress.md](progress.md) for detailed progress.

## Completed Features

- SQLite caching layer with TTL support
- SEC Edgar API client (CIK lookup, 10-K retrieval)
- Financial Modeling Prep client (graceful degradation without API key)
- Rate limiting middleware
- Structured logging (console + file)

## Budget

- Monthly limit: $200
- Current spend: $0

## Tech Stack

- Python 3.9+
- LangGraph (agent orchestration)
- Claude API (LLM)
- SQLite (caching)
- SEC Edgar API (free)
- Financial Modeling Prep (free tier)
