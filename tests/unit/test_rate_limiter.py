import time

from bot.ai.rate_limiter import RateLimiter


async def test_calls_within_budget_do_not_wait() -> None:
    limiter = RateLimiter(max_calls=3, period_seconds=10)
    start = time.monotonic()

    for _ in range(3):
        await limiter.acquire()

    assert time.monotonic() - start < 0.5


async def test_call_over_budget_waits_for_the_window_to_free_up() -> None:
    limiter = RateLimiter(max_calls=2, period_seconds=0.2)
    start = time.monotonic()

    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()  # third call within the same window must wait

    elapsed = time.monotonic() - start
    assert elapsed >= 0.15


async def test_calls_after_the_window_expires_do_not_wait() -> None:
    limiter = RateLimiter(max_calls=1, period_seconds=0.1)

    await limiter.acquire()
    time.sleep(0.15)  # let the window fully expire

    start = time.monotonic()
    await limiter.acquire()

    assert time.monotonic() - start < 0.05
