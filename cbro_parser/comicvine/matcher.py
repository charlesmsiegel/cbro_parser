"""Series and issue matching logic for ComicVine data."""

import logging
import re

from ..cache.sqlite_cache import SQLiteCache
from ..models import ComicVineIssue, ComicVineVolume, MatchedBook, ParsedIssue
from ..utils.text_normalizer import (
    build_search_query,
    extract_year_from_name,
    normalize_series_name,
)
from .api_client import ComicVineClient

logger = logging.getLogger(__name__)


class SeriesMatcher:
    """Matches parsed issues to ComicVine volumes and issues."""

    def __init__(
        self,
        cv_client: ComicVineClient,
        cache: SQLiteCache,
        interactive: bool = False,
    ):
        """
        Initialize the matcher.

        Args:
            cv_client: ComicVine API client.
            cache: SQLite cache for storing lookups.
            interactive: Whether to prompt for ambiguous matches.
        """
        self.cv_client = cv_client
        self.cache = cache
        self.interactive = interactive

        # In-memory cache for current session
        self._volume_issues_cache: dict[int, dict[str, ComicVineIssue]] = {}

    def match_issue(self, parsed: ParsedIssue) -> MatchedBook | None:
        """
        Match a parsed issue to ComicVine data.

        Args:
            parsed: The parsed issue from CBRO.

        Returns:
            MatchedBook if successful, None if no match found.
        """
        # Step 1: Normalize series name
        normalized = normalize_series_name(parsed.series_name)
        logger.debug(
            f"Matching: {parsed.series_name} #{parsed.issue_number} -> normalized: '{normalized}'"
        )

        # Step 2: Try to find volume (from cache first)
        volume = self._find_volume(normalized, parsed)
        if not volume:
            logger.debug(f"  No volume match for '{parsed.series_name}'")
            return None

        logger.debug(
            f"  Volume matched: {volume.name} ({volume.start_year}) [CV:{volume.cv_volume_id}]"
        )

        # Step 3: Find the specific issue
        issue = self._find_issue(volume, parsed.issue_number)
        if not issue:
            logger.debug(
                f"  Issue #{parsed.issue_number} not found in volume {volume.cv_volume_id}"
            )
            return None

        logger.debug(f"  Issue matched: #{issue.issue_number} [CV:{issue.cv_issue_id}]")

        # Step 4: Build the matched book
        pub_year = str(volume.start_year)  # Default to volume start year
        if issue.cover_date and len(issue.cover_date) >= 4:
            pub_year = issue.cover_date[:4]

        return MatchedBook(
            series=volume.name,
            number=parsed.issue_number,
            volume=str(volume.start_year),
            year=pub_year,
            format_type=parsed.format_type,
            cv_volume_id=volume.cv_volume_id,
            cv_issue_id=issue.cv_issue_id,
        )

    def _find_volume(
        self, normalized_name: str, parsed: ParsedIssue
    ) -> ComicVineVolume | None:
        """Find the correct volume for a series."""
        # Determine target year from hints
        target_year = None
        if parsed.year_hint:
            try:
                target_year = int(parsed.year_hint)
            except ValueError:
                pass
        elif parsed.volume_hint:
            # Volume hint might be year or volume number
            try:
                vol_num = int(parsed.volume_hint)
                if vol_num > 1900:  # It's a year
                    target_year = vol_num
            except ValueError:
                pass

        # Also check series name for embedded year
        if not target_year:
            target_year = extract_year_from_name(parsed.series_name)

        # Check cache first
        cached_volume_id = self.cache.get_volume_for_series(
            normalized_name, target_year
        )
        if cached_volume_id and cached_volume_id > 0:
            volume = self.cache.get_volume(cached_volume_id)
            if volume:
                logger.debug(
                    f"  Cache hit for '{normalized_name}' -> {volume.name} ({volume.start_year})"
                )
                return volume

        # Search ComicVine
        search_query = build_search_query(parsed.series_name)
        logger.debug(f"  Searching ComicVine for: '{search_query}'")
        volumes = self.cv_client.search_volumes(search_query, limit=15)

        if not volumes:
            logger.debug(f"  No volumes found on ComicVine for '{search_query}'")
            return None

        logger.debug(f"  Found {len(volumes)} candidate volumes")

        # Cache all results
        for vol in volumes:
            self.cache.cache_volume(vol)

        # Find best match
        best_match = self._select_best_volume(volumes, normalized_name, target_year)

        if best_match:
            # Cache the mapping
            self.cache.cache_series_mapping(
                normalized_name,
                best_match.start_year,
                best_match.cv_volume_id,
                confidence=1.0,
            )

        # Interactive mode: ask user if uncertain
        if not best_match and self.interactive and volumes:
            best_match = self._interactive_select_volume(parsed.series_name, volumes)
            if best_match:
                self.cache.cache_series_mapping(
                    normalized_name,
                    best_match.start_year,
                    best_match.cv_volume_id,
                    confidence=0.9,  # User-selected
                )

        return best_match

    def _select_best_volume(
        self,
        volumes: list[ComicVineVolume],
        normalized_name: str,
        target_year: int | None,
    ) -> ComicVineVolume | None:
        """Select the best matching volume from candidates."""
        scored_volumes = []

        for vol in volumes:
            score = 0.0
            vol_normalized = normalize_series_name(vol.name)

            # Exact name match
            if vol_normalized == normalized_name:
                score += 100
            elif normalized_name in vol_normalized or vol_normalized in normalized_name:
                score += 50

            # Check aliases
            for alias in vol.aliases:
                alias_normalized = normalize_series_name(alias)
                if alias_normalized == normalized_name:
                    score += 80
                    break
                elif (
                    normalized_name in alias_normalized
                    or alias_normalized in normalized_name
                ):
                    score += 30

            # Year matching
            if target_year and vol.start_year:
                year_diff = abs(vol.start_year - target_year)
                if year_diff == 0:
                    score += 30
                elif year_diff <= 1:
                    score += 20
                elif year_diff <= 3:
                    score += 10

            # Prefer volumes with more issues (more likely to be main series)
            if vol.issue_count > 10:
                score += 5
            elif vol.issue_count > 50:
                score += 10

            scored_volumes.append((score, vol))

        if not scored_volumes:
            return None

        # Sort by score descending
        scored_volumes.sort(key=lambda x: x[0], reverse=True)

        best_score, best_vol = scored_volumes[0]

        # Log top candidates for debugging
        for score, vol in scored_volumes[:3]:
            logger.debug(f"    Candidate: {vol.name} ({vol.start_year}) score={score}")

        # Only return if score is reasonable
        if best_score >= 50:
            return best_vol

        logger.debug(f"  Best score {best_score} < 50 threshold, no match")
        return None

    def _find_issue(
        self, volume: ComicVineVolume, issue_number: str
    ) -> ComicVineIssue | None:
        """Find a specific issue within a volume."""
        # Check cache first
        cached = self.cache.get_issue(volume.cv_volume_id, issue_number)
        if cached:
            return cached

        # Check in-memory cache
        if volume.cv_volume_id in self._volume_issues_cache:
            issue_map = self._volume_issues_cache[volume.cv_volume_id]
            if issue_number in issue_map:
                return issue_map[issue_number]

        # Fetch all issues for volume (more efficient than individual lookups)
        issues = self.cv_client.get_volume_issues(volume.cv_volume_id)

        # Cache all issues
        self.cache.cache_volume_issues(issues)

        # Build in-memory lookup
        issue_map = {i.issue_number: i for i in issues}
        self._volume_issues_cache[volume.cv_volume_id] = issue_map

        return issue_map.get(issue_number)

    def _interactive_select_volume(
        self, original_name: str, volumes: list[ComicVineVolume]
    ) -> ComicVineVolume | None:
        """Interactively prompt user to select a volume."""
        print(f"\nNo confident match for: {original_name}")
        print("Please select the correct volume:\n")

        for i, vol in enumerate(volumes[:10], 1):
            print(f"  [{i}] {vol.name} ({vol.start_year}) - {vol.publisher}")
            print(f"      {vol.issue_count} issues")

        print("  [0] Skip this series")
        print()

        while True:
            try:
                choice = input("Enter number: ").strip()
                choice_num = int(choice)

                if choice_num == 0:
                    return None
                elif 1 <= choice_num <= min(10, len(volumes)):
                    return volumes[choice_num - 1]
            except (ValueError, KeyboardInterrupt):
                return None
