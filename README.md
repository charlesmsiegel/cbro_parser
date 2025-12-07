# CBRO Parser

A Python application that parses comic book reading orders from [comicbookreadingorders.com](https://comicbookreadingorders.com) and creates ComicRack-compatible `.cbl` reading list files with ComicVine metadata.

## Features

- **GUI Application** - Tkinter-based interface with filterable reading order list
- **CLI Support** - Command-line interface for scripting and automation
- **ComicVine Integration** - Matches series and issues against the ComicVine database
- **Smart Caching** - SQLite cache for ComicVine lookups (30-day expiry) and JSON cache for reading order index
- **Rate Limiting** - Respects ComicVine API limits (200 req/15min) and CBRO crawl delay (5 seconds)
- **Instant Startup** - Cached reading order list loads immediately on GUI launch
- **Complete Output** - Includes both matched and unmatched issues in reading order

## Installation

### Prerequisites

- Python 3.11+
- A ComicVine API key ([get one here](https://comicvine.gamespot.com/api/))

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/cbro_parser.git
cd cbro_parser

# Install the package
pip install -e .

# Create .env file with your API key
echo "COMICVINE_API=your_api_key_here" > .env
```

## Usage

### GUI Mode (Default)

Simply run:

```bash
cbro-parser
```

The GUI provides:
- Filterable list of 400+ reading orders from CBRO
- Filter by text, publisher (Marvel/DC/Other), and category (Characters/Events/Master)
- Multi-select with checkboxes
- Progress dialog with detailed logging
- Output directory selection

### CLI Mode

#### Parse a single reading order

```bash
# Basic usage
cbro-parser parse https://comicbookreadingorders.com/dc/events/blackest-night-reading-order/

# With options
cbro-parser parse URL -o "Blackest Night.cbl" -n "Blackest Night" -v

# Dry run (show what would be created)
cbro-parser parse URL --dry-run
```

#### Batch process multiple URLs

```bash
# Create a file with URLs (one per line)
cbro-parser batch urls.txt --output-dir ./output
```

#### Prepopulate cache from existing .cbl files

```bash
cbro-parser prepopulate "Reading Lists/"
```

#### View cache statistics

```bash
cbro-parser stats
```

## Configuration

Create a `.env` file in the project root:

```env
COMICVINE_API=your_api_key_here
```

### Optional Settings

These can be set in the `.env` file or modified in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CBRO_BASE_URL` | `https://comicbookreadingorders.com` | Base URL for CBRO |
| `CBRO_CRAWL_DELAY` | `5` | Seconds between CBRO requests |
| `CV_RATE_LIMIT_REQUESTS` | `200` | Max ComicVine requests per window |
| `CV_RATE_LIMIT_WINDOW` | `900` | Rate limit window in seconds (15 min) |
| `CV_SAFE_DELAY` | `1.0` | Minimum seconds between CV requests |
| `CACHE_EXPIRY_DAYS` | `30` | Days before cache entries expire |

## Output Format

The parser creates ComicRack-compatible `.cbl` files:

```xml
<?xml version="1.0"?>
<ReadingList xmlns:xsd="http://www.w3.org/2001/XMLSchema"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Name>Blackest Night</Name>
  <Books>
    <Book Series="Green Lantern" Number="43" Volume="2005" Year="2009">
      <Id>550e8400-e29b-41d4-a716-446655440000</Id>
    </Book>
    <!-- More books... -->
  </Books>
  <Matchers />
</ReadingList>
```

**Field mapping:**
- `Series` - Series name from ComicVine (or parsed name if unmatched)
- `Number` - Issue number
- `Volume` - Series start year (e.g., "2005" for Green Lantern Vol. 4)
- `Year` - Issue publication year

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  CBRO Website   │────▶│   Parse HTML    │────▶│  Parsed Issues  │
│ (Reading Order) │     │  (BeautifulSoup)│     │  (Series + #)   │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   .cbl File     │◀────│  Match Issues   │◀────│  SQLite Cache   │
│ (ComicRack)     │     │  (ComicVine)    │     │  (30-day TTL)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. **Scrape** - Fetches reading order page from CBRO (respects 5s crawl delay)
2. **Parse** - Extracts issue references using regex patterns
3. **Match** - Looks up series/issues in ComicVine (cached in SQLite)
4. **Output** - Writes all issues to `.cbl` file in reading order

## Project Structure

```
cbro_parser/
├── __init__.py
├── main.py              # Entry point (GUI default, CLI with args)
├── cli.py               # Command-line interface
├── config.py            # Configuration from .env
├── models.py            # Pydantic data models
├── cache/
│   └── sqlite_cache.py  # Persistent SQLite cache
├── cbl/
│   ├── reader.py        # .cbl file reader
│   └── writer.py        # .cbl file writer
├── comicvine/
│   ├── api_client.py    # ComicVine API client
│   ├── matcher.py       # Series/issue matching logic
│   └── rate_limiter.py  # Sliding window rate limiter
├── gui/
│   ├── app.py           # Main tkinter application
│   └── progress_dialog.py
├── scraper/
│   ├── cbro_scraper.py  # Reading order page parser
│   └── index_scraper.py # Index page discovery
└── utils/
    └── text_normalizer.py
```

## Troubleshooting

### "No volumes found" for a series

The ComicVine search may not find exact matches. Try:
- Check if the series name on CBRO matches ComicVine's naming
- Use `--interactive` mode to manually select volumes
- Prepopulate the cache from existing `.cbl` files

### Rate limit errors

The parser respects ComicVine's rate limits automatically. If you see errors:
- Wait 15 minutes for the rate limit window to reset
- Check `cbro-parser stats` to see cache hit rates
- Prepopulate the cache to reduce API calls

### Missing issues in output

Run with `-v` (verbose) to see detailed parsing/matching logs:
```bash
cbro-parser parse URL -v --dry-run
```

## Dependencies

- `requests` - HTTP client
- `beautifulsoup4` + `lxml` - HTML parsing
- `python-dotenv` - Environment configuration
- `pydantic` - Data validation
- `tkinter` - GUI (included with Python)

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- [Comic Book Reading Orders](https://comicbookreadingorders.com) for the reading order data
- [ComicVine](https://comicvine.gamespot.com) for the comic database API
- [ComicRack](http://comicrack.cyolito.com/) for the `.cbl` format specification
