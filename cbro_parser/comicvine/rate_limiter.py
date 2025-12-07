"""Rate limiter for ComicVine API requests."""

import time
from collections import deque
from threading import Lock


class RateLimiter:
    """
    Token bucket rate limiter for ComicVine API.

    Enforces:
    - 200 requests per 15-minute window
    - Minimum 1 second between requests (safe pace)
    """

    def __init__(
        self,
        max_requests: int = 200,
        window_seconds: int = 900,  # 15 minutes
        min_interval: float = 1.0,
    ):
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum requests allowed in the window.
            window_seconds: Size of the sliding window in seconds.
            min_interval: Minimum seconds between requests.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.min_interval = min_interval

        self._request_times: deque[float] = deque()
        self._last_request_time: float = 0.0
        self._lock = Lock()

    def acquire(self) -> None:
        """Block until a request can be made within rate limits."""
        with self._lock:
            current_time = time.time()

            # Remove requests outside the window
            cutoff = current_time - self.window_seconds
            while self._request_times and self._request_times[0] < cutoff:
                self._request_times.popleft()

            # Wait if we've hit the window limit
            if len(self._request_times) >= self.max_requests:
                sleep_until = self._request_times[0] + self.window_seconds
                sleep_time = sleep_until - current_time
                if sleep_time > 0:
                    time.sleep(sleep_time)
                current_time = time.time()
                # Clean up again after sleeping
                cutoff = current_time - self.window_seconds
                while self._request_times and self._request_times[0] < cutoff:
                    self._request_times.popleft()

            # Enforce minimum interval between requests
            elapsed = current_time - self._last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
                current_time = time.time()

            self._request_times.append(current_time)
            self._last_request_time = current_time

    def remaining_requests(self) -> int:
        """Return number of requests remaining in current window."""
        with self._lock:
            current_time = time.time()
            cutoff = current_time - self.window_seconds
            while self._request_times and self._request_times[0] < cutoff:
                self._request_times.popleft()
            return self.max_requests - len(self._request_times)

    def time_until_reset(self) -> float:
        """Return seconds until the oldest request expires from window."""
        with self._lock:
            if not self._request_times:
                return 0.0
            oldest = self._request_times[0]
            return max(0.0, (oldest + self.window_seconds) - time.time())

    def requests_made(self) -> int:
        """Return number of requests made in current window."""
        with self._lock:
            current_time = time.time()
            cutoff = current_time - self.window_seconds
            while self._request_times and self._request_times[0] < cutoff:
                self._request_times.popleft()
            return len(self._request_times)
