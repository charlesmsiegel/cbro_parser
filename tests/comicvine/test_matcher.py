"""Tests for cbro_parser.comicvine.matcher module."""

import pytest
from unittest.mock import MagicMock, patch

from cbro_parser.comicvine.matcher import SeriesMatcher
from cbro_parser.cache.sqlite_cache import SQLiteCache
from cbro_parser.models import (
    ComicVineIssue,
    ComicVineVolume,
    MatchedBook,
    ParsedIssue,
)


class TestSeriesMatcherInit:
    """Tests for SeriesMatcher initialization."""

    def test_init_stores_dependencies(self, temp_db, mock_config):
        """Test that matcher stores its dependencies."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()

        matcher = SeriesMatcher(cv_client, cache)

        assert matcher.cv_client is cv_client
        assert matcher.cache is cache
        assert matcher.interactive is False

    def test_init_with_interactive(self, temp_db, mock_config):
        """Test initialization with interactive mode."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()

        matcher = SeriesMatcher(cv_client, cache, interactive=True)

        assert matcher.interactive is True


class TestSeriesMatcherSelectBestVolume:
    """Tests for _select_best_volume method."""

    def test_exact_name_match_highest_score(self, temp_db):
        """Test that exact name matches score highest."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()
        matcher = SeriesMatcher(cv_client, cache)

        volumes = [
            ComicVineVolume(
                cv_volume_id=1,
                name="Green Lantern",
                start_year=2005,
                publisher="DC",
                issue_count=67,
            ),
            ComicVineVolume(
                cv_volume_id=2,
                name="Green Lantern Corps",
                start_year=2006,
                publisher="DC",
                issue_count=40,
            ),
        ]

        best = matcher._select_best_volume(volumes, "green lantern", target_year=None)

        assert best is not None
        assert best.cv_volume_id == 1

    def test_year_matching_improves_score(self, temp_db):
        """Test that year matching improves score."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()
        matcher = SeriesMatcher(cv_client, cache)

        volumes = [
            ComicVineVolume(
                cv_volume_id=1,
                name="Green Lantern",
                start_year=2005,
                publisher="DC",
                issue_count=67,
            ),
            ComicVineVolume(
                cv_volume_id=2,
                name="Green Lantern",
                start_year=2011,
                publisher="DC",
                issue_count=52,
            ),
        ]

        best = matcher._select_best_volume(volumes, "green lantern", target_year=2011)

        assert best is not None
        assert best.cv_volume_id == 2

    def test_alias_matching(self, temp_db):
        """Test that aliases are considered."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()
        matcher = SeriesMatcher(cv_client, cache)

        volumes = [
            ComicVineVolume(
                cv_volume_id=1,
                name="The Amazing Spider-Man",
                start_year=1963,
                publisher="Marvel",
                issue_count=700,
                aliases=["Amazing Spider-Man", "ASM"],
            ),
        ]

        best = matcher._select_best_volume(volumes, "amazing spider man", target_year=None)

        assert best is not None
        assert best.cv_volume_id == 1

    def test_score_threshold(self, temp_db):
        """Test that low scores return None."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()
        matcher = SeriesMatcher(cv_client, cache)

        volumes = [
            ComicVineVolume(
                cv_volume_id=1,
                name="Totally Different Series",
                start_year=2020,
                publisher="DC",
                issue_count=10,
            ),
        ]

        best = matcher._select_best_volume(volumes, "batman", target_year=None)

        assert best is None

    def test_prefers_volumes_with_more_issues(self, temp_db):
        """Test preference for volumes with more issues."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()
        matcher = SeriesMatcher(cv_client, cache)

        volumes = [
            ComicVineVolume(
                cv_volume_id=1,
                name="Batman",
                start_year=2016,
                publisher="DC",
                issue_count=5,
            ),
            ComicVineVolume(
                cv_volume_id=2,
                name="Batman",
                start_year=2016,
                publisher="DC",
                issue_count=100,
            ),
        ]

        best = matcher._select_best_volume(volumes, "batman", target_year=2016)

        # Both match equally on name/year, but #2 has more issues
        assert best is not None
        assert best.cv_volume_id == 2


class TestSeriesMatcherFindVolume:
    """Tests for _find_volume method."""

    def test_uses_cache_first(self, temp_db, sample_volume):
        """Test that cache is checked first."""
        cache = SQLiteCache(temp_db)
        cache.cache_volume(sample_volume)
        cache.cache_series_mapping("green lantern", 2005, sample_volume.cv_volume_id)

        cv_client = MagicMock()
        matcher = SeriesMatcher(cv_client, cache)

        parsed = ParsedIssue(
            series_name="Green Lantern",
            issue_number="1",
            year_hint="2005",
        )

        volume = matcher._find_volume("green lantern", parsed)

        assert volume is not None
        assert volume.cv_volume_id == sample_volume.cv_volume_id
        # Should not have called API
        cv_client.search_volumes.assert_not_called()

    def test_searches_api_when_not_cached(self, temp_db, sample_volume):
        """Test that API is searched when not in cache."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()
        cv_client.search_volumes.return_value = [sample_volume]

        matcher = SeriesMatcher(cv_client, cache)

        parsed = ParsedIssue(
            series_name="Green Lantern",
            issue_number="1",
            year_hint="2005",
        )

        volume = matcher._find_volume("green lantern", parsed)

        assert volume is not None
        cv_client.search_volumes.assert_called_once()

    def test_extracts_year_from_parsed(self, temp_db, sample_volume):
        """Test year extraction from parsed issue hints."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()
        cv_client.search_volumes.return_value = [sample_volume]

        matcher = SeriesMatcher(cv_client, cache)

        # Test year_hint
        parsed = ParsedIssue(
            series_name="Green Lantern",
            issue_number="1",
            year_hint="2005",
        )

        volume = matcher._find_volume("green lantern", parsed)
        assert volume is not None

    def test_extracts_year_from_volume_hint(self, temp_db):
        """Test year extraction from volume hint when it's a year."""
        cache = SQLiteCache(temp_db)

        volume_2011 = ComicVineVolume(
            cv_volume_id=54321,
            name="Green Lantern",
            start_year=2011,
            publisher="DC",
            issue_count=52,
        )

        cv_client = MagicMock()
        cv_client.search_volumes.return_value = [volume_2011]

        matcher = SeriesMatcher(cv_client, cache)

        parsed = ParsedIssue(
            series_name="Green Lantern",
            issue_number="1",
            volume_hint="2011",  # This is a year
        )

        volume = matcher._find_volume("green lantern", parsed)
        assert volume is not None
        assert volume.start_year == 2011


class TestSeriesMatcherFindIssue:
    """Tests for _find_issue method."""

    def test_uses_cache_first(self, temp_db, sample_volume, sample_issue):
        """Test that cache is checked first."""
        cache = SQLiteCache(temp_db)
        cache.cache_issue(sample_issue)

        cv_client = MagicMock()
        matcher = SeriesMatcher(cv_client, cache)

        issue = matcher._find_issue(sample_volume, "1")

        assert issue is not None
        assert issue.cv_issue_id == sample_issue.cv_issue_id
        cv_client.get_volume_issues.assert_not_called()

    def test_fetches_all_issues_and_caches(self, temp_db, sample_volume, sample_issues):
        """Test fetching and caching all issues."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()
        cv_client.get_volume_issues.return_value = sample_issues

        matcher = SeriesMatcher(cv_client, cache)

        issue = matcher._find_issue(sample_volume, "2")

        assert issue is not None
        assert issue.issue_number == "2"

        # Should have fetched once
        cv_client.get_volume_issues.assert_called_once()

        # Should be cached now - second call shouldn't hit API
        issue2 = matcher._find_issue(sample_volume, "3")
        assert issue2 is not None
        assert cv_client.get_volume_issues.call_count == 1

    def test_returns_none_for_missing_issue(self, temp_db, sample_volume, sample_issues):
        """Test None returned for missing issue."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()
        cv_client.get_volume_issues.return_value = sample_issues

        matcher = SeriesMatcher(cv_client, cache)

        issue = matcher._find_issue(sample_volume, "999")

        assert issue is None


class TestSeriesMatcherMatchIssue:
    """Tests for match_issue method."""

    def test_successful_match(self, temp_db, sample_volume, sample_issue):
        """Test successful issue matching."""
        cache = SQLiteCache(temp_db)
        cache.cache_volume(sample_volume)
        cache.cache_series_mapping("green lantern", 2005, sample_volume.cv_volume_id)
        cache.cache_issue(sample_issue)

        cv_client = MagicMock()
        matcher = SeriesMatcher(cv_client, cache)

        parsed = ParsedIssue(
            series_name="Green Lantern",
            issue_number="1",
            year_hint="2005",
        )

        matched = matcher.match_issue(parsed)

        assert matched is not None
        assert isinstance(matched, MatchedBook)
        assert matched.series == "Green Lantern"
        assert matched.number == "1"
        assert matched.volume == "2005"
        assert matched.cv_volume_id == sample_volume.cv_volume_id
        assert matched.cv_issue_id == sample_issue.cv_issue_id

    def test_returns_none_when_no_volume(self, temp_db):
        """Test None returned when volume not found."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()
        cv_client.search_volumes.return_value = []

        matcher = SeriesMatcher(cv_client, cache)

        parsed = ParsedIssue(
            series_name="Nonexistent Series",
            issue_number="1",
        )

        matched = matcher.match_issue(parsed)

        assert matched is None

    def test_returns_none_when_no_issue(self, temp_db, sample_volume):
        """Test None returned when issue not found."""
        cache = SQLiteCache(temp_db)
        cache.cache_volume(sample_volume)
        cache.cache_series_mapping("green lantern", 2005, sample_volume.cv_volume_id)

        cv_client = MagicMock()
        cv_client.get_volume_issues.return_value = []

        matcher = SeriesMatcher(cv_client, cache)

        parsed = ParsedIssue(
            series_name="Green Lantern",
            issue_number="999",
            year_hint="2005",
        )

        matched = matcher.match_issue(parsed)

        assert matched is None

    def test_preserves_format_type(self, temp_db, sample_volume, sample_issue):
        """Test that format type is preserved."""
        cache = SQLiteCache(temp_db)
        cache.cache_volume(sample_volume)
        cache.cache_series_mapping("green lantern", 2005, sample_volume.cv_volume_id)
        cache.cache_issue(sample_issue)

        cv_client = MagicMock()
        matcher = SeriesMatcher(cv_client, cache)

        parsed = ParsedIssue(
            series_name="Green Lantern",
            issue_number="1",
            year_hint="2005",
            format_type="Annual",
        )

        matched = matcher.match_issue(parsed)

        assert matched is not None
        assert matched.format_type == "Annual"

    def test_uses_cover_date_for_year(self, temp_db, sample_volume, sample_issue):
        """Test that cover date is used for year."""
        cache = SQLiteCache(temp_db)
        cache.cache_volume(sample_volume)
        cache.cache_series_mapping("green lantern", 2005, sample_volume.cv_volume_id)
        cache.cache_issue(sample_issue)

        cv_client = MagicMock()
        matcher = SeriesMatcher(cv_client, cache)

        parsed = ParsedIssue(
            series_name="Green Lantern",
            issue_number="1",
        )

        matched = matcher.match_issue(parsed)

        assert matched is not None
        # sample_issue has cover_date="2005-07-01"
        assert matched.year == "2005"


class TestSeriesMatcherInteractive:
    """Tests for interactive mode."""

    @patch("builtins.input")
    @patch("builtins.print")
    def test_interactive_select_volume(self, mock_print, mock_input, temp_db):
        """Test interactive volume selection."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()

        matcher = SeriesMatcher(cv_client, cache, interactive=True)

        volumes = [
            ComicVineVolume(
                cv_volume_id=1,
                name="Batman",
                start_year=2011,
                publisher="DC",
                issue_count=52,
            ),
            ComicVineVolume(
                cv_volume_id=2,
                name="Batman",
                start_year=2016,
                publisher="DC",
                issue_count=85,
            ),
        ]

        # Simulate user selecting option 2
        mock_input.return_value = "2"

        selected = matcher._interactive_select_volume("Batman", volumes)

        assert selected is not None
        assert selected.cv_volume_id == 2

    @patch("builtins.input")
    @patch("builtins.print")
    def test_interactive_skip(self, mock_print, mock_input, temp_db):
        """Test interactive skip (selecting 0)."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()

        matcher = SeriesMatcher(cv_client, cache, interactive=True)

        volumes = [
            ComicVineVolume(
                cv_volume_id=1,
                name="Test",
                start_year=2020,
                publisher="DC",
                issue_count=10,
            ),
        ]

        mock_input.return_value = "0"

        selected = matcher._interactive_select_volume("Test", volumes)

        assert selected is None

    @patch("builtins.input")
    @patch("builtins.print")
    def test_interactive_invalid_input(self, mock_print, mock_input, temp_db):
        """Test interactive mode with invalid input."""
        cache = SQLiteCache(temp_db)
        cv_client = MagicMock()

        matcher = SeriesMatcher(cv_client, cache, interactive=True)

        volumes = [
            ComicVineVolume(
                cv_volume_id=1,
                name="Test",
                start_year=2020,
                publisher="DC",
                issue_count=10,
            ),
        ]

        # Simulate invalid input
        mock_input.side_effect = ValueError("Invalid")

        selected = matcher._interactive_select_volume("Test", volumes)

        assert selected is None
