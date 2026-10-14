"""Parent-portal accounts are mirrored into the shared auth database.

Portal accounts used to exist only in ``sixthform.db``, which meant an
account created in the Parent Portal could not be used at the universal
login screen. These cover the mirror that closes that gap, in both
directions.
"""

from __future__ import annotations

import sqlite3

import pytest

from education_system.platform.identity.auth.core import UserAuth
from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    shared_auth_mirror as mirror,
)


def _auth_user(auth_db: str, username: str):
    conn = sqlite3.connect(auth_db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, display_name, email, is_active FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            return None
        systems = conn.execute(
            "SELECT system_key, role FROM user_systems WHERE user_id = ?", (row["id"],)
        ).fetchall()
        return dict(row), [dict(s) for s in systems]
    finally:
        conn.close()


def test_create_account_mirrors_into_shared_auth(feature_db):
    pp = feature_db.mods["parent_portal"]
    pp.create_account(username="mum", password="password1", full_name="Mo Um",
                      email="mo@example.test")

    user, systems = _auth_user(feature_db.auth_db, "mum")
    assert user["display_name"] == "Mo Um"
    assert user["email"] == "mo@example.test"
    assert user["is_active"] == 1
    assert systems == [{"system_key": "sixth_form", "role": "parent"}]


def test_mirrored_account_can_use_the_universal_login(feature_db):
    pp = feature_db.mods["parent_portal"]
    pp.create_account(username="dad", password="password1", full_name="Da Ad")

    info = UserAuth(feature_db.auth_db).login("dad", "password1")
    assert info["systems"] == [{"system_key": "sixth_form", "role": "parent"}]
    # The portal minimum (8 chars) is below the shared password policy;
    # mirroring must not force a reset the parent cannot complete.
    assert not info.get("must_change_password")
    assert not info.get("password_expired")


def test_username_taken_by_another_system_is_refused(feature_db):
    pp = feature_db.mods["parent_portal"]
    UserAuth(feature_db.auth_db).create_user(
        "sf.teacher", "N0t-A-Parent!42", display_name="Teacher",
        systems=[("sixth_form", "teacher")])

    with pytest.raises(pp.ValidationError):
        pp.create_account(username="sf.teacher", password="password1",
                          full_name="Impostor")

    # The staff account keeps its own credentials and role.
    _, systems = _auth_user(feature_db.auth_db, "sf.teacher")
    assert systems == [{"system_key": "sixth_form", "role": "teacher"}]
    assert UserAuth(feature_db.auth_db).login("sf.teacher", "N0t-A-Parent!42")


def test_reset_backfills_an_unmirrored_account(feature_db):
    """Accounts created before the mirror existed have no recoverable
    plaintext, so a password reset is what brings them into shared auth."""
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="legacy", password="password1", full_name="Leg Acy")

    # Simulate a pre-mirror account by dropping the shadow row.
    conn = sqlite3.connect(feature_db.auth_db)
    conn.execute("DELETE FROM user_systems WHERE user_id = "
                 "(SELECT id FROM users WHERE username = 'legacy')")
    conn.execute("DELETE FROM users WHERE username = 'legacy'")
    conn.commit()
    conn.close()
    assert not mirror.has_mirror("legacy")

    pp.set_password(aid, "password2")

    assert mirror.has_mirror("legacy")
    assert UserAuth(feature_db.auth_db).login("legacy", "password2")
    assert pp.authenticate("legacy", "password2") is not None


def test_list_accounts_reports_login_state(feature_db):
    pp = feature_db.mods["parent_portal"]
    pp.create_account(username="listed", password="password1", full_name="Lis Ted")
    entry = next(a for a in pp.list_accounts() if a["username"] == "listed")
    assert entry["login_enabled"] is True


def test_disabling_an_account_blocks_the_universal_login(feature_db):
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="paused", password="password1", full_name="Pa Used")
    pp.set_active(aid, False)

    assert _auth_user(feature_db.auth_db, "paused")[0]["is_active"] == 0
    with pytest.raises(Exception):
        UserAuth(feature_db.auth_db).login("paused", "password1")

    pp.set_active(aid, True)
    assert UserAuth(feature_db.auth_db).login("paused", "password1")


def test_deleting_an_account_revokes_shared_access(feature_db):
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="gone", password="password1", full_name="Go Ne")
    pp.delete_account(aid)

    user, systems = _auth_user(feature_db.auth_db, "gone")
    # The row survives so audit/history FKs aren't orphaned, but it is
    # deactivated and holds no system access.
    assert user["is_active"] == 0
    assert systems == []
    with pytest.raises(Exception):
        UserAuth(feature_db.auth_db).login("gone", "password1")


def test_password_changed_on_the_shared_side_still_works_in_the_portal(feature_db):
    """Without this the two stores drift the first time a parent uses the
    login screen's change-password form."""
    pp = feature_db.mods["parent_portal"]
    pp.create_account(username="changer", password="password1", full_name="Ch Anger")
    auth = UserAuth(feature_db.auth_db)
    user_id = _auth_user(feature_db.auth_db, "changer")[0]["id"]

    auth.change_password(user_id, "password1", "Str0ng!Passw0rd#9")

    assert pp.authenticate("changer", "Str0ng!Passw0rd#9") is not None
    assert pp.authenticate("changer", "password1") is None


def test_shared_fallback_ignores_non_parent_accounts(feature_db):
    """The fallback must not let an unrelated shared account authenticate
    against a portal username."""
    UserAuth(feature_db.auth_db).create_user(
        "outsider", "0utsider!Pass9", systems=[("university", "admin")])
    assert mirror.verify_shared_password("outsider", "0utsider!Pass9") is False


def test_shared_fallback_refuses_a_deactivated_account(feature_db):
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="halted", password="password1", full_name="Ha Lted")
    pp.set_active(aid, False)
    assert mirror.verify_shared_password("halted", "password1") is False
