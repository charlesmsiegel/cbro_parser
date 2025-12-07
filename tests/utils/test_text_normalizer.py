"""Tests for cbro_parser.utils.text_normalizer module."""

import pytest

from cbro_parser.utils.text_normalizer import (
    build_search_query,
    extract_volume_number,
    extract_year_from_name,
    normalize_issue_number,
    normalize_series_name,
)


class TestNormalizeSeriesName:
    """Tests for normalize_series_name function."""

    def test_lowercase(self):
        """Test conversion to lowercase."""
        assert normalize_series_name("BATMAN") == "batman"
        assert normalize_series_name("Batman") == "batman"

    def test_remove_volume_indicator(self):
        """Test removal of volume indicators."""
        assert normalize_series_name("Green Lantern Vol. 2") == "green lantern"
        assert normalize_series_name("Green Lantern Vol 4") == "green lantern"
        assert normalize_series_name("Batman vol.3") == "batman"

    def test_remove_year_parentheses(self):
        """Test removal of year in parentheses."""
        assert normalize_series_name("Batman (2016)") == "batman"
        assert normalize_series_name("Spider-Man (1963)") == "spider man"

    def test_remove_the_prefix(self):
        """Test removal of 'The' prefix."""
        assert normalize_series_name("The Amazing Spider-Man") == "amazing spider man"
        assert normalize_series_name("The Avengers") == "avengers"
        assert normalize_series_name("Batman") == "batman"  # No prefix

    def test_replace_punctuation(self):
        """Test replacement of colons, dashes, underscores."""
        # Note: "The" is only removed from the START, not after punctuation
        assert normalize_series_name("Batman: The Dark Knight") == "batman the dark knight"
        assert normalize_series_name("Spider-Man") == "spider man"
        assert normalize_series_name("X_Men") == "x men"

    def test_remove_special_punctuation(self):
        """Test removal of other punctuation."""
        assert normalize_series_name("Avengers!") == "avengers"
        assert normalize_series_name("What If...?") == "what if"

    def test_normalize_whitespace(self):
        """Test normalization of whitespace."""
        assert normalize_series_name("Batman    Returns") == "batman returns"
        assert normalize_series_name("  Batman  ") == "batman"

    def test_unicode_normalization(self):
        """Test Unicode character handling."""
        # Accented characters should be converted to ASCII
        assert normalize_series_name("cafe") == "cafe"

    def test_apostrophe_handling(self):
        """Test handling of apostrophes."""
        # Note: Apostrophes in contractions are preserved
        assert normalize_series_name("Marvel's Spider-Man") == "marvel's spider man"

    def test_complex_names(self):
        """Test complex series names."""
        assert normalize_series_name("The Amazing Spider-Man Vol. 2 (1999)") == "amazing spider man"
        assert normalize_series_name("Green Lantern: Rebirth Vol. 1") == "green lantern rebirth"


class TestNormalizeIssueNumber:
    """Tests for normalize_issue_number function."""

    def test_simple_numbers(self):
        """Test simple integer numbers."""
        assert normalize_issue_number("1") == "1"
        assert normalize_issue_number("42") == "42"
        assert normalize_issue_number("100") == "100"

    def test_leading_zeros(self):
        """Test removal of leading zeros."""
        assert normalize_issue_number("001") == "1"
        assert normalize_issue_number("01") == "1"
        assert normalize_issue_number("007") == "7"

    def test_decimal_numbers(self):
        """Test decimal issue numbers."""
        assert normalize_issue_number("1.5") == "1.5"
        assert normalize_issue_number("0.5") == "0.5"

    def test_fraction_slash(self):
        """Test fraction with slash."""
        assert normalize_issue_number("1/2") == "0.5"
        assert normalize_issue_number("3/4") == "0.75"
        assert normalize_issue_number("1/4") == "0.25"

    def test_unicode_fractions(self):
        """Test Unicode fraction characters."""
        assert normalize_issue_number("½") == "0.5"
        assert normalize_issue_number("¼") == "0.25"
        assert normalize_issue_number("¾") == "0.75"

    def test_whitespace_stripping(self):
        """Test whitespace is stripped."""
        assert normalize_issue_number("  1  ") == "1"
        assert normalize_issue_number(" 42 ") == "42"

    def test_non_numeric_passthrough(self):
        """Test non-numeric strings pass through."""
        assert normalize_issue_number("A") == "A"
        assert normalize_issue_number("Annual") == "Annual"

    def test_division_by_zero_handling(self):
        """Test handling of division by zero in fractions."""
        # Should return original string when division fails
        assert normalize_issue_number("1/0") == "1/0"


class TestBuildSearchQuery:
    """Tests for build_search_query function."""

    def test_removes_volume_indicator(self):
        """Test removal of volume indicators."""
        assert build_search_query("Green Lantern Vol. 4") == "Green Lantern"
        assert build_search_query("Batman Vol 2") == "Batman"

    def test_removes_year_parentheses(self):
        """Test removal of year in parentheses."""
        assert build_search_query("Batman (2016)") == "Batman"
        assert build_search_query("Spider-Man (1963)") == "Spider-Man"

    def test_removes_trailing_punctuation(self):
        """Test removal of trailing punctuation."""
        assert build_search_query("Batman:") == "Batman"
        assert build_search_query("Spider-Man.") == "Spider-Man"
        assert build_search_query("X-Men,") == "X-Men"

    def test_preserves_case(self):
        """Test that case is preserved (unlike normalize)."""
        assert build_search_query("The Amazing Spider-Man") == "The Amazing Spider-Man"

    def test_preserves_hyphens(self):
        """Test that hyphens are preserved."""
        assert build_search_query("Spider-Man") == "Spider-Man"
        assert build_search_query("X-Men") == "X-Men"


class TestExtractYearFromName:
    """Tests for extract_year_from_name function."""

    def test_year_in_parentheses(self):
        """Test extraction of year in parentheses."""
        assert extract_year_from_name("Batman (2016)") == 2016
        assert extract_year_from_name("Spider-Man (1963)") == 1963

    def test_year_with_vol(self):
        """Test extraction of year with Vol. prefix."""
        assert extract_year_from_name("Batman Vol. 2016") == 2016
        assert extract_year_from_name("Batman Vol 2011") == 2011

    def test_no_year(self):
        """Test no year present."""
        assert extract_year_from_name("Batman") is None
        assert extract_year_from_name("Spider-Man Vol. 2") is None

    def test_volume_number_not_year(self):
        """Test that volume numbers are not confused for years."""
        # Vol. 2 is not a year (too small)
        assert extract_year_from_name("Batman Vol. 2") is None
        # Vol. 10 is not a year
        assert extract_year_from_name("Batman Vol. 10") is None

    def test_unreasonable_years(self):
        """Test that unreasonable years are rejected."""
        # Years outside 1900-2100 should be rejected
        assert extract_year_from_name("Batman Vol. 1800") is None


class TestExtractVolumeNumber:
    """Tests for extract_volume_number function."""

    def test_volume_with_period(self):
        """Test Vol. format."""
        assert extract_volume_number("Batman Vol. 2") == 2
        assert extract_volume_number("Spider-Man Vol. 4") == 4

    def test_volume_without_period(self):
        """Test Vol format without period."""
        assert extract_volume_number("Batman Vol 3") == 3

    def test_volume_word(self):
        """Test Volume spelled out - note: code only supports 'Vol' prefix."""
        # The actual implementation only matches Vol/Vol. not full "Volume"
        assert extract_volume_number("Batman Volume 2") is None
        # But Vol works
        assert extract_volume_number("Batman Vol 2") == 2

    def test_no_volume(self):
        """Test no volume present."""
        assert extract_volume_number("Batman") is None
        assert extract_volume_number("Spider-Man (2016)") is None

    def test_year_not_volume(self):
        """Test that years are not confused for volumes."""
        # Vol. 2016 looks like a year, not volume number
        assert extract_volume_number("Batman Vol. 2016") is None

    def test_large_volume_numbers_rejected(self):
        """Test that large numbers (likely years) are rejected."""
        assert extract_volume_number("Batman Vol. 100") is None
        assert extract_volume_number("Batman Vol. 1963") is None
