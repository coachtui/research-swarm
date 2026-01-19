"""Utility functions for research-swarm."""
from typing import Any, Dict


def extract_token_usage(response_metadata: Dict[str, Any]) -> int:
    """
    Extract token usage from Anthropic API response metadata.

    Handles the new response format where tokens are split into
    input_tokens and output_tokens instead of total_tokens.

    Args:
        response_metadata: Response metadata dict from ChatAnthropic

    Returns:
        Total tokens used (input + output)
    """
    usage = response_metadata.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    return input_tokens + output_tokens
