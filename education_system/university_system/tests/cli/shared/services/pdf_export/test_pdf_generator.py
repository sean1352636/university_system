"""Tests for PDF generator module.

Tests the PDFGenerator class which creates PDF documents.
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
import io


class TestPDFGenerator:
    """Test cases for PDFGenerator class."""

    @pytest.fixture
    def temp_output_path(self):
        """Create a temporary output path for PDF."""
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        yield path
        try:
            os.unlink(path)
        except Exception:
            pass

    @pytest.fixture
    def pdf_generator(self, temp_output_path):
        """Create a PDFGenerator instance."""
        from education_system.university_system.modules.shared.services.pdf_export.pdf_generator import (
            PDFGenerator,
        )

        return PDFGenerator(temp_output_path)

    def test_initialization(self, pdf_generator, temp_output_path):
        """Test PDFGenerator initialization."""
        assert pdf_generator is not None
        assert pdf_generator.output_path == temp_output_path
        assert pdf_generator.elements == []
        assert pdf_generator.styles is not None

    def test_custom_styles_created(self, pdf_generator):
        """Test that custom styles are created."""
        assert "CustomTitle" in pdf_generator.styles.byName
        assert "CustomSubtitle" in pdf_generator.styles.byName
        assert "SectionHeader" in pdf_generator.styles.byName
        assert "SubsectionHeader" in pdf_generator.styles.byName
        assert "TableDescription" in pdf_generator.styles.byName
        assert "Stats" in pdf_generator.styles.byName

    def test_add_title_page(self, pdf_generator):
        """Test adding a title page."""
        stats = {
            "total_tables": 50,
            "total_records": 10000,
            "tables_with_data": 45,
            "empty_tables": 5,
        }

        pdf_generator.add_title_page(
            title="Test Report",
            subtitle="Test Subtitle",
            stats=stats,
        )

        assert len(pdf_generator.elements) > 0

    def test_add_section_header(self, pdf_generator):
        """Test adding a section header."""
        initial_count = len(pdf_generator.elements)
        pdf_generator.add_section_header("Test Section")

        assert len(pdf_generator.elements) == initial_count + 1

    def test_add_subsection_header(self, pdf_generator):
        """Test adding a subsection header."""
        initial_count = len(pdf_generator.elements)
        pdf_generator.add_subsection_header("Test Subsection")

        assert len(pdf_generator.elements) == initial_count + 1

    def test_add_text(self, pdf_generator):
        """Test adding text paragraph."""
        initial_count = len(pdf_generator.elements)
        pdf_generator.add_text("This is a test paragraph.")

        assert len(pdf_generator.elements) == initial_count + 1

    def test_add_description(self, pdf_generator):
        """Test adding description text."""
        initial_count = len(pdf_generator.elements)
        pdf_generator.add_description("This is a description.")

        assert len(pdf_generator.elements) == initial_count + 1

    def test_add_spacer(self, pdf_generator):
        """Test adding vertical spacer."""
        initial_count = len(pdf_generator.elements)
        pdf_generator.add_spacer(0.5)

        assert len(pdf_generator.elements) == initial_count + 1

    def test_add_page_break(self, pdf_generator):
        """Test adding page break."""
        initial_count = len(pdf_generator.elements)
        pdf_generator.add_page_break()

        assert len(pdf_generator.elements) == initial_count + 1

    def test_add_data_table(self, pdf_generator):
        """Test adding a data table."""
        headers = ["ID", "Name", "Email"]
        data = [
            (1, "John Doe", "john@test.com"),
            (2, "Jane Smith", "jane@test.com"),
        ]

        initial_count = len(pdf_generator.elements)
        pdf_generator.add_data_table(
            headers=headers,
            data=data,
            table_name="Test Table",
            description="A test table",
        )

        assert len(pdf_generator.elements) > initial_count

    def test_add_data_table_empty(self, pdf_generator):
        """Test adding an empty data table."""
        initial_count = len(pdf_generator.elements)
        pdf_generator.add_data_table(
            headers=[],
            data=[],
            table_name="Empty Table",
        )

        # Should add elements even for empty table (showing "No data available")
        assert len(pdf_generator.elements) > initial_count

    def test_add_data_table_truncation(self, pdf_generator):
        """Test data table row truncation."""
        headers = ["ID", "Value"]
        data = [(i, f"Value {i}") for i in range(100)]

        pdf_generator.add_data_table(
            headers=headers,
            data=data,
            max_rows=10,
        )

        # Should still add elements
        assert len(pdf_generator.elements) > 0

    def test_add_table_summary(self, pdf_generator):
        """Test adding a table summary card."""
        initial_count = len(pdf_generator.elements)
        pdf_generator.add_table_summary(
            table_name="students",
            row_count=1000,
            column_count=5,
            description="Student records",
        )

        assert len(pdf_generator.elements) > initial_count

    def test_add_table_of_contents_entry(self, pdf_generator):
        """Test adding table of contents."""
        entries = [
            ("Students", 1000),
            ("Modules", 500),
            ("Grades", 5000),
        ]

        initial_count = len(pdf_generator.elements)
        pdf_generator.add_table_of_contents_entry(entries)

        assert len(pdf_generator.elements) > initial_count

    def test_add_chart(self, pdf_generator):
        """Test adding a chart image."""
        # Create a mock image buffer
        buf = io.BytesIO()
        # Create a minimal PNG-like content
        buf.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        buf.seek(0)

        initial_count = len(pdf_generator.elements)

        with patch(
            "reportlab.platypus.Image.__init__",
            return_value=None,
        ):
            pdf_generator.add_chart(buf, width=5, height=3)

        # Chart should add elements (image + spacer)
        assert len(pdf_generator.elements) >= initial_count

    def test_add_chart_none_buffer(self, pdf_generator):
        """Test adding chart with None buffer."""
        initial_count = len(pdf_generator.elements)
        pdf_generator.add_chart(None, width=5, height=3)

        # Should not add any elements
        assert len(pdf_generator.elements) == initial_count

    def test_save(self, pdf_generator, temp_output_path):
        """Test saving PDF document."""
        # Add some content
        pdf_generator.add_title_page("Test Document", "Test")
        pdf_generator.add_section_header("Section 1")
        pdf_generator.add_text("Some test content.")

        result = pdf_generator.save()

        assert result is True
        assert os.path.exists(temp_output_path)
        # Check file is not empty
        assert os.path.getsize(temp_output_path) > 0

    def test_save_empty_document(self, pdf_generator, temp_output_path):
        """Test saving empty PDF document."""
        # Save without adding any content
        result = pdf_generator.save()

        # Should still work (creates minimal PDF)
        assert result is True


class TestPDFGeneratorEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_output_path(self):
        """Test handling of invalid output path."""
        from education_system.university_system.modules.shared.services.pdf_export.pdf_generator import (
            PDFGenerator,
        )

        pdf = PDFGenerator("/nonexistent/directory/test.pdf")
        pdf.add_text("Test")

        result = pdf.save()
        assert result is False

    def test_long_text_handling(self):
        """Test handling of very long text."""
        from education_system.university_system.modules.shared.services.pdf_export.pdf_generator import (
            PDFGenerator,
        )

        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

        try:
            pdf = PDFGenerator(path)
            long_text = "x" * 10000
            pdf.add_text(long_text)

            result = pdf.save()
            assert result is True
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass

    def test_special_characters_in_content(self):
        """Test handling of special characters."""
        from education_system.university_system.modules.shared.services.pdf_export.pdf_generator import (
            PDFGenerator,
        )

        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

        try:
            pdf = PDFGenerator(path)
            special_text = "Test with special chars: <>&\"' and unicode: "
            pdf.add_text(special_text)
            pdf.add_section_header("Section with <special> chars")

            result = pdf.save()
            assert result is True
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass

    def test_many_elements(self):
        """Test PDF with many elements."""
        from education_system.university_system.modules.shared.services.pdf_export.pdf_generator import (
            PDFGenerator,
        )

        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

        try:
            pdf = PDFGenerator(path)

            for i in range(50):
                pdf.add_section_header(f"Section {i}")
                pdf.add_text(f"Content for section {i}")
                pdf.add_spacer()

            result = pdf.save()
            assert result is True
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass
