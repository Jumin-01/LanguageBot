"""A minimal in-process rate limiter for outgoing Gemini calls.

No external queue/broker: for a bot used by one or two people, a simple
in-memory rolling window is enough to stop bursts of calls from blowing
through the free-tier per-minute limit -- exactly the failure mode hit
during development, where several calls fired back-to-back and immediately
came back 429.
"""

import asyncio
import time
from collections import deque


class RateLimiter:
    def __init__(self, max_calls: int, period_seconds: float) -> None:
        self._max_calls = max_calls
        self._period = period_seconds
        self._call_times: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            self._evict_expired()

            if len(self._call_times) >= self._max_calls:
                wait_for = self._period - (time.monotonic() - self._call_times[0])
                if wait_for > 0:
                    await asyncio.sleep(wait_for)
                self._evict_expired()

            self._call_times.append(time.monotonic())

    def _evict_expired(self) -> None:
        now = time.monotonic()
        while self._call_times and now - self._call_times[0] >= self._period:
            self._call_times.popleft()
