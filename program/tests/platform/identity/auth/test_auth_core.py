"""Tests for shared.auth.core — UserAuth login, registration, lockout, roles."""

import os
import shutil
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

from education_system.platform.identity.auth.core import UserAuth
from education_system.platform.identity.auth.exceptions import AuthError
from education_system.platform.identity.auth.defaults import MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_MINUTES
from education_system.platform.identity.auth.db import connect


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def _template_auth_db(tmp_path_factory):
    from education_system.platform.identity.auth.schema import initialise_auth_db, seed_default_users
    path = str(tmp_path_factory.mktemp("auth_core_tpl") / "template_auth.db")
    initialise_auth_db(path)
    seed_default_users(path)
    return path


@pytest.fixture
def auth_db(tmp_path, _template_auth_db):
    db_path = str(tmp_path / "test_auth.db")
    shutil.copy2(_template_auth_db, db_path)
    return db_path


@pytest.fixture
def auth(auth_db):
    return UserAuth(db_path=auth_db)


# ── Login ─────────────────────────────────────────────────────────────────


class TestLogin:
    def test_valid_credentials(self, auth):
        result = auth.login("admin1", "admin1234")
        assert result["username"] == "admin1"
        assert "id" in result
        assert "systems" in result

    def test_sets_current_user(self, auth):
        auth.login("admin1", "admin1234")
        assert auth.is_logged_in
        assert auth.current_user["username"] == "admin1"

    def test_returns_systems(self, auth):
        result = auth.login("superadmin", "SuperAdmin@123")
        system_keys = {s["system_key"] for s in result["systems"]}
        assert "sixth_form" in system_keys
        assert "university" in system_keys

    def test_wrong_password(self, auth):
        with pytest.raises(AuthError, match="Invalid username or password"):
            auth.login("admin1", "wrongpass")

    def test_unknown_user(self, auth):
        with pytest.raises(AuthError, match="Invalid username or password"):
            auth.login("nonexistent", "anything")

    def test_same_error_message_for_both(self, auth):
        """No user-enumeration via distinct error messages."""
        with pytest.raises(AuthError) as exc1:
            auth.login("admin1", "wrong")
        with pytest.raises(AuthError) as exc2:
            auth.login("nonexistent", "wrong")
        assert str(exc1.value) == str(exc2.value)


# ── provision_user (legacy → shared bcrypt migration) ───────────────────────


class TestProvisionUser:
    def test_creates_bcrypt_account(self, auth, auth_db):
        uid = auth.provision_user(
            "migrant1", "student123",
            display_name="Migrant One", email="m1@uni.test",
            systems=[("university", "student")],
        )
        conn = connect(auth_db)
        try:
            row = conn.execute(
                "SELECT password_hash, legacy_salt, password_changed_at "
                "FROM users WHERE id = ?", (uid,)
            ).fetchone()
            assert row["password_hash"].startswith("$2")  # bcrypt
            assert row["legacy_salt"] is None
            assert row["password_changed_at"] is not None
            sysrow = conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ?", (uid,)
            ).fetchone()
            assert (sysrow["system_key"], sysrow["role"]) == ("university", "student")
        finally:
            conn.close()

    def test_login_via_fast_path_after_provision(self, auth):
        auth.provision_user(
            "migrant2", "student123", systems=[("university", "staff")]
        )
        result = auth.login("migrant2", "student123")
        assert result["username"] == "migrant2"
        assert {"system_key": "university", "role": "staff"} in result["systems"]

    def test_idempotent(self, auth, auth_db):
        uid1 = auth.provision_user("migrant3", "student123", systems=[("university", "student")])
        uid2 = auth.provision_user("migrant3", "student123", systems=[("university", "student")])
        assert uid1 == uid2
        conn = connect(auth_db)
        try:
            assert conn.execute(
                "SELECT COUNT(*) FROM users WHERE username = ?", ("migrant3",)
            ).fetchone()[0] == 1
            assert conn.execute(
                "SELECT COUNT(*) FROM user_systems WHERE user_id = ?", (uid1,)
            ).fetchone()[0] == 1
        finally:
            conn.close()

    def test_role_kept_current(self, auth, auth_db):
        uid = auth.provision_user("migrant4", "student123", systems=[("university", "student")])
        auth.provision_user("migrant4", "student123", systems=[("university", "admin")])
        conn = connect(auth_db)
        try:
            role = conn.execute(
                "SELECT role FROM user_systems WHERE user_id = ? AND system_key = 'university'",
                (uid,),
            ).fetchone()[0]
            assert role == "admin"
        finally:
            conn.close()

    def test_weak_password_still_provisions(self, auth):
        # 'student123' fails validate_password_strength; provision must accept it.
        uid = auth.provision_user("migrant5", "student123", systems=[("university", "student")])
        assert uid > 0
        assert auth.login("migrant5", "student123")["username"] == "migrant5"


# ── Lockout ───────────────────────────────────────────────────────────────


class TestLockout:
    def test_lockout_after_max_attempts(self, auth):
        for _ in range(MAX_LOGIN_ATTEMPTS):
            with pytest.raises(AuthError, match="Invalid username or password"):
                auth.login("staff1", "wrong")

        with pytest.raises(AuthError, match="locked"):
            auth.login("staff1", "wrong")

    def test_lockout_persists_with_correct_password(self, auth):
        for _ in range(MAX_LOGIN_ATTEMPTS):
            with pytest.raises(AuthError):
                auth.login("staff1", "wrong")

        with pytest.raises(AuthError, match="locked"):
            auth.login("staff1", "staff1234")  # correct password, still locked

    def test_lockout_expires(self, auth, auth_db):
        for _ in range(MAX_LOGIN_ATTEMPTS):
            with pytest.raises(AuthError):
                auth.login("staff1", "wrong")

        # Manually expire the lockout
        past = (datetime.utcnow() - timedelta(minutes=LOCKOUT_DURATION_MINUTES + 1)).isoformat()
        conn = connect(auth_db)
        conn.execute("UPDATE users SET locked_until = ? WHERE username = 'staff1'", (past,))
        conn.commit()
        conn.close()

        result = auth.login("staff1", "staff1234")
        assert result["username"] == "staff1"

    def test_successful_login_resets_counter(self, auth):
        for _ in range(MAX_LOGIN_ATTEMPTS - 1):
            with pytest.raises(AuthError):
                auth.login("admin1", "wrong")
        # Succeed
        auth.login("admin1", "admin1234")
        # One more failure should NOT lock
        with pytest.raises(AuthError, match="Invalid"):
            auth.login("admin1", "wrong")
        # Still not locked — can still try
        auth.login("admin1", "admin1234")


# ── Disabled account ──────────────────────────────────────────────────────


class TestDisabledAccount:
    def test_inactive_user_cannot_login(self, auth, auth_db):
        conn = connect(auth_db)
        conn.execute("UPDATE users SET is_active = 0 WHERE username = 'student1'")
        conn.commit()
        conn.close()

        with pytest.raises(AuthError, match="Invalid username or password"):
            auth.login("student1", "student1234")


# ── Registration ──────────────────────────────────────────────────────────


class TestCreateUser:
    def test_create_and_login(self, auth):
        uid = auth.create_user(
            "newuser", "N3wStr0ng!Pass#",
            display_name="New User",
            email="new@test.com",
            systems=[("sixth_form", "student")],
        )
        assert uid > 0
        result = auth.login("newuser", "N3wStr0ng!Pass#")
        assert result["username"] == "newuser"

    def test_duplicate_username(self, auth):
        auth.create_user("dupuser", "N3wStr0ng!Pass#")
        with pytest.raises(AuthError, match="already exists"):
            auth.create_user("dupuser", "N3wStr0ng!Pass#")

    def test_weak_password_rejected(self, auth):
        with pytest.raises(AuthError):
            auth.create_user("weakuser", "short")

    def test_systems_assigned(self, auth):
        auth.create_user(
            "sysuser", "N3wStr0ng!Pass#",
            systems=[("sixth_form", "student"), ("secondary", "student")],
        )
        result = auth.login("sysuser", "N3wStr0ng!Pass#")
        keys = {s["system_key"] for s in result["systems"]}
        assert keys == {"sixth_form", "secondary"}


# ── Role / system access ─────────────────────────────────────────────────


class TestRoleForSystem:
    def test_get_role_for_system(self, auth):
        auth.login("admin1", "admin1234")
        assert auth.get_role_for_system("sixth_form") == "admin"

    def test_no_role_for_wrong_system(self, auth):
        auth.login("admin1", "admin1234")
        # admin1 is college-only
        assert auth.get_role_for_system("university") is None

    def test_superadmin_has_all(self, auth):
        auth.login("superadmin", "SuperAdmin@123")
        for sys_key in ("university", "sixth_form", "secondary", "primary"):
            assert auth.get_role_for_system(sys_key) == "admin"

    def test_no_role_when_not_logged_in(self, auth):
        assert auth.get_role_for_system("sixth_form") is None


# ── Logout ────────────────────────────────────────────────────────────────


class TestLogout:
    def test_logout_clears_state(self, auth):
        auth.login("admin1", "admin1234")
        assert auth.is_logged_in
        auth.logout()
        assert not auth.is_logged_in
        assert auth.current_user is None

    def test_logout_invalidates_session(self, auth):
        auth.login("admin1", "admin1234")
        token = auth._current_token
        auth.logout()
        assert auth.session_manager.validate_session(token) is None


# ── Password change ───────────────────────────────────────────────────────


class TestChangePassword:
    def test_change_password(self, auth):
        uid = auth.create_user("chpw", "Old$trong1Pass!")
        auth.change_password(uid, "Old$trong1Pass!", "New$trong1Pass!")
        result = auth.login("chpw", "New$trong1Pass!")
        assert result["username"] == "chpw"

    def test_wrong_old_password(self, auth):
        uid = auth.create_user("chpw2", "Old$trong1Pass!")
        with pytest.raises(AuthError, match="incorrect"):
            auth.change_password(uid, "WrongOldPass!1", "New$trong1Pass!")

    def test_weak_new_password(self, auth):
        uid = auth.create_user("chpw3", "Old$trong1Pass!")
        with pytest.raises(AuthError):
            auth.change_password(uid, "Old$trong1Pass!", "weak")


# ── get_user_by_id ────────────────────────────────────────────────────────


class TestGetUserById:
    def test_existing_user(self, auth):
        result = auth.login("admin1", "admin1234")
        user = auth.get_user_by_id(result["id"])
        assert user["username"] == "admin1"
        assert "password_hash" not in user

    def test_nonexistent_user(self, auth):
        assert auth.get_user_by_id(999999) is None
