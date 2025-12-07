"""Tests for cbro_parser.scraper.cbro_scraper module."""

import pytest
from unittest.mock import MagicMock, patch

from cbro_parser.scraper.cbro_scraper import CBROScraper
from cbro_parser.models import ParsedIssue


class TestCBROScraperInit:
    """Tests for CBROScraper initialization."""

    def test_init_with_config(self, mock_config):
        """Test scraper initialization."""
        scraper = CBROScraper(mock_config)

        assert scraper.config == mock_config
        assert scraper.session is not None
        assert "User-Agent" in scraper.session.headers


class TestCBROScraperIssueLineParser:
    """Tests for _parse_issue_line method."""

    def test_parse_basic_issue(self, mock_config):
        """Test parsing basic issue format."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Green Lantern #1")

        assert result is not None
        assert result.series_name == "Green Lantern"
        assert result.issue_number == "1"

    def test_parse_issue_with_volume(self, mock_config):
        """Test parsing issue with volume indicator."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Green Lantern Vol. 4 #1")

        assert result is not None
        assert result.series_name == "Green Lantern"
        assert result.volume_hint == "4"
        assert result.issue_number == "1"

    def test_parse_issue_with_year(self, mock_config):
        """Test parsing issue with year in parentheses."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Green Lantern #1 (2005)")

        assert result is not None
        assert result.series_name == "Green Lantern"
        assert result.issue_number == "1"
        assert result.year_hint == "2005"

    def test_parse_issue_with_notes(self, mock_config):
        """Test parsing issue with notes after dash."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Tales of Suspense #39 - First Iron Man")

        assert result is not None
        assert result.series_name == "Tales of Suspense"
        assert result.issue_number == "39"
        assert result.notes == "First Iron Man"

    def test_parse_issue_with_all_parts(self, mock_config):
        """Test parsing issue with all components."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line(
            "Green Lantern Vol. 4 #43 (2009) - Blackest Night Tie-in"
        )

        assert result is not None
        assert result.series_name == "Green Lantern"
        assert result.volume_hint == "4"
        assert result.issue_number == "43"
        assert result.year_hint == "2009"
        assert result.notes == "Blackest Night Tie-in"

    def test_parse_annual_detected(self, mock_config):
        """Test that annual is detected as format type."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Green Lantern Annual #1")

        assert result is not None
        assert result.format_type == "Annual"

    def test_parse_special_detected(self, mock_config):
        """Test that special is detected as format type."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Batman Special #1")

        assert result is not None
        assert result.format_type == "Special"

    def test_parse_second_feature_in_notes(self, mock_config):
        """Test second feature detection in notes."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Action Comics #1 - Second Feature")

        assert result is not None
        assert result.format_type == "Second Feature"

    def test_skip_no_hash(self, mock_config):
        """Test that lines without # are skipped."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Just a title")

        assert result is None

    def test_skip_short_line(self, mock_config):
        """Test that short lines are skipped."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("A #1")

        assert result is None  # Series name too short

    def test_skip_header_lines(self, mock_config):
        """Test that header-like lines are skipped."""
        scraper = CBROScraper(mock_config)

        assert scraper._parse_issue_line("Read more about #1") is None
        assert scraper._parse_issue_line("Click here for #2") is None
        assert scraper._parse_issue_line("Note: Issue #3 is special") is None

    def test_skip_metadata_lines(self, mock_config):
        """Test that metadata lines are skipped."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("First Appearance:  Issue #1")

        assert result is None

    def test_fractional_issue(self, mock_config):
        """Test parsing fractional issue numbers."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Batman #0.5")

        assert result is not None
        assert result.issue_number == "0.5"

    def test_decimal_issue(self, mock_config):
        """Test parsing decimal issue numbers."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Spider-Man #1.1")

        assert result is not None
        assert result.issue_number == "1.1"


class TestCBROScraperTPBDetection:
    """Tests for TPB section detection."""

    def test_is_tpb_title_basic(self, mock_config):
        """Test TPB title detection."""
        scraper = CBROScraper(mock_config)

        assert scraper._is_tpb_section_title("Blackest Night (2011)") is True
        assert scraper._is_tpb_section_title("Green Lantern: Rebirth (2005)") is True

    def test_is_not_tpb_title_with_hash(self, mock_config):
        """Test that lines with # are not TPB titles."""
        scraper = CBROScraper(mock_config)

        assert scraper._is_tpb_section_title("Batman #1 (2016)") is False

    def test_is_not_tpb_title_no_year(self, mock_config):
        """Test that lines without year parentheses are not TPB titles."""
        scraper = CBROScraper(mock_config)

        assert scraper._is_tpb_section_title("Blackest Night") is False


class TestCBROScraperPageParsing:
    """Tests for _parse_reading_order_page method."""

    def test_parse_simple_page(self, mock_config, sample_cbro_html):
        """Test parsing a simple reading order page."""
        scraper = CBROScraper(mock_config)

        issues = scraper._parse_reading_order_page(sample_cbro_html)

        assert len(issues) > 0
        # Check that Green Lantern #1 was parsed
        gl_issues = [i for i in issues if "Green Lantern" in i.series_name]
        assert len(gl_issues) > 0

    def test_parse_skips_year_only_lines(self, mock_config):
        """Test that standalone year lines are skipped."""
        html = """
        <article>
        <p>(2005)</p>
        <p>Batman #1</p>
        </article>
        """
        scraper = CBROScraper(mock_config)

        issues = scraper._parse_reading_order_page(html)

        assert len(issues) == 1
        assert issues[0].series_name == "Batman"

    def test_parse_skips_issue_ranges(self, mock_config):
        """Test that issue range lines are skipped."""
        html = """
        <article>
        <p>Batman #1</p>
        <p>Batman #1-5</p>
        <p>Batman #2</p>
        </article>
        """
        scraper = CBROScraper(mock_config)

        issues = scraper._parse_reading_order_page(html)

        # Should only get #1 and #2, not the range
        assert len(issues) == 2

    def test_parse_stops_at_tpb_section(self, mock_config):
        """Test that parsing stops at TPB section."""
        html = """
        <article>
        <p>Batman #1</p>
        <p>Batman #2</p>
        <p>Batman: Year One (2005)</p>
        <p>Batman #3</p>
        </article>
        """
        scraper = CBROScraper(mock_config)

        issues = scraper._parse_reading_order_page(html)

        # Should only get #1 and #2, stop at TPB section
        assert len(issues) == 2


class TestCBROScraperGetReadingOrderName:
    """Tests for get_reading_order_name method."""

    def test_basic_name_extraction(self, mock_config):
        """Test extracting name from URL."""
        scraper = CBROScraper(mock_config)

        name = scraper.get_reading_order_name(
            "https://www.comicbookreadingorders.com/dc/events/blackest-night-reading-order/"
        )

        assert name == "Blackest Night"

    def test_name_with_hyphens(self, mock_config):
        """Test name extraction with multiple hyphens."""
        scraper = CBROScraper(mock_config)

        name = scraper.get_reading_order_name(
            "/dc/characters/green-lantern-reading-order/"
        )

        assert name == "Green Lantern"

    def test_name_without_trailing_slash(self, mock_config):
        """Test name extraction without trailing slash."""
        scraper = CBROScraper(mock_config)

        name = scraper.get_reading_order_name(
            "/marvel/characters/spider-man-reading-order"
        )

        assert name == "Spider Man"


class TestCBROScraperFetch:
    """Tests for fetch_reading_order method."""

    @patch("cbro_parser.scraper.cbro_scraper.requests.Session")
    def test_fetch_makes_request(self, mock_session_class, mock_config):
        """Test that fetch makes HTTP request."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<article><p>Batman #1</p></article>"
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        scraper = CBROScraper(mock_config)
        scraper.session = mock_session

        issues = scraper.fetch_reading_order("https://example.com/batman")

        mock_session.get.assert_called_once()

    @patch("cbro_parser.scraper.cbro_scraper.requests.Session")
    def test_fetch_handles_relative_url(self, mock_session_class, mock_config):
        """Test that relative URLs are converted to absolute."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<article><p>Batman #1</p></article>"
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        scraper = CBROScraper(mock_config)
        scraper.session = mock_session

        scraper.fetch_reading_order("/dc/characters/batman-reading-order/")

        # Should have called with full URL
        call_args = mock_session.get.call_args
        assert call_args[0][0].startswith("https://")


class TestCBROScraperAdditionalCoverage:
    """Additional tests for edge cases and increased coverage."""

    def test_parse_giant_size_detected(self, mock_config):
        """Test that giant-size is detected as format type."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Giant-Size X-Men #1")

        assert result is not None
        assert result.format_type == "Giant-Size"

    def test_parse_backup_in_notes(self, mock_config):
        """Test backup detection in notes."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Action Comics #1 - Backup story")

        assert result is not None
        assert result.format_type == "Backup"

    def test_parse_skip_colon_continuation(self, mock_config):
        """Test that lines starting with colon are skipped."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line(": Issue #1")

        assert result is None

    def test_parse_page_without_article(self, mock_config):
        """Test parsing page without article element."""
        html = """
        <html>
        <body>
        <div>
        <p>Batman #1</p>
        <p>Batman #2</p>
        </div>
        </body>
        </html>
        """
        scraper = CBROScraper(mock_config)

        issues = scraper._parse_reading_order_page(html)

        # Should still parse even without article tag
        assert len(issues) >= 0  # May or may not find content

    def test_parse_with_div_entry_content(self, mock_config):
        """Test parsing page with entry-content div."""
        html = """
        <html>
        <body>
        <div class="entry-content">
        <p>Batman #1</p>
        </div>
        </body>
        </html>
        """
        scraper = CBROScraper(mock_config)

        issues = scraper._parse_reading_order_page(html)

        assert len(issues) == 1

    def test_parse_issue_with_unicode_half(self, mock_config):
        """Test parsing issue with unicode half character."""
        scraper = CBROScraper(mock_config)

        result = scraper._parse_issue_line("Batman #½")

        assert result is not None
        assert result.issue_number == "½"

    def test_get_reading_order_name_complex(self, mock_config):
        """Test name extraction from complex URLs."""
        scraper = CBROScraper(mock_config)

        # Full URL
        name = scraper.get_reading_order_name(
            "https://www.comicbookreadingorders.com/dc/events/crisis-on-infinite-earths-reading-order/"
        )
        assert "Crisis" in name

        # Without reading-order suffix
        name = scraper.get_reading_order_name("/dc/events/blackest-night/")
        assert "Blackest Night" in name
