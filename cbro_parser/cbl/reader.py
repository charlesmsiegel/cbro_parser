"""Reader for ComicRack .cbl reading list files."""

from pathlib import Path
from typing import Generator

import defusedxml.ElementTree as ET

from ..models import MatchedBook, ReadingList


class CBLReader:
    """Reads ComicRack .cbl reading list files."""

    def read(self, file_path: Path) -> ReadingList:
        """
        Read a .cbl file into a ReadingList.

        Args:
            file_path: Path to the .cbl file.

        Returns:
            ReadingList object.
        """
        tree = ET.parse(file_path)
        root = tree.getroot()

        name = root.findtext("Name", default=file_path.stem)
        books = []

        books_elem = root.find("Books")
        if books_elem is not None:
            for book_elem in books_elem.findall("Book"):
                book = MatchedBook(
                    series=book_elem.get("Series", ""),
                    number=book_elem.get("Number", ""),
                    volume=book_elem.get("Volume", ""),
                    year=book_elem.get("Year", ""),
                    format_type=book_elem.get("Format"),
                    book_id=book_elem.findtext("Id", ""),
                )
                books.append(book)

        return ReadingList(name=name, books=books)

    def read_all(self, directory: Path) -> Generator[ReadingList, None, None]:
        """
        Read all .cbl files from a directory recursively.

        Args:
            directory: Root directory to search.

        Yields:
            ReadingList objects.
        """
        for cbl_path in directory.rglob("*.cbl"):
            try:
                yield self.read(cbl_path)
            except ET.ParseError as e:
                print(f"Warning: Failed to parse {cbl_path}: {e}")
            except Exception as e:
                print(f"Warning: Error reading {cbl_path}: {e}")

    def extract_series_volume_pairs(self, directory: Path) -> list[tuple[str, str]]:
        """
        Extract unique series/volume pairs from all .cbl files.

        Useful for cache prepopulation.

        Args:
            directory: Root directory containing .cbl files.

        Returns:
            List of (series_name, volume_year) tuples.
        """
        pairs = set()

        for reading_list in self.read_all(directory):
            for book in reading_list.books:
                if book.series and book.volume:
                    pairs.add((book.series, book.volume))

        return sorted(pairs)


def read_reading_list(file_path: Path) -> ReadingList:
    """
    Convenience function to read a reading list.

    Args:
        file_path: Path to the .cbl file.

    Returns:
        ReadingList object.
    """
    reader = CBLReader()
    return reader.read(file_path)
