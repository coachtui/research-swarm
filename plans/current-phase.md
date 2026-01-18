# Phase 1: Foundation & Project Scaffolding

**Status**: Ready to Execute
**Duration**: 1-2 sessions (2-3 hours)
**Owner**: Tui
**Dependencies**: None (starting fresh)

---

## Objective

Build a solid, clean foundation that will support all future development. This phase focuses on getting the development environment right, establishing project structure, and validating that core dependencies work.

---

## Tasks Breakdown

### 1. Python Environment Setup
**Priority**: Critical
**Estimated Time**: 30 min

- [ ] Install Python 3.10+ (check: `python --version`)
- [ ] Create virtual environment: `python -m venv venv`
- [ ] Activate venv: `source venv/bin/activate` (Mac/Linux)
- [ ] Upgrade pip: `pip install --upgrade pip`

**Validation**: `which python` should point to venv

---

### 2. Dependency Management
**Priority**: Critical
**Estimated Time**: 20 min

Create `requirements.txt` with initial dependencies:

```txt
# Core framework
langgraph==0.0.55
langchain==0.1.0
langchain-anthropic==0.1.0

# Data handling
pydantic==2.5.0
python-dotenv==1.0.0

# API clients (will expand in Phase 2)
requests==2.31.0
aiohttp==3.9.0

# Utilities
loguru==0.7.2
python-dateutil==2.8.2

# Testing (will expand in Phase 10)
pytest==7.4.3
pytest-cov==4.1.0
```

- [ ] Create requirements.txt
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Verify LangGraph: `python -c "import langgraph; print(langgraph.__version__)"`

**Validation**: No import errors

---

### 3. Project Structure
**Priority**: Critical
**Estimated Time**: 20 min

Create clean folder hierarchy:

```
research-swarm/
├── .env.example          # Template for API keys
├── .gitignore           # Exclude secrets, cache
├── requirements.txt     # Dependencies
├── README.md           # Quick start guide
├── setup.py            # Package metadata
│
├── research_swarm/     # Main package
│   ├── __init__.py
│   ├── __main__.py     # CLI entry point
│   ├── config.py       # Load .env, settings
│   ├── logger.py       # Logging setup
│   │
│   ├── agents/         # Agent modules (Phase 3-6)
│   │   ├── __init__.py
│   │   ├── fundamentalist.py
│   │   ├── news_hound.py
│   │   ├── quant.py
│   │   └── manager.py
│   │
│   ├── data/           # Data clients (Phase 2)
│   │   ├── __init__.py
│   │   ├── sec_client.py
│   │   ├── news_client.py
│   │   └── cache.py
│   │
│   ├── orchestration/  # Workflow (Phase 7)
│   │   ├── __init__.py
│   │   └── workflow.py
│   │
│   └── reports/        # Report gen (Phase 8)
│       ├── __init__.py
│       └── generator.py
│
├── data/               # Cache & state (gitignored)
│   ├── cache/
│   └── state/
│
├── reports/            # Generated reports
│   └── archive/
│
├── tests/              # Test suite (Phase 10)
│   ├── __init__.py
│   └── test_config.py
│
└── plans/              # Project planning (this file!)
    ├── master-plan.md
    └── current-phase.md
```

**Commands**:
```bash
mkdir -p research_swarm/{agents,data,orchestration,reports}
mkdir -p data/{cache,state}
mkdir -p reports/archive
mkdir -p tests

touch research_swarm/__init__.py
touch research_swarm/__main__.py
touch research_swarm/{config,logger}.py
touch research_swarm/agents/__init__.py
touch research_swarm/data/__init__.py
touch research_swarm/orchestration/__init__.py
touch research_swarm/reports/__init__.py
touch tests/__init__.py
```

**Validation**: `tree -L 2 research_swarm` shows structure

---

### 4. Configuration Management
**Priority**: Critical
**Estimated Time**: 30 min

**File: `.env.example`**
```bash
# LLM API Keys
ANTHROPIC_API_KEY=sk-ant-...

# Financial Data
FMP_API_KEY=your_key_here  # financialmodelingprep.com (free tier)

# News Data
NEWS_API_KEY=your_key_here  # newsapi.org ($50/month)

# Email Notifications (Phase 9)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# App Settings
LOG_LEVEL=INFO
CACHE_DIR=./data/cache
STATE_DIR=./data/state
```

**File: `research_swarm/config.py`**
```python
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str
    fmp_api_key: str = ""  # Optional for Phase 1
    news_api_key: str = ""  # Optional for Phase 1

    # Paths
    cache_dir: Path = Path("./data/cache")
    state_dir: Path = Path("./data/state")
    reports_dir: Path = Path("./reports")

    # Logging
    log_level: str = "INFO"

    # LLM Settings
    default_model: str = "claude-3-5-haiku-20241022"  # Cheap for Phase 1
    max_tokens: int = 4000
    temperature: float = 0.1

    class Config:
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()
```

**Tasks**:
- [ ] Create `.env.example`
- [ ] Copy to `.env` and add real `ANTHROPIC_API_KEY`
- [ ] Implement `config.py`
- [ ] Test: `python -c "from research_swarm.config import settings; print(settings.anthropic_api_key[:10])"`

**Validation**: Prints first 10 chars of API key without errors

---

### 5. Logging Setup
**Priority**: High
**Estimated Time**: 20 min

**File: `research_swarm/logger.py`**
```python
import sys
from loguru import logger
from research_swarm.config import settings

# Remove default handler
logger.remove()

# Add console handler with pretty formatting
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.log_level,
    colorize=True,
)

# Add file handler (persists logs)
logger.add(
    "./data/logs/research_swarm_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
)

# Usage example
if __name__ == "__main__":
    logger.info("Logger initialized")
    logger.debug("Debug message")
    logger.warning("Warning message")
    logger.error("Error message")
```

**Tasks**:
- [ ] Create `logger.py`
- [ ] Create log directory: `mkdir -p data/logs`
- [ ] Test: `python -m research_swarm.logger`

**Validation**: See colored output in console + log file created

---

### 6. CLI Entry Point
**Priority**: High
**Estimated Time**: 30 min

**File: `research_swarm/__init__.py`**
```python
__version__ = "0.1.0"
__author__ = "Tui"
```

**File: `research_swarm/__main__.py`**
```python
import sys
from research_swarm.logger import logger
from research_swarm.config import settings

def main():
    """Main CLI entry point."""
    logger.info(f"Research Swarm v{__version__}")
    logger.info(f"Using model: {settings.default_model}")
    logger.info(f"Cache directory: {settings.cache_dir}")

    # Phase 1: Just print config and exit
    logger.success("✓ Configuration loaded successfully")
    logger.success("✓ Logging initialized")
    logger.success("✓ Environment validated")

    print("\n🎯 Phase 1 Complete! Ready for Phase 2.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
```

**Tasks**:
- [ ] Implement `__init__.py` and `__main__.py`
- [ ] Test: `python -m research_swarm`

**Validation**: Prints success messages and exits cleanly

---

### 7. LangGraph "Hello World"
**Priority**: High
**Estimated Time**: 30 min

**File: `tests/test_langgraph_basic.py`**
```python
"""Verify LangGraph is working with a minimal workflow."""
from langgraph.graph import StateGraph
from typing import TypedDict
from research_swarm.logger import logger

class State(TypedDict):
    message: str
    count: int

def node_a(state: State) -> State:
    logger.info(f"Node A: {state['message']}")
    return {"message": state["message"], "count": state["count"] + 1}

def node_b(state: State) -> State:
    logger.info(f"Node B: {state['message']}")
    return {"message": state["message"] + " (processed)", "count": state["count"] + 1}

def test_basic_workflow():
    """Test a simple 2-node workflow."""
    workflow = StateGraph(State)
    workflow.add_node("node_a", node_a)
    workflow.add_node("node_b", node_b)
    workflow.add_edge("node_a", "node_b")
    workflow.set_entry_point("node_a")
    workflow.set_finish_point("node_b")

    app = workflow.compile()

    result = app.invoke({"message": "Hello LangGraph", "count": 0})

    assert result["message"] == "Hello LangGraph (processed)"
    assert result["count"] == 2
    logger.success("✓ LangGraph workflow test passed!")

if __name__ == "__main__":
    test_basic_workflow()
```

**Tasks**:
- [ ] Create test file
- [ ] Run: `python tests/test_langgraph_basic.py`
- [ ] Verify test passes

**Validation**: Test passes, logs show node execution

---

### 8. Git Setup
**Priority**: Medium
**Estimated Time**: 15 min

**File: `.gitignore`**
```gitignore
# Environment
.env
venv/
__pycache__/
*.pyc
.pytest_cache/

# Data & Cache
data/cache/
data/state/
data/logs/

# Reports (optionally commit examples later)
reports/*.pdf

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

**Tasks**:
- [ ] Create `.gitignore`
- [ ] Initialize repo: `git init`
- [ ] Add files: `git add .`
- [ ] First commit: `git commit -m "Phase 1: Project foundation"`

**Validation**: `git status` shows clean working tree

---

### 9. README Quick Start
**Priority**: Medium
**Estimated Time**: 20 min

**File: `README.md`**
```markdown
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
```

**Tasks**:
- [ ] Create README.md
- [ ] Verify instructions work on clean system (optional)

---

## Success Criteria (Definition of Done)

- [ ] All tasks above completed
- [ ] `python -m research_swarm` runs without errors
- [ ] LangGraph test passes
- [ ] Config loads API keys correctly
- [ ] Logging outputs to console and file
- [ ] Git initialized with clean commit history
- [ ] Project structure matches plan

---

## Cost Estimate for Phase 1

**Total API Costs**: ~$0.50
- LangGraph test uses <1000 tokens (free tier)
- Config validation: $0

**Time Investment**: 2-3 hours

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Python version mismatch | Low | Use pyenv to install 3.10+ |
| Dependency conflicts | Medium | Use clean venv, pin versions |
| API key issues | Low | Validate in config.py, fail fast |
| Folder permission errors | Low | Use mkdir -p, run as user |

---

## Next Phase Preview

**Phase 2: Data Pipeline Foundation**
- Build SEC Edgar client
- Implement SQLite caching
- Test fetching real 10-K filing
- Set up rate limiting

---

## Notes for Tui

- Keep this phase simple - resist urge to add features
- Focus on "can I run this?" not "is this perfect?"
- If stuck >30 min on any task, document blocker and move on
- First commit should be small and clean
- Use `logger.info()` liberally to see what's happening

---

**Last Updated**: 2025-01-18
**Next Review**: After Phase 1 completion
