"""Command-line interface for CBRO Parser."""

import argparse
import logging
import sys
from pathlib import Path

import requests

from .cache.sqlite_cache import SQLiteCache
from .cbl.reader import CBLReader
from .cbl.writer import CBLWriter
from .comicvine.api_client import ComicVineClient
from .comicvine.matcher import SeriesMatcher
from .comicvine.rate_limiter import RateLimiter
from .config import Config
from .models import ReadingList
from .scraper.cbro_scraper import CBROScraper
from .utils.text_normalizer import normalize_series_name


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Parse comic book reading orders and create .cbl files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Parse a URL and create a .cbl file
  cbro-parser parse https://www.comicbookreadingorders.com/dc/events/blackest-night-reading-order/

  # Parse with custom output file
  cbro-parser parse /dc/characters/green-lantern-reading-order/ -o "Green Lantern.cbl"

  # Batch mode: process multiple URLs from a file
  cbro-parser batch urls.txt --output-dir ./output

  # Prepopulate cache from existing .cbl files
  cbro-parser prepopulate "Reading Lists/"

  # Show cache statistics
  cbro-parser stats
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Parse command
    parse_parser = subparsers.add_parser(
        "parse", help="Parse a single reading order URL"
    )
    parse_parser.add_argument("url", help="URL or relative path to reading order")
    parse_parser.add_argument("-o", "--output", help="Output .cbl file path")
    parse_parser.add_argument(
        "-n", "--name", help="Reading list name (default: from page)"
    )
    parse_parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Interactive mode for ambiguous matches",
    )
    parse_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without writing",
    )
    parse_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose output"
    )

    # Batch command
    batch_parser = subparsers.add_parser(
        "batch", help="Process multiple URLs from file"
    )
    batch_parser.add_argument("url_file", help="File containing URLs (one per line)")
    batch_parser.add_argument(
        "--output-dir", default="output", help="Output directory for .cbl files"
    )
    batch_parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Interactive mode for ambiguous matches",
    )

    # Prepopulate command
    prepop_parser = subparsers.add_parser(
        "prepopulate", help="Prepopulate cache from existing .cbl files"
    )
    prepop_parser.add_argument("directory", help="Directory containing .cbl files")

    # Stats command
    subparsers.add_parser("stats", help="Show cache statistics")

    # Global options
    parser.add_argument("--env", help="Path to .env file", default=".env")
    parser.add_argument(
        "--cache-db",
        help="Path to SQLite cache database",
        default="comicvine_cache.db",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize components
    try:
        config = Config(Path(args.env) if args.env else None)
        config.cache_db_path = Path(args.cache_db)
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    cache = SQLiteCache(config.cache_db_path, expiry_days=30)

    # Execute command
    if args.command == "stats":
        cmd_stats(cache, args)
    elif args.command == "prepopulate":
        cmd_prepopulate(cache, config, args)
    elif args.command == "parse":
        cmd_parse(cache, config, args)
    elif args.command == "batch":
        cmd_batch(cache, config, args)


def cmd_stats(cache: SQLiteCache, args) -> None:
    """Show cache statistics."""
    stats = cache.get_stats()
    print("\nCache Statistics:")
    print(f"  Volumes:         {stats['volumes']:,}")
    print(f"  Issues:          {stats['issues']:,}")
    print(f"  Series Mappings: {stats['series_mappings']:,}")
    print()


def cmd_prepopulate(cache: SQLiteCache, config: Config, args) -> None:
    """Prepopulate cache from existing .cbl files."""
    directory = Path(args.directory)
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        sys.exit(1)

    reader = CBLReader()

    volumes_added = set()
    mappings_added = 0

    print(f"Scanning {directory} for .cbl files...")

    for reading_list in reader.read_all(directory):
        for book in reading_list.books:
            if not book.series or not book.volume:
                continue

            # Create a mapping for cache
            key = (book.series, book.volume)
            if key not in volumes_added:
                normalized = normalize_series_name(book.series)
                try:
                    start_year = int(book.volume)
                except ValueError:
                    continue

                # We don't have CV IDs, but we can create mappings
                # that will be verified/updated on first use
                cache.cache_series_mapping(
                    normalized_name=normalized,
                    start_year=start_year,
                    cv_volume_id=-1,  # Placeholder - will be replaced on verification
                    confidence=0.5,  # Lower confidence for unverified
                )

                volumes_added.add(key)
                mappings_added += 1

    print(f"\nPrepopulated cache with {mappings_added} series mappings")
    print("Note: Mappings will be verified against ComicVine on first use")


def cmd_parse(cache: SQLiteCache, config: Config, args) -> None:
    """Parse a single URL."""
    # Configure logging based on verbosity
    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(name)s: %(message)s",
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
        )

    rate_limiter = RateLimiter(
        max_requests=config.cv_rate_limit_requests,
        window_seconds=config.cv_rate_limit_window_seconds,
        min_interval=config.cv_safe_delay_seconds,
    )

    cv_client = ComicVineClient(config, rate_limiter)
    scraper = CBROScraper(config)
    matcher = SeriesMatcher(cv_client, cache, interactive=args.interactive)
    writer = CBLWriter()

    print(f"Fetching reading order from: {args.url}")

    try:
        parsed_issues = scraper.fetch_reading_order(args.url)
    except requests.RequestException as e:
        print(f"Error fetching reading order: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error parsing reading order: {e}")
        sys.exit(1)

    print(f"Found {len(parsed_issues)} issues")

    # Match issues - keep all in original order
    from .models import MatchedBook

    all_books = []
    unmatched = []
    matched_count = 0

    for i, parsed in enumerate(parsed_issues, 1):
        if args.verbose:
            print(
                f"  [{i}/{len(parsed_issues)}] {parsed.series_name} #{parsed.issue_number}"
            )

        matched = matcher.match_issue(parsed)
        if matched:
            all_books.append(matched)
            matched_count += 1
        else:
            # Create unmatched book entry to preserve reading order
            unmatched_book = MatchedBook(
                series=parsed.series_name,
                number=parsed.issue_number,
                volume=parsed.volume_hint or parsed.year_hint or "0",
                year=parsed.year_hint or "0",
                format_type=parsed.format_type,
                confidence=0.0,  # Mark as unmatched
            )
            all_books.append(unmatched_book)
            unmatched.append(parsed)

    print(f"\nMatched: {matched_count}, Unmatched: {len(unmatched)}")

    if unmatched:
        print("\nUnmatched issues:")
        # Group by series for cleaner output
        from collections import defaultdict

        by_series = defaultdict(list)
        for p in unmatched:
            by_series[p.series_name].append(p.issue_number)

        for series, issues in sorted(by_series.items()):
            if len(issues) <= 5:
                print(f"  - {series}: #{', #'.join(issues)}")
            else:
                print(
                    f"  - {series}: #{', #'.join(issues[:3])}... ({len(issues)} issues)"
                )

    if args.dry_run:
        print("\n[DRY RUN] Would create reading list with above entries")
        return

    # Create reading list with all issues in original order
    list_name = args.name or scraper.get_reading_order_name(args.url)
    reading_list = ReadingList(name=list_name, books=all_books)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(f"{list_name}.cbl")

    writer.write(reading_list, output_path)
    print(f"\nWritten: {output_path}")


def cmd_batch(cache: SQLiteCache, config: Config, args) -> None:
    """Process multiple URLs from a file."""
    url_file = Path(args.url_file)
    if not url_file.exists():
        print(f"Error: URL file not found: {url_file}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rate_limiter = RateLimiter(
        max_requests=config.cv_rate_limit_requests,
        window_seconds=config.cv_rate_limit_window_seconds,
        min_interval=config.cv_safe_delay_seconds,
    )

    cv_client = ComicVineClient(config, rate_limiter)
    scraper = CBROScraper(config)
    matcher = SeriesMatcher(cv_client, cache, interactive=args.interactive)
    writer = CBLWriter()

    urls = [
        line.strip()
        for line in url_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

    print(f"Processing {len(urls)} URLs...")

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] {url}")

        try:
            parsed_issues = scraper.fetch_reading_order(url)

            # Match issues - keep all in original order (same as cmd_parse)
            from .models import MatchedBook

            all_books = []
            matched_count = 0
            for parsed in parsed_issues:
                matched = matcher.match_issue(parsed)
                if matched:
                    all_books.append(matched)
                    matched_count += 1
                else:
                    # Create unmatched book entry to preserve reading order
                    unmatched_book = MatchedBook(
                        series=parsed.series_name,
                        number=parsed.issue_number,
                        volume=parsed.volume_hint or parsed.year_hint or "0",
                        year=parsed.year_hint or "0",
                        format_type=parsed.format_type,
                        confidence=0.0,  # Mark as unmatched
                    )
                    all_books.append(unmatched_book)

            list_name = scraper.get_reading_order_name(url)
            reading_list = ReadingList(name=list_name, books=all_books)

            output_path = output_dir / f"{list_name}.cbl"
            writer.write(reading_list, output_path)

            unmatched_count = len(all_books) - matched_count
            print(
                f"  -> {matched_count}/{len(all_books)} issues matched, written to {output_path}"
                + (f" ({unmatched_count} unmatched)" if unmatched_count else "")
            )

        except requests.RequestException as e:
            print(f"  Error fetching URL: {e}")
        except ValueError as e:
            print(f"  Error parsing content: {e}")
        except OSError as e:
            print(f"  Error writing file: {e}")

        # Show rate limiter status
        remaining = rate_limiter.remaining_requests()
        if remaining < 50:
            print(f"  (Rate limit: {remaining} requests remaining)")


if __name__ == "__main__":
    main()
