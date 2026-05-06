"""Tests for document_manager.status (StatusMixin)"""
from unittest.mock import patch


def test_check_document_expiry_no_data(doc_manager, feed_input):
    feed_input("30")
    doc_manager.check_document_expiry()


def test_check_document_expiry_value_error(doc_manager, feed_input):
    feed_input("not-a-number")
    doc_manager.check_document_expiry()


def test_check_document_expiry_with_expiring(doc_manager, feed_input, seed_document):
    from datetime import datetime, timedelta
    soon = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    seed_document(status="Verified", expiry=soon)
    feed_input("30", "n")
    doc_manager.check_document_expiry()


def test_check_document_expiry_with_expired_email(doc_manager, feed_input, seed_document):
    from datetime import datetime, timedelta
    past = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    seed_document(status="Pending", expiry=past)
    feed_input("30", "y")
    doc_manager.check_document_expiry()


def test_update_document_status_invalid_id(doc_manager, feed_input, capsys):
    feed_input("abc")
    doc_manager.update_document_status()
    assert "Invalid" in capsys.readouterr().out


def test_update_document_status_not_found(doc_manager, feed_input, capsys):
    feed_input("9999")
    doc_manager.update_document_status()
    assert "not found" in capsys.readouterr().out.lower()


def test_update_document_status_invalid_choice(doc_manager, feed_input, seed_document, capsys):
    did = seed_document()
    feed_input(str(did), "9")
    doc_manager.update_document_status()
    assert "Invalid" in capsys.readouterr().out


def test_update_document_status_verified(doc_manager, feed_input, seed_document):
    did = seed_document()
    with patch.object(doc_manager, "create_notification"):
        feed_input(str(did), "1", "looks good")
        doc_manager.update_document_status()


def test_update_document_status_rejected(doc_manager, feed_input, seed_document):
    did = seed_document()
    with patch.object(doc_manager, "create_notification"):
        feed_input(str(did), "2", "bad")
        doc_manager.update_document_status()


def test_update_document_status_pending(doc_manager, feed_input, seed_document):
    did = seed_document()
    with patch.object(doc_manager, "create_notification"):
        feed_input(str(did), "3", "")
        doc_manager.update_document_status()
