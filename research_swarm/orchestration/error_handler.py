"""Retry logic and error handling for orchestration."""

import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..logger import logger


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""

    def __init__(self, last_exception: Exception, attempt_count: int):
        """Initialize RetryError.

        Args:
            last_exception: The last exception that was raised
            attempt_count: Number of attempts made
        """
        self.last_exception = last_exception
        self.attempt_count = attempt_count
        super().__init__(
            f"All {attempt_count} retry attempts failed. Last error: {last_exception}"
        )


class RetryHandler:
    """Handles retry logic with exponential backoff."""

    def __init__(self, config: Optional[RetryConfig] = None):
        """Initialize RetryHandler.

        Args:
            config: Retry configuration. Defaults to RetryConfig()
        """
        self.config = config or RetryConfig()

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt with exponential backoff and jitter.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Calculate base delay with exponential backoff
        delay = min(
            self.config.base_delay_seconds
            * (self.config.exponential_base**attempt),
            self.config.max_delay_seconds,
        )

        # Add jitter if enabled (±50%)
        if self.config.jitter:
            jitter_factor = random.uniform(0.5, 1.5)
            delay *= jitter_factor

        return delay

    def execute(
        self,
        func: Callable[..., Any],
        *args,
        on_retry: Optional[Callable[[int, Exception], None]] = None,
        **kwargs,
    ) -> Any:
        """Execute a function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments for func
            on_retry: Optional callback called on each retry with (attempt, exception)
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            RetryError: If all retry attempts are exhausted
        """
        last_exception = None

        for attempt in range(self.config.max_retries):
            try:
                result = func(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"Retry succeeded on attempt {attempt + 1}")
                return result

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Attempt {attempt + 1}/{self.config.max_retries} failed: {e}"
                )

                # Call on_retry callback if provided
                if on_retry:
                    try:
                        on_retry(attempt, e)
                    except Exception as callback_error:
                        logger.error(f"on_retry callback failed: {callback_error}")

                # If this was the last attempt, raise RetryError
                if attempt == self.config.max_retries - 1:
                    raise RetryError(last_exception, self.config.max_retries)

                # Calculate and wait for backoff delay
                delay = self.calculate_delay(attempt)
                logger.info(f"Retrying in {delay:.2f} seconds...")
                time.sleep(delay)

        # This should never be reached, but just in case
        raise RetryError(last_exception, self.config.max_retries)


def is_retryable_error(exception: Exception) -> bool:
    """Determine if an error should trigger a retry.

    Args:
        exception: Exception to check

    Returns:
        True if the error is retryable (transient), False otherwise
    """
    # Rate limit errors (common with API calls)
    if "rate" in str(exception).lower() or "limit" in str(exception).lower():
        return True

    # Timeout errors
    if "timeout" in str(exception).lower():
        return True

    # Connection errors
    if any(
        term in str(exception).lower()
        for term in ["connection", "network", "unavailable"]
    ):
        return True

    # Specific HTTP status codes that are retryable
    error_str = str(exception).lower()
    if any(code in error_str for code in ["429", "502", "503", "504"]):
        return True

    # Default: don't retry (could be validation error, auth error, etc.)
    return False
