"""Writer for ComicRack-compatible .cbl reading list files."""

import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

from ..models import ReadingList


class CBLWriter:
    """Writes ComicRack-compatible .cbl reading list files."""

    def write(self, reading_list: ReadingList, output_path: Path) -> None:
        """
        Write a reading list to a .cbl file.

        Args:
            reading_list: The reading list to write.
            output_path: Path to the output .cbl file.
        """
        # Create root element with namespaces
        root = ET.Element("ReadingList")
        root.set("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")

        # Add name
        name_elem = ET.SubElement(root, "Name")
        name_elem.text = reading_list.name

        # Add books
        books_elem = ET.SubElement(root, "Books")

        for book in reading_list.books:
            book_elem = ET.SubElement(books_elem, "Book")
            book_elem.set("Series", book.series)
            book_elem.set("Number", book.number)
            book_elem.set("Volume", book.volume)
            book_elem.set("Year", book.year)

            if book.format_type:
                book_elem.set("Format", book.format_type)

            # Add Id child element
            id_elem = ET.SubElement(book_elem, "Id")
            id_elem.text = book.book_id

        # Add empty Matchers element
        ET.SubElement(root, "Matchers")

        # Format and write
        xml_string = self._prettify(root)

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_string)

    def _prettify(self, elem: ET.Element) -> str:
        """Return a pretty-printed XML string."""
        rough_string = ET.tostring(elem, encoding="unicode")
        reparsed = minidom.parseString(rough_string)

        # Get pretty printed version
        pretty = reparsed.toprettyxml(indent="  ")

        # Fix the declaration and clean up
        lines = pretty.split("\n")
        # Replace first line with proper declaration
        lines[0] = '<?xml version="1.0"?>'

        # Remove empty lines but keep structure
        cleaned_lines = []
        for line in lines:
            # Skip completely empty lines
            if line.strip():
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)


def write_reading_list(reading_list: ReadingList, output_path: Path) -> None:
    """
    Convenience function to write a reading list.

    Args:
        reading_list: The reading list to write.
        output_path: Path to the output .cbl file.
    """
    writer = CBLWriter()
    writer.write(reading_list, output_path)
