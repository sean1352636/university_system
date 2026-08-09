"""Tests for document_manager.upload (UploadMixin)"""
import os
from datetime import datetime, timedelta
from unittest.mock import patch


# ── Helpers ────────────────────────────────────────────────────────────────

def _real_file(tmp_path, name="x.pdf", content=b"abc"):
    p = tmp_path / name
    p.write_bytes(content)
    return str(p)


# ── upload_student_document ────────────────────────────────────────────────

def test_upload_student_document_no_student(doc_manager):
    with patch.object(doc_manager, "select_student", return_value=None):
        doc_manager.upload_student_document()


def test_upload_student_document_no_type(doc_manager, seed_student):
    sid = seed_student()
    with patch.object(doc_manager, "select_student", return_value=sid), \
         patch.object(doc_manager, "select_document_type", return_value=None):
        doc_manager.upload_student_document()


def test_upload_student_document_full_flow(doc_manager, seed_student, tmp_path, feed_input):
    sid = seed_student()
    fp = _real_file(tmp_path)
    with patch.object(doc_manager, "select_student", return_value=sid), \
         patch.object(doc_manager, "select_document_type",
                      return_value=(1, "ID Photo", False, 5, "pdf")), \
         patch.object(doc_manager, "select_tags", return_value=""), \
         patch.object(doc_manager, "create_workflow_steps"), \
         patch.object(doc_manager, "create_notification"):
        feed_input(fp)
        doc_manager.upload_student_document()


def test_upload_student_document_replaces_existing(doc_manager, seed_document, tmp_path, feed_input):
    did = seed_document(type_id=1)
    fp = _real_file(tmp_path)
    with patch.object(doc_manager, "select_student", return_value="STU001"), \
         patch.object(doc_manager, "select_document_type",
                      return_value=(1, "ID Photo", False, 5, "pdf")), \
         patch.object(doc_manager, "select_tags", return_value=""), \
         patch.object(doc_manager, "create_workflow_steps"), \
         patch.object(doc_manager, "create_notification"):
        # choice=1 (new version), then file path
        feed_input("1", fp)
        doc_manager.upload_student_document()


def test_upload_student_document_existing_cancel(doc_manager, seed_document, feed_input):
    seed_document(type_id=1)
    with patch.object(doc_manager, "select_student", return_value="STU001"), \
         patch.object(doc_manager, "select_document_type",
                      return_value=(1, "ID Photo", False, 5, "pdf")):
        feed_input("3")
        doc_manager.upload_student_document()


def test_upload_student_document_existing_additional(doc_manager, seed_document, tmp_path, feed_input):
    seed_document(type_id=1)
    fp = _real_file(tmp_path)
    with patch.object(doc_manager, "select_student", return_value="STU001"), \
         patch.object(doc_manager, "select_document_type",
                      return_value=(1, "ID Photo", False, 5, "pdf")), \
         patch.object(doc_manager, "select_tags", return_value=""), \
         patch.object(doc_manager, "create_workflow_steps"), \
         patch.object(doc_manager, "create_notification"):
        feed_input("2", fp)
        doc_manager.upload_student_document()


def test_upload_with_expiry(doc_manager, seed_student, tmp_path, feed_input):
    sid = seed_student()
    fp = _real_file(tmp_path)
    with patch.object(doc_manager, "select_student", return_value=sid), \
         patch.object(doc_manager, "select_document_type",
                      return_value=(3, "ID Card", True, 5, "pdf")), \
         patch.object(doc_manager, "select_tags", return_value=""), \
         patch.object(doc_manager, "get_expiry_date", return_value="2099-12-31"), \
         patch.object(doc_manager, "create_workflow_steps"), \
         patch.object(doc_manager, "create_notification"):
        feed_input(fp)
        doc_manager.upload_student_document()


def test_upload_no_file_info(doc_manager, seed_student):
    sid = seed_student()
    with patch.object(doc_manager, "select_student", return_value=sid), \
         patch.object(doc_manager, "select_document_type",
                      return_value=(1, "ID Photo", False, 5, "pdf")), \
         patch.object(doc_manager, "get_file_upload_details", return_value=None):
        doc_manager.upload_student_document()


# ── select_student ────────────────────────────────────────────────────────

def test_select_student_by_id(doc_manager, temp_db, seed_student, feed_input):
    sid = seed_student()
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input(sid)
    out = doc_manager.select_student(cur)
    conn.close()
    assert out == sid


def test_select_student_id_not_found(doc_manager, temp_db, feed_input, capsys):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input("MISSING")
    out = doc_manager.select_student(cur)
    conn.close()
    assert out is None


def test_select_student_search(doc_manager, temp_db, seed_student, feed_input):
    sid = seed_student()
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input("", "Alice", "1")
    out = doc_manager.select_student(cur)
    conn.close()
    assert out == sid


def test_select_student_search_invalid_index(doc_manager, temp_db, seed_student, feed_input):
    seed_student()
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input("", "Alice", "99")
    out = doc_manager.select_student(cur)
    conn.close()
    assert out is None


def test_select_student_search_value_error(doc_manager, temp_db, seed_student, feed_input):
    seed_student()
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input("", "Alice", "abc")
    out = doc_manager.select_student(cur)
    conn.close()
    assert out is None


def test_select_student_search_no_match(doc_manager, temp_db, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input("", "ZZZZ")
    out = doc_manager.select_student(cur)
    conn.close()
    assert out is None


def test_select_student_empty_search(doc_manager, temp_db, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input("", "")
    out = doc_manager.select_student(cur)
    conn.close()
    assert out is None


# ── select_document_type ──────────────────────────────────────────────────

def test_select_document_type(doc_manager, temp_db, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input("1")
    out = doc_manager.select_document_type(cur)
    conn.close()
    assert out is not None
    assert len(out) == 5


def test_select_document_type_invalid_index(doc_manager, temp_db, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input("99")
    out = doc_manager.select_document_type(cur)
    conn.close()
    assert out is None


def test_select_document_type_value_error(doc_manager, temp_db, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input("abc")
    out = doc_manager.select_document_type(cur)
    conn.close()
    assert out is None


def test_select_document_type_none_available(doc_manager, temp_db, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    conn.execute("DELETE FROM document_types")
    conn.commit()
    cur = conn.cursor()
    out = doc_manager.select_document_type(cur)
    conn.close()
    assert out is None


# ── get_file_upload_details ───────────────────────────────────────────────

def test_get_file_upload_details_success(doc_manager, tmp_path, feed_input):
    fp = _real_file(tmp_path, "doc.pdf")
    feed_input(fp)
    out = doc_manager.get_file_upload_details("pdf,jpg", 5)
    assert out[1] == "doc.pdf"


def test_get_file_upload_details_missing(doc_manager, feed_input, capsys):
    feed_input("/nonexistent.pdf")
    assert doc_manager.get_file_upload_details("pdf", 5) is None


def test_get_file_upload_details_bad_format(doc_manager, tmp_path, feed_input):
    fp = _real_file(tmp_path, "doc.txt")
    feed_input(fp)
    assert doc_manager.get_file_upload_details("pdf,jpg", 5) is None


def test_get_file_upload_details_too_large(doc_manager, tmp_path, feed_input):
    fp = _real_file(tmp_path, "big.pdf", content=b"x" * (2 * 1024 * 1024))
    feed_input(fp)
    assert doc_manager.get_file_upload_details("pdf", 1) is None


# ── get_expiry_date ───────────────────────────────────────────────────────

def test_get_expiry_date_valid(doc_manager, feed_input):
    feed_input("2099-12-31")
    assert doc_manager.get_expiry_date() == "2099-12-31"


def test_get_expiry_date_invalid_then_valid(doc_manager, feed_input):
    feed_input("not-a-date", "2099-12-31")
    assert doc_manager.get_expiry_date() == "2099-12-31"


def test_get_expiry_date_past_then_future(doc_manager, feed_input):
    past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    feed_input(past, "2099-12-31")
    assert doc_manager.get_expiry_date() == "2099-12-31"


# ── select_tags ───────────────────────────────────────────────────────────

def test_select_tags_empty(doc_manager, temp_db, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input("")
    assert doc_manager.select_tags(cur) == ""
    conn.close()


def test_select_tags_with_choices(doc_manager, temp_db, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input("1,2")
    out = doc_manager.select_tags(cur)
    conn.close()
    assert "," in out


def test_select_tags_invalid(doc_manager, temp_db, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    feed_input("abc")
    assert doc_manager.select_tags(cur) == ""
    conn.close()


def test_select_tags_no_tags(doc_manager, temp_db, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    conn.execute("DELETE FROM document_tags")
    conn.commit()
    cur = conn.cursor()
    assert doc_manager.select_tags(cur) == ""
    conn.close()


# ── create_workflow_steps ─────────────────────────────────────────────────

def test_create_workflow_steps_required(doc_manager, temp_db, seed_document):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    did = seed_document()
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    doc_manager.create_workflow_steps(cur, did, type_id=1)
    conn.commit()
    rows = conn.execute(
        "SELECT COUNT(*) FROM document_workflow WHERE document_id = ?", (did,)
    ).fetchone()[0]
    conn.close()
    assert rows == 3


def test_create_workflow_steps_no_approval(doc_manager, temp_db, seed_document):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    did = seed_document()
    conn = sqlite3.connect(temp_db)
    conn.execute("UPDATE document_types SET requires_approval = 0 WHERE type_id = 1")
    conn.commit()
    cur = conn.cursor()
    doc_manager.create_workflow_steps(cur, did, type_id=1)
    conn.close()


# ── create_notification ───────────────────────────────────────────────────

def test_create_notification(doc_manager, temp_db, seed_student):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    sid = seed_student()
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    doc_manager.create_notification(cur, sid, "x", "title", "msg", document_id=None)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM notifications WHERE recipient_id = ?", (sid,)).fetchone()[0]
    conn.close()
    assert n == 1
