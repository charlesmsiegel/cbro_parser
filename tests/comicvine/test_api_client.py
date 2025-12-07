"""Tests for cbro_parser.comicvine.api_client module."""

from unittest.mock import MagicMock, patch

import pytest

from cbro_parser.comicvine.api_client import ComicVineAPIError, ComicVineClient
from cbro_parser.comicvine.rate_limiter import RateLimiter
from cbro_parser.models import ComicVineIssue, ComicVineVolume


class TestComicVineClientInit:
    """Tests for ComicVineClient initialization."""

    def test_init_creates_rate_limiter(self, mock_config):
        """Test that client creates rate limiter if not provided."""
        client = ComicVineClient(mock_config)

        assert client.rate_limiter is not None
        assert isinstance(client.rate_limiter, RateLimiter)

    def test_init_uses_provided_rate_limiter(self, mock_config):
        """Test that client uses provided rate limiter."""
        rate_limiter = RateLimiter(max_requests=50)
        client = ComicVineClient(mock_config, rate_limiter)

        assert client.rate_limiter is rate_limiter
        assert client.rate_limiter.max_requests == 50

    def test_init_has_session(self, mock_config):
        """Test that client has session with User-Agent."""
        client = ComicVineClient(mock_config)

        assert client.session is not None
        assert "User-Agent" in client.session.headers


class TestComicVineClientSearchVolumes:
    """Tests for search_volumes method."""

    @patch("cbro_parser.comicvine.api_client.requests.Session")
    def test_search_volumes_basic(self, mock_session_class, mock_config):
        """Test basic volume search."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status_code": 1,
            "results": [
                {
                    "id": 12345,
                    "name": "Green Lantern",
                    "start_year": 2005,
                    "publisher": {"name": "DC Comics"},
                    "count_of_issues": 67,
                    "aliases": "GL\nGreen Lantern Vol. 4",
                }
            ],
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ComicVineClient(mock_config)
        client.session = mock_session

        volumes = client.search_volumes("Green Lantern")

        assert len(volumes) == 1
        assert volumes[0].name == "Green Lantern"
        assert volumes[0].start_year == 2005
        assert volumes[0].publisher == "DC Comics"
        assert "GL" in volumes[0].aliases

    @patch("cbro_parser.comicvine.api_client.requests.Session")
    def test_search_volumes_handles_missing_fields(
        self, mock_session_class, mock_config
    ):
        """Test search handles missing optional fields."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status_code": 1,
            "results": [
                {
                    "id": 12345,
                    "name": "Test",
                    "start_year": None,
                    "publisher": None,
                    "count_of_issues": 0,  # API returns 0, not None typically
                    "aliases": None,
                }
            ],
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ComicVineClient(mock_config)
        client.session = mock_session

        volumes = client.search_volumes("Test")

        assert len(volumes) == 1
        assert volumes[0].start_year == 0
        assert volumes[0].publisher == ""
        assert volumes[0].issue_count == 0
        assert volumes[0].aliases == []

    @patch("cbro_parser.comicvine.api_client.requests.Session")
    def test_search_volumes_handles_string_year(self, mock_session_class, mock_config):
        """Test search handles year as string."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status_code": 1,
            "results": [
                {
                    "id": 12345,
                    "name": "Test",
                    "start_year": "1963?",  # Some have question marks
                    "publisher": None,
                    "count_of_issues": 0,
                    "aliases": None,
                }
            ],
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ComicVineClient(mock_config)
        client.session = mock_session

        volumes = client.search_volumes("Test")

        assert volumes[0].start_year == 1963


class TestComicVineClientGetVolume:
    """Tests for get_volume method."""

    @patch("cbro_parser.comicvine.api_client.requests.Session")
    def test_get_volume(self, mock_session_class, mock_config):
        """Test getting volume details."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status_code": 1,
            "results": {
                "id": 12345,
                "name": "Batman",
                "start_year": 2016,
                "publisher": {"name": "DC Comics"},
                "count_of_issues": 85,
                "aliases": None,
            },
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ComicVineClient(mock_config)
        client.session = mock_session

        volume = client.get_volume(12345)

        assert volume.cv_volume_id == 12345
        assert volume.name == "Batman"
        assert volume.start_year == 2016


class TestComicVineClientGetVolumeIssues:
    """Tests for get_volume_issues method."""

    @patch("cbro_parser.comicvine.api_client.requests.Session")
    def test_get_volume_issues_basic(self, mock_session_class, mock_config):
        """Test getting issues for a volume."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status_code": 1,
            "number_of_total_results": 2,
            "results": [
                {
                    "id": 99999,
                    "issue_number": "1",
                    "cover_date": "2016-06-01",
                    "name": "I Am Gotham Part 1",
                },
                {
                    "id": 99998,
                    "issue_number": "2",
                    "cover_date": "2016-07-01",
                    "name": "I Am Gotham Part 2",
                },
            ],
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ComicVineClient(mock_config)
        client.session = mock_session

        issues = client.get_volume_issues(12345)

        assert len(issues) == 2
        assert issues[0].issue_number == "1"
        assert issues[1].issue_number == "2"

    @patch("cbro_parser.comicvine.api_client.requests.Session")
    def test_get_volume_issues_handles_pagination(
        self, mock_session_class, mock_config
    ):
        """Test pagination handling."""
        mock_session = MagicMock()

        # First call returns partial results
        first_response = MagicMock()
        first_response.json.return_value = {
            "status_code": 1,
            "number_of_total_results": 3,
            "results": [
                {"id": 1, "issue_number": "1", "cover_date": "", "name": None},
                {"id": 2, "issue_number": "2", "cover_date": "", "name": None},
            ],
        }

        # Second call returns remaining
        second_response = MagicMock()
        second_response.json.return_value = {
            "status_code": 1,
            "number_of_total_results": 3,
            "results": [
                {"id": 3, "issue_number": "3", "cover_date": "", "name": None},
            ],
        }

        mock_session.get.side_effect = [first_response, second_response]
        mock_session_class.return_value = mock_session

        client = ComicVineClient(mock_config)
        client.session = mock_session

        issues = client.get_volume_issues(12345)

        assert len(issues) == 3

    @patch("cbro_parser.comicvine.api_client.requests.Session")
    def test_get_volume_issues_handles_many_pages(
        self, mock_session_class, mock_config
    ):
        """Test that pagination works iteratively for many pages.

        Regression test for: Recursive Pagination Risk
        - api_client.py:206 used recursive calls for pagination
        - Could stack overflow for series with 10,000+ issues
        - Should use iterative approach instead
        """
        mock_session = MagicMock()

        # Simulate 5 pages of results (500 total issues)
        responses = []
        for page in range(5):
            response = MagicMock()
            response.json.return_value = {
                "status_code": 1,
                "number_of_total_results": 500,
                "results": [
                    {
                        "id": page * 100 + i,
                        "issue_number": str(page * 100 + i + 1),
                        "cover_date": "",
                        "name": None,
                    }
                    for i in range(100)
                ],
            }
            responses.append(response)

        mock_session.get.side_effect = responses
        mock_session_class.return_value = mock_session

        client = ComicVineClient(mock_config)
        client.session = mock_session

        issues = client.get_volume_issues(12345)

        # Should have all 500 issues
        assert len(issues) == 500
        # Should have made 5 requests
        assert mock_session.get.call_count == 5

    @patch("cbro_parser.comicvine.api_client.requests.Session")
    def test_get_volume_issues_handles_missing_fields(
        self, mock_session_class, mock_config
    ):
        """Test handling of missing optional fields."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status_code": 1,
            "number_of_total_results": 1,
            "results": [
                {
                    "id": 99999,
                    "issue_number": None,
                    "cover_date": None,
                    "name": None,
                },
            ],
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ComicVineClient(mock_config)
        client.session = mock_session

        issues = client.get_volume_issues(12345)

        assert len(issues) == 1
        assert issues[0].issue_number == ""
        assert issues[0].cover_date == ""


class TestComicVineClientSearchIssue:
    """Tests for search_issue method."""

    @patch("cbro_parser.comicvine.api_client.requests.Session")
    def test_search_issue_basic(self, mock_session_class, mock_config):
        """Test basic issue search."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status_code": 1,
            "results": [
                {
                    "id": 99999,
                    "volume": {"id": 12345},
                    "issue_number": "1",
                    "cover_date": "2016-06-01",
                    "name": "I Am Gotham",
                },
            ],
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ComicVineClient(mock_config)
        client.session = mock_session

        issue = client.search_issue("Batman", "1")

        assert issue is not None
        assert issue.issue_number == "1"

    @patch("cbro_parser.comicvine.api_client.requests.Session")
    def test_search_issue_with_year_filter(self, mock_session_class, mock_config):
        """Test issue search with year filter."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status_code": 1,
            "results": [
                {
                    "id": 11111,
                    "volume": {"id": 12345},
                    "issue_number": "1",
                    "cover_date": "2011-06-01",
                    "name": "Issue 1",
                },
                {
                    "id": 22222,
                    "volume": {"id": 54321},
                    "issue_number": "1",
                    "cover_date": "2016-06-01",
                    "name": "Issue 1",
                },
            ],
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ComicVineClient(mock_config)
        client.session = mock_session

        issue = client.search_issue("Batman", "1", year=2016)

        # Should get the 2016 one
        assert issue is not None
        assert issue.cv_issue_id == 22222

    @patch("cbro_parser.comicvine.api_client.requests.Session")
    def test_search_issue_not_found(self, mock_session_class, mock_config):
        """Test issue search when not found."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status_code": 1,
            "results": [],
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ComicVineClient(mock_config)
        client.session = mock_session

        issue = client.search_issue("Nonexistent", "999")

        assert issue is None


class TestComicVineClientErrors:
    """Tests for error handling."""

    @patch("cbro_parser.comicvine.api_client.requests.Session")
    def test_api_error_raised(self, mock_session_class, mock_config):
        """Test that API errors are raised."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status_code": 100,
            "error": "Invalid API Key",
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = ComicVineClient(mock_config)
        client.session = mock_session

        with pytest.raises(ComicVineAPIError, match="Invalid API Key"):
            client.search_volumes("Test")

    def test_remaining_requests_passthrough(self, mock_config):
        """Test that remaining_requests delegates to rate limiter."""
        rate_limiter = RateLimiter(max_requests=100, min_interval=0)
        client = ComicVineClient(mock_config, rate_limiter)

        assert client.remaining_requests() == 100

        # After acquiring, should decrease
        rate_limiter.acquire()
        assert client.remaining_requests() == 99
