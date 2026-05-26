"""
Retry utility with exponential backoff
"""

import time
from typing import Callable, TypeVar, Any

T = TypeVar('T')


def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    log_prefix: str = "[RETRY]",
) -> T:
    """Retry with exponential backoff."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exc = e
            if attempt == max_retries - 1:
                raise
            delay = initial_delay * (2 ** attempt)
            print(f"{log_prefix} Attempt {attempt + 1}/{max_retries} failed: {e}", flush=True)
            print(f"{log_prefix} Waiting {delay:.1f}s before retry...", flush=True)
            time.sleep(delay)
    raise last_exc  # pragma: no cover
