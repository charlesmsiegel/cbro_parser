"""Tests for cbro_parser.models module."""

import pytest
from pydantic import ValidationError

from cbro_parser.models import (
    ComicVineIssue,
    ComicVineVolume,
    MatchedBook,
    ParsedIssue,
    ReadingList,
    ReadingOrderEntry,
)


class TestReadingOrderEntry:
    """Tests for ReadingOrderEntry model."""

    def test_create_basic(self):
        """Test creating a basic reading order entry."""
        entry = ReadingOrderEntry(
            name="Batman",
            url="https://example.com/batman",
            publisher="DC",
            category="characters",
        )
        assert entry.name == "Batman"
        assert entry.url == "https://example.com/batman"
        assert entry.publisher == "DC"
        assert entry.category == "characters"

    def test_display_name(self):
        """Test the display_name method."""
        entry = ReadingOrderEntry(
            name="Batman",
            url="https://example.com/batman",
            publisher="DC",
            category="characters",
        )
        assert entry.display_name() == "Batman (DC - Characters)"

    def test_display_name_events(self):
        """Test display_name for events category."""
        entry = ReadingOrderEntry(
            name="Crisis on Infinite Earths",
            url="https://example.com/crisis",
            publisher="DC",
            category="events",
        )
        assert entry.display_name() == "Crisis on Infinite Earths (DC - Events)"

    def test_missing_required_field(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            ReadingOrderEntry(name="Batman", url="https://example.com")


class TestParsedIssue:
    """Tests for ParsedIssue model."""

    def test_create_minimal(self):
        """Test creating a parsed issue with minimal fields."""
        issue = ParsedIssue(
            series_name="Batman",
            issue_number="1",
        )
        assert issue.series_name == "Batman"
        assert issue.issue_number == "1"
        assert issue.volume_hint is None
        assert issue.year_hint is None
        assert issue.format_type is None
        assert issue.notes is None

    def test_create_full(self):
        """Test creating a parsed issue with all fields."""
        issue = ParsedIssue(
            series_name="Batman",
            issue_number="42",
            volume_hint="2",
            year_hint="2016",
            format_type="Annual",
            notes="First appearance of new villain",
        )
        assert issue.series_name == "Batman"
        assert issue.issue_number == "42"
        assert issue.volume_hint == "2"
        assert issue.year_hint == "2016"
        assert issue.format_type == "Annual"
        assert issue.notes == "First appearance of new villain"

    def test_fractional_issue_number(self):
        """Test issue with fractional number."""
        issue = ParsedIssue(
            series_name="Batman",
            issue_number="0.5",
        )
        assert issue.issue_number == "0.5"


class TestComicVineVolume:
    """Tests for ComicVineVolume model."""

    def test_create_basic(self):
        """Test creating a basic volume."""
        volume = ComicVineVolume(
            cv_volume_id=12345,
            name="Batman",
            start_year=2016,
            publisher="DC Comics",
            issue_count=85,
        )
        assert volume.cv_volume_id == 12345
        assert volume.name == "Batman"
        assert volume.start_year == 2016
        assert volume.publisher == "DC Comics"
        assert volume.issue_count == 85
        assert volume.aliases == []

    def test_create_with_aliases(self):
        """Test creating a volume with aliases."""
        volume = ComicVineVolume(
            cv_volume_id=12345,
            name="The Amazing Spider-Man",
            start_year=1963,
            publisher="Marvel",
            issue_count=700,
            aliases=["Amazing Spider-Man", "ASM"],
        )
        assert volume.aliases == ["Amazing Spider-Man", "ASM"]


class TestComicVineIssue:
    """Tests for ComicVineIssue model."""

    def test_create_basic(self):
        """Test creating a basic issue."""
        issue = ComicVineIssue(
            cv_issue_id=99999,
            cv_volume_id=12345,
            issue_number="1",
            cover_date="2016-06-01",
        )
        assert issue.cv_issue_id == 99999
        assert issue.cv_volume_id == 12345
        assert issue.issue_number == "1"
        assert issue.cover_date == "2016-06-01"
        assert issue.name is None

    def test_create_with_name(self):
        """Test creating an issue with name."""
        issue = ComicVineIssue(
            cv_issue_id=99999,
            cv_volume_id=12345,
            issue_number="1",
            cover_date="2016-06-01",
            name="I Am Gotham Part 1",
        )
        assert issue.name == "I Am Gotham Part 1"


class TestMatchedBook:
    """Tests for MatchedBook model."""

    def test_create_basic(self):
        """Test creating a basic matched book."""
        book = MatchedBook(
            series="Batman",
            number="1",
            volume="2016",
            year="2016",
        )
        assert book.series == "Batman"
        assert book.number == "1"
        assert book.volume == "2016"
        assert book.year == "2016"
        assert book.format_type is None
        assert book.book_id  # Should have auto-generated UUID
        assert book.cv_volume_id is None
        assert book.cv_issue_id is None
        assert book.confidence == 1.0

    def test_create_with_cv_ids(self):
        """Test creating a matched book with ComicVine IDs."""
        book = MatchedBook(
            series="Batman",
            number="1",
            volume="2016",
            year="2016",
            cv_volume_id=12345,
            cv_issue_id=99999,
            confidence=0.95,
        )
        assert book.cv_volume_id == 12345
        assert book.cv_issue_id == 99999
        assert book.confidence == 0.95

    def test_create_with_format(self):
        """Test creating a matched book with format type."""
        book = MatchedBook(
            series="Batman",
            number="1",
            volume="2016",
            year="2016",
            format_type="Annual",
        )
        assert book.format_type == "Annual"

    def test_book_id_is_uuid(self):
        """Test that book_id is a valid UUID format."""
        book = MatchedBook(
            series="Batman",
            number="1",
            volume="2016",
            year="2016",
        )
        # UUID format: 8-4-4-4-12 hex characters
        parts = book.book_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12

    def test_different_books_have_different_ids(self):
        """Test that different books get unique IDs."""
        book1 = MatchedBook(series="Batman", number="1", volume="2016", year="2016")
        book2 = MatchedBook(series="Batman", number="1", volume="2016", year="2016")
        assert book1.book_id != book2.book_id


class TestReadingList:
    """Tests for ReadingList model."""

    def test_create_empty(self):
        """Test creating an empty reading list."""
        reading_list = ReadingList(name="Test List")
        assert reading_list.name == "Test List"
        assert reading_list.books == []

    def test_create_with_books(self):
        """Test creating a reading list with books."""
        book = MatchedBook(
            series="Batman",
            number="1",
            volume="2016",
            year="2016",
        )
        reading_list = ReadingList(name="Batman Reading Order", books=[book])
        assert reading_list.name == "Batman Reading Order"
        assert len(reading_list.books) == 1
        assert reading_list.books[0].series == "Batman"

    def test_create_with_multiple_books(self):
        """Test creating a reading list with multiple books."""
        books = [
            MatchedBook(series="Batman", number="1", volume="2016", year="2016"),
            MatchedBook(series="Batman", number="2", volume="2016", year="2016"),
            MatchedBook(series="Batman", number="3", volume="2016", year="2016"),
        ]
        reading_list = ReadingList(name="Batman Reading Order", books=books)
        assert len(reading_list.books) == 3
