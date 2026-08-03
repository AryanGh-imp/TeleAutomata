import asyncio
import random
import time

import pytest

from teleautomata.infrastructure.scheduling import AccountRateLimiter, retry_delay


def test_retry_delay_never_exceeds_maximum() -> None:
    rng = random.Random(1234)
    original = random.uniform
    try:
        random.uniform = rng.uniform  # type: ignore[assignment]
        for attempt in range(1, 12):
            delay = retry_delay(initial=1.0, maximum=30.0, attempt=attempt)
            assert 0.0 <= delay <= 30.0
    finally:
        random.uniform = original  # type: ignore[assignment]


def test_retry_delay_ceiling_grows_with_attempt() -> None:
    """Full jitter samples [0, cap); the cap itself should back off exponentially."""
    # Force the sampler to return its upper bound so we observe the cap directly.
    original = random.uniform
    try:
        random.uniform = lambda low, high: high  # type: ignore[assignment]
        caps = [retry_delay(initial=1.0, maximum=100.0, attempt=n) for n in range(1, 5)]
        assert caps == [1.0, 2.0, 4.0, 8.0]
    finally:
        random.uniform = original  # type: ignore[assignment]


def test_retry_delay_attempt_zero_is_safe() -> None:
    original = random.uniform
    try:
        random.uniform = lambda low, high: high  # type: ignore[assignment]
        assert retry_delay(initial=1.0, maximum=100.0, attempt=0) == 1.0
    finally:
        random.uniform = original  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_rate_limiter_paces_same_account() -> None:
    limiter = AccountRateLimiter(min_interval_seconds=0.05)
    start = time.monotonic()
    await limiter.acquire("primary")
    await limiter.acquire("primary")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.05


@pytest.mark.asyncio
async def test_rate_limiter_does_not_pace_across_accounts() -> None:
    limiter = AccountRateLimiter(min_interval_seconds=0.2)
    start = time.monotonic()
    await asyncio.gather(limiter.acquire("a"), limiter.acquire("b"))
    elapsed = time.monotonic() - start
    # Distinct accounts hold distinct locks, so neither waits for the other.
    assert elapsed < 0.2
