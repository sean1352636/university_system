"""Tests for PDF export manager.

Tests the PDFExportManager class which orchestrates the full export process.
"""

import os
import tempfile
from education_system.university_system.infrastructure.database.db import sqlite3
import pytest
from unittest.mock import patch, MagicMock, call

class TestPDFExportManager:
    """Test cases for PDFExportManager class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary test database."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create test tables
        cursor.execute("""
            CREATE TABLE students (
                id INTEGER PRIMARY KEY,
                name TEXT,
                status TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE modules (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)

        # Insert test data
        cursor.executemany(
            "INSERT INTO students (name, status) VALUES (?, ?)",
            [
                ("Student 1", "active"),
                ("Student 2", "active"),
                ("Student 3", "inactive"),
            ],
        )

        cursor.executemany(
            "INSERT INTO modules (name) VALUES (?)",
            [
                ("Module 1",),
                ("Module 2",),
            ],
        )

        conn.commit()
        conn.close()
        os.close(fd)

        yield db_path

        try:
            os.unlink(db_path)
        except Exception:
            pass

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        path = tempfile.mkdtemp()
        yield path
        # Cleanup
        import shutil

        try:
            shutil.rmtree(path)
        except Exception:
            pass

    @pytest.fixture
    def export_manager(self, temp_db, temp_output_dir):
        """Create a PDFExportManager instance."""
        from education_system.university_system.modules.shared.services.pdf_export.export_manager import (
            PDFExportManager,
        )

        return PDFExportManager(db_path=temp_db, output_dir=temp_output_dir)

    def test_initialization(self, export_manager, temp_db, temp_output_dir):
        """Test PDFExportManager initialization."""
        assert export_manager is not None
        assert export_manager.db_path == temp_db
        assert export_manager.output_dir == temp_output_dir
        assert export_manager.aggregator is not None
        assert export_manager.chart_builder is not None

    def test_initialization_creates_output_dir(self, temp_db):
        """Test that initialization creates output directory if needed."""
        from education_system.university_system.modules.shared.services.pdf_export.export_manager import (
            PDFExportManager,
        )

        new_dir = tempfile.mkdtemp()
        nested_dir = os.path.join(new_dir, "nested", "output")

        try:
            manager = PDFExportManager(db_path=temp_db, output_dir=nested_dir)
            assert os.path.exists(nested_dir)
        finally:
            import shutil

            shutil.rmtree(new_dir)

    def test_get_export_preview(self, export_manager):
        """Test getting export preview."""
        preview = export_manager.get_export_preview()

        assert "statistics" in preview
        assert "categories" in preview
        assert "estimated_pages" in preview

        stats = preview["statistics"]
        assert stats["total_tables"] >= 2  # students and modules
        assert stats["total_records"] >= 5  # 3 students + 2 modules

    def test_export_full_database(self, export_manager, temp_output_dir):
        """Test full database export."""
        output_path = export_manager.export_full_database(
            output_filename="test_export.pdf",
            include_data=True,
            include_charts=True,
            max_rows_per_table=10,
        )

        assert output_path is not None
        assert os.path.exists(output_path)
        assert output_path.endswith(".pdf")
        assert os.path.getsize(output_path) > 0

    def test_export_summary_only(self, export_manager, temp_output_dir):
        """Test summary-only export."""
        output_path = export_manager.export_summary_only(
            output_filename="summary_export.pdf"
        )

        assert output_path is not None
        assert os.path.exists(output_path)

    def test_export_with_progress_callback(self, export_manager, temp_output_dir):
        """Test export with progress callback."""
        progress_calls = []

        def callback(message, percent):
            progress_calls.append((message, percent))

        output_path = export_manager.export_full_database(
            output_filename="progress_test.pdf",
            progress_callback=callback,
        )

        assert output_path is not None
        assert len(progress_calls) > 0
        # First call should be at 0%
        assert progress_calls[0][1] == 0
        # Last call should be at 100%
        assert progress_calls[-1][1] == 100

    def test_export_default_filename(self, export_manager, temp_output_dir):
        """Test export with auto-generated filename."""
        output_path = export_manager.export_full_database()

        assert output_path is not None
        assert os.path.exists(output_path)
        assert "database_export_" in os.path.basename(output_path)

    def test_export_without_data(self, export_manager, temp_output_dir):
        """Test export without including data."""
        output_path = export_manager.export_full_database(
            output_filename="no_data_export.pdf",
            include_data=False,
            include_charts=True,
        )

        assert output_path is not None
        assert os.path.exists(output_path)

    def test_export_without_charts(self, export_manager, temp_output_dir):
        """Test export without including charts."""
        output_path = export_manager.export_full_database(
            output_filename="no_charts_export.pdf",
            include_data=True,
            include_charts=False,
        )

        assert output_path is not None
        assert os.path.exists(output_path)

    def test_export_minimal(self, export_manager, temp_output_dir):
        """Test minimal export (no data, no charts)."""
        output_path = export_manager.export_full_database(
            output_filename="minimal_export.pdf",
            include_data=False,
            include_charts=False,
        )

        assert output_path is not None
        assert os.path.exists(output_path)

class TestExportDatabaseToPDF:
    """Test the convenience function."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary test database."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        cursor.execute("INSERT INTO test (id) VALUES (1)")
        conn.commit()
        conn.close()
        os.close(fd)

        yield db_path

        try:
            os.unlink(db_path)
        except Exception:
            pass

    def test_export_database_to_pdf_function(self, temp_db):
        """Test the convenience function."""
        from education_system.university_system.modules.shared.services.pdf_export.export_manager import (
            export_database_to_pdf,
        )

        # Mock the paths module to use temp db
        with patch(
            "education_system.university_system.modules.shared.services.pdf_export.export_manager.paths"
        ) as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db
            mock_paths.EXPORTS_DIR = tempfile.mkdtemp()

            try:
                output_path = export_database_to_pdf(
                    include_data=False,
                    include_charts=False,
                )

                assert output_path is not None
                assert os.path.exists(output_path)
            finally:
                import shutil

                try:
                    shutil.rmtree(mock_paths.EXPORTS_DIR)
                except Exception:
                    pass

class TestExportManagerEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_database(self):
        """Test export of empty database."""
        from education_system.university_system.modules.shared.services.pdf_export.export_manager import (
            PDFExportManager,
        )

        fd, db_path = tempfile.mkstemp(suffix=".db")
        conn = sqlite3.connect(db_path)
        # Create empty table
        conn.execute("CREATE TABLE empty (id INTEGER)")
        conn.commit()
        conn.close()
        os.close(fd)

        output_dir = tempfile.mkdtemp()

        try:
            manager = PDFExportManager(db_path=db_path, output_dir=output_dir)
            output_path = manager.export_full_database(
                output_filename="empty_db.pdf",
                include_data=True,
                include_charts=False,
            )

            assert output_path is not None
            assert os.path.exists(output_path)
        finally:
            os.unlink(db_path)
            import shutil

            shutil.rmtree(output_dir)

    def test_large_max_rows(self):
        """Test with large max_rows_per_table value."""
        from education_system.university_system.modules.shared.services.pdf_export.export_manager import (
            PDFExportManager,
        )

        fd, db_path = tempfile.mkstemp(suffix=".db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER, data TEXT)")
        # Insert some rows
        for i in range(100):
            conn.execute("INSERT INTO test VALUES (?, ?)", (i, f"data_{i}"))
        conn.commit()
        conn.close()
        os.close(fd)

        output_dir = tempfile.mkdtemp()

        try:
            manager = PDFExportManager(db_path=db_path, output_dir=output_dir)
            output_path = manager.export_full_database(
                output_filename="large_rows.pdf",
                max_rows_per_table=1000,  # More than available
                include_charts=False,
            )

            assert output_path is not None
            assert os.path.exists(output_path)
        finally:
            os.unlink(db_path)
            import shutil

            shutil.rmtree(output_dir)
