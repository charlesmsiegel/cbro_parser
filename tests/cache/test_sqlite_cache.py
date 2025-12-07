"""Tests for cbro_parser.cache.sqlite_cache module."""

import time
from datetime import datetime, timedelta

import pytest

from cbro_parser.cache.sqlite_cache import SQLiteCache
from cbro_parser.models import ComicVineIssue, ComicVineVolume


class TestSQLiteCacheInit:
    """Tests for SQLiteCache initialization."""

    def test_creates_database(self, temp_db):
        """Test that cache creates database file."""
        cache = SQLiteCache(temp_db)
        assert temp_db.exists()

    def test_creates_tables(self, temp_db):
        """Test that cache creates required tables."""
        cache = SQLiteCache(temp_db)

        # Verify tables exist by checking stats
        stats = cache.get_stats()
        assert "volumes" in stats
        assert "issues" in stats
        assert "series_mappings" in stats

    def test_custom_expiry_days(self, temp_db):
        """Test custom expiry days setting."""
        cache = SQLiteCache(temp_db, expiry_days=7)
        assert cache.expiry_days == 7


class TestSQLiteCacheVolumes:
    """Tests for volume caching."""

    def test_cache_and_get_volume(self, temp_db, sample_volume):
        """Test caching and retrieving a volume."""
        cache = SQLiteCache(temp_db)

        cache.cache_volume(sample_volume)
        retrieved = cache.get_volume(sample_volume.cv_volume_id)

        assert retrieved is not None
        assert retrieved.cv_volume_id == sample_volume.cv_volume_id
        assert retrieved.name == sample_volume.name
        assert retrieved.start_year == sample_volume.start_year
        assert retrieved.publisher == sample_volume.publisher
        assert retrieved.issue_count == sample_volume.issue_count
        assert retrieved.aliases == sample_volume.aliases

    def test_get_nonexistent_volume(self, temp_db):
        """Test getting a volume that doesn't exist."""
        cache = SQLiteCache(temp_db)

        retrieved = cache.get_volume(99999)

        assert retrieved is None

    def test_update_volume(self, temp_db, sample_volume):
        """Test updating an existing volume."""
        cache = SQLiteCache(temp_db)

        cache.cache_volume(sample_volume)

        # Update the volume
        updated = ComicVineVolume(
            cv_volume_id=sample_volume.cv_volume_id,
            name="Green Lantern Updated",
            start_year=2005,
            publisher="DC Comics",
            issue_count=100,
            aliases=["New Alias"],
        )
        cache.cache_volume(updated)

        retrieved = cache.get_volume(sample_volume.cv_volume_id)
        assert retrieved.name == "Green Lantern Updated"
        assert retrieved.issue_count == 100

    def test_volume_with_empty_aliases(self, temp_db):
        """Test caching volume with no aliases."""
        cache = SQLiteCache(temp_db)

        volume = ComicVineVolume(
            cv_volume_id=11111,
            name="Test Volume",
            start_year=2020,
            publisher="Test",
            issue_count=10,
            aliases=[],
        )
        cache.cache_volume(volume)

        retrieved = cache.get_volume(11111)
        assert retrieved.aliases == []


class TestSQLiteCacheIssues:
    """Tests for issue caching."""

    def test_cache_and_get_issue(self, temp_db, sample_issue):
        """Test caching and retrieving an issue."""
        cache = SQLiteCache(temp_db)

        cache.cache_issue(sample_issue)
        retrieved = cache.get_issue(
            sample_issue.cv_volume_id,
            sample_issue.issue_number,
        )

        assert retrieved is not None
        assert retrieved.cv_issue_id == sample_issue.cv_issue_id
        assert retrieved.cv_volume_id == sample_issue.cv_volume_id
        assert retrieved.issue_number == sample_issue.issue_number
        assert retrieved.cover_date == sample_issue.cover_date
        assert retrieved.name == sample_issue.name

    def test_get_nonexistent_issue(self, temp_db):
        """Test getting an issue that doesn't exist."""
        cache = SQLiteCache(temp_db)

        retrieved = cache.get_issue(12345, "999")

        assert retrieved is None

    def test_cache_volume_issues(self, temp_db, sample_issues):
        """Test bulk caching of issues."""
        cache = SQLiteCache(temp_db)

        cache.cache_volume_issues(sample_issues)

        for issue in sample_issues:
            retrieved = cache.get_issue(
                issue.cv_volume_id,
                issue.issue_number,
            )
            assert retrieved is not None
            assert retrieved.cv_issue_id == issue.cv_issue_id

    def test_get_volume_issues(self, temp_db, sample_issues):
        """Test getting all issues for a volume."""
        cache = SQLiteCache(temp_db)

        cache.cache_volume_issues(sample_issues)
        retrieved = cache.get_volume_issues(12345)

        assert len(retrieved) == len(sample_issues)

    def test_issue_without_cover_date(self, temp_db):
        """Test caching issue without cover date."""
        cache = SQLiteCache(temp_db)

        issue = ComicVineIssue(
            cv_issue_id=88888,
            cv_volume_id=12345,
            issue_number="Special",
            cover_date="",
            name=None,
        )
        cache.cache_issue(issue)

        retrieved = cache.get_issue(12345, "Special")
        assert retrieved is not None
        assert retrieved.cover_date == ""


class TestSQLiteCacheSeriesMapping:
    """Tests for series name mapping."""

    def test_cache_and_get_mapping(self, temp_db):
        """Test caching and retrieving a series mapping."""
        cache = SQLiteCache(temp_db)

        cache.cache_series_mapping(
            normalized_name="green lantern",
            start_year=2005,
            cv_volume_id=12345,
            confidence=1.0,
        )

        volume_id = cache.get_volume_for_series("green lantern", 2005)

        assert volume_id == 12345

    def test_get_mapping_without_year(self, temp_db):
        """Test getting mapping without specifying year."""
        cache = SQLiteCache(temp_db)

        cache.cache_series_mapping("batman", 2011, 11111, confidence=1.0)
        cache.cache_series_mapping("batman", 2016, 22222, confidence=1.0)

        # Should return highest confidence/most recent
        volume_id = cache.get_volume_for_series("batman")

        assert volume_id in [11111, 22222]

    def test_get_mapping_with_year(self, temp_db):
        """Test getting mapping with specific year."""
        cache = SQLiteCache(temp_db)

        cache.cache_series_mapping("batman", 2011, 11111)
        cache.cache_series_mapping("batman", 2016, 22222)

        assert cache.get_volume_for_series("batman", 2011) == 11111
        assert cache.get_volume_for_series("batman", 2016) == 22222

    def test_get_nonexistent_mapping(self, temp_db):
        """Test getting a mapping that doesn't exist."""
        cache = SQLiteCache(temp_db)

        volume_id = cache.get_volume_for_series("nonexistent")

        assert volume_id is None


class TestSQLiteCacheStats:
    """Tests for cache statistics."""

    def test_empty_stats(self, temp_db):
        """Test stats on empty cache."""
        cache = SQLiteCache(temp_db)
        stats = cache.get_stats()

        assert stats["volumes"] == 0
        assert stats["issues"] == 0
        assert stats["series_mappings"] == 0

    def test_stats_after_caching(self, temp_db, sample_volume, sample_issues):
        """Test stats after caching data."""
        cache = SQLiteCache(temp_db)

        cache.cache_volume(sample_volume)
        cache.cache_volume_issues(sample_issues)
        cache.cache_series_mapping("test", 2020, 12345)

        stats = cache.get_stats()

        assert stats["volumes"] == 1
        assert stats["issues"] == len(sample_issues)
        assert stats["series_mappings"] == 1


class TestSQLiteCacheExpiry:
    """Tests for cache expiry functionality."""

    def test_expired_volume_not_returned(self, temp_db, sample_volume):
        """Test that expired volumes are not returned."""
        # Use a very small expiry that allows for timestamp precision issues
        # The cache checks if (now - cached_at) > timedelta(days=expiry_days)
        # With expiry_days=0, anything older than 0 days is expired
        # We need to patch _is_expired to simulate expiry
        cache = SQLiteCache(temp_db, expiry_days=30)

        cache.cache_volume(sample_volume)

        # Patch _is_expired to always return True
        original_is_expired = cache._is_expired
        cache._is_expired = lambda x: True

        retrieved = cache.get_volume(sample_volume.cv_volume_id)

        # Restore original
        cache._is_expired = original_is_expired

        # Should be None because it's expired
        assert retrieved is None

    def test_clear_expired(self, temp_db, sample_volume):
        """Test clearing expired entries."""
        cache = SQLiteCache(temp_db, expiry_days=0)

        cache.cache_volume(sample_volume)
        time.sleep(0.1)

        removed = cache.clear_expired()

        assert removed >= 1

    def test_non_expired_not_removed(self, temp_db, sample_volume):
        """Test that non-expired entries are not removed."""
        cache = SQLiteCache(temp_db, expiry_days=30)

        cache.cache_volume(sample_volume)
        removed = cache.clear_expired()

        assert removed == 0

        retrieved = cache.get_volume(sample_volume.cv_volume_id)
        assert retrieved is not None


class TestSQLiteCacheContextManager:
    """Tests for database connection context manager."""

    def test_transaction_commit(self, temp_db, sample_volume):
        """Test that successful operations are committed."""
        cache = SQLiteCache(temp_db)

        cache.cache_volume(sample_volume)

        # Create new cache instance to verify persistence
        cache2 = SQLiteCache(temp_db)
        retrieved = cache2.get_volume(sample_volume.cv_volume_id)

        assert retrieved is not None

    def test_connection_closed_after_operation(self, temp_db):
        """Test that connections are properly closed."""
        cache = SQLiteCache(temp_db)

        # Multiple operations should work without connection issues
        for i in range(10):
            cache.cache_series_mapping(f"test{i}", 2020, i)

        stats = cache.get_stats()
        assert stats["series_mappings"] == 10
