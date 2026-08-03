import asyncio
import random
import time
from collections import defaultdict


class AccountRateLimiter:
    """In-process per-account pacing. Deploy one worker per account for distributed use."""

    def __init__(self, min_interval_seconds: float) -> None:
        self._interval = min_interval_seconds
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_request: dict[str, float] = {}

    async def acquire(self, account: str) -> None:
        async with self._locks[account]:
            remaining = self._interval - (time.monotonic() - self._last_request.get(account, 0.0))
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_request[account] = time.monotonic()


def retry_delay(initial: float, maximum: float, attempt: int) -> float:
    """Exponential backoff with bounded full jitter."""
    return random.uniform(0, min(maximum, initial * (2 ** max(attempt - 1, 0))))
