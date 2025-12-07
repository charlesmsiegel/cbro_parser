"""Tests for shared scraper utilities.

Regression tests for: Code Duplication bugs
- Crawl delay logic duplicated in cbro_scraper.py and index_scraper.py
- Reading order name extraction duplicated in both scrapers
"""

import time
import pytest

from cbro_parser.scraper.utils import CrawlDelayManager, extract_reading_order_name


class TestCrawlDelayManager:
    """Tests for CrawlDelayManager class."""

    def test_first_request_no_delay(self):
        """Test that first request has no delay."""
        manager = CrawlDelayManager(delay_seconds=1.0)

        start = time.time()
        manager.wait()
        elapsed = time.time() - start

        # First request should be immediate (< 0.1s tolerance)
        assert elapsed < 0.1

    def test_respects_crawl_delay(self):
        """Test that subsequent requests wait for the delay."""
        manager = CrawlDelayManager(delay_seconds=0.2)

        # First request
        manager.wait()

        # Second request should wait
        start = time.time()
        manager.wait()
        elapsed = time.time() - start

        # Should have waited approximately delay_seconds
        assert 0.15 <= elapsed <= 0.35

    def test_no_delay_if_enough_time_passed(self):
        """Test that no delay if enough time has passed."""
        manager = CrawlDelayManager(delay_seconds=0.1)

        # First request
        manager.wait()

        # Wait longer than delay
        time.sleep(0.15)

        # Next request should be immediate
        start = time.time()
        manager.wait()
        elapsed = time.time() - start

        assert elapsed < 0.05

    def test_tracks_last_request_time(self):
        """Test that manager tracks last request time."""
        manager = CrawlDelayManager(delay_seconds=1.0)

        assert manager.last_request_time == 0.0

        manager.wait()

        assert manager.last_request_time > 0
        assert time.time() - manager.last_request_time < 0.1


class TestExtractReadingOrderName:
    """Tests for extract_reading_order_name function."""

    def test_extracts_name_from_full_url(self):
        """Test extracting name from a full URL."""
        url = "https://www.comicbookreadingorders.com/dc/characters/batman-reading-order/"
        name = extract_reading_order_name(url)
        assert name == "Batman"

    def test_extracts_name_from_url_without_trailing_slash(self):
        """Test extracting name from URL without trailing slash."""
        url = "https://www.comicbookreadingorders.com/marvel/events/secret-wars-reading-order"
        name = extract_reading_order_name(url)
        assert name == "Secret Wars"

    def test_handles_multi_word_names(self):
        """Test extracting multi-word names."""
        url = "/dc/events/blackest-night-reading-order/"
        name = extract_reading_order_name(url)
        assert name == "Blackest Night"

    def test_handles_relative_urls(self):
        """Test extracting from relative URLs."""
        url = "/marvel/characters/iron-man-reading-order/"
        name = extract_reading_order_name(url)
        assert name == "Iron Man"

    def test_title_cases_result(self):
        """Test that result is title cased."""
        url = "/dc/characters/green-lantern-reading-order/"
        name = extract_reading_order_name(url)
        assert name == "Green Lantern"

    def test_handles_complex_names(self):
        """Test handling complex character/event names."""
        url = "/marvel/characters/x-men-reading-order/"
        name = extract_reading_order_name(url)
        assert name == "X Men"

    def test_preserves_numbers(self):
        """Test that numbers are preserved in names."""
        url = "/dc/events/crisis-on-infinite-earths-reading-order/"
        name = extract_reading_order_name(url)
        assert name == "Crisis On Infinite Earths"
