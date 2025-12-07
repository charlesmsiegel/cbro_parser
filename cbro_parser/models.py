"""Pydantic models for CBRO Parser."""

from uuid import uuid4

from pydantic import BaseModel, Field


class ReadingOrderEntry(BaseModel):
    """Entry from CBRO index pages representing an available reading order."""

    name: str
    url: str
    publisher: str  # "Marvel", "DC", or "Other"
    category: str  # "characters", "events", or "master"

    def display_name(self) -> str:
        """Return formatted display name for GUI."""
        return f"{self.name} ({self.publisher} - {self.category.title()})"


class ParsedIssue(BaseModel):
    """Raw issue parsed from a CBRO reading order page."""

    series_name: str
    issue_number: str
    volume_hint: str | None = None  # e.g., "2" from "Vol. 2"
    year_hint: str | None = None  # e.g., "2009" from "(2009)"
    format_type: str | None = None  # e.g., "Annual", "Second Feature"
    notes: str | None = None  # Extra context from page


class ComicVineVolume(BaseModel):
    """Volume (series) data from ComicVine."""

    cv_volume_id: int
    name: str
    start_year: int
    publisher: str
    issue_count: int
    aliases: list[str] = Field(default_factory=list)


class ComicVineIssue(BaseModel):
    """Issue data from ComicVine."""

    cv_issue_id: int
    cv_volume_id: int
    issue_number: str
    cover_date: str  # YYYY-MM-DD format
    name: str | None = None


class MatchedBook(BaseModel):
    """Fully matched book ready for .cbl output."""

    series: str
    number: str
    volume: str  # Start year of volume (e.g., "2005")
    year: str  # Publication year of issue
    format_type: str | None = None  # e.g., "Annual", "Second Feature"
    book_id: str = Field(default_factory=lambda: str(uuid4()))

    # Optional tracking for debugging
    cv_volume_id: int | None = None
    cv_issue_id: int | None = None
    confidence: float = 1.0


class ReadingList(BaseModel):
    """Complete reading list for .cbl output."""

    name: str
    books: list[MatchedBook] = Field(default_factory=list)
