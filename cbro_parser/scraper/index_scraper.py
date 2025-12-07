"""Scraper for discovering all reading orders from CBRO index pages."""

import json
import logging
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..config import Config
from ..models import ReadingOrderEntry
from .utils import CrawlDelayManager, extract_reading_order_name

# Type alias for progress callback function
ProgressCallback = Callable[[int, int, str], None]

logger = logging.getLogger(__name__)


# Index pages to scrape for reading order discovery
INDEX_PAGES = [
    # Marvel
    (
        "https://www.comicbookreadingorders.com/marvel/characters/",
        "Marvel",
        "characters",
    ),
    (
        "https://www.comicbookreadingorders.com/marvel/events/",
        "Marvel",
        "events",
    ),
    (
        "https://www.comicbookreadingorders.com/marvel/marvel-master-reading-order-part-1/",
        "Marvel",
        "master",
    ),
    # DC
    (
        "https://www.comicbookreadingorders.com/dc/characters/",
        "DC",
        "characters",
    ),
    (
        "https://www.comicbookreadingorders.com/dc/events/",
        "DC",
        "events",
    ),
    (
        "https://www.comicbookreadingorders.com/dc/dc-master-reading-order-part-1/",
        "DC",
        "master",
    ),
    # Other publishers (Image, Dark Horse, Valiant, IDW, etc.)
    (
        "https://www.comicbookreadingorders.com/other/",
        "Other",
        "characters",
    ),
]


class IndexScraper:
    """Scrapes CBRO index pages to discover all available reading orders."""

    # Cache file name
    CACHE_FILE = "reading_orders_cache.json"

    def __init__(self, config: Config):
        """
        Initialize the index scraper.

        Args:
            config: Application configuration.
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "CBROParser/1.0 (ComicRack list generator; "
                "respects robots.txt crawl-delay)"
            }
        )
        self._crawl_delay = CrawlDelayManager(config.cbro_crawl_delay_seconds)
        self._cache_path = config.cache_db_path.parent / self.CACHE_FILE

    def load_cached_orders(self) -> list[ReadingOrderEntry] | None:
        """
        Load reading orders from cache file.

        Returns:
            List of cached reading orders, or None if no cache.
        """
        if not self._cache_path.exists():
            logger.debug("No reading order cache found")
            return None

        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            entries = [ReadingOrderEntry(**entry) for entry in data.get("entries", [])]
            cached_at = data.get("cached_at", "unknown")
            logger.info(f"Loaded {len(entries)} cached reading orders from {cached_at}")
            return entries
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse reading order cache: {e}")
            return None
        except OSError as e:
            logger.warning(f"Failed to read reading order cache: {e}")
            return None

    def save_to_cache(self, entries: list[ReadingOrderEntry]) -> None:
        """
        Save reading orders to cache file.

        Args:
            entries: List of reading orders to cache.
        """
        try:
            data = {
                "cached_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "entries": [entry.model_dump() for entry in entries],
            }
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(entries)} reading orders to cache")
        except OSError as e:
            logger.warning(f"Failed to save reading order cache: {e}")

    def fetch_all_reading_orders(
        self, progress_callback: ProgressCallback | None = None
    ) -> list[ReadingOrderEntry]:
        """
        Fetch all available reading orders from index pages.

        Args:
            progress_callback: Optional callback(current, total, message)
                for progress updates.

        Returns:
            List of ReadingOrderEntry objects.
        """
        all_entries = []
        total_pages = len(INDEX_PAGES)

        for i, (url, publisher, category) in enumerate(INDEX_PAGES):
            if progress_callback:
                progress_callback(i, total_pages, f"Fetching {publisher} {category}...")

            try:
                # Master reading order pages ARE the reading orders themselves,
                # not index pages with links to other reading orders
                if category == "master":
                    name = f"{publisher} Master Reading Order"
                    all_entries.append(
                        ReadingOrderEntry(
                            name=name,
                            url=url,
                            publisher=publisher,
                            category=category,
                        )
                    )
                else:
                    entries = self._fetch_index_page(url, publisher, category)
                    all_entries.extend(entries)
            except requests.RequestException as e:
                print(f"Warning: Failed to fetch {url}: {e}")

        if progress_callback:
            progress_callback(total_pages, total_pages, "Done")

        # Sort by name for consistent ordering
        all_entries.sort(key=lambda e: (e.publisher, e.category, e.name.lower()))

        # Save to cache for next startup
        self.save_to_cache(all_entries)

        return all_entries

    def _fetch_index_page(
        self, url: str, publisher: str, category: str
    ) -> list[ReadingOrderEntry]:
        """
        Fetch and parse a single index page.

        Args:
            url: URL of the index page.
            publisher: Publisher name (Marvel, DC).
            category: Category (characters, events).

        Returns:
            List of ReadingOrderEntry objects from this page.
        """
        self._crawl_delay.wait()

        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        return self._parse_index_page(response.text, url, publisher, category)

    def _parse_index_page(
        self, html: str, base_url: str, publisher: str, category: str
    ) -> list[ReadingOrderEntry]:
        """
        Parse an index page to extract reading order links.

        Args:
            html: HTML content of the page.
            base_url: Base URL for resolving relative links.
            publisher: Publisher name.
            category: Category name.

        Returns:
            List of ReadingOrderEntry objects.
        """
        soup = BeautifulSoup(html, "lxml")
        entries = []
        seen_urls = set()

        # Find the main content area
        content = soup.find("article") or soup.find("div", class_="entry-content")
        if not content:
            content = soup

        # Find all links that look like reading orders
        for link in content.find_all("a", href=True):
            href = link["href"]

            # Skip non-reading-order links
            if not self._is_reading_order_link(href):
                continue

            # Resolve relative URLs
            full_url = urljoin(base_url, href)

            # Skip duplicates
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Extract name from link text
            name = link.get_text(strip=True)
            if not name or len(name) < 2:
                # Try to extract from URL
                name = self._extract_name_from_url(href)

            if name:
                entries.append(
                    ReadingOrderEntry(
                        name=name,
                        url=full_url,
                        publisher=publisher,
                        category=category,
                    )
                )

        return entries

    def _is_reading_order_link(self, href: str) -> bool:
        """Check if a link appears to be a reading order page."""
        # Must contain "reading-order" in the URL
        if "reading-order" not in href.lower():
            return False

        # Skip anchors and non-content links
        if href.startswith("#") or "wp-content" in href:
            return False

        # Skip admin and non-page links
        if any(
            x in href.lower() for x in ["wp-admin", "wp-login", "feed", "comment", "?"]
        ):
            return False

        return True

    def _extract_name_from_url(self, url: str) -> str:
        """Extract a readable name from a URL path."""
        return extract_reading_order_name(url)


def get_default_index_scraper() -> IndexScraper:
    """Create an IndexScraper with default configuration."""
    from ..config import get_config

    return IndexScraper(get_config())
