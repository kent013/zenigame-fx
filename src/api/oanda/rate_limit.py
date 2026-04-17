from __future__ import annotations

import threading
import time


class TokenBucket:
    """Token bucket rate limiter. OANDA v20 の公式上限 100 req/sec に対し、50 req/sec で安全側に設定。"""

    def __init__(self, rate_per_sec: float = 50.0, capacity: int = 50) -> None:
        self._rate = rate_per_sec
        self._capacity = capacity
        self._tokens: float = capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> None:
        with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last
                self._last = now
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                wait = (tokens - self._tokens) / self._rate
                time.sleep(wait)
