"""Tests for cbro_parser.cbl.reader and writer modules."""

import pytest
from pathlib import Path

from cbro_parser.cbl.reader import CBLReader, read_reading_list
from cbro_parser.cbl.writer import CBLWriter, write_reading_list
from cbro_parser.models import MatchedBook, ReadingList


class TestCBLWriter:
    """Tests for CBLWriter class."""

    def test_write_empty_list(self, temp_dir):
        """Test writing an empty reading list."""
        writer = CBLWriter()
        reading_list = ReadingList(name="Empty List")
        output_path = temp_dir / "empty.cbl"

        writer.write(reading_list, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "Empty List" in content
        # Books element may be empty or self-closing
        assert "<Books" in content

    def test_write_single_book(self, temp_dir, sample_matched_book):
        """Test writing a list with one book."""
        writer = CBLWriter()
        reading_list = ReadingList(
            name="Single Book List",
            books=[sample_matched_book],
        )
        output_path = temp_dir / "single.cbl"

        writer.write(reading_list, output_path)

        content = output_path.read_text()
        assert 'Series="Green Lantern"' in content
        assert 'Number="1"' in content
        assert 'Volume="2005"' in content
        assert 'Year="2005"' in content

    def test_write_multiple_books(self, temp_dir):
        """Test writing a list with multiple books."""
        writer = CBLWriter()
        books = [
            MatchedBook(series="Batman", number="1", volume="2016", year="2016"),
            MatchedBook(series="Batman", number="2", volume="2016", year="2016"),
            MatchedBook(series="Batman", number="3", volume="2016", year="2016"),
        ]
        reading_list = ReadingList(name="Batman Order", books=books)
        output_path = temp_dir / "batman.cbl"

        writer.write(reading_list, output_path)

        content = output_path.read_text()
        # Count Book elements (may include closing tags)
        assert content.count('Series="Batman"') == 3
        assert 'Number="1"' in content
        assert 'Number="2"' in content
        assert 'Number="3"' in content

    def test_write_with_format(self, temp_dir):
        """Test writing book with format type."""
        writer = CBLWriter()
        book = MatchedBook(
            series="Batman",
            number="1",
            volume="2016",
            year="2016",
            format_type="Annual",
        )
        reading_list = ReadingList(name="Test", books=[book])
        output_path = temp_dir / "format.cbl"

        writer.write(reading_list, output_path)

        content = output_path.read_text()
        assert 'Format="Annual"' in content

    def test_write_creates_parent_dirs(self, temp_dir):
        """Test that write creates parent directories."""
        writer = CBLWriter()
        reading_list = ReadingList(name="Test")
        output_path = temp_dir / "subdir" / "nested" / "test.cbl"

        writer.write(reading_list, output_path)

        assert output_path.exists()

    def test_write_xml_declaration(self, temp_dir):
        """Test XML declaration in output."""
        writer = CBLWriter()
        reading_list = ReadingList(name="Test")
        output_path = temp_dir / "test.cbl"

        writer.write(reading_list, output_path)

        content = output_path.read_text()
        assert content.startswith('<?xml version="1.0"?>')

    def test_write_namespaces(self, temp_dir):
        """Test XML namespaces in output."""
        writer = CBLWriter()
        reading_list = ReadingList(name="Test")
        output_path = temp_dir / "test.cbl"

        writer.write(reading_list, output_path)

        content = output_path.read_text()
        assert 'xmlns:xsd="http://www.w3.org/2001/XMLSchema"' in content
        assert 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' in content

    def test_write_has_matchers_element(self, temp_dir):
        """Test that output includes Matchers element."""
        writer = CBLWriter()
        reading_list = ReadingList(name="Test")
        output_path = temp_dir / "test.cbl"

        writer.write(reading_list, output_path)

        content = output_path.read_text()
        assert "<Matchers/>" in content or "<Matchers>" in content


class TestCBLReader:
    """Tests for CBLReader class."""

    def test_read_basic(self, temp_dir, sample_cbl_content):
        """Test reading a basic CBL file."""
        cbl_path = temp_dir / "test.cbl"
        cbl_path.write_text(sample_cbl_content)

        reader = CBLReader()
        reading_list = reader.read(cbl_path)

        assert reading_list.name == "Test Reading List"
        assert len(reading_list.books) == 2

    def test_read_book_attributes(self, temp_dir, sample_cbl_content):
        """Test that book attributes are read correctly."""
        cbl_path = temp_dir / "test.cbl"
        cbl_path.write_text(sample_cbl_content)

        reader = CBLReader()
        reading_list = reader.read(cbl_path)

        book = reading_list.books[0]
        assert book.series == "Green Lantern"
        assert book.number == "1"
        assert book.volume == "2005"
        assert book.year == "2005"
        assert book.book_id == "test-uuid-1234"

    def test_read_book_with_format(self, temp_dir, sample_cbl_content):
        """Test reading book with format attribute."""
        cbl_path = temp_dir / "test.cbl"
        cbl_path.write_text(sample_cbl_content)

        reader = CBLReader()
        reading_list = reader.read(cbl_path)

        book = reading_list.books[1]
        assert book.format_type == "Annual"

    def test_read_empty_books(self, temp_dir):
        """Test reading file with no books."""
        content = '''<?xml version="1.0"?>
<ReadingList>
  <Name>Empty</Name>
  <Books></Books>
</ReadingList>'''
        cbl_path = temp_dir / "empty.cbl"
        cbl_path.write_text(content)

        reader = CBLReader()
        reading_list = reader.read(cbl_path)

        assert reading_list.name == "Empty"
        assert len(reading_list.books) == 0

    def test_read_uses_filename_as_fallback_name(self, temp_dir):
        """Test that filename is used when Name element missing."""
        content = '''<?xml version="1.0"?>
<ReadingList>
  <Books></Books>
</ReadingList>'''
        cbl_path = temp_dir / "my_list.cbl"
        cbl_path.write_text(content)

        reader = CBLReader()
        reading_list = reader.read(cbl_path)

        assert reading_list.name == "my_list"

    def test_read_all(self, temp_dir, sample_cbl_content):
        """Test reading all CBL files from directory."""
        # Create multiple CBL files
        (temp_dir / "list1.cbl").write_text(sample_cbl_content)
        (temp_dir / "list2.cbl").write_text(sample_cbl_content.replace(
            "Test Reading List", "Second List"
        ))

        reader = CBLReader()
        reading_lists = list(reader.read_all(temp_dir))

        assert len(reading_lists) == 2

    def test_read_all_recursive(self, temp_dir, sample_cbl_content):
        """Test reading CBL files recursively."""
        # Create nested structure
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        (temp_dir / "root.cbl").write_text(sample_cbl_content)
        (subdir / "nested.cbl").write_text(sample_cbl_content)

        reader = CBLReader()
        reading_lists = list(reader.read_all(temp_dir))

        assert len(reading_lists) == 2

    def test_read_all_handles_invalid_files(self, temp_dir, sample_cbl_content):
        """Test that invalid files don't crash read_all."""
        (temp_dir / "valid.cbl").write_text(sample_cbl_content)
        (temp_dir / "invalid.cbl").write_text("not valid xml <broken")

        reader = CBLReader()
        reading_lists = list(reader.read_all(temp_dir))

        # Should get the valid one, skip invalid
        assert len(reading_lists) == 1


class TestRoundTrip:
    """Tests for writing and reading back."""

    def test_roundtrip_preserves_data(self, temp_dir):
        """Test that write then read preserves data."""
        original_books = [
            MatchedBook(
                series="Batman",
                number="1",
                volume="2016",
                year="2016",
                book_id="custom-id-1",
            ),
            MatchedBook(
                series="Batman",
                number="2",
                volume="2016",
                year="2016",
                format_type="Special",
                book_id="custom-id-2",
            ),
        ]
        original = ReadingList(name="Batman Reading Order", books=original_books)

        output_path = temp_dir / "roundtrip.cbl"

        writer = CBLWriter()
        writer.write(original, output_path)

        reader = CBLReader()
        loaded = reader.read(output_path)

        assert loaded.name == original.name
        assert len(loaded.books) == len(original.books)

        for orig, loaded_book in zip(original.books, loaded.books):
            assert loaded_book.series == orig.series
            assert loaded_book.number == orig.number
            assert loaded_book.volume == orig.volume
            assert loaded_book.year == orig.year
            assert loaded_book.book_id == orig.book_id


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_read_reading_list(self, temp_dir, sample_cbl_content):
        """Test read_reading_list convenience function."""
        cbl_path = temp_dir / "test.cbl"
        cbl_path.write_text(sample_cbl_content)

        reading_list = read_reading_list(cbl_path)

        assert reading_list.name == "Test Reading List"

    def test_write_reading_list(self, temp_dir):
        """Test write_reading_list convenience function."""
        reading_list = ReadingList(name="Convenience Test")
        output_path = temp_dir / "convenience.cbl"

        write_reading_list(reading_list, output_path)

        assert output_path.exists()


class TestCBLReaderExtractSeriesVolumePairs:
    """Tests for extract_series_volume_pairs method."""

    def test_extract_series_volume_pairs(self, temp_dir, sample_cbl_content):
        """Test extracting series/volume pairs from CBL files."""
        cbl_path = temp_dir / "test.cbl"
        cbl_path.write_text(sample_cbl_content)

        reader = CBLReader()
        pairs = reader.extract_series_volume_pairs(temp_dir)

        assert len(pairs) > 0
        # Should have (series, volume) tuples
        assert all(isinstance(p, tuple) and len(p) == 2 for p in pairs)

    def test_extract_series_volume_pairs_empty_dir(self, temp_dir):
        """Test extracting from empty directory."""
        reader = CBLReader()
        pairs = reader.extract_series_volume_pairs(temp_dir)

        assert pairs == []

    def test_extract_series_volume_pairs_skips_incomplete(self, temp_dir):
        """Test that incomplete entries are skipped."""
        content = '''<?xml version="1.0"?>
<ReadingList>
  <Name>Test</Name>
  <Books>
    <Book Series="Batman" Number="1" Volume="" Year="2016">
      <Id>test-id</Id>
    </Book>
    <Book Series="" Number="1" Volume="2016" Year="2016">
      <Id>test-id-2</Id>
    </Book>
  </Books>
</ReadingList>'''
        cbl_path = temp_dir / "incomplete.cbl"
        cbl_path.write_text(content)

        reader = CBLReader()
        pairs = reader.extract_series_volume_pairs(temp_dir)

        # Should skip entries without series or volume
        assert len(pairs) == 0
