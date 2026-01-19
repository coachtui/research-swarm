# Research Swarm - Handoff Checklist

Use this checklist when delegating the system to a new developer.

---

## Pre-Handoff (Current Owner)

- [ ] Ensure all tests passing: `pytest -m "not integration"`
- [ ] Verify schedule is installed: `python -m research_swarm schedule status`
- [ ] Export API keys securely (1Password, encrypted file, etc.)
- [ ] Document any custom modifications in CHANGELOG
- [ ] Create backup of persistence DB: `cp data/persistence.db data/persistence.backup.db`
- [ ] Generate final cost report: `python -m research_swarm cost --dashboard`
- [ ] Review recent runs: `python -m research_swarm history --limit 5`
- [ ] Document any pending issues or known bugs

---

## During Handoff

- [ ] Transfer API keys via secure channel (1Password, encrypted email)
- [ ] Grant repository access (GitHub, GitLab, etc.)
- [ ] Share `.env` file securely (encrypted, never plain text)
- [ ] Walk through architecture: [architecture.md](architecture.md)
- [ ] Demonstrate CLI commands
- [ ] Show where logs are stored (`~/Library/Logs/research_swarm/`)
- [ ] Review cost monitoring procedures
- [ ] Explain backup and recovery procedures
- [ ] Discuss automation schedule and email notifications
- [ ] Review any custom configurations or modifications

---

## Post-Handoff (New Owner)

### Environment Setup

- [ ] Clone repository: `git clone <repo-url> research-swarm`
- [ ] Set up Python 3.11.9 with pyenv:
  ```bash
  pyenv install 3.11.9
  pyenv local 3.11.9
  eval "$(pyenv init -)"
  python --version  # Verify 3.11.9
  ```
- [ ] Install dependencies: `pip install -r requirements.txt && pip install -e .`
- [ ] Configure `.env` with API keys:
  ```bash
  cp .env.example .env
  nano .env  # Add API keys
  ```

### Verification Steps

- [ ] Run first test: `python -m research_swarm run AAPL`
- [ ] Check result: `python -m research_swarm history --limit 1`
- [ ] Generate report: `python -m research_swarm report <run_id>`
- [ ] Test email: `python -m research_swarm notify --test`
- [ ] Verify costs: `python -m research_swarm cost`
- [ ] Check cache: `python -m research_swarm cache stats`

### Automation Setup

- [ ] Install schedule: `python -m research_swarm schedule install`
- [ ] Verify schedule: `python -m research_swarm schedule status`
- [ ] Check logs location: `ls ~/Library/Logs/research_swarm/`
- [ ] Verify schedule works: Wait for next scheduled run or test manually

### Testing

- [ ] Run full test suite: `eval "$(pyenv init -)" && pytest -m "not integration"`
- [ ] Verify all tests pass (264 tests expected)
- [ ] Test resume functionality: Create and resume a run
- [ ] Test batch analysis: `python -m research_swarm run AAPL NVDA MSFT`
- [ ] Test cost dashboard: `python -m research_swarm cost --dashboard`

### Documentation Review

- [ ] Read [User Guide](user-guide.md) - Quick start, CLI, workflows
- [ ] Read [Architecture](architecture.md) - System design, agents
- [ ] Review [Maintenance](maintenance.md) - Routine procedures
- [ ] Review [Troubleshooting](troubleshooting.md) - Common issues
- [ ] Bookmark [API Reference](api-reference.md) - Programmatic usage
- [ ] Review [FAQ](faq.md) - Frequently asked questions

### Knowledge Transfer

- [ ] New owner can run analysis independently
- [ ] New owner understands cost monitoring
- [ ] New owner knows how to troubleshoot common issues
- [ ] New owner has access to all resources (docs, logs, databases)
- [ ] New owner can modify configuration (watchlist, .env)
- [ ] New owner knows how to update dependencies
- [ ] New owner understands backup procedures

---

## Validation

- [ ] New owner successfully runs analysis without help
- [ ] New owner can interpret reports and moat scores
- [ ] New owner can monitor costs and identify issues
- [ ] New owner has tested email notifications
- [ ] New owner knows where to find documentation
- [ ] New owner understands automation schedule

---

## Timeline

| Phase | Duration | Description |
|-------|----------|-------------|
| Pre-Handoff | 30 minutes | Prepare documentation and backups |
| Handoff Session | 60-90 minutes | Walk through system and transfer keys |
| Environment Setup | 30 minutes | New owner sets up local environment |
| Testing & Validation | 30 minutes | New owner runs first analysis |
| **Total** | **2.5-3 hours** | **Complete handoff** |

---

## Success Criteria

**Handoff is successful when**:
- ✅ New owner runs first analysis independently (without assistance)
- ✅ New owner interprets results correctly
- ✅ New owner understands cost monitoring
- ✅ New owner knows how to troubleshoot common issues
- ✅ New owner has access to all required resources
- ✅ Automation continues running on schedule

---

## Emergency Contacts

**For Critical Issues**:
- Previous owner: [Contact information]
- API Key Recovery: Check 1Password shared vault
- Repository Access: GitHub organization admin
- Documentation: See `docs/` directory

---

## Post-Handoff Support

**First Week**:
- Daily check-ins (5-10 minutes)
- Available for questions via Slack/email
- Review first automated run together

**First Month**:
- Weekly check-ins (15 minutes)
- Review cost trends
- Answer questions about customization

**Ongoing**:
- Available for major issues
- Review system changes before deployment
- Consult on architecture modifications

---

**Last Updated**: 2026-01-18
**Status**: Active
**Next Review**: 2026-04-18 (quarterly)
