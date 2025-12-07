"""Tests for cbro_parser.scraper.index_scraper module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cbro_parser.models import ReadingOrderEntry
from cbro_parser.scraper.index_scraper import INDEX_PAGES, IndexScraper


class TestIndexScraperInit:
    """Tests for IndexScraper initialization."""

    def test_init_with_config(self, mock_config):
        """Test scraper initialization."""
        scraper = IndexScraper(mock_config)

        assert scraper.config == mock_config
        assert scraper.session is not None


class TestIndexScraperCache:
    """Tests for cache loading and saving."""

    def test_save_and_load_cache(
        self, mock_config, temp_dir, sample_reading_order_entry
    ):
        """Test saving and loading from cache."""
        mock_config.cache_db_path = temp_dir / "cache.db"
        scraper = IndexScraper(mock_config)

        entries = [sample_reading_order_entry]
        scraper.save_to_cache(entries)

        loaded = scraper.load_cached_orders()

        assert loaded is not None
        assert len(loaded) == 1
        assert loaded[0].name == sample_reading_order_entry.name
        assert loaded[0].url == sample_reading_order_entry.url

    def test_load_nonexistent_cache(self, mock_config, temp_dir):
        """Test loading when no cache exists."""
        mock_config.cache_db_path = temp_dir / "nonexistent.db"
        scraper = IndexScraper(mock_config)

        loaded = scraper.load_cached_orders()

        assert loaded is None

    def test_load_corrupted_cache(self, mock_config, temp_dir):
        """Test loading corrupted cache file."""
        mock_config.cache_db_path = temp_dir / "cache.db"
        scraper = IndexScraper(mock_config)

        # Write invalid JSON
        cache_path = temp_dir / "reading_orders_cache.json"
        cache_path.write_text("not valid json {{{")

        loaded = scraper.load_cached_orders()

        assert loaded is None


class TestIndexScraperLinkDetection:
    """Tests for _is_reading_order_link method."""

    def test_valid_reading_order_link(self, mock_config):
        """Test detection of valid reading order links."""
        scraper = IndexScraper(mock_config)

        assert scraper._is_reading_order_link("/dc/characters/batman-reading-order/")
        assert scraper._is_reading_order_link(
            "https://example.com/spider-man-reading-order/"
        )

    def test_reject_non_reading_order(self, mock_config):
        """Test rejection of non-reading-order links."""
        scraper = IndexScraper(mock_config)

        assert not scraper._is_reading_order_link("/about/")
        assert not scraper._is_reading_order_link("/contact/")

    def test_reject_anchor_links(self, mock_config):
        """Test rejection of anchor links."""
        scraper = IndexScraper(mock_config)

        assert not scraper._is_reading_order_link("#section")

    def test_reject_wp_content(self, mock_config):
        """Test rejection of wp-content links."""
        scraper = IndexScraper(mock_config)

        assert not scraper._is_reading_order_link("/wp-content/uploads/image.jpg")

    def test_reject_admin_links(self, mock_config):
        """Test rejection of admin links."""
        scraper = IndexScraper(mock_config)

        assert not scraper._is_reading_order_link("/wp-admin/")
        assert not scraper._is_reading_order_link("/wp-login.php")


class TestIndexScraperNameExtraction:
    """Tests for _extract_name_from_url method."""

    def test_basic_extraction(self, mock_config):
        """Test basic name extraction from URL."""
        scraper = IndexScraper(mock_config)

        name = scraper._extract_name_from_url("/dc/characters/batman-reading-order/")

        assert name == "Batman"

    def test_extraction_with_multiple_words(self, mock_config):
        """Test extraction with multiple words."""
        scraper = IndexScraper(mock_config)

        name = scraper._extract_name_from_url(
            "/dc/characters/green-lantern-reading-order/"
        )

        assert name == "Green Lantern"

    def test_extraction_removes_suffix(self, mock_config):
        """Test that reading-order suffix is removed."""
        scraper = IndexScraper(mock_config)

        name = scraper._extract_name_from_url("/events/blackest-night-reading-order")

        assert "Reading Order" not in name
        assert name == "Blackest Night"


class TestIndexScraperPageParsing:
    """Tests for _parse_index_page method."""

    def test_parse_index_page(self, mock_config, sample_index_html):
        """Test parsing an index page."""
        scraper = IndexScraper(mock_config)

        entries = scraper._parse_index_page(
            sample_index_html,
            "https://www.comicbookreadingorders.com/dc/characters/",
            "DC",
            "characters",
        )

        assert len(entries) == 3
        names = [e.name for e in entries]
        assert "Green Lantern" in names
        assert "Batman" in names
        assert "Superman" in names

    def test_parse_sets_publisher(self, mock_config, sample_index_html):
        """Test that publisher is set correctly."""
        scraper = IndexScraper(mock_config)

        entries = scraper._parse_index_page(
            sample_index_html,
            "https://example.com",
            "Marvel",
            "events",
        )

        for entry in entries:
            assert entry.publisher == "Marvel"

    def test_parse_sets_category(self, mock_config, sample_index_html):
        """Test that category is set correctly."""
        scraper = IndexScraper(mock_config)

        entries = scraper._parse_index_page(
            sample_index_html,
            "https://example.com",
            "DC",
            "events",
        )

        for entry in entries:
            assert entry.category == "events"

    def test_parse_deduplicates_urls(self, mock_config):
        """Test that duplicate URLs are filtered."""
        html = """
        <article>
        <a href="/batman-reading-order/">Batman</a>
        <a href="/batman-reading-order/">Batman Again</a>
        </article>
        """
        scraper = IndexScraper(mock_config)

        entries = scraper._parse_index_page(
            html,
            "https://example.com",
            "DC",
            "characters",
        )

        assert len(entries) == 1

    def test_parse_skips_non_reading_order_links(self, mock_config):
        """Test that non-reading-order links are skipped."""
        html = """
        <article>
        <a href="/batman-reading-order/">Batman</a>
        <a href="/about/">About</a>
        <a href="/contact/">Contact</a>
        </article>
        """
        scraper = IndexScraper(mock_config)

        entries = scraper._parse_index_page(
            html,
            "https://example.com",
            "DC",
            "characters",
        )

        assert len(entries) == 1


class TestIndexScraperFetchAll:
    """Tests for fetch_all_reading_orders method."""

    @patch.object(IndexScraper, "_fetch_index_page")
    def test_progress_callback_called(self, mock_fetch, mock_config):
        """Test that progress callback is called."""
        mock_fetch.return_value = []
        scraper = IndexScraper(mock_config)

        progress_calls = []

        def callback(current, total, message):
            progress_calls.append((current, total, message))

        scraper.fetch_all_reading_orders(progress_callback=callback)

        assert len(progress_calls) > 0
        # Should have final "Done" call
        assert progress_calls[-1][2] == "Done"

    @patch.object(IndexScraper, "_fetch_index_page")
    def test_master_pages_added_directly(self, mock_fetch, mock_config):
        """Test that master reading order pages are added directly."""
        mock_fetch.return_value = []
        scraper = IndexScraper(mock_config)

        entries = scraper.fetch_all_reading_orders()

        # Should include master reading order entries
        master_entries = [e for e in entries if e.category == "master"]
        assert len(master_entries) > 0

    @patch.object(IndexScraper, "_fetch_index_page")
    def test_entries_sorted(self, mock_fetch, mock_config):
        """Test that entries are sorted."""
        mock_fetch.return_value = [
            ReadingOrderEntry(
                name="Zebra",
                url="https://example.com/zebra",
                publisher="DC",
                category="characters",
            ),
            ReadingOrderEntry(
                name="Alpha",
                url="https://example.com/alpha",
                publisher="DC",
                category="characters",
            ),
        ]
        scraper = IndexScraper(mock_config)

        entries = scraper.fetch_all_reading_orders()

        # DC characters should be sorted
        dc_chars = [
            e for e in entries if e.publisher == "DC" and e.category == "characters"
        ]
        if len(dc_chars) >= 2:
            names = [e.name for e in dc_chars]
            # "Alpha" should come before "Zebra"
            alpha_idx = names.index("Alpha")
            zebra_idx = names.index("Zebra")
            assert alpha_idx < zebra_idx


class TestIndexPages:
    """Tests for INDEX_PAGES constant."""

    def test_index_pages_structure(self):
        """Test that INDEX_PAGES has expected structure."""
        for url, publisher, category in INDEX_PAGES:
            assert isinstance(url, str)
            assert url.startswith("https://")
            assert publisher in ["Marvel", "DC", "Other"]
            assert category in ["characters", "events", "master"]

    def test_has_marvel_and_dc(self):
        """Test that both Marvel and DC are included."""
        publishers = set(p for _, p, _ in INDEX_PAGES)
        assert "Marvel" in publishers
        assert "DC" in publishers


class TestIndexScraperErrorHandling:
    """Tests for specific exception handling in IndexScraper."""

    def test_load_cached_orders_handles_json_error(self, mock_config, temp_dir):
        """Test load_cached_orders handles JSONDecodeError specifically."""
        mock_config.cache_db_path = temp_dir / "cache.db"

        scraper = IndexScraper(mock_config)

        # Write malformed JSON to cache location
        cache_path = temp_dir / "reading_orders_cache.json"
        cache_path.write_text("{invalid json content}")

        # Should handle gracefully and return None
        result = scraper.load_cached_orders()
        assert result is None

    def test_load_cached_orders_handles_file_not_found(self, mock_config, temp_dir):
        """Test load_cached_orders handles FileNotFoundError."""
        mock_config.cache_db_path = temp_dir / "nonexistent_cache.db"

        scraper = IndexScraper(mock_config)

        # Should return None when cache doesn't exist
        result = scraper.load_cached_orders()
        assert result is None

    def test_save_to_cache_handles_permission_error(self, mock_config, temp_dir):
        """Test save_to_cache handles OSError/PermissionError."""
        import os

        from cbro_parser.models import ReadingOrderEntry

        mock_config.cache_db_path = temp_dir / "cache.db"
        scraper = IndexScraper(mock_config)

        entries = [
            ReadingOrderEntry(
                name="Test",
                url="https://example.com/test",
                publisher="DC",
                category="characters",
            )
        ]

        # Make cache directory unwritable
        cache_path = temp_dir / "reading_orders_cache.json"
        cache_path.write_text("{}")

        try:
            os.chmod(cache_path, 0o000)
        except OSError:
            pytest.skip("Cannot change file permissions on this system")

        try:
            # Should handle error gracefully without raising
            scraper.save_to_cache(entries)
            # If we get here without exception, the error was handled
        except PermissionError:
            pytest.fail("save_to_cache should handle PermissionError gracefully")
        finally:
            os.chmod(cache_path, 0o644)
