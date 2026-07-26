"""Tests for document_manager.search (SearchMixin)"""
from unittest.mock import patch


def test_advanced_search_no_results(doc_manager, feed_input, capsys):
    feed_input("", "", "", "", "", "")
    doc_manager.advanced_search()
    out = capsys.readouterr().out
    assert "No documents" in out


def test_advanced_search_with_results_view_details(doc_manager, feed_input, seed_document):
    seed_document()
    with patch.object(doc_manager, "view_document_details") as v:
        feed_input("Alice", "", "", "", "", "", "1", "1")
        doc_manager.advanced_search()
        v.assert_called_once_with(1)


def test_advanced_search_export(doc_manager, feed_input, seed_document):
    seed_document()
    with patch.object(doc_manager, "export_search_results") as e:
        feed_input("Alice", "", "", "", "", "", "2")
        doc_manager.advanced_search()
        e.assert_called_once()


def test_advanced_search_bulk_update(doc_manager, feed_input, seed_document):
    seed_document()
    with patch.object(doc_manager, "bulk_update_from_search") as b:
        feed_input("Alice", "", "", "", "", "", "3")
        doc_manager.advanced_search()
        b.assert_called_once()


def test_advanced_search_return(doc_manager, feed_input, seed_document):
    seed_document()
    feed_input("Alice", "", "", "", "", "", "4")
    doc_manager.advanced_search()


def test_execute_advanced_search_all_filters(doc_manager, seed_document):
    seed_document(status="Pending", tags="urgent")
    results = doc_manager.execute_advanced_search({
        "student": "Alice",
        "doc_type": "ID",
        "status": "Pending",
        "from_date": "2024-01-01",
        "to_date": "2030-01-01",
        "tags": "urgent,verified",
    })
    assert isinstance(results, list)


def test_execute_advanced_search_empty(doc_manager):
    assert doc_manager.execute_advanced_search({}) == []


def test_execute_advanced_search_handles_db_error(doc_manager, monkeypatch, capsys):
    from education_system.systems.university.infrastructure.utils import (
        document_manager as dm_pkg,
    )
    from education_system.systems.university.infrastructure.database.db import sqlite3

    def boom(*a, **k):
        raise sqlite3.Error("boom")

    monkeypatch.setattr(dm_pkg, "get_connection", boom)
    assert doc_manager.execute_advanced_search({}) == []
