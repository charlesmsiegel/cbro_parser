"""ComicVine API client."""

import requests

from ..config import Config
from ..models import ComicVineIssue, ComicVineVolume
from .rate_limiter import RateLimiter


class ComicVineAPIError(Exception):
    """ComicVine API error."""

    pass


class ComicVineClient:
    """Client for ComicVine API."""

    def __init__(
        self, config: Config, rate_limiter: RateLimiter | None = None
    ):
        """
        Initialize the ComicVine client.

        Args:
            config: Application configuration.
            rate_limiter: Optional rate limiter. If not provided, creates one.
        """
        self.config = config
        self.rate_limiter = rate_limiter or RateLimiter(
            max_requests=config.cv_rate_limit_requests,
            window_seconds=config.cv_rate_limit_window_seconds,
            min_interval=config.cv_safe_delay_seconds,
        )

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "CBROParser/1.0"})

    def _make_request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a rate-limited API request."""
        self.rate_limiter.acquire()

        url = f"{self.config.cv_base_url}/{endpoint}"

        request_params = {
            "api_key": self.config.comicvine_api_key,
            "format": "json",
        }
        if params:
            request_params.update(params)

        response = self.session.get(url, params=request_params, timeout=30)
        response.raise_for_status()

        data = response.json()

        if data.get("status_code") != 1:
            error_msg = data.get("error", "Unknown error")
            raise ComicVineAPIError(f"API error: {error_msg}")

        return data

    def search_volumes(
        self, query: str, limit: int = 10
    ) -> list[ComicVineVolume]:
        """
        Search for volumes (series) by name.

        Args:
            query: Series name to search for.
            limit: Maximum results to return.

        Returns:
            List of matching volumes.
        """
        data = self._make_request(
            "search",
            {
                "query": query,
                "resources": "volume",
                "field_list": "id,name,start_year,publisher,count_of_issues,aliases",
                "limit": limit,
            },
        )

        volumes = []
        for result in data.get("results", []):
            publisher_name = ""
            if result.get("publisher"):
                publisher_name = result["publisher"].get("name", "")

            aliases = []
            if result.get("aliases"):
                aliases = [
                    a.strip()
                    for a in result["aliases"].split("\n")
                    if a.strip()
                ]

            # Handle start_year which can be int, str, or None
            start_year = result.get("start_year")
            if isinstance(start_year, str):
                # Remove any non-numeric characters (e.g., "1950?" -> "1950")
                start_year = "".join(c for c in start_year if c.isdigit())
                start_year = int(start_year) if start_year else 0
            elif start_year is None:
                start_year = 0

            volumes.append(
                ComicVineVolume(
                    cv_volume_id=result["id"],
                    name=result.get("name", ""),
                    start_year=start_year,
                    publisher=publisher_name,
                    issue_count=result.get("count_of_issues", 0),
                    aliases=aliases,
                )
            )

        return volumes

    def get_volume(self, volume_id: int) -> ComicVineVolume:
        """
        Get detailed volume information.

        Args:
            volume_id: The ComicVine volume ID.

        Returns:
            Volume details.
        """
        data = self._make_request(
            f"volume/4050-{volume_id}",
            {
                "field_list": "id,name,start_year,publisher,count_of_issues,aliases"
            },
        )

        result = data["results"]
        publisher_name = ""
        if result.get("publisher"):
            publisher_name = result["publisher"].get("name", "")

        aliases = []
        if result.get("aliases"):
            aliases = [
                a.strip() for a in result["aliases"].split("\n") if a.strip()
            ]

        # Handle start_year which can be int, str, or None
        start_year = result.get("start_year")
        if isinstance(start_year, str):
            start_year = "".join(c for c in start_year if c.isdigit())
            start_year = int(start_year) if start_year else 0
        elif start_year is None:
            start_year = 0

        return ComicVineVolume(
            cv_volume_id=result["id"],
            name=result.get("name", ""),
            start_year=start_year,
            publisher=publisher_name,
            issue_count=result.get("count_of_issues", 0),
            aliases=aliases,
        )

    def get_volume_issues(
        self, volume_id: int, offset: int = 0
    ) -> list[ComicVineIssue]:
        """
        Get all issues for a volume.

        Args:
            volume_id: The ComicVine volume ID.
            offset: Pagination offset.

        Returns:
            List of issues in the volume.
        """
        data = self._make_request(
            "issues",
            {
                "filter": f"volume:{volume_id}",
                "field_list": "id,volume,issue_number,cover_date,name",
                "sort": "issue_number:asc",
                "offset": offset,
                "limit": 100,
            },
        )

        issues = []
        for result in data.get("results", []):
            issues.append(
                ComicVineIssue(
                    cv_issue_id=result["id"],
                    cv_volume_id=volume_id,
                    issue_number=result.get("issue_number") or "",
                    cover_date=result.get("cover_date") or "",
                    name=result.get("name"),
                )
            )

        # Handle pagination if needed
        total_results = data.get("number_of_total_results", 0)
        if offset + len(issues) < total_results:
            issues.extend(self.get_volume_issues(volume_id, offset + 100))

        return issues

    def search_issue(
        self, series_name: str, issue_number: str, year: int | None = None
    ) -> ComicVineIssue | None:
        """
        Search for a specific issue.

        Note: This is less efficient than volume-based lookup.
        Use get_volume_issues when possible.

        Args:
            series_name: Name of the series.
            issue_number: Issue number to find.
            year: Optional year filter.

        Returns:
            Matching issue or None.
        """
        query = f"{series_name} {issue_number}"

        data = self._make_request(
            "search",
            {
                "query": query,
                "resources": "issue",
                "field_list": "id,volume,issue_number,cover_date,name",
                "limit": 10,
            },
        )

        for result in data.get("results", []):
            if result.get("issue_number") == issue_number:
                # If year filter provided, check cover_date
                if year and result.get("cover_date"):
                    try:
                        issue_year = int(result["cover_date"][:4])
                        if abs(issue_year - year) > 1:  # Allow 1 year tolerance
                            continue
                    except (ValueError, IndexError):
                        pass

                return ComicVineIssue(
                    cv_issue_id=result["id"],
                    cv_volume_id=result["volume"]["id"],
                    issue_number=result["issue_number"],
                    cover_date=result.get("cover_date") or "",
                    name=result.get("name"),
                )

        return None

    def remaining_requests(self) -> int:
        """Return number of API requests remaining in current window."""
        return self.rate_limiter.remaining_requests()
