"""Users, announcements, chat, notifications, documents and dashboard routes.

Run against a temporary database, with real rows and real SQL, because the
thing under test is who can reach whose rows. The seed makes the two id spaces
collide on purpose: S1001's central id (3) is S1002's local id, and admin's
central id (19) is S1019's local id. A route that uses the token's ``user_id``
against a local table fails these tests.
"""

from __future__ import annotations

import io
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt as pyjwt
import pytest
from flask import Flask

from education_system import paths
from education_system.api.university.learners import document_routes
from education_system.api.university.operations import (
    announcement_routes,
    chat_routes,
    dashboard_routes,
    notification_routes,
    user_routes,
)
from education_system.platform.delivery.api.university.errors import register_error_handlers
from education_system.systems.university.infrastructure.database import db as db_module

_SECRET = "routes-test-secret-with-enough-length-for-hs256"

#: username: (central id, role)
_CENTRAL = {"admin": (19, "admin"), "S1001": (3, "student"), "S1002": (2, "student"),
            "prof": (40, "instructor"), "prof2": (42, "instructor"), "sue": (41, "staff"),
            "S1019": (1, "student"), "nobody": (50, "student"), "dad": (51, "parent"),
            "cook": (52, "shop_manager")}
#: (local id, username, role, student id)
_LOCAL = [(1, "admin", "admin", None), (2, "S1001", "student", "S1001"),
          (3, "S1002", "student", "S1002"), (4, "prof", "instructor", None),
          (5, "sue", "staff", None), (6, "prof2", "instructor", None),
          (19, "S1019", "student", "S1019")]

_UNIVERSITY_SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT,
    email TEXT, role TEXT, student_id TEXT, created_at TEXT, updated_at TEXT,
    service_account INTEGER DEFAULT 0);
CREATE TABLE user_accounts (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, salt TEXT,
    user_id INTEGER, is_active INTEGER, two_fa_secret TEXT);
CREATE TABLE students (student_id TEXT PRIMARY KEY, email_address TEXT, first_name TEXT, last_name TEXT);
CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER, subject TEXT,
    message TEXT, content TEXT, attachment_path TEXT, assignment_id INTEGER, is_read INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0, is_deleted_by_sender INTEGER DEFAULT 0,
    is_deleted_by_recipient INTEGER DEFAULT 0, sent_at TEXT, read_at TEXT, reply_to INTEGER);
CREATE TABLE announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id INTEGER NOT NULL,
    title TEXT NOT NULL, content TEXT NOT NULL, target_audience TEXT NOT NULL, is_urgent INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1, start_date TEXT NOT NULL, end_date TEXT, created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL);
CREATE TABLE announcement_viewers (id INTEGER PRIMARY KEY, announcement_id INTEGER, viewer_id INTEGER,
    viewed_at TEXT);
CREATE TABLE user_preferences (user_id TEXT, email_notifications INTEGER);
CREATE TABLE communication_log (id INTEGER PRIMARY KEY, user_id INTEGER, action_type TEXT,
    action_details TEXT, performed_at TEXT);
CREATE TABLE chat_rooms (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, room_type TEXT,
    created_by INTEGER, created_at TEXT, is_active INTEGER DEFAULT 1, max_members INTEGER, category TEXT,
    icon TEXT, colour TEXT, linked_course_code TEXT, linked_assignment_group_id INTEGER,
    announcement_mode INTEGER DEFAULT 0, oh_starts_at TEXT, oh_ends_at TEXT, slow_mode_seconds INTEGER,
    is_encrypted INTEGER DEFAULT 0);
CREATE TABLE chat_room_members (id INTEGER PRIMARY KEY, room_id INTEGER, user_id INTEGER, joined_at TEXT,
    is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, muted_until TEXT, is_favourite INTEGER DEFAULT 0);
CREATE TABLE chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER, sender_id INTEGER,
    content TEXT, sent_at TEXT, edited_at TEXT, is_deleted INTEGER DEFAULT 0, reply_to_id INTEGER,
    pinned_at TEXT, pinned_by INTEGER, attachment_path TEXT, attachment_name TEXT, attachment_mime TEXT,
    attachment_size INTEGER, flagged_at TEXT, is_encrypted INTEGER DEFAULT 0);
CREATE TABLE chat_room_keys (room_id INTEGER PRIMARY KEY, key_b64 TEXT, created_at TEXT);
CREATE TABLE chat_room_bans (room_id INTEGER, user_id INTEGER, banned_at TEXT, banned_by INTEGER, reason TEXT);
CREATE TABLE chat_room_invitations (id INTEGER PRIMARY KEY, room_id INTEGER, user_id INTEGER, invited_by INTEGER,
    invited_at TEXT, status TEXT, responded_at TEXT);
CREATE TABLE chat_filter_words (id INTEGER PRIMARY KEY, word TEXT, severity TEXT, created_at TEXT);
CREATE TABLE safeguarding_flags (id INTEGER PRIMARY KEY, message_id INTEGER, room_id INTEGER, user_id INTEGER,
    matched_word TEXT, severity TEXT, created_at TEXT);
CREATE TABLE chat_message_reads (user_id INTEGER, room_id INTEGER, last_read_message_id INTEGER,
    last_read_at TEXT, PRIMARY KEY (user_id, room_id));
CREATE TABLE document_types (type_id INTEGER PRIMARY KEY, type_name TEXT, description TEXT, is_required INTEGER,
    has_expiry INTEGER, max_file_size_mb INTEGER, allowed_extensions TEXT, category TEXT, sort_order INTEGER,
    is_active INTEGER DEFAULT 1);
CREATE TABLE documents (document_id INTEGER PRIMARY KEY AUTOINCREMENT, source_type TEXT, owner_id TEXT,
    document_type TEXT, document_name TEXT, file_path TEXT, file_content TEXT, file_size INTEGER, file_hash TEXT,
    original_filename TEXT, upload_date TEXT, expiry_date TEXT, status TEXT DEFAULT 'active',
    verification_status TEXT, verification_date TEXT, verification_notes TEXT, verified_by TEXT,
    version_number INTEGER DEFAULT 1, parent_document_id INTEGER, is_current_version INTEGER DEFAULT 1,
    workflow_status TEXT, tags TEXT, notes TEXT, uploaded_by TEXT, updated_at TEXT);
"""


def _apply_university_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_UNIVERSITY_SCHEMA)


def _seed_university(conn: sqlite3.Connection, uploads: Path) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    past, future = "2020-01-01 00:00:00", "2099-01-01 00:00:00"
    conn.executemany(
        "INSERT INTO users (id, username, first_name, last_name, email, role, student_id, created_at, "
        "updated_at) VALUES (?, ?, ?, 'Test', ?, ?, ?, ?, ?)",
        [(i, name, name.title(), f"{name.lower()}@uni.example", role, student, now, now)
         for i, name, role, student in _LOCAL])
    conn.executemany(
        "INSERT INTO students (student_id, email_address, first_name, last_name) VALUES (?, ?, 'A', 'B')",
        [(s, f"{s.lower()}@uni.example") for *_x, s in _LOCAL if s])
    conn.execute(
        "INSERT INTO user_accounts (id, username, password_hash, salt, user_id, is_active, two_fa_secret) "
        "VALUES (1, 'admin', 'HASH-MUST-NOT-LEAK', 'SALT-MUST-NOT-LEAK', 1, 1, 'MFA-MUST-NOT-LEAK')")
    conn.executemany(
        "INSERT INTO messages (id, sender_id, recipient_id, subject, message, content, is_read, sent_at) "
        "VALUES (?, 1, ?, ?, ?, ?, ?, ?)",
        [(1, 2, "for S1001", "x", "S1001 body", 0, now), (2, 3, "for S1002", "x", "S1002 secret", 0, now),
         (3, 2, "old for S1001", "x", "read body", 1, past)])
    conn.executemany(
        "INSERT INTO announcements (id, creator_id, title, content, target_audience, is_active, start_date, "
        "end_date, created_at, updated_at) VALUES (?, ?, ?, 'body', ?, ?, ?, ?, ?, ?)",
        [(1, 4, "Everyone", "all", 1, past, None, now, now),
         (2, 5, "Staff only", "staff", 1, past, None, now, now),
         (3, 4, "Over", "all", 1, past, past, now, now),
         (4, 4, "Not yet", "all", 1, future, None, now, now),
         (5, 4, "Hidden", "all", 0, past, None, now, now)])
    conn.executemany(
        "INSERT INTO chat_rooms (id, name, room_type, created_by, created_at) VALUES (?, ?, ?, 4, ?)",
        [(1, "CS101", "course", now), (2, "Common room", "public", now), (3, "Secret", "private", now)])
    conn.executemany(
        "INSERT INTO chat_room_members (room_id, user_id, joined_at, is_admin, is_banned) VALUES (?, ?, ?, ?, ?)",
        [(1, 2, now, 0, 0), (1, 4, now, 1, 0), (1, 19, now, 0, 1), (2, 4, now, 1, 0)])
    conn.execute(
        "INSERT INTO chat_messages (id, room_id, sender_id, content, sent_at, attachment_path, attachment_name) "
        "VALUES (1, 1, 4, 'hello', ?, '/srv/secret/path.pdf', 'path.pdf')", (now,))
    conn.execute("INSERT INTO chat_filter_words (word, severity) VALUES ('forbiddenword', 'block')")
    conn.execute(
        "INSERT INTO document_types (type_id, type_name, max_file_size_mb, allowed_extensions) "
        "VALUES (11, 'Transcript', 1, '.pdf,.txt')")
    folder = uploads / "student_documents" / "S1002"
    folder.mkdir(parents=True)
    (folder / "transcript.txt").write_text("S1002 transcript")
    conn.executemany(
        "INSERT INTO documents (document_id, source_type, owner_id, document_type, document_name, file_path, "
        "original_filename, upload_date, verification_status, uploaded_by) "
        "VALUES (?, 'student', ?, '11', 'Transcript', ?, ?, ?, 'Pending', ?)",
        [(1, "S1002", str(folder / "transcript.txt"), "transcript.txt", now, "S1002"),
         # Owned by "3": must not match the token whose central id is 3.
         (2, "3", "/etc/passwd", "passwd", now, "admin")])


@pytest.fixture()
def client(tmp_path, monkeypatch):
    university_db = tmp_path / "student_records.db"
    auth_db = tmp_path / "auth.db"
    uploads = tmp_path / "uploads"
    uploads.mkdir()

    conn = sqlite3.connect(university_db)
    _apply_university_schema(conn)
    _seed_university(conn, uploads)
    conn.commit()
    conn.close()

    conn = sqlite3.connect(auth_db)
    conn.executescript(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, is_active INTEGER, last_login TEXT, "
        "password_hash TEXT);")
    conn.executemany(
        "INSERT INTO users (id, username, is_active, password_hash) VALUES (?, ?, 1, 'HASH-MUST-NOT-LEAK')",
        [(central, name) for name, (central, _role) in _CENTRAL.items()])
    conn.commit()
    conn.close()

    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", str(university_db))
    monkeypatch.setattr(paths, "UNIVERSITY_DEFAULT_DB_PATH", university_db)
    monkeypatch.setattr(paths, "UNIVERSITY_UPLOAD_DIR", uploads)
    for module in (announcement_routes, chat_routes, dashboard_routes, document_routes,
                   notification_routes, user_routes):
        monkeypatch.setattr(module, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(user_routes, "safe_log_security_event", lambda *a, **k: None)
    monkeypatch.setattr(document_routes, "publish_document_changed", lambda **k: None)
    from education_system.systems.university.infrastructure.email.admin import announcements as mixin
    monkeypatch.setattr(mixin, "send_bulk", lambda *a, **k: None)
    assert db_module.DEFAULT_DB_PATH == str(university_db), "not isolated from the live database"

    app = Flask(__name__)
    app.config.update(TESTING=True, AUTH_DB_PATH=str(auth_db),
                      API_CONFIG={"jwt": {"secret_key": _SECRET, "algorithm": "HS256"}})
    register_error_handlers(app)
    for blueprint in (announcement_routes.announcement_bp, chat_routes.chat_bp,
                      dashboard_routes.dashboard_bp, document_routes.document_bp,
                      notification_routes.notification_bp, user_routes.user_bp):
        app.register_blueprint(blueprint)

    # Cross-system messages key on the central id: 3 is S1001, 2 is S1002.
    service = notification_routes.InterSystemMessagingService(db_path=str(auth_db))
    for recipient, system, name, subject, body in (
            (3, "university", "S1001", "to S1001", "cross body"),
            (2, "university", "S1002", "to S1002", "cross secret"),
            (3, "secondary", "S1001", "other system", "not here")):
        service.send_message(sender_id=40, sender_system="primary", sender_name="Head",
                             recipient_id=recipient, recipient_system=system,
                             recipient_name=name, student_name=None, student_id=None,
                             subject=subject, body=body)

    test_client = app.test_client()
    test_client.university_db = university_db
    test_client.uploads = uploads
    return test_client


def _auth(username: str, role: str | None = None) -> dict:
    central, default_role = _CENTRAL[username]
    now = datetime.now(timezone.utc)
    token = pyjwt.encode({"sub": username, "user_id": central, "role": role or default_role,
                          "type": "access", "iat": now, "exp": now + timedelta(hours=1)},
                         _SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _rows(client, sql: str, *params):
    conn = sqlite3.connect(client.university_db)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


@pytest.mark.parametrize("method,path", [
    ("get", "/api/users"), ("get", "/api/users/me"), ("get", "/api/users/2"), ("patch", "/api/users/2"),
    ("get", "/api/announcements"), ("post", "/api/announcements"), ("get", "/api/announcements/1"),
    ("patch", "/api/announcements/1"), ("delete", "/api/announcements/1"),
    ("post", "/api/announcements/1/viewed"),
    ("get", "/api/chat/rooms"), ("post", "/api/chat/rooms"), ("get", "/api/chat/rooms/1"),
    ("post", "/api/chat/rooms/1/join"), ("post", "/api/chat/rooms/1/leave"),
    ("get", "/api/chat/rooms/1/members"), ("get", "/api/chat/rooms/1/messages"),
    ("post", "/api/chat/rooms/1/messages"), ("post", "/api/chat/rooms/1/read"),
    ("delete", "/api/chat/messages/1"), ("get", "/api/chat/unread"),
    ("get", "/api/notifications"), ("post", "/api/notifications"), ("get", "/api/notifications/unread-count"),
    ("get", "/api/notifications/university/1"), ("post", "/api/notifications/university/1/read"),
    ("post", "/api/notifications/read-all"),
    ("get", "/api/documents"), ("post", "/api/documents"), ("get", "/api/documents/types"),
    ("get", "/api/documents/1"), ("get", "/api/documents/1/download"),
    ("patch", "/api/documents/1/verification"),
    ("get", "/api/dashboard"), ("get", "/api/dashboard/students/S1001"), ("get", "/api/dashboard/operations"),
])
def test_every_route_needs_a_token(client, method, path):
    assert getattr(client, method)(path).status_code == 401


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def test_inbox_holds_only_the_callers_messages_in_both_stores(client):
    items = client.get("/api/notifications", headers=_auth("S1001")).get_json()["items"]
    assert {(i["source"], i["subject"]) for i in items} == {
        ("university", "for S1001"), ("cross-system", "to S1001")}
    assert "secret" not in json.dumps(items)


def test_inbox_is_unread_only_by_default_and_can_show_everything(client):
    items = client.get("/api/notifications?unread_only=false&source=university",
                       headers=_auth("S1001")).get_json()["items"]
    assert {i["subject"] for i in items} == {"for S1001", "old for S1001"}


def test_inbox_pagination_counts_both_stores(client):
    body = client.get("/api/notifications?per_page=1&page=2", headers=_auth("S1001")).get_json()
    assert len(body["items"]) == 1
    assert body["pagination"]["total"] == 2


def test_unread_count_uses_each_stores_own_id(client):
    body = client.get("/api/notifications/unread-count", headers=_auth("S1001")).get_json()
    assert body == {"university": 1, "cross_system": 1, "total": 2}


def test_another_persons_message_is_not_found(client):
    headers = _auth("S1001")
    assert client.get("/api/notifications/university/2", headers=headers).status_code == 404
    assert client.get("/api/notifications/cross-system/2", headers=headers).status_code == 404
    assert client.post("/api/notifications/university/2/read", headers=headers).status_code == 404
    assert client.post("/api/notifications/cross-system/2/read", headers=headers).status_code == 404
    assert _rows(client, "SELECT is_read FROM messages WHERE id = 2") == [(0,)]


def test_message_for_another_system_is_not_in_the_university_inbox(client):
    assert client.get("/api/notifications/cross-system/3", headers=_auth("S1001")).status_code == 404


def test_staff_cannot_read_someone_elses_inbox_either(client):
    assert client.get("/api/notifications/university/1", headers=_auth("admin")).status_code == 404


def test_caller_with_no_local_profile_does_not_fall_back_to_the_central_id(client):
    # "nobody" has central id 50; S1019's central id 1 would read local admin.
    items = client.get("/api/notifications?source=university",
                       headers=_auth("nobody")).get_json()["items"]
    assert items == []


def test_mark_read_and_read_all_touch_only_own_rows(client):
    headers = _auth("S1001")
    assert client.post("/api/notifications/university/1/read", headers=headers).status_code == 200
    assert _rows(client, "SELECT is_read FROM messages WHERE id = 1") == [(1,)]
    assert client.post("/api/notifications/read-all", headers=headers).get_json()["cross_system"] == 1
    assert _rows(client, "SELECT is_read FROM messages WHERE id = 2") == [(0,)]
    assert client.get("/api/notifications/unread-count", headers=_auth("S1002")).get_json()["total"] == 2


def test_only_staff_can_send(client):
    body = {"recipient": "S1002", "subject": "s", "body": "b"}
    assert client.post("/api/notifications", json=body, headers=_auth("S1001")).status_code == 403
    response = client.post("/api/notifications", json=body, headers=_auth("sue"))
    assert response.status_code == 201
    assert _rows(client, "SELECT sender_id, recipient_id FROM messages WHERE id = ?",
                 response.get_json()["id"]) == [(5, 3)]


def test_send_to_unknown_recipient_is_404(client):
    body = {"recipient": "ghost", "subject": "s", "body": "b"}
    assert client.post("/api/notifications", json=body, headers=_auth("sue")).status_code == 404


def test_role_outside_the_university_is_refused(client):
    assert client.get("/api/notifications", headers=_auth("cook")).status_code == 403


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("who,status", [("S1001", 403), ("prof", 403), ("dad", 403),
                                        ("sue", 200), ("admin", 200)])
def test_who_can_list_users(client, who, status):
    assert client.get("/api/users", headers=_auth(who)).status_code == status


def test_user_payloads_carry_no_secrets(client):
    for path in ("/api/users?per_page=100", "/api/users/1", "/api/users/me"):
        text = client.get(path, headers=_auth("admin")).get_data(as_text=True)
        for secret in ("MUST-NOT-LEAK", "password", "salt", "two_fa", "mfa"):
            assert secret not in text, path


def test_a_student_reads_their_own_profile_by_local_id_only(client):
    headers = _auth("S1001")  # central id 3, local id 2
    assert client.get("/api/users/me", headers=headers).get_json()["id"] == 2
    assert client.get("/api/users/2", headers=headers).status_code == 200
    # Local id 3 is S1002: equal to the token's user_id, and still not theirs.
    assert client.get("/api/users/3", headers=headers).status_code == 403


def test_user_search_treats_wildcards_as_text(client):
    body = client.get("/api/users?search=%25", headers=_auth("admin")).get_json()
    assert body["items"] == []


def test_invalid_role_filter_is_rejected(client):
    response = client.get("/api/users?role=wizard", headers=_auth("admin"))
    assert response.status_code == 400
    assert response.mimetype == "application/problem+json"


@pytest.mark.parametrize("who", ["S1001", "prof", "sue"])
def test_only_administrators_change_users(client, who):
    response = client.patch("/api/users/2", json={"first_name": "X"}, headers=_auth(who))
    assert response.status_code == 403


def test_admin_changes_a_name_and_email(client):
    response = client.patch("/api/users/2", json={"first_name": "New", "email": "new@uni.example"},
                            headers=_auth("admin"))
    assert response.status_code == 200
    assert _rows(client, "SELECT first_name, email FROM users WHERE id = 2") == [("New", "new@uni.example")]


@pytest.mark.parametrize("body", [{"role": "admin"}, {"is_active": 0}, {"password": "x"},
                                  {"password_hash": "x"}, {"username": "x"}, {"student_id": "x"},
                                  {"email": "not-an-address"}, {"first_name": ""}, {}])
def test_user_update_refuses_everything_else(client, body):
    assert client.patch("/api/users/2", json=body, headers=_auth("admin")).status_code == 400
    assert _rows(client, "SELECT role, username FROM users WHERE id = 2") == [("student", "S1001")]


def test_duplicate_email_is_a_conflict(client):
    response = client.patch("/api/users/2", json={"email": "s1002@uni.example"}, headers=_auth("admin"))
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------

def test_reader_sees_only_live_announcements_for_their_role(client):
    items = client.get("/api/announcements", headers=_auth("S1001")).get_json()["items"]
    assert [i["title"] for i in items] == ["Everyone"]


@pytest.mark.parametrize("announcement_id", [2, 3, 4, 5])
def test_reader_cannot_open_one_outside_the_rule_by_id(client, announcement_id):
    path = f"/api/announcements/{announcement_id}"
    assert client.get(path, headers=_auth("S1001")).status_code == 404
    assert client.post(f"{path}/viewed", headers=_auth("S1001")).status_code == 404


def test_mark_viewed_is_recorded_under_the_local_id(client):
    assert client.post("/api/announcements/1/viewed", headers=_auth("S1001")).status_code == 200
    assert _rows(client, "SELECT viewer_id FROM announcement_viewers") == [(2,)]


def test_only_staff_create_announcements(client):
    body = {"title": "T", "content": "C", "target_audience": "all"}
    assert client.post("/api/announcements", json=body, headers=_auth("S1001")).status_code == 403
    response = client.post("/api/announcements", json=body, headers=_auth("prof"))
    assert response.status_code == 201
    assert response.get_json()["creator_id"] == 4


@pytest.mark.parametrize("body", [{"title": "T", "content": "C"},
                                  {"title": "T", "content": "C", "target_audience": "martians"},
                                  {"title": "T", "content": "C", "target_audience": "all",
                                   "start_date": "tomorrow"}])
def test_bad_announcements_are_rejected(client, body):
    assert client.post("/api/announcements", json=body, headers=_auth("prof")).status_code == 400


def test_only_creator_or_admin_edits_and_hides(client):
    edit = {"title": "Changed"}
    assert client.patch("/api/announcements/1", json=edit, headers=_auth("prof2")).status_code == 403
    assert client.patch("/api/announcements/1", json=edit, headers=_auth("S1001")).status_code == 403
    assert client.delete("/api/announcements/1", headers=_auth("sue")).status_code == 403
    assert client.patch("/api/announcements/1", json=edit, headers=_auth("prof")).get_json()["title"] == "Changed"
    assert client.delete("/api/announcements/1", headers=_auth("admin")).status_code == 200
    assert _rows(client, "SELECT is_active FROM announcements WHERE id = 1") == [(0,)]


def test_editing_cannot_reassign_the_creator(client):
    response = client.patch("/api/announcements/1", json={"creator_id": 1}, headers=_auth("prof"))
    assert response.status_code == 400


def test_managed_scope_is_own_for_staff_and_all_for_admin(client):
    mine = client.get("/api/announcements?scope=managed", headers=_auth("sue")).get_json()["items"]
    assert [i["title"] for i in mine] == ["Staff only"]
    assert client.get("/api/announcements?scope=managed", headers=_auth("admin")).get_json()[
        "pagination"]["total"] == 5
    assert client.get("/api/announcements?scope=managed", headers=_auth("S1001")).status_code == 403


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

def test_joined_rooms_use_the_local_id(client):
    items = client.get("/api/chat/rooms", headers=_auth("S1001")).get_json()["items"]
    assert [r["id"] for r in items] == [1]
    # Central id 3 is S1002's local id, and S1002 is in no rooms.
    assert client.get("/api/chat/rooms", headers=_auth("S1002")).get_json()["items"] == []


@pytest.mark.parametrize("who", ["S1002", "admin", "sue", "nobody"])
def test_non_members_cannot_read_a_room_staff_included(client, who):
    assert client.get("/api/chat/rooms/1/messages", headers=_auth(who)).status_code == 403
    assert client.get("/api/chat/rooms/1/members", headers=_auth(who)).status_code == 403
    response = client.post("/api/chat/rooms/1/messages", json={"content": "hi"}, headers=_auth(who))
    assert response.status_code == 403


def test_a_banned_member_is_shut_out(client):
    assert client.get("/api/chat/rooms/1/messages", headers=_auth("S1019")).status_code == 403
    assert client.get("/api/chat/rooms/1", headers=_auth("S1019")).status_code == 404


def test_member_reads_messages_without_server_paths(client):
    response = client.get("/api/chat/rooms/1/messages", headers=_auth("S1001"))
    assert response.get_json()["items"][0]["content"] == "hello"
    assert "attachment_path" not in response.get_json()["items"][0]
    assert "/srv/secret" not in response.get_data(as_text=True)


def test_member_list_hides_email_addresses(client):
    text = client.get("/api/chat/rooms/1/members", headers=_auth("S1001")).get_data(as_text=True)
    assert "uni.example" not in text
    assert "is_banned" not in text


def test_send_stores_the_local_sender(client):
    response = client.post("/api/chat/rooms/1/messages", json={"content": "mine"}, headers=_auth("S1001"))
    assert response.status_code == 201
    assert _rows(client, "SELECT sender_id FROM chat_messages WHERE id = ?",
                 response.get_json()["id"]) == [(2,)]


def test_the_safeguarding_filter_still_applies(client):
    response = client.post("/api/chat/rooms/1/messages", json={"content": "a forbiddenword b"},
                           headers=_auth("S1001"))
    assert response.status_code == 409
    assert _rows(client, "SELECT COUNT(*) FROM chat_messages WHERE content LIKE '%forbiddenword%'") == [(0,)]


def test_empty_and_oversized_messages_are_rejected(client):
    for content in ("   ", "x" * 4001):
        response = client.post("/api/chat/rooms/1/messages", json={"content": content}, headers=_auth("S1001"))
        assert response.status_code == 400


def test_joining_follows_the_room_type(client):
    headers = _auth("S1002")
    assert client.post("/api/chat/rooms/1/join", headers=headers).status_code == 403  # course
    assert client.post("/api/chat/rooms/3/join", headers=headers).status_code == 403  # no invitation
    assert client.post("/api/chat/rooms/2/join", headers=headers).get_json()["joined"] is True
    assert _rows(client, "SELECT user_id FROM chat_room_members WHERE room_id = 2 AND user_id = 3") == [(3,)]


def test_a_private_room_is_invisible_to_outsiders(client):
    assert client.get("/api/chat/rooms/3", headers=_auth("S1001")).status_code == 404
    assert client.get("/api/chat/rooms/2", headers=_auth("S1001")).status_code == 200


def test_course_rooms_need_staff_to_create(client):
    body = {"name": "New", "room_type": "course"}
    assert client.post("/api/chat/rooms", json=body, headers=_auth("S1001")).status_code == 403
    assert client.post("/api/chat/rooms", json=body, headers=_auth("prof")).status_code == 201


def test_student_can_create_a_public_room(client):
    body = {"name": "Study", "room_type": "public"}
    assert client.post("/api/chat/rooms", json=body, headers=_auth("S1001")).status_code == 201


def test_message_delete_is_for_the_sender_or_a_room_admin(client):
    assert client.delete("/api/chat/messages/1", headers=_auth("S1002")).status_code == 403
    assert client.delete("/api/chat/messages/1", headers=_auth("S1001")).status_code == 403
    assert client.delete("/api/chat/messages/1", headers=_auth("prof")).status_code == 200
    assert client.get("/api/chat/rooms/1/messages", headers=_auth("S1001")).get_json()[
        "items"][0]["content"] == ""


def test_unread_counts_are_the_callers(client):
    assert client.get("/api/chat/unread", headers=_auth("S1001")).get_json()["rooms"] == {"1": 1}
    assert client.post("/api/chat/rooms/1/read", headers=_auth("S1001")).status_code == 200
    assert client.get("/api/chat/unread", headers=_auth("S1001")).get_json()["rooms"] == {"1": 0}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("who,status", [("S1002", 200), ("admin", 200), ("S1001", 403),
                                        ("prof", 403), ("sue", 403), ("dad", 403)])
def test_who_can_read_a_document(client, who, status):
    assert client.get("/api/documents/1", headers=_auth(who)).status_code == status
    assert client.get("/api/documents/1/download", headers=_auth(who)).status_code == status


def test_owner_is_never_matched_on_the_central_id(client):
    # Document 2 is owned by "3", and S1001's central id is 3.
    assert client.get("/api/documents/2", headers=_auth("S1001")).status_code == 403


def test_document_payloads_hide_the_server_path(client):
    text = client.get("/api/documents/1", headers=_auth("S1002")).get_data(as_text=True)
    assert "file_path" not in text and "file_content" not in text
    assert str(client.uploads) not in text


def test_download_returns_the_file(client):
    response = client.get("/api/documents/1/download", headers=_auth("S1002"))
    assert response.data == b"S1002 transcript"
    assert "attachment" in response.headers["Content-Disposition"]


def test_download_will_not_leave_the_upload_folder(client):
    response = client.get("/api/documents/2/download", headers=_auth("admin"))
    assert response.status_code == 404


def test_listing_is_pinned_to_the_caller(client):
    assert client.get("/api/documents", headers=_auth("S1001")).get_json()["items"] == []
    assert client.get("/api/documents?owner_id=S1002", headers=_auth("S1001")).status_code == 403
    assert [d["document_id"] for d in client.get("/api/documents", headers=_auth("S1002")).get_json()["items"]] == [1]
    assert client.get("/api/documents?owner_id=S1002", headers=_auth("admin")).get_json()["pagination"]["total"] == 1


def _upload(client, who, **form):
    data = {"file": (io.BytesIO(form.pop("content", b"plain text body")), form.pop("name", "notes.txt")),
            "type_id": "11", **form}
    return client.post("/api/documents", data=data, content_type="multipart/form-data", headers=_auth(who))


def test_a_student_uploads_their_own_and_versions_chain(client):
    first = _upload(client, "S1001")
    assert first.status_code == 201, first.get_data(as_text=True)
    assert first.get_json()["owner_id"] == "S1001"
    assert first.get_json()["verification_status"] == "Pending"
    second = _upload(client, "S1001")
    assert second.get_json()["version_number"] == 2
    assert second.get_json()["parent_document_id"] == first.get_json()["document_id"]
    assert _rows(client, "SELECT is_current_version FROM documents WHERE document_id = ?",
                 first.get_json()["document_id"]) == [(0,)]
    stored = _rows(client, "SELECT file_path FROM documents WHERE document_id = ?",
                   first.get_json()["document_id"])[0][0]
    assert Path(stored).is_relative_to(client.uploads)
    assert _rows(client, "SELECT COUNT(*) FROM messages WHERE recipient_id = 2 AND subject LIKE '[Documents]%'")[0][0] == 2


def test_student_cannot_upload_for_someone_else(client):
    assert _upload(client, "S1001", student_id="S1002").status_code == 403


def test_admin_can_upload_for_a_student(client):
    response = _upload(client, "admin", student_id="S1002")
    assert response.status_code == 201
    assert response.get_json()["owner_id"] == "S1002"


@pytest.mark.parametrize("form,status", [
    ({"name": "evil.exe"}, 400), ({"type_id": "999"}, 404), ({"type_id": "x"}, 400),
    ({"content": b"x" * (1024 * 1024 + 1)}, 413)])
def test_bad_uploads_are_rejected(client, form, status):
    assert _upload(client, "S1001", **form).status_code == status
    assert _rows(client, "SELECT COUNT(*) FROM documents WHERE owner_id = 'S1001'") == [(0,)]


def test_upload_folder_cannot_be_chosen_by_path_traversal(client):
    assert _upload(client, "admin", student_id="../../etc").status_code == 404


def test_only_administrators_verify(client):
    body = {"verification_status": "Verified", "notes": "ok"}
    for who in ("S1002", "prof", "sue"):
        assert client.patch("/api/documents/1/verification", json=body, headers=_auth(who)).status_code == 403
    response = client.patch("/api/documents/1/verification", json=body, headers=_auth("admin"))
    assert response.get_json()["verification_status"] == "Verified"
    assert response.get_json()["verified_by"] == "admin"
    assert client.patch("/api/documents/1/verification", json={"verification_status": "Great"},
                        headers=_auth("admin")).status_code == 400


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def test_each_role_gets_its_own_view(client):
    for who, view in (("S1001", "student"), ("prof", "instructor"), ("admin", "admin"), ("sue", "staff")):
        assert client.get("/api/dashboard", headers=_auth(who)).get_json()["view"] == view


def test_student_view_is_keyed_on_their_own_student_id(client, monkeypatch):
    seen = []
    service = dashboard_routes.DashboardService
    monkeypatch.setattr(service, "get_student_dashboard_data", staticmethod(lambda s: seen.append(s) or {}))
    monkeypatch.setattr(service, "get_student_financial_summary", staticmethod(lambda s: {}))
    assert client.get("/api/dashboard", headers=_auth("S1001")).status_code == 200
    assert seen == ["S1001"]


@pytest.mark.parametrize("who", ["dad", "cook"])
def test_roles_with_no_dashboard_are_refused(client, who):
    assert client.get("/api/dashboard", headers=_auth(who)).status_code == 403


def test_student_without_a_record_gets_404(client):
    assert client.get("/api/dashboard", headers=_auth("nobody")).status_code == 404


@pytest.mark.parametrize("who,status", [("S1001", 200), ("S1002", 403), ("prof", 403), ("dad", 403),
                                        ("sue", 200), ("admin", 200)])
def test_who_can_see_a_students_dashboard(client, who, status):
    assert client.get("/api/dashboard/students/S1001", headers=_auth(who)).status_code == status


def test_dashboard_path_is_not_matched_on_the_central_id(client):
    # S1001's central id is 3.
    assert client.get("/api/dashboard/students/3", headers=_auth("S1001")).status_code == 403


@pytest.mark.parametrize("who,status", [("S1001", 403), ("prof", 403), ("sue", 403), ("admin", 200)])
def test_who_can_see_operations(client, who, status):
    assert client.get("/api/dashboard/operations", headers=_auth(who)).status_code == status
