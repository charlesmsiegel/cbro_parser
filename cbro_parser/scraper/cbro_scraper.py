"""Scraper for comicbookreadingorders.com reading order pages."""

import logging
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..config import Config
from ..models import ParsedIssue

logger = logging.getLogger(__name__)


class CBROScraper:
    """Scraper for comicbookreadingorders.com reading order pages."""

    # Issue parsing patterns
    # Matches: "Series Name #123" with optional volume, year, and notes
    ISSUE_PATTERN = re.compile(
        r"^(?P<series>.+?)\s*"  # Series name (non-greedy)
        r"(?:Vol\.?\s*(?P<volume>\d+)\s*)?"  # Optional volume
        r"#(?P<number>[\d½]+(?:[./][\dA-Za-z]+)?)"  # Issue number
        r"(?:\s*\((?P<year>\d{4})\))?"  # Optional year in parentheses
        r"(?:\s*[-–—]\s*(?P<notes>.+))?$",  # Optional notes after dash
        re.IGNORECASE,
    )

    # Alternative pattern for "Series Name Vol. X #Y" format
    ALT_PATTERN = re.compile(
        r"^(?P<series>.+?)\s+"
        r"Vol(?:ume)?\.?\s*(?P<volume>\d+)\s*"
        r"#(?P<number>[\d½]+(?:[./][\dA-Za-z]+)?)"
        r"(?:\s*\((?P<year>\d{4})\))?"
        r"(?:\s*[-–—]\s*(?P<notes>.+))?$",
        re.IGNORECASE,
    )

    # Pattern to detect TPB section titles: "Title (YYYY)" without a #
    # These mark the start of trade paperback breakdowns which we should skip
    TPB_TITLE_PATTERN = re.compile(
        r"^[A-Za-z][\w\s:'\-]+\s*\(\d{4}\)$"
    )

    # Pattern to detect issue ranges like "#0-8" or "#43-52" (TPB contents)
    ISSUE_RANGE_PATTERN = re.compile(
        r"#\d+\s*[-–—]\s*\d+"
    )

    def __init__(self, config: Config):
        """
        Initialize the scraper.

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
        self._last_request_time = 0.0

    def _respect_crawl_delay(self) -> None:
        """Ensure we respect the 5-second crawl-delay from robots.txt."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.config.cbro_crawl_delay_seconds:
            time.sleep(self.config.cbro_crawl_delay_seconds - elapsed)
        self._last_request_time = time.time()

    def fetch_reading_order(self, url: str) -> list[ParsedIssue]:
        """
        Fetch and parse a reading order page.

        Args:
            url: Full URL or relative path to reading order page.

        Returns:
            List of parsed issues in reading order.
        """
        if not url.startswith("http"):
            url = urljoin(self.config.cbro_base_url, url)

        self._respect_crawl_delay()

        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        return self._parse_reading_order_page(response.text)

    def _parse_reading_order_page(self, html: str) -> list[ParsedIssue]:
        """Parse the HTML content into a list of issues."""
        soup = BeautifulSoup(html, "lxml")
        issues = []
        in_tpb_section = False

        # Statistics for logging
        stats = {
            "total_lines": 0,
            "empty_lines": 0,
            "tpb_section_lines": 0,
            "year_lines": 0,
            "range_lines": 0,
            "no_hash_lines": 0,
            "header_lines": 0,
            "no_match_lines": 0,
            "short_series_lines": 0,
            "parsed_issues": 0,
        }

        # Primary content is typically in article or main content div
        content = soup.find("article") or soup.find(
            "div", class_="entry-content"
        )
        if not content:
            content = soup
            logger.debug("No article/entry-content found, using full page")

        # Get all text content as lines for sequential processing
        text = content.get_text(separator="\n", strip=True)
        lines = text.split("\n")
        stats["total_lines"] = len(lines)

        for line in lines:
            line = line.strip()
            if not line:
                stats["empty_lines"] += 1
                continue

            # Check if we've hit the TPB section (stop parsing)
            # TPB titles look like "Blackest Night (2011)" - title with year, no #
            if self._is_tpb_section_title(line):
                in_tpb_section = True
                logger.debug(f"TPB section started at: {line}")
                continue

            # Skip everything in TPB section
            if in_tpb_section:
                stats["tpb_section_lines"] += 1
                continue

            # Skip standalone year lines like "(2009)"
            if re.match(r"^\(\d{4}\)$", line):
                stats["year_lines"] += 1
                logger.debug(f"Skipped year line: {line}")
                continue

            # Skip issue range lines like "Blackest Night #0-8" (TPB contents)
            if self.ISSUE_RANGE_PATTERN.search(line):
                stats["range_lines"] += 1
                logger.debug(f"Skipped range line: {line}")
                continue

            parsed = self._parse_issue_line(line, stats)
            if parsed:
                issues.append(parsed)
                stats["parsed_issues"] += 1

        # Log statistics
        logger.info(
            f"Parsing complete: {stats['parsed_issues']} issues found from "
            f"{stats['total_lines']} lines"
        )
        logger.debug(
            f"Line breakdown: "
            f"empty={stats['empty_lines']}, "
            f"tpb_section={stats['tpb_section_lines']}, "
            f"year={stats['year_lines']}, "
            f"range={stats['range_lines']}, "
            f"no_hash={stats['no_hash_lines']}, "
            f"headers={stats['header_lines']}, "
            f"no_match={stats['no_match_lines']}, "
            f"short_series={stats['short_series_lines']}"
        )

        return issues

    def _is_tpb_section_title(self, line: str) -> bool:
        """
        Check if a line is a Trade Paperback section title.

        TPB titles look like "Blackest Night (2011)" - a title followed
        by a year in parentheses, WITHOUT a # character.
        """
        # Must not contain # (would be an issue)
        if "#" in line:
            return False

        # Must match the TPB title pattern
        if self.TPB_TITLE_PATTERN.match(line):
            return True

        return False

    def _parse_issue_line(
        self, line: str, stats: dict | None = None
    ) -> ParsedIssue | None:
        """
        Parse a single line into a ParsedIssue.

        Handles formats like:
        - "Green Lantern #43"
        - "Green Lantern Vol. 2 #76"
        - "Iron Man Vol. 3 #1 (1998)"
        - "Tales of Suspense #39 - First Iron Man"
        - "Blackest Night #1"

        Args:
            line: Text line to parse.
            stats: Optional dictionary to track parsing statistics.

        Returns:
            ParsedIssue or None if line doesn't match.
        """
        # Skip lines that are clearly not issues
        if len(line) < 5 or "#" not in line:
            if stats:
                stats["no_hash_lines"] += 1
            return None

        # Skip lines that look like headers, navigation, or metadata
        skip_prefixes = (
            "Read", "Click", "See", "Check", "Note:",
            "Powers:", "Created by",
        )
        if line.startswith(skip_prefixes):
            if stats:
                stats["header_lines"] += 1
            logger.debug(f"Skipped header line: {line}")
            return None

        # Skip lines that start with ":" - these are continuations of metadata fields
        # (e.g., "First Appearance" on one line, ":  Issue #1" on next)
        if line.startswith(":"):
            if stats:
                stats["header_lines"] += 1
            logger.debug(f"Skipped metadata continuation: {line}")
            return None

        # Skip metadata lines like "First Appearance:  Issue #1" or "Powers:  Something"
        # These have a label followed by colon and TWO spaces before the content
        if ":  " in line:
            # Check if it starts with a metadata label (word followed by :  )
            # Note: re is already imported at module level
            if re.match(r"^[A-Za-z ]+:  ", line):
                if stats:
                    stats["header_lines"] += 1
                logger.debug(f"Skipped metadata line: {line}")
                return None

        # Try primary pattern
        match = self.ISSUE_PATTERN.match(line)
        if not match:
            # Try alternative pattern
            match = self.ALT_PATTERN.match(line)

        if not match:
            if stats:
                stats["no_match_lines"] += 1
            logger.debug(f"No pattern match for: {line}")
            return None

        groups = match.groupdict()

        # Clean up series name
        series_name = groups["series"].strip()

        # Skip if series name is too short or looks invalid
        if len(series_name) < 2:
            if stats:
                stats["short_series_lines"] += 1
            logger.debug(f"Series name too short: {line}")
            return None

        # Determine format type from context
        format_type = None
        series_lower = series_name.lower()
        if "annual" in series_lower:
            format_type = "Annual"
        elif "special" in series_lower:
            format_type = "Special"
        elif "giant" in series_lower:
            format_type = "Giant-Size"

        # Check notes for format hints
        notes = groups.get("notes")
        if notes:
            notes_lower = notes.lower()
            if "second feature" in notes_lower:
                format_type = "Second Feature"
            elif "backup" in notes_lower:
                format_type = "Backup"

        logger.debug(
            f"Parsed: {series_name} #{groups['number']}"
            + (f" Vol.{groups.get('volume')}" if groups.get("volume") else "")
            + (f" ({groups.get('year')})" if groups.get("year") else "")
        )

        return ParsedIssue(
            series_name=series_name,
            issue_number=groups["number"],
            volume_hint=groups.get("volume"),
            year_hint=groups.get("year"),
            format_type=format_type,
            notes=notes,
        )

    def get_reading_order_name(self, url: str) -> str:
        """
        Extract a readable name from a reading order URL.

        Args:
            url: URL to the reading order.

        Returns:
            Human-readable name.
        """
        # Extract the slug from the URL
        path = url.rstrip("/").split("/")[-1]

        # Remove common suffixes
        path = re.sub(r"-reading-order$", "", path, flags=re.IGNORECASE)

        # Convert slug to title
        name = path.replace("-", " ").title()

        return name
