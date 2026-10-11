import unittest

from app.core.rate_limit import RateLimiter


class RateLimiterTests(unittest.TestCase):
    def test_blocks_after_max_and_resets(self):
        rl = RateLimiter(max_hits=3, window_seconds=60)
        for _ in range(3):
            self.assertFalse(rl.is_blocked("a"))
            rl.hit("a")
        self.assertTrue(rl.is_blocked("a"))
        self.assertFalse(rl.is_blocked("b"))
        rl.reset("a")
        self.assertFalse(rl.is_blocked("a"))

    def test_window_expires(self):
        rl = RateLimiter(max_hits=1, window_seconds=0)
        rl.hit("a")
        self.assertFalse(rl.is_blocked("a"))


if __name__ == "__main__":
    unittest.main()
