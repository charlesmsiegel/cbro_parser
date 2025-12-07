"""Tests for cbro_parser.comicvine.rate_limiter module."""

import time
import threading
import pytest

from cbro_parser.comicvine.rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init_default_values(self):
        """Test default initialization values."""
        limiter = RateLimiter()
        assert limiter.max_requests == 200
        assert limiter.window_seconds == 900
        assert limiter.min_interval == 1.0

    def test_init_custom_values(self):
        """Test custom initialization values."""
        limiter = RateLimiter(
            max_requests=10,
            window_seconds=60,
            min_interval=0.5,
        )
        assert limiter.max_requests == 10
        assert limiter.window_seconds == 60
        assert limiter.min_interval == 0.5

    def test_acquire_records_request(self):
        """Test that acquire records the request."""
        limiter = RateLimiter(min_interval=0)

        assert limiter.requests_made() == 0
        limiter.acquire()
        assert limiter.requests_made() == 1

    def test_remaining_requests(self):
        """Test remaining_requests calculation."""
        limiter = RateLimiter(max_requests=10, min_interval=0)

        assert limiter.remaining_requests() == 10

        limiter.acquire()
        assert limiter.remaining_requests() == 9

        limiter.acquire()
        assert limiter.remaining_requests() == 8

    def test_min_interval_enforcement(self):
        """Test minimum interval between requests."""
        limiter = RateLimiter(min_interval=0.1)

        start = time.time()
        limiter.acquire()
        limiter.acquire()
        elapsed = time.time() - start

        assert elapsed >= 0.1  # At least one interval

    def test_time_until_reset_empty(self):
        """Test time_until_reset with no requests."""
        limiter = RateLimiter()
        assert limiter.time_until_reset() == 0.0

    def test_time_until_reset_with_requests(self):
        """Test time_until_reset after requests."""
        limiter = RateLimiter(window_seconds=60, min_interval=0)

        limiter.acquire()
        reset_time = limiter.time_until_reset()

        # Should be close to window_seconds
        assert 59 <= reset_time <= 60

    def test_requests_expire_from_window(self):
        """Test that old requests expire from the window."""
        limiter = RateLimiter(
            max_requests=10,
            window_seconds=0.1,  # Very short window
            min_interval=0,
        )

        limiter.acquire()
        assert limiter.requests_made() == 1

        time.sleep(0.15)  # Wait for window to expire

        assert limiter.requests_made() == 0
        assert limiter.remaining_requests() == 10

    def test_thread_safety(self):
        """Test that rate limiter is thread-safe."""
        limiter = RateLimiter(max_requests=100, min_interval=0)
        results = []

        def make_request():
            limiter.acquire()
            results.append(1)

        threads = [threading.Thread(target=make_request) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 20
        assert limiter.requests_made() == 20

    def test_window_limit_enforcement(self):
        """Test that window limit blocks when exceeded."""
        limiter = RateLimiter(
            max_requests=2,
            window_seconds=0.2,
            min_interval=0,
        )

        # First two should be fast
        start = time.time()
        limiter.acquire()
        limiter.acquire()
        first_two = time.time() - start

        assert first_two < 0.1  # Should be very fast

        # Third should wait for window
        limiter.acquire()
        total = time.time() - start

        # Should have waited for the window
        assert total >= 0.15


class TestRateLimiterEdgeCases:
    """Edge case tests for RateLimiter."""

    def test_zero_max_requests(self):
        """Test behavior with zero max requests."""
        # This is an edge case - would block forever
        # Just test initialization works
        limiter = RateLimiter(max_requests=0)
        assert limiter.max_requests == 0

    def test_very_short_window(self):
        """Test with very short window."""
        limiter = RateLimiter(
            max_requests=1,
            window_seconds=0.01,
            min_interval=0,
        )

        limiter.acquire()
        time.sleep(0.02)

        # Should be able to make another request
        limiter.acquire()
        assert limiter.requests_made() == 1  # Old one expired

    def test_remaining_after_expiry(self):
        """Test remaining requests after some expire."""
        limiter = RateLimiter(
            max_requests=5,
            window_seconds=0.1,
            min_interval=0,
        )

        # Make 3 requests
        limiter.acquire()
        limiter.acquire()
        limiter.acquire()

        assert limiter.remaining_requests() == 2

        # Wait for expiry
        time.sleep(0.15)

        assert limiter.remaining_requests() == 5
