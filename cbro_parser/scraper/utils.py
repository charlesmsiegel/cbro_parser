"""Shared utilities for CBRO scrapers."""

import re
import time


class CrawlDelayManager:
    """Manages crawl delay to respect robots.txt rate limits.

    Used by both CBROScraper and IndexScraper to ensure we respect
    the site's crawl-delay directive.
    """

    def __init__(self, delay_seconds: float):
        """
        Initialize the crawl delay manager.

        Args:
            delay_seconds: Minimum seconds between requests.
        """
        self.delay_seconds = delay_seconds
        self.last_request_time = 0.0

    def wait(self) -> None:
        """Wait if necessary to respect the crawl delay."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self.last_request_time = time.time()


def extract_reading_order_name(url: str) -> str:
    """
    Extract a human-readable name from a reading order URL.

    Args:
        url: URL or path to a reading order page.

    Returns:
        Human-readable name extracted from the URL.

    Examples:
        >>> extract_reading_order_name("/dc/characters/batman-reading-order/")
        'Batman'
        >>> extract_reading_order_name("/marvel/events/secret-wars-reading-order")
        'Secret Wars'
    """
    # Extract the slug from the URL (last path segment)
    path = url.rstrip("/").split("/")[-1]

    # Remove common suffixes
    path = re.sub(r"-reading-order$", "", path, flags=re.IGNORECASE)

    # Convert slug to title case
    name = path.replace("-", " ").title()

    return name
