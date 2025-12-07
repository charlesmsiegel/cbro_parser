# CBRO Parser - TODO / Improvement List

A comprehensive list of issues, pain points, and areas for improvement identified through codebase analysis.

---

## Priority 1: Critical Issues

### Security

- [x] **API Key Exposed** - The `.env` file contains a plaintext API key that may be in git history. Rotate the key immediately and ensure `.env` is in `.gitignore` - **VERIFIED: `.env` was never committed and is properly gitignored**
- [x] **XXE Vulnerability** - `cbl/reader.py:23` uses `ET.parse()` without protection against XML External Entity attacks. Use `defusedxml` or configure the parser safely - **FIXED: Now uses `defusedxml.ElementTree`**

### Testing

- [x] **No Test Suite** - Despite `pytest` and `pytest-cov` being declared as dev dependencies, there are zero test files in the repository. Critical components completely untested:
  - API client error handling
  - Cache expiry logic
  - Matcher scoring algorithm
  - HTML parsing patterns
  - GUI threading logic
  - **FIXED: Comprehensive test suite created with 235 tests and 92% coverage**

---

## Priority 2: High Impact Issues

### Bug Fixes

- [ ] **Batch Mode Loses Data** - `cli.py:320-324` discards unmatched books in batch mode, but single parse mode preserves them (`cli.py:248-250`). Inconsistent behavior causes data loss

### Thread Safety

- [ ] **Global Config Not Thread-Safe** - `config.py:72,80` uses global variable pattern without thread safety, but GUI uses multiple threads (`app.py:339,418`)
- [ ] **Daemon Threads Without Cleanup** - `gui/app.py:339,418` creates daemon threads with no proper shutdown handling or synchronization

### Code Duplication

- [ ] **Crawl Delay Logic Duplicated** - Identical implementation in:
  - `scraper/cbro_scraper.py:69-74`
  - `scraper/index_scraper.py:128-133`
  - Extract to shared utility

- [ ] **Reading Order Name Extraction Duplicated** - Same logic in:
  - `scraper/cbro_scraper.py:314-333`
  - `scraper/index_scraper.py:287-298`

---

## Priority 3: Medium Impact Issues

### Error Handling

- [ ] **Inconsistent Error Reporting** - Mix of `print()` (35 instances) and `logging` (28 instances). Standardize on logging throughout
- [ ] **Bare Exception Handling** - `cli.py:234` catches all exceptions without specific handling. Similar issues in:
  - `cbl/reader.py:59-62`
  - `scraper/index_scraper.py:105-107`
  - `gui/app.py:356-367`
- [ ] **Missing Error Context** - Exceptions re-raised without adding context (`cache/sqlite_cache.py:93`)

### Performance

- [ ] **Recursive Pagination Risk** - `api_client.py:206` uses recursive calls for pagination with no depth limit. Could stack overflow for series with 10,000+ issues
- [ ] **Regex Not Precompiled** - `scraper/cbro_scraper.py:22-50` patterns recompiled on every use. Should be module-level compiled constants
- [ ] **Cache Full Table Scans** - `cache/sqlite_cache.py:339-373` `clear_expired()` runs full table scans
- [ ] **GUI Event Queue Buildup** - `gui/app.py:447-545` could queue thousands of update events via `root.after(0, ...)`

### Hardcoded Values

Values that should be configurable:

| Value | Location | Current |
|-------|----------|---------|
| HTTP timeout | `api_client.py:52`, `cbro_scraper.py:91`, `index_scraper.py:203` | 30s hardcoded 3x |
| Regex patterns | `cbro_scraper.py:22-50` | Hardcoded |
| Cache filename | `index_scraper.py:66` | "reading_orders_cache.json" |
| Pagination limit | `api_client.py:187` | 100 |
| API field lists | `api_client.py:81,132-135,184` | Hardcoded 3x |
| Search limit | `api_client.py:64` | 10 |
| Volume candidate limit | `matcher.py:270` | 10 |
| Year thresholds | `matcher.py:245`, `text_normalizer.py:151` | 2100, 1900 |
| GUI window sizes | `app.py:32`, `progress_dialog.py:26` | Hardcoded |

### Type Safety

- [ ] **Weak Callback Types** - `index_scraper.py:136` uses `callable` instead of proper `Callable[[int, int, str], None]`
- [ ] **Missing TypedDict** - `cbro_scraper.py:201` uses `dict | None` where TypedDict would be clearer
- [ ] **No Runtime Validation** - Intermediate parsing steps have no Pydantic validation

---

## Priority 4: Lower Impact / Nice to Have

### Documentation

- [ ] **Empty Module Docstrings** - `cache/__init__.py`, `gui/__init__.py`, `utils/__init__.py`, `scraper/__init__.py`
- [ ] **Scoring Algorithm Undocumented** - `matcher.py:165-234` has magic numbers without explanation
- [ ] **Complex Parsing Logic** - `cbro_scraper.py:96-181` needs inline comments
- [ ] **Configuration Options** - README missing docs for socket timeout, regex patterns, pagination settings

### Magic Numbers

- [ ] `matcher.py:203,205,207` - Year matching thresholds (0, 1, 3 years) unexplained
- [ ] `matcher.py:210-213` - Issue count scoring (10, 50) unexplained
- [ ] `matcher.py:230` - Score threshold (50) has no justification
- [ ] `rate_limiter.py:21` - min_interval hardcoded to 1.0

### Dead / Incomplete Code

- [ ] **Unused Function** - `cbl/reader.py:64-85` `extract_series_volume_pairs()` defined but never called
- [ ] **Interactive Mode Incomplete** - `matcher.py:263-287` only works in CLI, GUI always passes `interactive=False`
- [ ] **Dry-Run Incomplete** - `cli.py:267-269` doesn't validate output paths or permissions
- [ ] **Prepopulate Placeholder** - `cli.py:176` uses `cv_volume_id = -1` placeholder that's never verified

### Inconsistent Naming

- [ ] **CV Prefix Inconsistent** - Mix of `cv_volume_id`, `cv_issue_id`, `cv_base_url` vs full `comicvine_` prefix

### Dependency Management

- [ ] **No Upper Version Bounds** - `pyproject.toml` uses `>=` without upper limits, risking breaking changes
- [ ] **Missing Type Stubs** - No mypy/pyright configuration for static type checking
- [ ] **No Logging Library** - Manual logging configuration, consider `structlog` or similar

### Missing Features

- [ ] **No Log Persistence** - No log files, rotation, or archival
- [ ] **No Progress Persistence** - Batch processing can't resume from failures
- [ ] **No Conflict Resolution** - Duplicate reading orders not deduplicated
- [ ] **No Metadata Preservation** - Source URL/timestamp not stored in output .cbl files
- [ ] **No Output Validation** - No schema validation of generated .cbl files

---

## Quick Reference: Files with Most Issues

| File | Issue Count | Primary Concerns |
|------|-------------|------------------|
| `cli.py` | 5 | Error handling, batch mode bug, hardcoded values |
| `matcher.py` | 5 | Magic numbers, incomplete interactive mode, typing |
| `api_client.py` | 4 | Hardcoded values, recursive pagination |
| `cbro_scraper.py` | 4 | Regex, duplication, documentation |
| `gui/app.py` | 4 | Threading, event queue, closures |
| `config.py` | 2 | Thread safety, global state |
| `cbl/reader.py` | 2 | XXE vulnerability, dead code |

---

## Testing Recommendations - COMPLETED

Test suite implemented with 235 tests and 92% coverage:

1. **Unit Tests** - DONE
   - [x] Cache operations (`sqlite_cache.py`) - 23 tests
   - [x] Text normalization (`text_normalizer.py`) - 34 tests
   - [x] Matcher scoring algorithm (`matcher.py`) - 22 tests
   - [x] Issue pattern parsing (`cbro_scraper.py`) - 34 tests

2. **Integration Tests** - DONE
   - [x] Full parsing pipeline (URL -> CBL file) - via CLI tests
   - [x] API client with mocked responses - 15 tests
   - [x] CLI commands end-to-end - 14 tests

3. **Fixture Data** - DONE (in `conftest.py`)
   - [x] Sample CBRO HTML pages
   - [x] Known ComicVine API responses (mocked)
   - [x] Edge case reading orders
