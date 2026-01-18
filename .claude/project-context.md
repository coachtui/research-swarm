# Research Swarm - Project Context

## Project Overview
An autonomous multi-agent AI system that researches stock market supply chain bottlenecks and generates bi-weekly investment thesis reports.

## Business Context
- **Founder**: Tui (construction professional, technical background)
- **Status**: Pre-revenue, side project alongside EquipmentAI Inspector
- **Budget**: $200/month maximum for APIs
- **Time Constraint**: Limited hours, needs automation

## Core Problem
Finding "hidden layer" investment opportunities (like Nittobo Glass supplying 60% of fiber optic components for AI networking) before they become obvious to the market.

## Solution Architecture
Build 4 specialized research agents that work together:

1. **Fundamentalist**: Analyzes financial statements (10-Ks, balance sheets)
2. **News Hound**: Tracks sentiment, catalysts, regulatory changes
3. **Quant**: Runs technical analysis + supply chain mapping
4. **Manager**: Synthesizes findings, scores opportunities (1-10 moat score)

## Success Criteria
- Bi-weekly thesis reports delivered automatically
- Each report covers 2-3 bottleneck opportunities
- Moat score ≥8 gets added to watchlist
- Total cost stays under $200/month

## Technical Constraints
- Must run on local machine (Mac/Linux)
- Maintainable by one person
- No exotic dependencies
- Must persist state (can't lose research between runs)

## Deliverables
- 4 working agent modules
- Orchestration system (runs agents in sequence)
- Automated scheduling (bi-weekly execution)
- Email notifications for high-priority findings
- Thesis report generator (markdown → PDF)

## Phase Strategy
Break into ~8-12 phases:
- Phases 1-2: Framework setup, file structure
- Phases 3-6: Build each agent individually
- Phase 7: Orchestration and communication
- Phase 8: Automation and deployment

## Cost Targets (Monthly)
- Claude API: $100-150
- Financial data APIs: $0-50 (use free tiers)
- News APIs: $30-50
- Total: $130-250 (target: stay under $200)

## Technology Preferences
- **Agent Framework**: LangGraph (better docs than CrewAI for financial workflows)
- **Data Sources**: SEC Edgar (free), Financial Modeling Prep (free tier), NewsAPI
- **Language**: Python 3.10+
- **Testing**: pytest
- **Deployment**: Local cron job (Mac) or Task Scheduler (Windows)

## Non-Goals (What We're NOT Building)
- Real-time trading system
- Mobile app
- Public web interface
- Multi-user support
- Historical backtesting engine

## Risk Factors
- API rate limits (need caching strategy)
- Data quality (need validation)
- Cost overruns (need usage tracking)
- Maintenance burden (need simple architecture)