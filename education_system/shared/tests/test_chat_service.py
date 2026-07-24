"""Tests for ChatService."""

import pytest

from education_system.shared.services.chat_service import ChatService, init_chat_db


@pytest.fixture()
def svc(tmp_path):
    db = str(tmp_path / "chat.db")
    init_chat_db(db)
    return ChatService(db)


# ── room management ──────────────────────────────────────────────────

def test_create_room(svc):
    room = svc.create_room("General", room_type="group", system_key="sixth_form", created_by=1)
    assert room["name"] == "General"
    assert room["room_type"] == "group"
    assert room["id"] is not None


def test_get_room(svc):
    room = svc.create_room("Staff Chat")
    fetched = svc.get_room(room["id"])
    assert fetched is not None
    assert fetched["name"] == "Staff Chat"


def test_get_room_missing(svc):
    assert svc.get_room(9999) is None


# ── participants ─────────────────────────────────────────────────────

def test_add_and_get_participants(svc):
    room = svc.create_room("Room A")
    svc.add_participant(room["id"], user_id=10)
    svc.add_participant(room["id"], user_id=20)

    participants = svc.get_room_participants(room["id"])
    user_ids = {p["user_id"] for p in participants}
    assert user_ids == {10, 20}


def test_add_participant_idempotent(svc):
    room = svc.create_room("Room B")
    svc.add_participant(room["id"], user_id=10)
    svc.add_participant(room["id"], user_id=10)

    participants = svc.get_room_participants(room["id"])
    assert len(participants) == 1


def test_remove_participant(svc):
    room = svc.create_room("Room C")
    svc.add_participant(room["id"], user_id=10)
    svc.add_participant(room["id"], user_id=20)

    svc.remove_participant(room["id"], user_id=10)
    participants = svc.get_room_participants(room["id"])
    assert len(participants) == 1
    assert participants[0]["user_id"] == 20


def test_get_user_rooms(svc):
    r1 = svc.create_room("Room 1")
    r2 = svc.create_room("Room 2")
    svc.add_participant(r1["id"], user_id=5)
    svc.add_participant(r2["id"], user_id=5)

    rooms = svc.get_user_rooms(user_id=5)
    assert len(rooms) == 2


# ── messaging ────────────────────────────────────────────────────────

def test_send_and_get_messages(svc):
    room = svc.create_room("Msg Room")
    svc.send_message(room["id"], sender_id=1, message_text="Hello")
    svc.send_message(room["id"], sender_id=2, message_text="Hi there")

    msgs = svc.get_messages(room["id"])
    assert len(msgs) == 2
    assert msgs[0]["message_text"] == "Hello"
    assert msgs[1]["message_text"] == "Hi there"


def test_edit_message(svc):
    room = svc.create_room("Edit Room")
    msg = svc.send_message(room["id"], sender_id=1, message_text="typo")
    assert svc.edit_message(msg["id"], "fixed")

    msgs = svc.get_messages(room["id"])
    assert msgs[0]["message_text"] == "fixed"
    assert msgs[0]["edited_at"] is not None


def test_delete_message(svc):
    room = svc.create_room("Del Room")
    msg = svc.send_message(room["id"], sender_id=1, message_text="secret")
    assert svc.delete_message(msg["id"])

    msgs = svc.get_messages(room["id"])
    assert msgs[0]["message_text"] == "[deleted]"
    assert msgs[0]["message_type"] == "deleted"


# ── read receipts ────────────────────────────────────────────────────

def test_mark_read(svc):
    room = svc.create_room("Read Room")
    svc.add_participant(room["id"], user_id=1)
    msg = svc.send_message(room["id"], sender_id=2, message_text="hi")

    assert svc.get_unread_count(user_id=1) == 1
    svc.mark_read(msg["id"], user_id=1)
    assert svc.get_unread_count(user_id=1) == 0


def test_mark_room_read(svc):
    room = svc.create_room("Bulk Read Room")
    svc.add_participant(room["id"], user_id=1)
    svc.send_message(room["id"], sender_id=2, message_text="a")
    svc.send_message(room["id"], sender_id=2, message_text="b")
    svc.send_message(room["id"], sender_id=2, message_text="c")

    assert svc.get_unread_count(user_id=1) == 3
    count = svc.mark_room_read(room["id"], user_id=1)
    assert count == 3
    assert svc.get_unread_count(user_id=1) == 0


def test_unread_count_zero_when_no_messages(svc):
    room = svc.create_room("Empty Room")
    svc.add_participant(room["id"], user_id=1)
    assert svc.get_unread_count(user_id=1) == 0
