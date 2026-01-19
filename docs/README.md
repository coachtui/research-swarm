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

**Latest**: Phase 12 - Documentation complete (2026-01-18)

---

## Documentation Map

### By Role

**New User** (first time setup):
1. [User Guide](user-guide.md) - Quick Start
2. [Examples](examples.md) - See commands in action
3. [FAQ](faq.md) - Common questions

**Developer** (extending/modifying):
1. [Architecture](architecture.md) - Understand design
2. [API Reference](api-reference.md) - Programmatic access
3. [Maintenance](maintenance.md) - How to extend agents

**Operator** (running regularly):
1. [User Guide](user-guide.md) - CLI commands
2. [Maintenance](maintenance.md) - Routine procedures
3. [Troubleshooting](troubleshooting.md) - Fix issues

**Team Lead** (onboarding new member):
1. [Handoff Checklist](handoff-checklist.md) - Step-by-step
2. [User Guide](user-guide.md) - System overview
3. [Troubleshooting](troubleshooting.md) - Common issues

---

## Key Concepts

### Moat Score (0-10)
Weighted competitive advantage metric:
- 8.0-10.0: Strong moat 🟢
- 6.0-7.9: Moderate moat 🟡
- 4.0-5.9: Weak moat 🟠
- 0.0-3.9: Very weak moat 🔴

### Agents
Four specialist agents analyze different aspects:
- **Fundamentalist**: Financial health (10-K analysis)
- **News Hound**: Market sentiment (news analysis)
- **Quant**: Technical indicators + supply chain
- **Manager**: Synthesizes all findings

### CLI Commands
- `run` - Analyze stocks
- `report` - Generate reports
- `cost` - Monitor spending
- `cache` - Manage cache
- `schedule` - Automation
- `history` - Past runs

---

## Cost Transparency

**Per-stock**: ~$0.037
**Bi-weekly run** (20 stocks): ~$0.73
**Monthly** (2 runs): ~$1.46
**Budget**: $200/month (99% under budget)

Monitor: `python -m research_swarm cost --dashboard`

---

## Need Help?

1. Check [FAQ](faq.md) for common questions
2. See [Troubleshooting](troubleshooting.md) for error solutions
3. Review [User Guide](user-guide.md) for detailed instructions
4. Check [Examples](examples.md) for command reference

---

## Contributing

This is a personal project but documentation improvements are welcome.

See [maintenance.md](maintenance.md) for how to extend agents or add features.

---

## Version History

See [CHANGELOG.md](../CHANGELOG.md) for detailed version history.

**Latest**: Phase 12 - Documentation & Maintenance (2026-01-18)

---

## License

MIT License - See [LICENSE](../LICENSE) for details.

---

**Project Repository**: [GitHub](https://github.com/your-repo/research-swarm)
**Last Updated**: 2026-01-18
**Status**: Production Ready ✅
