"""SQLite-based cache for ComicVine data."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

from ..models import ComicVineIssue, ComicVineVolume


class SQLiteCache:
    """Persistent SQLite cache for ComicVine API data."""

    SCHEMA = """
        -- Volumes table
        CREATE TABLE IF NOT EXISTS volumes (
            cv_volume_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            start_year INTEGER,
            publisher TEXT,
            issue_count INTEGER,
            aliases TEXT,  -- JSON array
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Issues table
        CREATE TABLE IF NOT EXISTS issues (
            cv_issue_id INTEGER PRIMARY KEY,
            cv_volume_id INTEGER NOT NULL,
            issue_number TEXT NOT NULL,
            cover_date TEXT,
            name TEXT,
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cv_volume_id) REFERENCES volumes(cv_volume_id)
        );

        -- Series name mapping (normalized name -> volume_id)
        CREATE TABLE IF NOT EXISTS series_mapping (
            normalized_name TEXT NOT NULL,
            start_year INTEGER,
            cv_volume_id INTEGER NOT NULL,
            confidence REAL DEFAULT 1.0,
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (normalized_name, start_year),
            FOREIGN KEY (cv_volume_id) REFERENCES volumes(cv_volume_id)
        );

        -- Issue lookup cache (quick lookup by series+number)
        CREATE TABLE IF NOT EXISTS issue_lookup (
            cv_volume_id INTEGER NOT NULL,
            issue_number TEXT NOT NULL,
            cv_issue_id INTEGER NOT NULL,
            publication_year INTEGER,
            PRIMARY KEY (cv_volume_id, issue_number),
            FOREIGN KEY (cv_volume_id) REFERENCES volumes(cv_volume_id),
            FOREIGN KEY (cv_issue_id) REFERENCES issues(cv_issue_id)
        );

        -- Indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_volumes_name ON volumes(name);
        CREATE INDEX IF NOT EXISTS idx_volumes_start_year ON volumes(start_year);
        CREATE INDEX IF NOT EXISTS idx_issues_volume ON issues(cv_volume_id);
        CREATE INDEX IF NOT EXISTS idx_series_mapping_name ON series_mapping(normalized_name);
    """

    def __init__(self, db_path: Path, expiry_days: int = 30):
        """
        Initialize the cache.

        Args:
            db_path: Path to the SQLite database file.
            expiry_days: Number of days before cache entries expire.
        """
        self.db_path = db_path
        self.expiry_days = expiry_days
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _is_expired(self, cached_at: str) -> bool:
        """Check if a cache entry has expired."""
        try:
            cached_time = datetime.fromisoformat(cached_at)
            return datetime.now() - cached_time > timedelta(days=self.expiry_days)
        except (ValueError, TypeError):
            return True

    # Volume methods
    def get_volume(self, cv_volume_id: int) -> ComicVineVolume | None:
        """Get a cached volume by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM volumes WHERE cv_volume_id = ?", (cv_volume_id,)
            ).fetchone()

            if row and not self._is_expired(row["cached_at"]):
                return ComicVineVolume(
                    cv_volume_id=row["cv_volume_id"],
                    name=row["name"],
                    start_year=row["start_year"] or 0,
                    publisher=row["publisher"] or "",
                    issue_count=row["issue_count"] or 0,
                    aliases=json.loads(row["aliases"] or "[]"),
                )
        return None

    def cache_volume(self, volume: ComicVineVolume) -> None:
        """Cache a volume."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO volumes
                (cv_volume_id, name, start_year, publisher, issue_count, aliases, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    volume.cv_volume_id,
                    volume.name,
                    volume.start_year,
                    volume.publisher,
                    volume.issue_count,
                    json.dumps(volume.aliases),
                ),
            )

    # Issue methods
    def get_issue(
        self, cv_volume_id: int, issue_number: str
    ) -> ComicVineIssue | None:
        """Get a cached issue by volume and number."""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT i.* FROM issues i
                JOIN issue_lookup l ON i.cv_issue_id = l.cv_issue_id
                WHERE l.cv_volume_id = ? AND l.issue_number = ?
            """,
                (cv_volume_id, issue_number),
            ).fetchone()

            if row and not self._is_expired(row["cached_at"]):
                return ComicVineIssue(
                    cv_issue_id=row["cv_issue_id"],
                    cv_volume_id=row["cv_volume_id"],
                    issue_number=row["issue_number"],
                    cover_date=row["cover_date"] or "",
                    name=row["name"],
                )
        return None

    def get_volume_issues(self, cv_volume_id: int) -> list[ComicVineIssue]:
        """Get all cached issues for a volume."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM issues
                WHERE cv_volume_id = ?
                ORDER BY issue_number
            """,
                (cv_volume_id,),
            ).fetchall()

            issues = []
            for row in rows:
                if not self._is_expired(row["cached_at"]):
                    issues.append(
                        ComicVineIssue(
                            cv_issue_id=row["cv_issue_id"],
                            cv_volume_id=row["cv_volume_id"],
                            issue_number=row["issue_number"],
                            cover_date=row["cover_date"] or "",
                            name=row["name"],
                        )
                    )
            return issues

    def cache_issue(self, issue: ComicVineIssue) -> None:
        """Cache an issue."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO issues
                (cv_issue_id, cv_volume_id, issue_number, cover_date, name, cached_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    issue.cv_issue_id,
                    issue.cv_volume_id,
                    issue.issue_number,
                    issue.cover_date,
                    issue.name,
                ),
            )

            # Also add to lookup table
            pub_year = None
            if issue.cover_date and len(issue.cover_date) >= 4:
                try:
                    pub_year = int(issue.cover_date[:4])
                except ValueError:
                    pass

            conn.execute(
                """
                INSERT OR REPLACE INTO issue_lookup
                (cv_volume_id, issue_number, cv_issue_id, publication_year)
                VALUES (?, ?, ?, ?)
            """,
                (
                    issue.cv_volume_id,
                    issue.issue_number,
                    issue.cv_issue_id,
                    pub_year,
                ),
            )

    def cache_volume_issues(self, issues: list[ComicVineIssue]) -> None:
        """Cache multiple issues at once (more efficient)."""
        with self._get_connection() as conn:
            for issue in issues:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO issues
                    (cv_issue_id, cv_volume_id, issue_number, cover_date, name, cached_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (
                        issue.cv_issue_id,
                        issue.cv_volume_id,
                        issue.issue_number,
                        issue.cover_date,
                        issue.name,
                    ),
                )

                pub_year = None
                if issue.cover_date and len(issue.cover_date) >= 4:
                    try:
                        pub_year = int(issue.cover_date[:4])
                    except ValueError:
                        pass

                conn.execute(
                    """
                    INSERT OR REPLACE INTO issue_lookup
                    (cv_volume_id, issue_number, cv_issue_id, publication_year)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        issue.cv_volume_id,
                        issue.issue_number,
                        issue.cv_issue_id,
                        pub_year,
                    ),
                )

    # Series mapping methods
    def get_volume_for_series(
        self, normalized_name: str, start_year: int | None = None
    ) -> int | None:
        """Get the cached volume ID for a normalized series name."""
        with self._get_connection() as conn:
            if start_year:
                row = conn.execute(
                    """
                    SELECT cv_volume_id, cached_at FROM series_mapping
                    WHERE normalized_name = ? AND start_year = ?
                """,
                    (normalized_name, start_year),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT cv_volume_id, cached_at FROM series_mapping
                    WHERE normalized_name = ?
                    ORDER BY confidence DESC, start_year DESC
                    LIMIT 1
                """,
                    (normalized_name,),
                ).fetchone()

            if row and not self._is_expired(row["cached_at"]):
                return row["cv_volume_id"]
        return None

    def cache_series_mapping(
        self,
        normalized_name: str,
        start_year: int,
        cv_volume_id: int,
        confidence: float = 1.0,
    ) -> None:
        """Cache a series name to volume mapping."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO series_mapping
                (normalized_name, start_year, cv_volume_id, confidence, cached_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (normalized_name, start_year, cv_volume_id, confidence),
            )

    # Statistics
    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._get_connection() as conn:
            volumes = conn.execute("SELECT COUNT(*) FROM volumes").fetchone()[0]
            issues = conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
            mappings = conn.execute(
                "SELECT COUNT(*) FROM series_mapping"
            ).fetchone()[0]

            return {
                "volumes": volumes,
                "issues": issues,
                "series_mappings": mappings,
            }

    def clear_expired(self) -> int:
        """Remove expired entries from cache. Returns count of removed entries."""
        cutoff = (
            datetime.now() - timedelta(days=self.expiry_days)
        ).isoformat()
        removed = 0

        with self._get_connection() as conn:
            # Remove expired volumes
            cursor = conn.execute(
                "DELETE FROM volumes WHERE cached_at < ?", (cutoff,)
            )
            removed += cursor.rowcount

            # Remove expired issues
            cursor = conn.execute(
                "DELETE FROM issues WHERE cached_at < ?", (cutoff,)
            )
            removed += cursor.rowcount

            # Remove expired mappings
            cursor = conn.execute(
                "DELETE FROM series_mapping WHERE cached_at < ?", (cutoff,)
            )
            removed += cursor.rowcount

            # Clean up orphaned issue_lookup entries
            conn.execute(
                """
                DELETE FROM issue_lookup
                WHERE cv_issue_id NOT IN (SELECT cv_issue_id FROM issues)
            """
            )

        return removed
