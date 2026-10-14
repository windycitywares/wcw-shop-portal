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
# Password-reset emails: 3 per address and 10 per IP per hour; reset attempts: 20 per IP per 15 min.
reset_requests_by_email = RateLimiter(max_hits=3, window_seconds=60 * 60)
reset_requests_by_ip = RateLimiter(max_hits=10, window_seconds=60 * 60)
reset_attempts_by_ip = RateLimiter(max_hits=20, window_seconds=15 * 60)
# Contact form: 5 messages per IP per hour.
contact_by_ip = RateLimiter(max_hits=5, window_seconds=60 * 60)
# Shop: price quotes 120 per IP per minute, cart saves 60, checkouts 12 per hour, order look-ups 15 per 15 minutes,
# wrong coupon codes 10 per 15 minutes (codes are random, so guessing one is hopeless at this rate).
quotes_by_ip = RateLimiter(max_hits=120, window_seconds=60)
cart_sync_by_ip = RateLimiter(max_hits=60, window_seconds=60)
checkout_by_ip = RateLimiter(max_hits=12, window_seconds=60 * 60)
order_lookup_by_ip = RateLimiter(max_hits=15, window_seconds=15 * 60)
coupon_failures_by_ip = RateLimiter(max_hits=10, window_seconds=15 * 60)
# Analytics events: 240 per IP per minute (a busy page sends a handful), reviews 6 per user per day,
# back-in-stock requests 10 per IP per hour, newsletter sign-ups 8 per IP per hour.
events_by_ip = RateLimiter(max_hits=240, window_seconds=60)
reviews_by_user = RateLimiter(max_hits=6, window_seconds=24 * 60 * 60)
stock_alerts_by_ip = RateLimiter(max_hits=10, window_seconds=60 * 60)
newsletter_by_ip = RateLimiter(max_hits=8, window_seconds=60 * 60)
