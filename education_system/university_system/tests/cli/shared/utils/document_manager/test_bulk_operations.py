"""Tests for document_manager.bulk_operations (BulkOperationsMixin)"""
import os
from unittest.mock import patch, MagicMock


def test_bulk_operations_menu_dispatches(doc_manager, feed_input):
    methods = ["bulk_status_update", "bulk_document_download", "bulk_expiry_update",
               "bulk_tag_assignment", "bulk_update_from_search"]
    for i, m in enumerate(methods, start=1):
        with patch.object(doc_manager, m) as p:
            feed_input(str(i))
            doc_manager.bulk_operations_menu()
            p.assert_called_once()


def test_bulk_operations_menu_invalid(doc_manager, feed_input):
    feed_input("99")
    doc_manager.bulk_operations_menu()


def test_bulk_status_update_by_type(doc_manager, feed_input, seed_document, capsys):
    seed_document(type_id=1, status="Pending")
    with patch.object(doc_manager, "select_document_type", return_value=(1, "ID Photo", False, 5, "jpg")):
        feed_input("1", "Verified", "ok", "y")
        doc_manager.bulk_status_update()


def test_bulk_status_update_by_status(doc_manager, feed_input, seed_document):
    seed_document(status="Pending")
    feed_input("2", "Pending", "Verified", "y")
    doc_manager.bulk_status_update()


def test_bulk_status_update_by_student(doc_manager, feed_input, seed_document, seed_student):
    seed_document(student_id=seed_student("STU777"))
    with patch.object(doc_manager, "select_student", return_value="STU777"):
        feed_input("3", "Verified", "y")
        doc_manager.bulk_status_update()


def test_bulk_status_update_cancelled(doc_manager, feed_input, seed_document):
    seed_document()
    feed_input("2", "Pending", "Verified", "n")
    doc_manager.bulk_status_update()


def test_bulk_status_update_select_returns_none(doc_manager, feed_input):
    with patch.object(doc_manager, "select_document_type", return_value=None):
        feed_input("1")
        doc_manager.bulk_status_update()


def test_bulk_document_download_by_student(doc_manager, feed_input, seed_document, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "real.pdf"
    src.write_text("data")
    sid = "STU111"
    seed_document(student_id=sid, file_path=str(src), filename="real.pdf")
    with patch.object(doc_manager, "select_student", return_value=sid):
        feed_input("1")
        doc_manager.bulk_document_download()


def test_bulk_document_download_by_type(doc_manager, feed_input, seed_document):
    seed_document(type_id=2)
    with patch.object(doc_manager, "select_document_type", return_value=(2, "ID", False, 5, "jpg")):
        feed_input("2")
        doc_manager.bulk_document_download()


def test_bulk_document_download_by_status(doc_manager, feed_input, seed_document):
    seed_document(status="Pending")
    feed_input("3", "Pending")
    doc_manager.bulk_document_download()


def test_bulk_document_download_no_results(doc_manager, feed_input, capsys):
    feed_input("3", "NonExistent")
    doc_manager.bulk_document_download()
    assert "No documents" in capsys.readouterr().out


def test_bulk_expiry_update(doc_manager, feed_input, seed_document):
    seed_document(type_id=3)
    with patch.object(doc_manager, "select_document_type", return_value=(3, "ID Card", True, 5, "pdf")), \
         patch.object(doc_manager, "get_expiry_date", return_value="2030-01-01"):
        feed_input("y")
        doc_manager.bulk_expiry_update()


def test_bulk_expiry_update_cancel(doc_manager, feed_input, seed_document):
    seed_document(type_id=3)
    with patch.object(doc_manager, "select_document_type", return_value=(3, "ID Card", True, 5, "pdf")), \
         patch.object(doc_manager, "get_expiry_date", return_value="2030-01-01"):
        feed_input("n")
        doc_manager.bulk_expiry_update()


def test_bulk_expiry_update_no_type(doc_manager):
    with patch.object(doc_manager, "select_document_type", return_value=None):
        doc_manager.bulk_expiry_update()


def test_bulk_expiry_update_no_documents(doc_manager, feed_input):
    with patch.object(doc_manager, "select_document_type",
                      return_value=(99, "Phantom", True, 5, "pdf")):
        doc_manager.bulk_expiry_update()


def test_bulk_tag_assignment_by_student(doc_manager, feed_input, seed_document, seed_student):
    sid = seed_student("STU222")
    seed_document(student_id=sid)
    with patch.object(doc_manager, "select_student", return_value=sid), \
         patch.object(doc_manager, "select_tags", return_value="urgent"):
        feed_input("1", "y")
        doc_manager.bulk_tag_assignment()


def test_bulk_tag_assignment_by_type(doc_manager, feed_input, seed_document):
    seed_document(type_id=1)
    with patch.object(doc_manager, "select_document_type", return_value=(1, "ID Photo", False, 5, "jpg")), \
         patch.object(doc_manager, "select_tags", return_value="urgent"):
        feed_input("2", "y")
        doc_manager.bulk_tag_assignment()


def test_bulk_tag_assignment_by_status(doc_manager, feed_input, seed_document):
    seed_document(status="Pending")
    with patch.object(doc_manager, "select_tags", return_value="verified"):
        feed_input("3", "Pending", "y")
        doc_manager.bulk_tag_assignment()


def test_bulk_tag_assignment_invalid_choice(doc_manager, feed_input):
    feed_input("99")
    doc_manager.bulk_tag_assignment()


def test_bulk_tag_assignment_no_tags(doc_manager, feed_input, seed_document):
    seed_document(status="Pending")
    with patch.object(doc_manager, "select_tags", return_value=""):
        feed_input("3", "Pending")
        doc_manager.bulk_tag_assignment()


def test_bulk_update_from_search_with_results(doc_manager, feed_input, seed_document):
    did = seed_document()
    results = [(did, "Alice Doe", "ID Photo", "Pending", "2025-01-01", 1, "")]
    feed_input("1", "Verified")
    doc_manager.bulk_update_from_search(results=results)


def test_bulk_update_from_search_tags(doc_manager, feed_input, seed_document):
    did = seed_document()
    results = [(did,)]
    with patch.object(doc_manager, "select_tags", return_value="urgent"):
        feed_input("2")
        doc_manager.bulk_update_from_search(results=results)


def test_bulk_update_from_search_expiry(doc_manager, feed_input, seed_document):
    did = seed_document()
    results = [(did,)]
    with patch.object(doc_manager, "get_expiry_date", return_value="2030-01-01"):
        feed_input("3")
        doc_manager.bulk_update_from_search(results=results)


def test_bulk_update_from_search_priority(doc_manager, feed_input, seed_document):
    did = seed_document()
    results = [(did,)]
    feed_input("4", "5")
    doc_manager.bulk_update_from_search(results=results)


def test_bulk_update_from_search_no_results(doc_manager, capsys):
    with patch.object(doc_manager, "execute_advanced_search", return_value=[]):
        doc_manager.bulk_update_from_search()
    assert "No documents" in capsys.readouterr().out


def test_bulk_update_from_search_lazy_search(doc_manager, feed_input, seed_document):
    did = seed_document()
    feed_input("1", "Verified")
    with patch.object(doc_manager, "execute_advanced_search",
                      return_value=[(did,)]):
        doc_manager.bulk_update_from_search()
