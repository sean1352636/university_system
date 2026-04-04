"""Tests for InterSystemMessagingService."""

import os
import pytest

from education_system.shared.messaging.messaging_service import InterSystemMessagingService


@pytest.fixture()
def svc(tmp_path):
    db = str(tmp_path / "msg.db")
    return InterSystemMessagingService(db_path=db)


# ── send + retrieve ──────────────────────────────────────────────────

def test_send_message_returns_dict(svc):
    msg = svc.send_message(
        sender_id=1, sender_system="college", sender_name="Alice",
        recipient_id=2, recipient_system="university", recipient_name="Bob",
        student_name="Charlie", student_id="STU001",
        subject="Handover", body="Please review.",
    )
    assert msg is not None
    assert msg["sender_id"] == 1
    assert msg["recipient_system"] == "university"
    assert msg["subject"] == "Handover"
    assert msg["is_read"] == 0


def test_get_inbox(svc):
    svc.send_message(1, "college", "A", 2, "uni", "B", "", "", "s1", "b1")
    svc.send_message(3, "school", "C", 2, "uni", "B", "", "", "s2", "b2")
    svc.send_message(1, "college", "A", 9, "uni", "X", "", "", "s3", "b3")

    inbox = svc.get_inbox(user_id=2)
    assert len(inbox) == 2

    # filter by system
    inbox_uni = svc.get_inbox(user_id=2, system="uni")
    assert len(inbox_uni) == 2


def test_get_sent(svc):
    svc.send_message(1, "college", "A", 2, "uni", "B", "", "", "s1", "b1")
    svc.send_message(1, "college", "A", 3, "uni", "C", "", "", "s2", "b2")

    sent = svc.get_sent(user_id=1)
    assert len(sent) == 2


def test_get_message(svc):
    msg = svc.send_message(1, "c", "A", 2, "u", "B", "", "", "sub", "body")
    fetched = svc.get_message(msg["id"])
    assert fetched is not None
    assert fetched["subject"] == "sub"


def test_get_message_missing(svc):
    assert svc.get_message(9999) is None


# ── mark read ────────────────────────────────────────────────────────

def test_mark_read(svc):
    msg = svc.send_message(1, "c", "A", 2, "u", "B", "", "", "sub", "body")
    assert msg["is_read"] == 0

    svc.mark_read(msg["id"])
    fetched = svc.get_message(msg["id"])
    assert fetched["is_read"] == 1


# ── search ───────────────────────────────────────────────────────────

def test_search_messages_by_subject(svc):
    svc.send_message(1, "c", "A", 2, "u", "B", "", "", "Transfer Info", "details")
    svc.send_message(1, "c", "A", 2, "u", "B", "", "", "Lunch", "menu")

    results = svc.search_messages(user_id=2, system="u", query="Transfer")
    assert len(results) == 1
    assert results[0]["subject"] == "Transfer Info"


def test_search_messages_by_student_name(svc):
    svc.send_message(1, "c", "A", 2, "u", "B", "Emma Smith", "S01", "Hi", "")
    results = svc.search_messages(user_id=2, system="u", query="Emma")
    assert len(results) == 1


# ── unread count ─────────────────────────────────────────────────────

def test_unread_count(svc):
    assert svc.get_unread_count(user_id=5) == 0

    svc.send_message(1, "c", "A", 5, "u", "B", "", "", "s1", "b1")
    svc.send_message(2, "c", "C", 5, "u", "B", "", "", "s2", "b2")
    assert svc.get_unread_count(user_id=5) == 2

    # mark one read
    inbox = svc.get_inbox(user_id=5)
    svc.mark_read(inbox[0]["id"])
    assert svc.get_unread_count(user_id=5) == 1


def test_unread_count_with_system_filter(svc):
    svc.send_message(1, "c", "A", 5, "uni", "B", "", "", "s1", "")
    svc.send_message(2, "c", "C", 5, "school", "B", "", "", "s2", "")

    assert svc.get_unread_count(user_id=5, system="uni") == 1
    assert svc.get_unread_count(user_id=5, system="school") == 1
    assert svc.get_unread_count(user_id=5) == 2
