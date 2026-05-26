"""
Retry utility with exponential backoff
"""

import time
from typing import Callable, TypeVar

T = TypeVar('T')


def retry_with_backoff(func: Callable[[], T], max_retries: int = 3, initial_delay: float = 1) -> T:
    """
    Retry a function with exponential backoff
    Args:
        func: Function to retry
        max_retries: Maximum number of retries
        initial_delay: Initial delay in seconds
    Returns:
        Result of func() or raises last exception
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise

            delay = initial_delay * (2 ** attempt)
            print(f"[RETRY] Attempt {attempt + 1}/{max_retries} failed: {e}", flush=True)
            print(f"[RETRY] Waiting {delay}s before retry...", flush=True)
            time.sleep(delay)
