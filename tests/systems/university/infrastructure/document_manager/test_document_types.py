"""Tests for document_manager.document_types (DocumentTypeMixin)"""
from unittest.mock import patch


def test_manage_document_templates_dispatches(doc_manager, feed_input):
    methods = ["view_document_types", "add_document_type", "modify_document_type",
               "set_course_requirements", "template_analytics"]
    for i, m in enumerate(methods, start=1):
        with patch.object(doc_manager, m) as p:
            feed_input(str(i))
            doc_manager.manage_document_templates()
            p.assert_called_once()


def test_manage_document_templates_invalid(doc_manager, feed_input):
    feed_input("99")
    doc_manager.manage_document_templates()


def test_view_document_types(doc_manager, capsys):
    doc_manager.view_document_types()
    out = capsys.readouterr().out
    assert "DOCUMENT TYPES" in out


def test_add_document_type_simple(doc_manager, feed_input, capsys):
    feed_input("CustomDoc", "desc", "y", "n", "10", "pdf,jpg", "y", "Misc", "5")
    doc_manager.add_document_type()
    out = capsys.readouterr().out
    assert "added successfully" in out or "already exists" in out


def test_add_document_type_with_expiry(doc_manager, feed_input, capsys):
    feed_input("ExpiringDoc", "desc", "y", "y", "60", "10", "pdf", "y", "Health", "0")
    doc_manager.add_document_type()


def test_add_document_type_value_error_recovers(doc_manager, feed_input):
    feed_input("WeirdDoc", "d", "y", "y", "abc", "xyz", "pdf", "y", "Cat", "abc")
    doc_manager.add_document_type()


def test_add_document_type_no_name(doc_manager, feed_input, capsys):
    feed_input("")
    doc_manager.add_document_type()
    assert "required" in capsys.readouterr().out.lower()


def test_add_document_type_duplicate(doc_manager, feed_input, capsys):
    feed_input("ID Photo", "dup", "y", "n", "10", "jpg", "y", "Identity", "0")
    doc_manager.add_document_type()
    assert "already exists" in capsys.readouterr().out


def test_modify_document_type_invalid_index(doc_manager, feed_input, capsys):
    feed_input("99")
    doc_manager.modify_document_type()
    assert "Invalid" in capsys.readouterr().out


def test_modify_document_type_value_error(doc_manager, feed_input, capsys):
    feed_input("notanumber")
    doc_manager.modify_document_type()
    assert "Invalid input" in capsys.readouterr().out


def test_modify_document_type_complete(doc_manager, feed_input):
    feed_input("1", "", "", "", "", "", "", "", "")
    doc_manager.modify_document_type()


def test_document_type_management_dispatch(doc_manager, feed_input):
    for choice, m in zip("123",
                         ["view_document_types", "add_document_type",
                          "modify_document_type"]):
        with patch.object(doc_manager, m) as p:
            feed_input(choice)
            doc_manager.document_type_management()
            p.assert_called_once()


def test_document_type_management_deactivate(doc_manager, feed_input, temp_db, capsys):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    feed_input("4", "1")
    doc_manager.document_type_management()
    conn = sqlite3.connect(temp_db)
    val = conn.execute("SELECT is_active FROM document_types WHERE type_id = 1").fetchone()
    conn.close()
    assert val[0] == 0


def test_template_analytics_runs(doc_manager):
    doc_manager.template_analytics()


def test_set_course_requirements_no_code(doc_manager, feed_input, capsys):
    feed_input("")
    doc_manager.set_course_requirements()
    assert "required" in capsys.readouterr().out.lower()


def test_set_course_requirements_no_selection(doc_manager, feed_input, capsys):
    feed_input("CS101", "BSc CS", "")
    doc_manager.set_course_requirements()


def test_set_course_requirements_with_selection(doc_manager, feed_input):
    feed_input("CS101", "BSc CS", "1,2", "y", "30", "y", "30")
    doc_manager.set_course_requirements()


def test_set_course_requirements_value_error(doc_manager, feed_input, capsys):
    feed_input("CS101", "BSc CS", "abc")
    doc_manager.set_course_requirements()
    assert "Invalid input" in capsys.readouterr().out
