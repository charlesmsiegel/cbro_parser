"""Tests for cbro_parser.cli module."""

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cbro_parser.cli import cmd_batch, cmd_parse, cmd_prepopulate, cmd_stats, main


class TestCLIStats:
    """Tests for stats command."""

    def test_cmd_stats_displays_stats(self, temp_db, capsys):
        """Test that stats command displays cache statistics."""
        from cbro_parser.cache.sqlite_cache import SQLiteCache

        cache = SQLiteCache(temp_db)
        args = MagicMock()

        cmd_stats(cache, args)

        captured = capsys.readouterr()
        assert "Cache Statistics:" in captured.out
        assert "Volumes:" in captured.out
        assert "Issues:" in captured.out
        assert "Series Mappings:" in captured.out


class TestCLIPrepopulate:
    """Tests for prepopulate command."""

    def test_cmd_prepopulate_nonexistent_dir(self, temp_db, temp_dir, capsys):
        """Test prepopulate with nonexistent directory."""
        from cbro_parser.cache.sqlite_cache import SQLiteCache

        cache = SQLiteCache(temp_db)
        args = MagicMock()
        args.directory = str(temp_dir / "nonexistent")

        with pytest.raises(SystemExit):
            cmd_prepopulate(cache, MagicMock(), args)

    def test_cmd_prepopulate_with_cbl_files(
        self, temp_db, temp_dir, mock_config, sample_cbl_content, capsys
    ):
        """Test prepopulate with existing CBL files."""
        from cbro_parser.cache.sqlite_cache import SQLiteCache

        # Create CBL file
        cbl_path = temp_dir / "test.cbl"
        cbl_path.write_text(sample_cbl_content)

        cache = SQLiteCache(temp_db)
        args = MagicMock()
        args.directory = str(temp_dir)

        cmd_prepopulate(cache, mock_config, args)

        captured = capsys.readouterr()
        assert "Prepopulated cache with" in captured.out


class TestCLIParse:
    """Tests for parse command."""

    @patch("cbro_parser.cli.CBROScraper")
    @patch("cbro_parser.cli.ComicVineClient")
    @patch("cbro_parser.cli.SeriesMatcher")
    @patch("cbro_parser.cli.CBLWriter")
    def test_cmd_parse_dry_run(
        self,
        mock_writer_cls,
        mock_matcher_cls,
        mock_cv_cls,
        mock_scraper_cls,
        temp_db,
        mock_config,
        sample_parsed_issue,
        capsys,
    ):
        """Test parse command in dry-run mode."""
        from cbro_parser.cache.sqlite_cache import SQLiteCache
        from cbro_parser.models import ParsedIssue

        # Setup mocks
        mock_scraper = MagicMock()
        mock_scraper.fetch_reading_order.return_value = [sample_parsed_issue]
        mock_scraper.get_reading_order_name.return_value = "Test Order"
        mock_scraper_cls.return_value = mock_scraper

        mock_matcher = MagicMock()
        mock_matcher.match_issue.return_value = None  # Unmatched
        mock_matcher_cls.return_value = mock_matcher

        cache = SQLiteCache(temp_db)
        args = MagicMock()
        args.url = "https://example.com/test-reading-order/"
        args.output = None
        args.name = None
        args.interactive = False
        args.dry_run = True
        args.verbose = False

        cmd_parse(cache, mock_config, args)

        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        # Writer should not have been called
        mock_writer_cls.return_value.write.assert_not_called()

    @patch("cbro_parser.cli.CBROScraper")
    @patch("cbro_parser.cli.ComicVineClient")
    @patch("cbro_parser.cli.SeriesMatcher")
    @patch("cbro_parser.cli.CBLWriter")
    def test_cmd_parse_creates_file(
        self,
        mock_writer_cls,
        mock_matcher_cls,
        mock_cv_cls,
        mock_scraper_cls,
        temp_db,
        temp_dir,
        mock_config,
        sample_parsed_issue,
        sample_matched_book,
        capsys,
    ):
        """Test parse command creates CBL file."""
        from cbro_parser.cache.sqlite_cache import SQLiteCache

        # Setup mocks
        mock_scraper = MagicMock()
        mock_scraper.fetch_reading_order.return_value = [sample_parsed_issue]
        mock_scraper.get_reading_order_name.return_value = "Test Order"
        mock_scraper_cls.return_value = mock_scraper

        mock_matcher = MagicMock()
        mock_matcher.match_issue.return_value = sample_matched_book
        mock_matcher_cls.return_value = mock_matcher

        cache = SQLiteCache(temp_db)
        args = MagicMock()
        args.url = "https://example.com/test-reading-order/"
        args.output = str(temp_dir / "output.cbl")
        args.name = "My List"
        args.interactive = False
        args.dry_run = False
        args.verbose = False

        cmd_parse(cache, mock_config, args)

        # Writer should have been called
        mock_writer_cls.return_value.write.assert_called_once()

    @patch("cbro_parser.cli.CBROScraper")
    def test_cmd_parse_handles_fetch_error(
        self,
        mock_scraper_cls,
        temp_db,
        mock_config,
        capsys,
    ):
        """Test parse command handles fetch errors."""
        import requests

        from cbro_parser.cache.sqlite_cache import SQLiteCache

        mock_scraper = MagicMock()
        mock_scraper.fetch_reading_order.side_effect = requests.RequestException(
            "Network error"
        )
        mock_scraper_cls.return_value = mock_scraper

        cache = SQLiteCache(temp_db)
        args = MagicMock()
        args.url = "https://example.com/test/"
        args.verbose = False

        with pytest.raises(SystemExit):
            cmd_parse(cache, mock_config, args)


class TestCLIBatch:
    """Tests for batch command."""

    @patch("cbro_parser.cli.CBROScraper")
    @patch("cbro_parser.cli.ComicVineClient")
    @patch("cbro_parser.cli.SeriesMatcher")
    @patch("cbro_parser.cli.CBLWriter")
    def test_cmd_batch_preserves_unmatched_issues(
        self,
        mock_writer_cls,
        mock_matcher_cls,
        mock_cv_cls,
        mock_scraper_cls,
        temp_db,
        temp_dir,
        mock_config,
        capsys,
    ):
        """Test that batch mode preserves unmatched issues like single parse mode.

        Regression test for: Batch Mode Loses Data bug
        - cli.py:320-324 discards unmatched books in batch mode
        - cli.py:248-250 preserves them in single parse mode
        - Behavior should be consistent
        """
        from cbro_parser.cache.sqlite_cache import SQLiteCache
        from cbro_parser.models import MatchedBook, ParsedIssue

        # Create URL file
        url_file = temp_dir / "urls.txt"
        url_file.write_text("https://example.com/test-order/")

        # Create 3 parsed issues
        parsed_issues = [
            ParsedIssue(
                series_name="Batman",
                issue_number="1",
                volume_hint=None,
                year_hint="2016",
                format_type=None,
                notes=None,
            ),
            ParsedIssue(
                series_name="Obscure Series",  # This one won't match
                issue_number="5",
                volume_hint=None,
                year_hint="2020",
                format_type=None,
                notes=None,
            ),
            ParsedIssue(
                series_name="Batman",
                issue_number="2",
                volume_hint=None,
                year_hint="2016",
                format_type=None,
                notes=None,
            ),
        ]

        # Setup mocks
        mock_scraper = MagicMock()
        mock_scraper.fetch_reading_order.return_value = parsed_issues
        mock_scraper.get_reading_order_name.return_value = "Test Order"
        mock_scraper_cls.return_value = mock_scraper

        # Matcher returns MatchedBook for Batman, None for Obscure Series
        def mock_match_issue(parsed):
            if parsed.series_name == "Batman":
                return MatchedBook(
                    series="Batman",
                    number=parsed.issue_number,
                    volume="2016",
                    year="2016",
                    format_type=None,
                    cv_volume_id=12345,
                    cv_issue_id=99999,
                    confidence=1.0,
                )
            return None  # Unmatched

        mock_matcher = MagicMock()
        mock_matcher.match_issue.side_effect = mock_match_issue
        mock_matcher_cls.return_value = mock_matcher

        cache = SQLiteCache(temp_db)
        args = MagicMock()
        args.url_file = str(url_file)
        args.output_dir = str(temp_dir / "output")
        args.interactive = False

        cmd_batch(cache, mock_config, args)

        # Get the ReadingList passed to writer.write()
        mock_writer_cls.return_value.write.assert_called_once()
        call_args = mock_writer_cls.return_value.write.call_args
        reading_list = call_args[0][0]

        # CRITICAL: Batch mode should preserve ALL 3 issues, not just the 2 matched ones
        assert len(reading_list.books) == 3, (
            f"Expected 3 books (including unmatched), got {len(reading_list.books)}. "
            "Batch mode is discarding unmatched issues!"
        )

        # Verify order is preserved
        assert reading_list.books[0].series == "Batman"
        assert reading_list.books[0].number == "1"
        assert (
            reading_list.books[1].series == "Obscure Series"
        )  # Unmatched but preserved
        assert reading_list.books[1].number == "5"
        assert reading_list.books[1].confidence == 0.0  # Marked as unmatched
        assert reading_list.books[2].series == "Batman"
        assert reading_list.books[2].number == "2"

    @patch("cbro_parser.cli.CBROScraper")
    @patch("cbro_parser.cli.ComicVineClient")
    @patch("cbro_parser.cli.SeriesMatcher")
    @patch("cbro_parser.cli.CBLWriter")
    def test_cmd_batch_processes_urls(
        self,
        mock_writer_cls,
        mock_matcher_cls,
        mock_cv_cls,
        mock_scraper_cls,
        temp_db,
        temp_dir,
        mock_config,
        sample_parsed_issue,
        sample_matched_book,
        capsys,
    ):
        """Test batch command processes multiple URLs."""
        from cbro_parser.cache.sqlite_cache import SQLiteCache

        # Create URL file
        url_file = temp_dir / "urls.txt"
        url_file.write_text(
            "https://example.com/batman/\nhttps://example.com/superman/"
        )

        # Setup mocks
        mock_scraper = MagicMock()
        mock_scraper.fetch_reading_order.return_value = [sample_parsed_issue]
        mock_scraper.get_reading_order_name.return_value = "Test"
        mock_scraper_cls.return_value = mock_scraper

        mock_matcher = MagicMock()
        mock_matcher.match_issue.return_value = sample_matched_book
        mock_matcher_cls.return_value = mock_matcher

        cache = SQLiteCache(temp_db)
        args = MagicMock()
        args.url_file = str(url_file)
        args.output_dir = str(temp_dir / "output")
        args.interactive = False

        cmd_batch(cache, mock_config, args)

        # Should have processed 2 URLs
        assert mock_scraper.fetch_reading_order.call_count == 2

    def test_cmd_batch_nonexistent_file(self, temp_db, temp_dir, mock_config, capsys):
        """Test batch command with nonexistent URL file."""
        from cbro_parser.cache.sqlite_cache import SQLiteCache

        cache = SQLiteCache(temp_db)
        args = MagicMock()
        args.url_file = str(temp_dir / "nonexistent.txt")

        with pytest.raises(SystemExit):
            cmd_batch(cache, mock_config, args)

    @patch("cbro_parser.cli.CBROScraper")
    @patch("cbro_parser.cli.ComicVineClient")
    @patch("cbro_parser.cli.SeriesMatcher")
    @patch("cbro_parser.cli.CBLWriter")
    def test_cmd_batch_skips_comments(
        self,
        mock_writer_cls,
        mock_matcher_cls,
        mock_cv_cls,
        mock_scraper_cls,
        temp_db,
        temp_dir,
        mock_config,
        sample_parsed_issue,
        capsys,
    ):
        """Test batch command skips comment lines."""
        from cbro_parser.cache.sqlite_cache import SQLiteCache

        # Create URL file with comments
        url_file = temp_dir / "urls.txt"
        url_file.write_text(
            "# This is a comment\nhttps://example.com/batman/\n# Another comment"
        )

        mock_scraper = MagicMock()
        mock_scraper.fetch_reading_order.return_value = [sample_parsed_issue]
        mock_scraper.get_reading_order_name.return_value = "Test"
        mock_scraper_cls.return_value = mock_scraper

        mock_matcher = MagicMock()
        mock_matcher.match_issue.return_value = None
        mock_matcher_cls.return_value = mock_matcher

        cache = SQLiteCache(temp_db)
        args = MagicMock()
        args.url_file = str(url_file)
        args.output_dir = str(temp_dir / "output")
        args.interactive = False

        cmd_batch(cache, mock_config, args)

        # Should only process 1 URL (not comments)
        assert mock_scraper.fetch_reading_order.call_count == 1


class TestCLIMain:
    """Tests for main CLI entry point."""

    def test_main_no_command_prints_help(self, capsys, monkeypatch):
        """Test main with no command prints help."""
        monkeypatch.setattr(sys, "argv", ["cbro-parser"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    def test_main_stats_command(self, temp_dir, temp_env_file, monkeypatch, capsys):
        """Test main with stats command."""
        cache_db = temp_dir / "cache.db"

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "cbro-parser",
                "--env",
                str(temp_env_file),
                "--cache-db",
                str(cache_db),
                "stats",
            ],
        )

        main()

        captured = capsys.readouterr()
        assert "Cache Statistics:" in captured.out

    def test_main_missing_api_key(self, temp_dir, monkeypatch, capsys):
        """Test main with missing API key raises error."""
        # Clear any existing env var
        monkeypatch.delenv("COMICVINE_API", raising=False)

        # Create empty .env file
        empty_env = temp_dir / "empty.env"
        empty_env.write_text("")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "cbro-parser",
                "--env",
                str(empty_env),
                "stats",
            ],
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1


class TestCLIArgumentParsing:
    """Tests for argument parsing."""

    def test_parse_command_args(self, temp_dir, temp_env_file, monkeypatch):
        """Test parse command argument parsing."""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "cbro-parser",
                "--env",
                str(temp_env_file),
                "parse",
                "https://example.com/test/",
                "-o",
                "output.cbl",
                "-n",
                "My List",
                "--dry-run",
                "-v",
            ],
        )

        # Capture the parsed args by patching cmd_parse
        captured_args = {}

        def mock_cmd_parse(cache, config, args):
            captured_args["url"] = args.url
            captured_args["output"] = args.output
            captured_args["name"] = args.name
            captured_args["dry_run"] = args.dry_run
            captured_args["verbose"] = args.verbose

        with patch("cbro_parser.cli.cmd_parse", mock_cmd_parse):
            main()

        assert captured_args["url"] == "https://example.com/test/"
        assert captured_args["output"] == "output.cbl"
        assert captured_args["name"] == "My List"
        assert captured_args["dry_run"] is True
        assert captured_args["verbose"] is True

    def test_batch_command_args(self, temp_dir, temp_env_file, monkeypatch):
        """Test batch command argument parsing."""
        url_file = temp_dir / "urls.txt"
        url_file.write_text("https://example.com/test/")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "cbro-parser",
                "--env",
                str(temp_env_file),
                "batch",
                str(url_file),
                "--output-dir",
                "custom_output",
                "-i",
            ],
        )

        captured_args = {}

        def mock_cmd_batch(cache, config, args):
            captured_args["url_file"] = args.url_file
            captured_args["output_dir"] = args.output_dir
            captured_args["interactive"] = args.interactive

        with patch("cbro_parser.cli.cmd_batch", mock_cmd_batch):
            main()

        assert captured_args["url_file"] == str(url_file)
        assert captured_args["output_dir"] == "custom_output"
        assert captured_args["interactive"] is True


class TestCLIErrorHandling:
    """Tests for specific exception handling in CLI commands."""

    @patch("cbro_parser.cli.CBROScraper")
    @patch("cbro_parser.cli.ComicVineClient")
    @patch("cbro_parser.cli.SeriesMatcher")
    @patch("cbro_parser.cli.CBLWriter")
    def test_cmd_parse_handles_network_error(
        self,
        mock_writer_cls,
        mock_matcher_cls,
        mock_cv_cls,
        mock_scraper_cls,
        temp_db,
        temp_dir,
        mock_config,
        capsys,
    ):
        """Test cmd_parse handles network errors specifically."""
        import requests

        from cbro_parser.cache.sqlite_cache import SQLiteCache

        mock_scraper = MagicMock()
        mock_scraper.fetch_reading_order.side_effect = requests.RequestException(
            "Connection failed"
        )
        mock_scraper_cls.return_value = mock_scraper

        cache = SQLiteCache(temp_db)
        args = MagicMock()
        args.url = "https://example.com/test/"
        args.output = str(temp_dir / "output.cbl")
        args.verbose = False
        args.interactive = False
        args.dry_run = False

        with pytest.raises(SystemExit) as exc_info:
            cmd_parse(cache, mock_config, args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error fetching reading order" in captured.out

    @patch("cbro_parser.cli.CBROScraper")
    @patch("cbro_parser.cli.ComicVineClient")
    @patch("cbro_parser.cli.SeriesMatcher")
    @patch("cbro_parser.cli.CBLWriter")
    def test_cmd_batch_handles_scraper_error_continues(
        self,
        mock_writer_cls,
        mock_matcher_cls,
        mock_cv_cls,
        mock_scraper_cls,
        temp_db,
        temp_dir,
        mock_config,
        sample_parsed_issue,
        sample_matched_book,
        capsys,
    ):
        """Test batch command continues after individual URL scraping errors."""
        import requests

        from cbro_parser.cache.sqlite_cache import SQLiteCache

        # Create URL file with 2 URLs
        url_file = temp_dir / "urls.txt"
        url_file.write_text("https://example.com/fail/\nhttps://example.com/succeed/")

        # First URL fails, second succeeds
        mock_scraper = MagicMock()
        mock_scraper.fetch_reading_order.side_effect = [
            requests.RequestException("Network error"),
            [sample_parsed_issue],
        ]
        mock_scraper.get_reading_order_name.return_value = "Test"
        mock_scraper_cls.return_value = mock_scraper

        mock_matcher = MagicMock()
        mock_matcher.match_issue.return_value = sample_matched_book
        mock_matcher_cls.return_value = mock_matcher

        cache = SQLiteCache(temp_db)
        args = MagicMock()
        args.url_file = str(url_file)
        args.output_dir = str(temp_dir / "output")
        args.interactive = False

        # Should not raise - continues after error
        cmd_batch(cache, mock_config, args)

        # Should have attempted both URLs
        assert mock_scraper.fetch_reading_order.call_count == 2

        # Error should be logged
        captured = capsys.readouterr()
        assert "Error" in captured.out
