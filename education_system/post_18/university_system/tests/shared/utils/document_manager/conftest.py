"""Shared fixtures for document_manager per-file tests.

The document_manager package's ``_common.get_connection`` is a wrapper
that delegates to a callable bound at the package level. Tests can swap
in their own ``get_connection`` by setting it on the package, and every
mixin will automatically route through it.
"""
from __future__ import annotations

import builtins

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.shared.utils import document_manager as _dm_pkg


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "doc_test.db")


@pytest.fixture
def patched_connection(temp_db, monkeypatch):
    """Route every ``get_connection`` call to the test DB."""
    def _conn(*args, **kwargs):
        return sqlite3.connect(temp_db)
    monkeypatch.setattr(_dm_pkg, "get_connection", _conn)
    return _conn


@pytest.fixture
def doc_manager(patched_connection, temp_db, tmp_path, monkeypatch):
    """Initialise DocumentManager against a fresh test DB."""
    monkeypatch.chdir(tmp_path)
    from education_system.post_18.university_system.modules.shared.utils.document_manager import (
        DocumentManager,
    )
    dm = DocumentManager()
    dm.current_user = "admin"
    dm.user_role = "admin"
    # Several mixins reference the legacy `document_type` column on the
    # ``documents`` table while the schema only declares ``type_id``. Add
    # the legacy column so test queries don't fail with "no such column".
    conn = sqlite3.connect(temp_db)
    try:
        conn.execute("ALTER TABLE documents ADD COLUMN document_type TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
    return dm


@pytest.fixture
def feed_input(monkeypatch):
    """Replace ``builtins.input`` with a queue of pre-supplied responses."""
    def _set(*responses):
        it = iter(responses)
        monkeypatch.setattr(builtins, "input", lambda *a, **k: next(it, ""))
    return _set


@pytest.fixture
def seed_student(temp_db):
    def _seed(student_id="STU001", first_name="Alice", last_name="Doe",
             email="alice@example.com", course="CS", year=1, program="BSc CS"):
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT OR IGNORE INTO students (student_id, first_name, last_name, "
            "email_address, course, year, program, enrollment_date, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')",
            (student_id, first_name, last_name, email, course, year, program,
             "2025-09-01"),
        )
        conn.commit()
        conn.close()
        return student_id
    return _seed


@pytest.fixture
def seed_document(temp_db, seed_student):
    def _seed(student_id=None, type_id=1, status="Pending", expiry=None,
              version=1, is_current=1, file_path="/tmp/x.pdf",
              filename="x.pdf", upload_date="2025-01-01 00:00:00", tags=""):
        sid = student_id or seed_student()
        conn = sqlite3.connect(temp_db)
        cur = conn.execute(
            "INSERT INTO documents (source_type, owner_id, type_id, document_type, "
            "file_path, original_filename, upload_date, expiry_date, verification_status, "
            "version_number, uploaded_by, file_size, file_hash, tags, "
            "is_current_version, workflow_status) "
            "VALUES ('student', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'admin', 0, '', ?, ?, "
            "'pending')",
            (sid, type_id, str(type_id), file_path, filename, upload_date, expiry,
             status, version, tags, is_current),
        )
        doc_id = cur.lastrowid
        conn.commit()
        conn.close()
        return doc_id
    return _seed


@pytest.fixture
def seed_audit(temp_db):
    def _seed(action="API_CALL", table_name="documents", record_id="1",
             timestamp="2026-05-01 12:00:00"):
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO audit_log (user_id, action, table_name, record_id, "
            "old_values, new_values, timestamp) VALUES (?, ?, ?, ?, '', '', ?)",
            ("admin", action, table_name, record_id, timestamp),
        )
        conn.commit()
        conn.close()
    return _seed
