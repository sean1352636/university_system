"""Tests for document_manager.versioning (VersioningMixin)"""
from unittest.mock import patch


def test_document_versioning_menu_dispatch(doc_manager, feed_input):
    methods = ["view_document_history", "compare_document_versions",
               "restore_previous_version", "archive_old_versions",
               "version_analytics"]
    for i, m in enumerate(methods, start=1):
        with patch.object(doc_manager, m) as p:
            feed_input(str(i))
            doc_manager.document_versioning_menu()
            p.assert_called_once()


def test_document_versioning_menu_invalid(doc_manager, feed_input):
    feed_input("99")
    doc_manager.document_versioning_menu()


def test_view_document_history_no_student(doc_manager):
    with patch.object(doc_manager, "select_student", return_value=None):
        doc_manager.view_document_history()


def test_view_document_history_no_documents(doc_manager, seed_student, capsys):
    sid = seed_student()
    with patch.object(doc_manager, "select_student", return_value=sid):
        doc_manager.view_document_history()
    assert "No documents" in capsys.readouterr().out


def test_view_document_history_with_docs(doc_manager, seed_document, feed_input):
    sid = "STU001"
    seed_document(student_id=sid)
    with patch.object(doc_manager, "select_student", return_value=sid):
        feed_input("1")
        doc_manager.view_document_history()


def test_view_document_history_invalid_index(doc_manager, seed_document, feed_input):
    sid = "STU001"
    seed_document(student_id=sid)
    with patch.object(doc_manager, "select_student", return_value=sid):
        feed_input("99")
        doc_manager.view_document_history()


def test_view_document_history_value_error(doc_manager, seed_document, feed_input):
    sid = "STU001"
    seed_document(student_id=sid)
    with patch.object(doc_manager, "select_student", return_value=sid):
        feed_input("abc")
        doc_manager.view_document_history()


def test_compare_versions_too_few(doc_manager, seed_document, feed_input, capsys):
    did = seed_document()
    feed_input(str(did))
    doc_manager.compare_document_versions()
    assert "at least 2" in capsys.readouterr().out


def test_compare_versions_with_two(doc_manager, temp_db, seed_document, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    did = seed_document(version=1, is_current=0)
    # Insert sibling version pointing to same parent
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO documents (source_type, owner_id, type_id, file_path, "
        "original_filename, upload_date, expiry_date, verification_status, "
        "version_number, parent_document_id, uploaded_by, file_size, file_hash, "
        "tags, is_current_version, workflow_status) "
        "VALUES ('student', 'STU001', 1, '/x', 'x.pdf', '2025-01-01', NULL, 'Pending', "
        "2, ?, 'admin', 0, 'h', '', 1, 'submitted')",
        (did,),
    )
    conn.commit()
    conn.close()
    feed_input(str(did), "1", "2")
    doc_manager.compare_document_versions()


def test_compare_versions_invalid_numbers(doc_manager, temp_db, seed_document, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    did = seed_document()
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO documents (source_type, owner_id, type_id, file_path, "
        "original_filename, upload_date, verification_status, version_number, "
        "parent_document_id, uploaded_by, file_size, file_hash, tags, "
        "is_current_version, workflow_status) "
        "VALUES ('student', 'STU001', 1, '/x', 'x.pdf', '2025-01-01', 'Pending', "
        "2, ?, 'admin', 0, 'h', '', 1, 'submitted')",
        (did,),
    )
    conn.commit()
    conn.close()
    feed_input(str(did), "99", "100")
    doc_manager.compare_document_versions()


def test_restore_previous_version_none(doc_manager, seed_document, feed_input, capsys):
    did = seed_document()
    feed_input(str(did))
    doc_manager.restore_previous_version()
    assert "No previous" in capsys.readouterr().out


def test_restore_previous_version_invalid(doc_manager, temp_db, seed_document, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    did = seed_document()
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO documents (source_type, owner_id, type_id, file_path, "
        "original_filename, upload_date, verification_status, version_number, "
        "parent_document_id, uploaded_by, file_size, file_hash, tags, "
        "is_current_version, workflow_status) "
        "VALUES ('student', 'STU001', 1, '/x', 'x.pdf', '2025-01-01', 'Pending', "
        "2, ?, 'admin', 0, 'h', '', 0, 'submitted')",
        (did,),
    )
    conn.commit()
    conn.close()
    feed_input(str(did), "99")
    doc_manager.restore_previous_version()


def test_restore_previous_version_confirm(doc_manager, temp_db, seed_document, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    did = seed_document()
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO documents (source_type, owner_id, type_id, file_path, "
        "original_filename, upload_date, verification_status, version_number, "
        "parent_document_id, uploaded_by, file_size, file_hash, tags, "
        "is_current_version, workflow_status) "
        "VALUES ('student', 'STU001', 1, '/x', 'x.pdf', '2025-01-01', 'Pending', "
        "2, ?, 'admin', 0, 'h', '', 0, 'submitted')",
        (did,),
    )
    conn.commit()
    conn.close()
    feed_input(str(did), "2", "y")
    doc_manager.restore_previous_version()


def test_restore_previous_version_decline(doc_manager, temp_db, seed_document, feed_input):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    did = seed_document()
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO documents (source_type, owner_id, type_id, file_path, "
        "original_filename, upload_date, verification_status, version_number, "
        "parent_document_id, uploaded_by, file_size, file_hash, tags, "
        "is_current_version, workflow_status) "
        "VALUES ('student', 'STU001', 1, '/x', 'x.pdf', '2025-01-01', 'Pending', "
        "2, ?, 'admin', 0, 'h', '', 0, 'submitted')",
        (did,),
    )
    conn.commit()
    conn.close()
    feed_input(str(did), "2", "n")
    doc_manager.restore_previous_version()


def test_archive_old_versions_none(doc_manager, capsys):
    doc_manager.archive_old_versions()
    assert "No old versions" in capsys.readouterr().out


def test_archive_old_versions_move(doc_manager, temp_db, tmp_path, seed_document, feed_input, monkeypatch):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    monkeypatch.chdir(tmp_path)
    fp = tmp_path / "old.pdf"
    fp.write_bytes(b"old")
    seed_document(version=1, is_current=0, file_path=str(fp))
    feed_input("1")
    doc_manager.archive_old_versions()


def test_archive_old_versions_zip(doc_manager, temp_db, tmp_path, seed_document, feed_input, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fp = tmp_path / "old.pdf"
    fp.write_bytes(b"old")
    seed_document(version=1, is_current=0, file_path=str(fp))
    feed_input("2")
    doc_manager.archive_old_versions()


def test_archive_old_versions_delete(doc_manager, temp_db, tmp_path, seed_document, feed_input, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fp = tmp_path / "old.pdf"
    fp.write_bytes(b"old")
    seed_document(version=1, is_current=0, file_path=str(fp))
    feed_input("3", "DELETE")
    doc_manager.archive_old_versions()


def test_archive_old_versions_delete_decline(doc_manager, temp_db, tmp_path, seed_document, feed_input, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fp = tmp_path / "old.pdf"
    fp.write_bytes(b"old")
    seed_document(version=1, is_current=0, file_path=str(fp))
    feed_input("3", "no")
    doc_manager.archive_old_versions()


def test_version_analytics_empty(doc_manager):
    doc_manager.version_analytics()


def test_version_analytics_with_data(doc_manager, temp_db, seed_document):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    did = seed_document(is_current=0, version=1)
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO documents (source_type, owner_id, type_id, file_path, "
        "original_filename, upload_date, verification_status, version_number, "
        "parent_document_id, uploaded_by, file_size, file_hash, tags, "
        "is_current_version, workflow_status) "
        "VALUES ('student', 'STU001', 1, '/x2', 'x2.pdf', '2025-02-01', 'Pending', "
        "2, ?, 'admin', 100, 'h', '', 1, 'submitted')",
        (did,),
    )
    conn.commit()
    conn.close()
    doc_manager.version_analytics()
