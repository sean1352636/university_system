"""Tests for document_manager.viewing (ViewingMixin)"""
from unittest.mock import patch


def test_view_student_documents_no_student(doc_manager):
    with patch.object(doc_manager, "select_student", return_value=None):
        doc_manager.view_student_documents()


def test_view_student_documents_no_docs(doc_manager, seed_student, capsys):
    sid = seed_student()
    with patch.object(doc_manager, "select_student", return_value=sid):
        doc_manager.view_student_documents()
    assert "No documents" in capsys.readouterr().out


def test_view_student_documents_with_docs(doc_manager, seed_document, feed_input):
    sid = "STU001"
    seed_document(student_id=sid)
    with patch.object(doc_manager, "select_student", return_value=sid):
        feed_input("n")
        doc_manager.view_student_documents()


def test_view_student_documents_drill_in(doc_manager, seed_document, feed_input):
    sid = "STU001"
    seed_document(student_id=sid)
    with patch.object(doc_manager, "select_student", return_value=sid), \
         patch.object(doc_manager, "view_document_details") as v:
        feed_input("y", "1")
        doc_manager.view_student_documents()
        v.assert_called_once()


def test_view_student_documents_with_expired(doc_manager, seed_document):
    from datetime import datetime, timedelta
    past = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    seed_document(expiry=past, student_id="STU010")
    with patch.object(doc_manager, "select_student", return_value="STU010"):
        from unittest.mock import patch as p2
        with p2("builtins.input", return_value="n"):
            doc_manager.view_student_documents()


def test_view_student_documents_warn_soon(doc_manager, seed_document):
    from datetime import datetime, timedelta
    soon = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    seed_document(expiry=soon, student_id="STU020")
    with patch.object(doc_manager, "select_student", return_value="STU020"):
        from unittest.mock import patch as p2
        with p2("builtins.input", return_value="n"):
            doc_manager.view_student_documents()


def test_view_document_details_with_id(doc_manager, seed_document):
    did = seed_document()
    doc_manager.view_document_details(doc_id=did)


def test_view_document_details_prompt(doc_manager, seed_document, feed_input):
    did = seed_document()
    feed_input(str(did))
    doc_manager.view_document_details()


def test_view_document_details_not_found(doc_manager, capsys):
    doc_manager.view_document_details(doc_id="9999")
    assert "not found" in capsys.readouterr().out.lower()


def test_view_document_details_with_workflow(doc_manager, temp_db, seed_document):
    from education_system.post_18.university_system.infrastructure.database.db import sqlite3
    did = seed_document()
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO document_workflow (document_id, step_name, step_order, assigned_to, "
        "status, comments, completed_date, completed_by) "
        "VALUES (?, 'Initial', 1, 'admin', 'completed', 'good', '2025-01-02', 'admin')",
        (did,),
    )
    conn.commit()
    conn.close()
    doc_manager.view_document_details(doc_id=did)
