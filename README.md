# Research Swarm

Multi-agent AI system for researching supply chain bottlenecks and generating bi-weekly investment thesis reports.

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

**Per-stock cost** (after Phase 11 optimization): approximately $0.037
- Fundamentalist: $0.010
- News Hound: $0.010
- Quant: $0.005
- Manager: $0.012

**Monthly cost** (2 bi-weekly runs, 20 stocks each): approximately $1.46

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

## Tech Stack

- Python 3.10+ (3.11.9 recommended)
- LangGraph (agent orchestration)
- Anthropic Claude API (Haiku 3.5 & Sonnet 3.5)
- SQLite (caching & persistence)
- SEC Edgar API (free)
- Financial Modeling Prep (free tier)
- NewsAPI (free tier)
- Yahoo Finance (yfinance)

---

## Contributing

This is a personal project but documentation improvements are welcome.

---

## License

MIT License - See [LICENSE](LICENSE) for details.
