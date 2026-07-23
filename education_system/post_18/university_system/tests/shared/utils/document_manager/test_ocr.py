"""Tests for document_manager.ocr (OCRMixin)"""
from unittest.mock import patch


def _enable_ocr(temp_db):
    from education_system.post_18.university_system.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO system_settings (setting_name, setting_value, description, updated_date) "
        "VALUES ('ocr_enabled', 'true', '', '2025-01-01')"
    )
    conn.commit()
    conn.close()


def test_ocr_integration_menu_dispatch(doc_manager, feed_input):
    methods = ["extract_text_from_document", "batch_ocr_processing",
               "view_ocr_results", "ocr_settings"]
    for i, m in enumerate(methods, start=1):
        if not hasattr(doc_manager, m):
            # ocr_settings comes from SettingsMixin or similar
            continue
        with patch.object(doc_manager, m, create=True) as p:
            feed_input(str(i))
            doc_manager.ocr_integration_menu()
            p.assert_called_once()


def test_ocr_integration_menu_invalid(doc_manager, feed_input):
    feed_input("99")
    doc_manager.ocr_integration_menu()


def test_extract_text_disabled(doc_manager, feed_input, capsys):
    feed_input("1")  # doc id
    doc_manager.extract_text_from_document()
    assert "not enabled" in capsys.readouterr().out


def test_extract_text_doc_not_found(doc_manager, temp_db, feed_input, capsys):
    _enable_ocr(temp_db)
    feed_input("9999")
    doc_manager.extract_text_from_document()
    assert "not found" in capsys.readouterr().out.lower()


def test_extract_text_success(doc_manager, temp_db, feed_input, seed_document, capsys):
    _enable_ocr(temp_db)
    did = seed_document()
    feed_input(str(did))
    doc_manager.extract_text_from_document()
    assert "Processing" in capsys.readouterr().out


def test_batch_ocr_disabled(doc_manager, capsys):
    doc_manager.batch_ocr_processing()
    assert "not enabled" in capsys.readouterr().out


def test_batch_ocr_all_pending(doc_manager, temp_db, feed_input, seed_document):
    _enable_ocr(temp_db)
    seed_document()
    feed_input("1", "y")
    doc_manager.batch_ocr_processing()


def test_batch_ocr_by_type(doc_manager, temp_db, feed_input, seed_document):
    _enable_ocr(temp_db)
    seed_document(type_id=1)
    with patch.object(doc_manager, "select_document_type",
                      return_value=(1, "ID Photo", False, 5, "jpg")):
        feed_input("2", "y")
        doc_manager.batch_ocr_processing()


def test_batch_ocr_by_student(doc_manager, temp_db, feed_input, seed_document, seed_student):
    _enable_ocr(temp_db)
    sid = seed_student("STU800")
    seed_document(student_id=sid)
    with patch.object(doc_manager, "select_student", return_value=sid):
        feed_input("3", "y")
        doc_manager.batch_ocr_processing()


def test_batch_ocr_invalid_choice(doc_manager, temp_db, feed_input):
    _enable_ocr(temp_db)
    feed_input("99")
    doc_manager.batch_ocr_processing()


def test_batch_ocr_no_documents(doc_manager, temp_db, feed_input, capsys):
    _enable_ocr(temp_db)
    feed_input("1")
    doc_manager.batch_ocr_processing()
    assert "No documents" in capsys.readouterr().out


def test_batch_ocr_decline(doc_manager, temp_db, feed_input, seed_document):
    _enable_ocr(temp_db)
    seed_document()
    feed_input("1", "n")
    doc_manager.batch_ocr_processing()


def test_view_ocr_results(doc_manager, feed_input, capsys):
    feed_input("1")
    doc_manager.view_ocr_results()
    assert "OCR" in capsys.readouterr().out
