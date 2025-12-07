"""Shared pytest fixtures for CBRO Parser tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cbro_parser.models import (
    ComicVineIssue,
    ComicVineVolume,
    MatchedBook,
    ParsedIssue,
    ReadingList,
    ReadingOrderEntry,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db(temp_dir):
    """Create a temporary database path."""
    return temp_dir / "test_cache.db"


@pytest.fixture
def temp_env_file(temp_dir):
    """Create a temporary .env file with a test API key."""
    env_path = temp_dir / ".env"
    env_path.write_text("COMICVINE_API=test_api_key_12345")
    return env_path


@pytest.fixture
def mock_config(temp_db):
    """Create a mock configuration object."""
    config = MagicMock()
    config.comicvine_api_key = "test_api_key"
    config.cv_base_url = "https://comicvine.gamespot.com/api"
    config.cv_rate_limit_requests = 200
    config.cv_rate_limit_window_seconds = 900
    config.cv_safe_delay_seconds = 0.01  # Fast for tests
    config.cbro_base_url = "https://www.comicbookreadingorders.com"
    config.cbro_crawl_delay_seconds = 0.01  # Fast for tests
    config.cache_db_path = temp_db
    config.cache_expiry_days = 30
    config.default_output_dir = Path("test_output")
    return config


@pytest.fixture
def sample_volume():
    """Create a sample ComicVine volume."""
    return ComicVineVolume(
        cv_volume_id=12345,
        name="Green Lantern",
        start_year=2005,
        publisher="DC Comics",
        issue_count=67,
        aliases=["GL", "Green Lantern Vol. 4"],
    )


@pytest.fixture
def sample_volume_2011():
    """Create another sample ComicVine volume."""
    return ComicVineVolume(
        cv_volume_id=54321,
        name="Green Lantern",
        start_year=2011,
        publisher="DC Comics",
        issue_count=52,
        aliases=["Green Lantern New 52"],
    )


@pytest.fixture
def sample_issue():
    """Create a sample ComicVine issue."""
    return ComicVineIssue(
        cv_issue_id=99999,
        cv_volume_id=12345,
        issue_number="1",
        cover_date="2005-07-01",
        name="No Fear",
    )


@pytest.fixture
def sample_issues():
    """Create a list of sample issues for a volume."""
    return [
        ComicVineIssue(
            cv_issue_id=99999,
            cv_volume_id=12345,
            issue_number="1",
            cover_date="2005-07-01",
            name="No Fear Part 1",
        ),
        ComicVineIssue(
            cv_issue_id=99998,
            cv_volume_id=12345,
            issue_number="2",
            cover_date="2005-08-01",
            name="No Fear Part 2",
        ),
        ComicVineIssue(
            cv_issue_id=99997,
            cv_volume_id=12345,
            issue_number="3",
            cover_date="2005-09-01",
            name="No Fear Part 3",
        ),
    ]


@pytest.fixture
def sample_parsed_issue():
    """Create a sample parsed issue."""
    return ParsedIssue(
        series_name="Green Lantern",
        issue_number="1",
        volume_hint=None,
        year_hint="2005",
        format_type=None,
        notes=None,
    )


@pytest.fixture
def sample_matched_book():
    """Create a sample matched book."""
    return MatchedBook(
        series="Green Lantern",
        number="1",
        volume="2005",
        year="2005",
        format_type=None,
        cv_volume_id=12345,
        cv_issue_id=99999,
        confidence=1.0,
    )


@pytest.fixture
def sample_reading_list(sample_matched_book):
    """Create a sample reading list."""
    return ReadingList(
        name="Green Lantern Reading Order",
        books=[sample_matched_book],
    )


@pytest.fixture
def sample_reading_order_entry():
    """Create a sample reading order entry."""
    return ReadingOrderEntry(
        name="Green Lantern",
        url="https://www.comicbookreadingorders.com/dc/characters/green-lantern-reading-order/",
        publisher="DC",
        category="characters",
    )


@pytest.fixture
def sample_cbl_content():
    """Sample CBL file content for testing."""
    return """<?xml version="1.0"?>
<ReadingList xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Name>Test Reading List</Name>
  <Books>
    <Book Series="Green Lantern" Number="1" Volume="2005" Year="2005">
      <Id>test-uuid-1234</Id>
    </Book>
    <Book Series="Green Lantern" Number="2" Volume="2005" Year="2005" Format="Annual">
      <Id>test-uuid-5678</Id>
    </Book>
  </Books>
  <Matchers/>
</ReadingList>"""


@pytest.fixture
def sample_cbro_html():
    """Sample CBRO reading order page HTML."""
    return """
<!DOCTYPE html>
<html>
<head><title>Green Lantern Reading Order</title></head>
<body>
<article>
<h1>Green Lantern Reading Order</h1>
<p>Start your Green Lantern journey here!</p>
<p>Green Lantern #1</p>
<p>Green Lantern #2</p>
<p>Green Lantern Vol. 4 #3</p>
<p>Green Lantern Corps #1 (2006)</p>
<p>Green Lantern #4 - Sinestro Returns</p>
<p>Green Lantern Annual #1</p>
<p>(2005)</p>
<p>Green Lantern #5</p>
</article>
</body>
</html>
"""


@pytest.fixture
def sample_index_html():
    """Sample CBRO index page HTML."""
    return """
<!DOCTYPE html>
<html>
<head><title>DC Characters</title></head>
<body>
<article>
<h1>DC Character Reading Orders</h1>
<ul>
<li><a href="/dc/characters/green-lantern-reading-order/">Green Lantern</a></li>
<li><a href="/dc/characters/batman-reading-order/">Batman</a></li>
<li><a href="/dc/characters/superman-reading-order/">Superman</a></li>
<li><a href="#anchor">Skip this</a></li>
<li><a href="/wp-content/image.jpg">Skip image</a></li>
</ul>
</article>
</body>
</html>
"""
