"""
Inngest background job functions for long-running stock analysis.

These functions handle the actual analysis work that takes 5-20 minutes,
which is too long for synchronous API calls.
"""

__version__ = "0.1.0"
