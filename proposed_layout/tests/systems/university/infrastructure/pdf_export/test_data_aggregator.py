"""Tests for PDF export data aggregator.

Tests the DataAggregator class which collects and organizes
database data for PDF export.
"""

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
import tempfile
import os
from unittest.mock import patch, MagicMock

class TestDataAggregator:
    """Test cases for DataAggregator class."""

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
                email TEXT,
                status TEXT,
                program TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE modules (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name TEXT,
                credits INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE scholarships (
                id INTEGER PRIMARY KEY,
                name TEXT,
                amount REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE empty_table (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
        """)

        # Insert test data
        cursor.executemany(
            "INSERT INTO students (name, email, status, program) VALUES (?, ?, ?, ?)",
            [
                ("John Doe", "john@test.com", "active", "Computer Science"),
                ("Jane Smith", "jane@test.com", "active", "Mathematics"),
                ("Bob Wilson", "bob@test.com", "inactive", "Computer Science"),
            ],
        )

        cursor.executemany(
            "INSERT INTO modules (code, name, credits) VALUES (?, ?, ?)",
            [
                ("CS101", "Introduction to Programming", 3),
                ("MATH201", "Calculus II", 4),
            ],
        )

        cursor.executemany(
            "INSERT INTO scholarships (name, amount) VALUES (?, ?)",
            [
                ("Merit Scholarship", 5000.00),
                ("Need-Based Grant", 3000.00),
            ],
        )

        conn.commit()
        conn.close()
        os.close(fd)

        yield db_path

        # Cleanup
        try:
            os.unlink(db_path)
        except Exception:
            pass

    @pytest.fixture
    def aggregator(self, temp_db):
        """Create a DataAggregator with the test database."""
        from education_system.systems.university.services.pdf_export.data_aggregator import (
            DataAggregator,
        )

        return DataAggregator(db_path=temp_db)

    def test_get_all_tables(self, aggregator):
        """Test retrieving list of all tables."""
        tables = aggregator.get_all_tables()

        assert isinstance(tables, list)
        assert "students" in tables
        assert "modules" in tables
        assert "scholarships" in tables
        assert "empty_table" in tables
        assert len(tables) == 4

    def test_get_table_info(self, aggregator):
        """Test getting metadata about a table."""
        info = aggregator.get_table_info("students")

        assert info["name"] == "students"
        assert info["row_count"] == 3
        assert len(info["columns"]) == 5
        assert "id" in info["column_names"]
        assert "name" in info["column_names"]
        assert "email" in info["column_names"]

    def test_get_table_info_empty_table(self, aggregator):
        """Test getting info for an empty table."""
        info = aggregator.get_table_info("empty_table")

        assert info["name"] == "empty_table"
        assert info["row_count"] == 0
        assert len(info["columns"]) == 2

    def test_get_table_info_nonexistent_table(self, aggregator):
        """Test getting info for a nonexistent table."""
        info = aggregator.get_table_info("nonexistent_table")

        assert info["name"] == "nonexistent_table"
        assert info["row_count"] == 0
        assert info["columns"] == []

    def test_get_table_data(self, aggregator):
        """Test retrieving table data."""
        columns, data = aggregator.get_table_data("students")

        assert len(columns) == 5
        assert len(data) == 3
        assert "name" in columns

        # Check data format
        assert all(isinstance(row, tuple) for row in data)

    def test_get_table_data_with_limit(self, aggregator):
        """Test retrieving table data with row limit."""
        columns, data = aggregator.get_table_data("students", limit=2)

        assert len(data) == 2

    def test_get_table_data_empty_table(self, aggregator):
        """Test retrieving data from empty table."""
        columns, data = aggregator.get_table_data("empty_table")

        assert len(columns) == 2
        assert len(data) == 0

    def test_get_summary_statistics(self, aggregator):
        """Test calculating summary statistics."""
        stats = aggregator.get_summary_statistics()

        assert stats["total_tables"] == 4
        assert stats["total_records"] == 7  # 3 students + 2 modules + 2 scholarships
        assert stats["tables_with_data"] == 3
        assert stats["empty_tables"] == 1
        assert "export_timestamp" in stats
        assert "largest_tables" in stats
        assert isinstance(stats["largest_tables"], list)

    def test_get_student_statistics(self, aggregator):
        """Test getting student-specific statistics."""
        stats = aggregator.get_student_statistics()

        assert stats["total_students"] == 3
        assert "by_status" in stats
        assert "active" in stats["by_status"]
        assert stats["by_status"]["active"] == 2
        assert stats["by_status"]["inactive"] == 1

    def test_get_financial_statistics(self, aggregator):
        """Test getting financial statistics."""
        stats = aggregator.get_financial_statistics()

        assert stats["scholarship_count"] == 2
        assert stats["scholarship_total"] == 8000.00

    def test_get_categorized_tables(self, aggregator):
        """Test organizing tables by category."""
        categorized = aggregator.get_categorized_tables()

        assert isinstance(categorized, dict)
        # Should have "Other" category for uncategorized tables
        assert "Other" in categorized or len(categorized) > 0

class TestDataAggregatorEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_db_path(self):
        """Test handling of invalid database path."""
        from education_system.systems.university.services.pdf_export.data_aggregator import (
            DataAggregator,
        )

        aggregator = DataAggregator(db_path="/nonexistent/path/database.db")
        tables = aggregator.get_all_tables()

        assert tables == []

    def test_malformed_table_name(self):
        """Test handling of special characters in table names."""
        from education_system.systems.university.services.pdf_export.data_aggregator import (
            DataAggregator,
        )

        # Create temp db with special table
        fd, db_path = tempfile.mkstemp(suffix=".db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE "test-table" (id INTEGER)')
        conn.commit()
        conn.close()
        os.close(fd)

        try:
            aggregator = DataAggregator(db_path=db_path)
            tables = aggregator.get_all_tables()
            assert "test-table" in tables
        finally:
            os.unlink(db_path)
