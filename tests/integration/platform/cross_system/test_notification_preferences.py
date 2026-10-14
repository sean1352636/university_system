"""Notification preferences: the table, the precedence rules and the API.

Every database here is a temp file; nothing touches the live auth.db.
"""

import sqlite3

import pytest
from flask import Flask

from education_system.platform.delivery.api.routes import notification_routes
from education_system.platform.delivery.api.security import authentication
from education_system.platform.features.notifications.preferences import (
    DEFAULTS,
    NotificationPreferences,
    PreferenceError,
)
from education_system.platform.identity.auth.schema import initialise_auth_db


@pytest.fixture()
def auth_db(tmp_path):
    path = str(tmp_path / "auth.db")
    initialise_auth_db(path)
    return path


@pytest.fixture()
def prefs(auth_db):
    return NotificationPreferences(auth_db)


def _add_user(db, username):
    conn = sqlite3.connect(db)
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, display_name, is_active) "
        "VALUES (?, 'x', ?, 1)", (username, username))
    uid = cur.lastrowid
    conn.execute("INSERT INTO user_systems (user_id, system_key, role) "
                 "VALUES (?, 'secondary', 'teacher')", (uid,))
    conn.commit()
    conn.close()
    return uid


# ── Service ──────────────────────────────────────────────────────────────

def test_defaults_are_in_app_on_email_off(prefs):
    assert DEFAULTS == {"in_app": True, "email": False}
    assert prefs.is_enabled(1, "offers", "in_app") is True
    assert prefs.is_enabled(1, "offers", "email") is False
    assert prefs.enabled_channels(1, "offers") == ["in_app"]


def test_explicit_category_wins_over_wildcard(prefs):
    prefs.set_preference(7, "*", "email", True)
    prefs.set_preference(7, "reminders", "email", False)
    assert prefs.is_enabled(7, "offers", "email") is True  # from the wildcard
    assert prefs.is_enabled(7, "reminders", "email") is False  # explicit
    assert prefs.enabled_channels(7, "handover") == ["in_app", "email"]


def test_preferences_are_per_user(prefs):
    prefs.set_preference(1, "offers", "in_app", False)
    assert prefs.is_enabled(1, "offers", "in_app") is False
    assert prefs.is_enabled(2, "offers", "in_app") is True


def test_bulk_update_is_all_or_nothing(prefs):
    with pytest.raises(PreferenceError):
        prefs.set_preferences(3, {"offers": {"email": True},
                                  "not-a-category": {"email": True}})
    # The valid half was not applied either.
    assert prefs.is_enabled(3, "offers", "email") is False


def test_unknown_channel_and_non_bool_rejected(prefs):
    with pytest.raises(PreferenceError):
        prefs.set_preference(1, "offers", "sms", True)
    with pytest.raises(PreferenceError):
        prefs.set_preferences(1, {"offers": {"email": "yes"}})


def test_get_preferences_reports_effective_and_explicit(prefs):
    prefs.set_preference(5, "withdrawals", "in_app", False)
    got = prefs.get_preferences(5)
    assert got["categories"]["withdrawals"]["in_app"] is False
    assert got["categories"]["offers"]["in_app"] is True
    assert got["explicit"] == [
        {"category": "withdrawals", "channel": "in_app", "enabled": False}]


def test_reset_restores_defaults(prefs):
    prefs.set_preference(5, "offers", "in_app", False)
    assert prefs.reset(5) == 1
    assert prefs.is_enabled(5, "offers", "in_app") is True


# ── API ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(auth_db, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-notification-prefs-0123456789")
    # token_required re-reads the user from the auth DB on every request.
    monkeypatch.setattr(authentication, "_auth_db_path", auth_db)
    notification_routes.init_notification_routes(auth_db)
    app = Flask(__name__)
    app.register_blueprint(notification_routes.notification_prefs_bp,
                           url_prefix="/api/v1/notifications")
    yield app.test_client()
    notification_routes.init_notification_routes(None)


def _headers(uid, username):
    token = authentication.generate_token(
        uid, username, [{"system_key": "secondary", "role": "teacher"}])
    return {"Authorization": f"Bearer {token}"}


def test_api_requires_authentication(client):
    assert client.get("/api/v1/notifications/preferences").status_code == 401


def test_api_round_trip(client, auth_db):
    uid = _add_user(auth_db, "prefs_user_a")
    headers = _headers(uid, "prefs_user_a")

    r = client.get("/api/v1/notifications/preferences", headers=headers)
    assert r.status_code == 200
    assert r.get_json()["categories"]["offers"]["email"] is False

    r = client.put("/api/v1/notifications/preferences", headers=headers,
                   json={"categories": {"offers": {"email": True}}})
    assert r.status_code == 200
    assert r.get_json()["categories"]["offers"]["email"] is True

    r = client.delete("/api/v1/notifications/preferences", headers=headers)
    assert r.status_code == 200
    assert r.get_json()["categories"]["offers"]["email"] is False


def test_api_rejects_bad_body(client, auth_db):
    uid = _add_user(auth_db, "prefs_user_b")
    headers = _headers(uid, "prefs_user_b")
    assert client.put("/api/v1/notifications/preferences", headers=headers,
                      json={}).status_code == 400
    assert client.put("/api/v1/notifications/preferences", headers=headers,
                      json={"categories": {"bogus": {"email": True}}}).status_code == 400


def test_api_only_touches_the_callers_preferences(client, auth_db):
    a = _add_user(auth_db, "prefs_user_c")
    b = _add_user(auth_db, "prefs_user_d")
    client.put("/api/v1/notifications/preferences", headers=_headers(a, "prefs_user_c"),
               json={"categories": {"offers": {"in_app": False}}})
    got = client.get("/api/v1/notifications/preferences",
                     headers=_headers(b, "prefs_user_d")).get_json()
    assert got["categories"]["offers"]["in_app"] is True
