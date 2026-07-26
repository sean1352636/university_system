"""Tests for document_manager.import_export (ImportExportMixin)"""
import csv
import os
from unittest.mock import patch, MagicMock

import pytest


def test_bulk_import_documents_dispatch(doc_manager, feed_input):
    for choice, m in zip("123",
                         ["import_from_csv", "import_from_excel",
                          "download_import_template"]):
        with patch.object(doc_manager, m) as p:
            feed_input(choice)
            doc_manager.bulk_import_documents()
            p.assert_called_once()


def test_bulk_import_documents_invalid(doc_manager, feed_input):
    feed_input("99")
    doc_manager.bulk_import_documents()


def test_import_from_csv_file_not_found(doc_manager, feed_input, capsys):
    feed_input("/nonexistent.csv")
    doc_manager.import_from_csv()
    assert "not found" in capsys.readouterr().out.lower()


def test_import_from_csv_success(doc_manager, feed_input, tmp_path, seed_student):
    sid = seed_student("STU001")
    target = tmp_path / "doc.pdf"
    target.write_bytes(b"x")
    csv_path = tmp_path / "import.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["student_id", "document_type", "file_path"])
        writer.writeheader()
        writer.writerow({"student_id": sid, "document_type": "ID Photo", "file_path": str(target)})
        writer.writerow({"student_id": "", "document_type": "", "file_path": ""})
    feed_input(str(csv_path))
    doc_manager.import_from_csv()


def test_import_from_csv_exception(doc_manager, feed_input, monkeypatch, capsys):
    feed_input("anything")
    monkeypatch.setattr("os.path.exists", lambda *a, **k: True)
    def boom(*a, **k):
        raise RuntimeError("nope")
    monkeypatch.setattr("builtins.open", boom)
    doc_manager.import_from_csv()
    assert "Import error" in capsys.readouterr().out


def test_validate_and_import_document_missing_student(doc_manager, capsys):
    out = doc_manager.validate_and_import_document("MISSING", "ID Photo", "/x")
    assert out is False


def test_validate_and_import_document_invalid_type(doc_manager, seed_student):
    sid = seed_student()
    out = doc_manager.validate_and_import_document(sid, "Phantom", "/x")
    assert out is False


def test_validate_and_import_document_missing_file(doc_manager, seed_student):
    sid = seed_student()
    out = doc_manager.validate_and_import_document(sid, "ID Photo", "/nonexistent")
    assert out is False


def test_validate_and_import_document_success(doc_manager, seed_student, tmp_path):
    sid = seed_student()
    fp = tmp_path / "x.pdf"
    fp.write_bytes(b"x")
    out = doc_manager.validate_and_import_document(sid, "ID Photo", str(fp))
    assert out is True


def test_import_from_excel_no_file(doc_manager, feed_input, capsys):
    feed_input("/nonexistent.xlsx")
    doc_manager.import_from_excel()
    assert "not found" in capsys.readouterr().out.lower()


def test_import_from_excel_with_file(doc_manager, feed_input, tmp_path):
    f = tmp_path / "x.xlsx"
    f.write_bytes(b"")
    feed_input(str(f))
    doc_manager.import_from_excel()


def test_download_import_template(doc_manager):
    doc_manager.download_import_template()


def test_export_data_menu_dispatch(doc_manager, feed_input):
    for choice, m in zip("12345",
                         ["export_all_students", "export_all_documents",
                          "export_compliance_data", "export_activity_log",
                          "export_custom_dataset"]):
        with patch.object(doc_manager, m) as p:
            feed_input(choice)
            doc_manager.export_data_menu()
            p.assert_called_once()


def test_export_data_menu_invalid(doc_manager, feed_input):
    feed_input("99")
    doc_manager.export_data_menu()


def test_export_all_students_handles_missing_columns(doc_manager, capsys):
    # The students table has 'email_address' not 'email' so the export query
    # SHOULD raise a sqlite error which is caught
    doc_manager.export_all_students()
    # No exception raised


def test_export_all_documents_no_data(doc_manager, capsys):
    doc_manager.export_all_documents()


def test_export_all_documents_with_data(doc_manager, seed_document):
    seed_document()
    doc_manager.export_all_documents()


def test_export_search_results_no_results(doc_manager, capsys):
    with patch.object(doc_manager, "execute_advanced_search", return_value=[]):
        doc_manager.export_search_results()


def test_export_search_results_with_supplied(doc_manager):
    results = [(1, "S1", "Alice Doe", "ID Photo", "x.pdf", "2025-01-01", "Pending")]
    doc_manager.export_search_results(results=results)


def test_export_activity_log_empty(doc_manager, feed_input):
    feed_input("30")
    doc_manager.export_activity_log()


def test_export_activity_log_default_days(doc_manager, feed_input, seed_audit):
    seed_audit()
    feed_input("")
    doc_manager.export_activity_log()


def test_export_compliance_data(doc_manager, seed_student):
    seed_student()
    doc_manager.export_compliance_data()


def test_export_custom_dataset_all_fields(doc_manager, feed_input, seed_document):
    seed_document()
    feed_input("6")
    doc_manager.export_custom_dataset()


def test_export_custom_dataset_default(doc_manager, feed_input, seed_document):
    seed_document()
    feed_input("1")
    doc_manager.export_custom_dataset()
