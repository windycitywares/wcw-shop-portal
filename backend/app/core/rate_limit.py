"""Small in-memory sliding-window rate limiter (per process).

Good enough to slow down password guessing on a single shared-hosting app.
Each Passenger/LiteSpeed worker keeps its own counters, so the effective limit
is "per worker"; move this to the database or Redis if you scale out.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_hits: int, window_seconds: int):
        self.max_hits = max_hits
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._hits[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        return q

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.max_hits

    def hit(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)
            if len(self._hits) > 10_000:  # keep memory bounded
                for k in [k for k, v in self._hits.items() if not v][:5_000]:
                    del self._hits[k]

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


# Failed sign-ins: 10 per account and 30 per IP address every 15 minutes.
failed_logins_by_email = RateLimiter(max_hits=10, window_seconds=15 * 60)
failed_logins_by_ip = RateLimiter(max_hits=30, window_seconds=15 * 60)
# Registrations: 5 per IP per hour.
registrations_by_ip = RateLimiter(max_hits=5, window_seconds=60 * 60)
