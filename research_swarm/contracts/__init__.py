"""Draft data contracts for the re-architected pipeline.

Target shape: fetch → compute → interpret → decide → render, with a typed
contract at every seam:

    TickerSnapshot   — everything fetched, assembled once (snapshot.py)
    AnalysisReport   — everything produced, persisted once (report.py)

Nothing imports these yet. They exist to be reviewed and then adopted stage
by stage; once adopted, AnalysisReport is the API response, the persisted
JSON, and the source for the generated frontend types.
"""

from research_swarm.contracts.snapshot import TickerSnapshot
from research_swarm.contracts.report import AnalysisReport

__all__ = ["TickerSnapshot", "AnalysisReport"]
