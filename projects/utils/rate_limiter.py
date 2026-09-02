import asyncio
import time


class AsyncRateLimiter:
    """
    Global leaky-bucket rate limiter meant to be shared across every coroutine
    that talks to a given endpoint, regardless of how many concurrent tasks
    are scheduled above it (batches, gathers, aiometer runs, etc.).

    Call `await limiter.acquire()` (or `async with limiter:`) right before
    firing an actual HTTP request. `block_for()` can be used to pause every
    waiter for a while, e.g. after receiving a 429, so a single rate-limit
    response backs off the whole pool instead of only the offending request.
    """

    def __init__(self, max_rate: float, time_period: float = 1.0):
        if max_rate <= 0 or time_period <= 0:
            raise ValueError("max_rate and time_period must be greater than 0.")

        self._max_rate = max_rate
        self._rate = max_rate / time_period
        self._level = 0.0
        self._last_check = time.monotonic()
        self._blocked_until = 0.0
        self._lock = asyncio.Lock()

    def _leak(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_check
        self._last_check = now
        self._level = max(0.0, self._level - elapsed * self._rate)

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                if now < self._blocked_until:
                    await asyncio.sleep(self._blocked_until - now)
                    continue

                self._leak()
                if self._level + 1 <= self._max_rate:
                    self._level += 1
                    return

                await asyncio.sleep((self._level + 1 - self._max_rate) / self._rate)

    async def block_for(self, seconds: float) -> None:
        """Force every future/waiting `acquire()` call to pause for `seconds`."""
        async with self._lock:
            self._blocked_until = max(self._blocked_until, time.monotonic() + seconds)

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *exc_info):
        return False
