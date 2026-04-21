"""Tests for setup_unified_database module."""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import patch


MODULE = "education_system.university_system.modules.scripts.setup_unified_database"


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def temp_db_path(temp_dir):
    return temp_dir / "student_records.db"


@pytest.fixture
def patched_paths(temp_dir, temp_db_path):
    """Patch DEFAULT_DB_PATH and DB_DIR to use temp directory."""
    with patch(f"{MODULE}.DEFAULT_DB_PATH", temp_db_path), \
         patch(f"{MODULE}.DB_DIR", temp_dir), \
         patch(f"{MODULE}.get_text", side_effect=lambda key, **kw: key):
        yield temp_db_path


def test_create_unified_database_returns_path(patched_paths):
    from education_system.university_system.modules.scripts.setup_unified_database import create_unified_database
    result = create_unified_database()
    assert result == str(patched_paths)
    assert patched_paths.exists()


def test_create_unified_database_has_students_table(patched_paths):
    from education_system.university_system.modules.scripts.setup_unified_database import create_unified_database
    create_unified_database()
    conn = sqlite3.connect(str(patched_paths))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
    assert cursor.fetchone() is not None
    conn.close()


def test_create_unified_database_has_payments_table(patched_paths):
    from education_system.university_system.modules.scripts.setup_unified_database import create_unified_database
    create_unified_database()
    conn = sqlite3.connect(str(patched_paths))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payments'")
    assert cursor.fetchone() is not None
    conn.close()


def test_create_unified_database_has_key_tables(patched_paths):
    from education_system.university_system.modules.scripts.setup_unified_database import create_unified_database
    create_unified_database()
    conn = sqlite3.connect(str(patched_paths))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()
    expected = {"students", "users", "modules", "payments", "student_fees", "fee_types",
                "attendance", "student_grades", "documents", "parking_lots", "orders"}
    assert expected.issubset(tables)


def test_create_unified_database_seeds_initial_data(patched_paths):
    from education_system.university_system.modules.scripts.setup_unified_database import create_unified_database
    create_unified_database()
    conn = sqlite3.connect(str(patched_paths))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM students")
    assert cursor.fetchone()[0] >= 5
    cursor.execute("SELECT COUNT(*) FROM fee_types")
    assert cursor.fetchone()[0] >= 5
    conn.close()


def test_test_unified_database_returns_true(patched_paths):
    from education_system.university_system.modules.scripts.setup_unified_database import (
        create_unified_database,
        test_unified_database,
    )
    create_unified_database()
    result = test_unified_database()
    assert result is True


def test_test_unified_database_returns_false_when_missing(temp_dir):
    missing = temp_dir / "nonexistent.db"
    with patch(f"{MODULE}.DEFAULT_DB_PATH", missing), \
         patch(f"{MODULE}.DB_DIR", temp_dir):
        from education_system.university_system.modules.scripts.setup_unified_database import test_unified_database
        result = test_unified_database()
        assert result is False


def test_backup_existing_database_no_file(patched_paths):
    from education_system.university_system.modules.scripts.setup_unified_database import backup_existing_database
    result = backup_existing_database()
    assert result is None


def test_backup_existing_database_copies_file(patched_paths):
    # Create a dummy DB to back up
    patched_paths.write_bytes(b"dummy")
    from education_system.university_system.modules.scripts.setup_unified_database import backup_existing_database
    result = backup_existing_database()
    assert result is not None
    assert Path(result).exists()


def test_add_initial_data_inserts_modules(patched_paths):
    from education_system.university_system.modules.scripts.setup_unified_database import create_unified_database
    create_unified_database()
    conn = sqlite3.connect(str(patched_paths))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM modules")
    assert cursor.fetchone()[0] >= 3
    conn.close()
