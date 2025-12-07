"""Text normalization utilities for series name matching."""

import re
from unicodedata import normalize as unicode_normalize


def normalize_series_name(name: str) -> str:
    """
    Normalize a series name for matching.

    Examples:
        "Green Lantern Vol. 2" -> "green lantern"
        "The Avengers" -> "avengers"
        "Batman: The Dark Knight" -> "batman dark knight"
        "The Amazing Spider-Man" -> "amazing spider man"

    Args:
        name: Original series name.

    Returns:
        Normalized name for comparison.
    """
    # Convert to lowercase
    name = name.lower()

    # Unicode normalization (handle accented characters)
    name = unicode_normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")

    # Remove volume indicators
    name = re.sub(r"\s+vol\.?\s*\d+", "", name)

    # Remove year in parentheses
    name = re.sub(r"\s*\(\d{4}\)", "", name)

    # Remove common prefixes
    name = re.sub(r"^the\s+", "", name)

    # Replace colons, dashes, and underscores with spaces
    name = re.sub(r"[:\-_]", " ", name)

    # Remove punctuation except apostrophes in words
    name = re.sub(r"[^\w\s']", "", name)

    # Remove standalone apostrophes but keep contractions
    name = re.sub(r"\s+'|'\s+", " ", name)

    # Normalize whitespace
    name = " ".join(name.split())

    return name.strip()


def normalize_issue_number(number: str) -> str:
    """
    Normalize an issue number for comparison.

    Examples:
        "1" -> "1"
        "001" -> "1"
        "1.5" -> "1.5"
        "1/2" -> "0.5"
        "½" -> "0.5"

    Args:
        number: Original issue number.

    Returns:
        Normalized issue number.
    """
    number = number.strip()

    # Handle Unicode fractions
    fraction_map = {
        "½": "0.5",
        "⅓": "0.333",
        "⅔": "0.667",
        "¼": "0.25",
        "¾": "0.75",
    }
    for frac, decimal in fraction_map.items():
        if frac in number:
            number = number.replace(frac, decimal)

    # Handle fractions like "1/2"
    if "/" in number:
        parts = number.split("/")
        if len(parts) == 2:
            try:
                numerator = float(parts[0])
                denominator = float(parts[1])
                if denominator != 0:
                    return str(numerator / denominator)
            except ValueError:
                pass

    # Remove leading zeros and normalize
    try:
        num = float(number)
        if num == int(num):
            return str(int(num))
        return str(num)
    except ValueError:
        return number


def build_search_query(series_name: str) -> str:
    """
    Build an optimized search query from series name.

    Removes volume indicators and year parentheticals that
    would confuse the search.

    Args:
        series_name: Original series name.

    Returns:
        Cleaned search query.
    """
    # Remove volume indicators for search
    query = re.sub(r"\s+Vol\.?\s*\d+", "", series_name, flags=re.IGNORECASE)

    # Remove year in parentheses
    query = re.sub(r"\s*\(\d{4}\)", "", query)

    # Remove trailing punctuation
    query = query.rstrip(".:;,-")

    return query.strip()


def extract_year_from_name(name: str) -> int | None:
    """
    Extract a year from a series name if present.

    Args:
        name: Series name possibly containing a year.

    Returns:
        Extracted year or None.
    """
    # Look for year in parentheses: "Batman (2016)"
    match = re.search(r"\((\d{4})\)", name)
    if match:
        return int(match.group(1))

    # Look for Vol. with year: "Vol. 2016"
    match = re.search(r"Vol\.?\s*(\d{4})", name, re.IGNORECASE)
    if match:
        year = int(match.group(1))
        if 1900 < year < 2100:  # Reasonable year range
            return year

    return None


def extract_volume_number(name: str) -> int | None:
    """
    Extract a volume number from a series name if present.

    Args:
        name: Series name possibly containing volume info.

    Returns:
        Volume number or None.
    """
    # Look for Vol. X pattern
    match = re.search(r"Vol\.?\s*(\d+)", name, re.IGNORECASE)
    if match:
        vol = int(match.group(1))
        if vol < 100:  # Volume numbers, not years
            return vol
    return None
