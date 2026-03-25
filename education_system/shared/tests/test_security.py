"""Cross-system security tests for the Education System.

Covers SQL injection prevention, authentication security, privilege
escalation, and input validation.
"""

import os
import re
import shutil
import string
import sys
import time

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

from education_system.shared.database.sql_safety import (
    validate_identifier,
    escape_like,
    build_where_clause,
    build_set_clause,
)
from education_system.shared.auth.core import UserAuth
from education_system.shared.auth.session_manager import SessionManager
from education_system.shared.auth.role_manager import RoleManager, ROLE_HIERARCHY
from education_system.shared.auth.password_manager import hash_password, verify_password
from education_system.shared.auth.defaults import MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_MINUTES
from education_system.shared.auth.exceptions import AuthError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _template_auth_db(tmp_path_factory):
    """Create a seeded template auth DB once per session."""
    from education_system.shared.auth.schema import initialise_auth_db, seed_default_users
    path = str(tmp_path_factory.mktemp("sec_template") / "template_auth.db")
    initialise_auth_db(path)
    seed_default_users(path)
    return path


@pytest.fixture
def auth_db(tmp_path, _template_auth_db):
    """Per-test copy of the seeded auth DB."""
    db_path = str(tmp_path / "test_auth.db")
    shutil.copy2(_template_auth_db, db_path)
    return db_path


@pytest.fixture
def auth(auth_db):
    """UserAuth instance pointed at the test database."""
    return UserAuth(db_path=auth_db)


@pytest.fixture
def session_mgr(auth_db):
    """SessionManager instance pointed at the test database."""
    return SessionManager(db_path=auth_db)


@pytest.fixture
def role_mgr(auth_db):
    """RoleManager instance pointed at the test database."""
    return RoleManager(db_path=auth_db)


# ===================================================================
# 1. SQL INJECTION TESTS
# ===================================================================

class TestValidateIdentifier:
    """validate_identifier must reject anything that isn't a safe SQL name."""

    @pytest.mark.parametrize("bad_name", [
        "students; DROP TABLE",
        "name' OR '1'='1",
        "col--comment",
        "",
        " ",
        "has space",
        "star*",
        "semi;colon",
        "single'quote",
        'double"quote',
        "percent%",
        "back\\slash",
        "dot.name",
        "dash-name",
        "123startsWithDigit",
        "tab\there",
    ])
    def test_rejects_unsafe(self, bad_name):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            validate_identifier(bad_name)

    @pytest.mark.parametrize("good_name", [
        "students",
        "first_name",
        "Column1",
        "_private",
        "mixedCaseTable",
        "ALL_CAPS",
        "a",
        "_",
    ])
    def test_accepts_safe(self, good_name):
        assert validate_identifier(good_name) == good_name


class TestEscapeLike:
    """escape_like must neutralise wildcard characters."""

    def test_escapes_percent(self):
        assert escape_like("100%") == "100\\%"

    def test_escapes_underscore(self):
        assert escape_like("first_name") == "first\\_name"

    def test_escapes_combined(self):
        assert escape_like("%_mix_%") == "\\%\\_mix\\_\\%"

    def test_plain_text_unchanged(self):
        assert escape_like("hello world") == "hello world"


class TestBuildWhereClause:
    """build_where_clause must use parameterised queries and reject bad columns."""

    def test_empty_conditions(self):
        clause, params = build_where_clause({})
        assert clause == ""
        assert params == []

    def test_single_condition(self):
        clause, params = build_where_clause({"status": "active"})
        assert "?" in clause
        assert params == ["active"]
        assert "status" in clause

    def test_null_value(self):
        clause, params = build_where_clause({"deleted_at": None})
        assert "IS NULL" in clause
        assert params == []

    def test_uses_placeholders_not_values(self):
        clause, params = build_where_clause({"name": "Robert'; DROP TABLE students--"})
        assert "Robert" not in clause
        assert "?" in clause
        assert params == ["Robert'; DROP TABLE students--"]

    def test_rejects_malicious_column(self):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            build_where_clause({"col; DROP TABLE x": "val"})

    def test_rejects_column_with_sql_comment(self):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            build_where_clause({"col--": "val"})

    def test_rejects_column_with_quote(self):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            build_where_clause({"col'name": "val"})


class TestBuildSetClause:
    """build_set_clause must use parameterised queries and reject bad columns."""

    def test_basic_set(self):
        clause, params = build_set_clause({"name": "Alice", "age": 21})
        assert "?" in clause
        assert "name" in clause
        assert params == ["Alice", 21]

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="No columns"):
            build_set_clause({})

    def test_rejects_malicious_column(self):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            build_set_clause({"1=1; --": "pwned"})

    def test_rejects_column_with_semicolon(self):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            build_set_clause({"name;DROP TABLE x": "val"})

    def test_uses_placeholders_not_values(self):
        clause, params = build_set_clause({"bio": "<script>alert(1)</script>"})
        assert "<script>" not in clause
        assert "?" in clause


# ===================================================================
# 2. AUTHENTICATION SECURITY TESTS
# ===================================================================

class TestBruteForceProtection:
    """Account must lock after MAX_LOGIN_ATTEMPTS failed logins."""

    def test_lockout_after_max_attempts(self, auth):
        for i in range(MAX_LOGIN_ATTEMPTS):
            with pytest.raises(AuthError, match="Invalid username or password"):
                auth.login("admin1", "WrongPassword!!")

        with pytest.raises(AuthError, match="locked"):
            auth.login("admin1", "WrongPassword!!")

    def test_successful_login_resets_counter(self, auth):
        # Fail a few times, then succeed — counter should reset
        for _ in range(MAX_LOGIN_ATTEMPTS - 1):
            with pytest.raises(AuthError):
                auth.login("admin1", "WrongPassword!!")

        # Correct password
        result = auth.login("admin1", "admin1234")
        assert result["username"] == "admin1"

        # Fail again — should start fresh, not lock immediately
        with pytest.raises(AuthError, match="Invalid username or password"):
            auth.login("admin1", "WrongPassword!!")

    def test_unknown_user_does_not_leak_existence(self, auth):
        """Both existing and non-existing users get the same error message."""
        with pytest.raises(AuthError, match="Invalid username or password"):
            auth.login("nonexistent_user_xyz", "anything")

        with pytest.raises(AuthError, match="Invalid username or password"):
            auth.login("admin1", "WrongPassword!!")


class TestTimingAttackResistance:
    """Login time should be roughly consistent regardless of username validity.

    NOTE: The current implementation does NOT perform a dummy bcrypt hash for
    unknown users, so there is a measurable timing difference between
    existing-user-wrong-password (~400ms for bcrypt) and nonexistent-user
    (~5ms).  This is a known weakness — the test documents it as xfail.
    """

    @pytest.mark.xfail(
        reason="Login skips bcrypt for unknown users — timing oracle exists (TODO: add dummy hash)",
        strict=True,
    )
    def test_consistent_login_timing(self, auth):
        iterations = 3
        valid_times = []
        invalid_times = []

        for _ in range(iterations):
            start = time.perf_counter()
            try:
                auth.login("admin1", "WrongPassword!!")
            except AuthError:
                pass
            valid_times.append(time.perf_counter() - start)

        # Use a fresh auth to avoid lockout
        auth2 = UserAuth(db_path=auth._db_path)
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                auth2.login("nonexistent_user_xyz", "WrongPassword!!")
            except AuthError:
                pass
            invalid_times.append(time.perf_counter() - start)

        avg_valid = sum(valid_times) / len(valid_times)
        avg_invalid = sum(invalid_times) / len(invalid_times)

        # Allow generous 10x ratio — we just want to rule out orders-of-magnitude
        # differences (e.g. instant rejection vs bcrypt hash). A real timing attack
        # needs sub-ms resolution, so this is a coarse sanity check.
        ratio = max(avg_valid, avg_invalid) / max(min(avg_valid, avg_invalid), 1e-9)
        assert ratio < 10, (
            f"Timing difference too large: valid_avg={avg_valid:.4f}s, "
            f"invalid_avg={avg_invalid:.4f}s, ratio={ratio:.1f}"
        )


class TestPasswordHashNotExposed:
    """Password hashes must never appear in user-facing data."""

    def test_login_response_has_no_hash(self, auth):
        result = auth.login("admin1", "admin1234")
        result_str = str(result)
        assert "password_hash" not in result_str
        assert "$2b$" not in result_str  # bcrypt prefix

    def test_get_user_has_no_hash(self, auth):
        result = auth.login("admin1", "admin1234")
        user = auth.get_user_by_id(result["id"])
        assert "password_hash" not in user
        assert "legacy_salt" not in user


class TestSessionSecurity:
    """Session tokens must be cryptographically random and properly managed."""

    def test_token_entropy(self, session_mgr, auth_db):
        """Tokens should be long enough and use a wide character set."""
        from education_system.shared.auth.db import connect
        conn = connect(auth_db)
        user_id = conn.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]
        conn.close()

        tokens = {session_mgr.create_session(user_id) for _ in range(20)}
        # All unique
        assert len(tokens) == 20
        # Each token should be at least 32 characters (secrets.token_urlsafe(32) → ~43 chars)
        for tok in tokens:
            assert len(tok) >= 32

    def test_session_fixation_new_token_on_login(self, auth):
        """Each login must produce a new session token."""
        auth.login("admin1", "admin1234")
        token1 = auth._current_token
        auth.logout()

        auth.login("admin1", "admin1234")
        token2 = auth._current_token

        assert token1 != token2

    def test_logout_destroys_session(self, auth, session_mgr):
        auth.login("admin1", "admin1234")
        token = auth._current_token
        assert session_mgr.validate_session(token) is not None

        auth.logout()
        assert session_mgr.validate_session(token) is None

    def test_invalidate_user_sessions(self, auth, session_mgr):
        """Invalidating all user sessions should destroy every token."""
        auth.login("admin1", "admin1234")
        user_id = auth.current_user["id"]
        token1 = auth._current_token

        # Create a second session
        token2 = session_mgr.create_session(user_id)

        session_mgr.invalidate_user_sessions(user_id)

        assert session_mgr.validate_session(token1) is None
        assert session_mgr.validate_session(token2) is None


# ===================================================================
# 3. PRIVILEGE ESCALATION TESTS
# ===================================================================

class TestRoleHierarchy:
    """Role checks must enforce the hierarchy correctly."""

    def test_student_cannot_reach_admin(self, role_mgr):
        assert not role_mgr.has_minimum_role("student", "admin")

    def test_student_cannot_reach_staff(self, role_mgr):
        assert not role_mgr.has_minimum_role("student", "staff")

    def test_staff_cannot_reach_admin(self, role_mgr):
        assert not role_mgr.has_minimum_role("staff", "admin")

    def test_admin_can_reach_all(self, role_mgr):
        for role in ROLE_HIERARCHY:
            assert role_mgr.has_minimum_role("admin", role)

    def test_unknown_role_has_no_privileges(self, role_mgr):
        assert not role_mgr.has_minimum_role("hacker", "student")


class TestCrossSystemAccess:
    """user_systems must prevent cross-system access."""

    def test_college_user_has_no_university_role(self, role_mgr, auth_db):
        """A college-only user should not have a university role."""
        from education_system.shared.auth.db import connect
        conn = connect(auth_db)
        row = conn.execute(
            "SELECT user_id FROM user_systems WHERE system_key = 'college' AND role = 'student'"
        ).fetchone()
        conn.close()

        if row:
            uni_role = role_mgr.get_user_role_for_system(row["user_id"], "university")
            # If this user is college-only, they should have no university role
            # (superadmin has both, so we check a non-superadmin)
            college_systems = role_mgr.get_user_systems(row["user_id"])
            system_keys = {s["system_key"] for s in college_systems}
            if "university" not in system_keys:
                assert uni_role is None

    def test_grant_and_revoke_access(self, role_mgr, auth_db):
        """Grant/revoke cycle must work cleanly."""
        from education_system.shared.auth.db import connect
        conn = connect(auth_db)
        row = conn.execute(
            "SELECT user_id FROM user_systems WHERE system_key = 'college' AND role = 'student'"
        ).fetchone()
        conn.close()

        if row:
            user_id = row["user_id"]
            # Grant university access
            role_mgr.grant_system_access(user_id, "university", "student")
            assert role_mgr.get_user_role_for_system(user_id, "university") == "student"

            # Revoke it
            role_mgr.revoke_system_access(user_id, "university")
            assert role_mgr.get_user_role_for_system(user_id, "university") is None

    def test_role_change_requires_valid_role(self, role_mgr, auth_db):
        """Granting a nonsense role should fail."""
        from education_system.shared.auth.db import connect
        conn = connect(auth_db)
        row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        conn.close()

        with pytest.raises(ValueError, match="Invalid role"):
            role_mgr.grant_system_access(row["id"], "college", "superuser_hacker")


# ===================================================================
# 4. INPUT VALIDATION TESTS
# ===================================================================

class TestXSSPrevention:
    """HTML/script tags should not be stored as executable content.

    These tests verify that the system either strips, escapes, or at
    minimum stores the input as-is (to be escaped at render time) without
    executing it.  The key thing is that raw HTML does NOT end up in
    identifiers or SQL-unsafe positions.
    """

    XSS_PAYLOADS = [
        "<script>alert('xss')</script>",
        '<img src=x onerror="alert(1)">',
        "javascript:alert(1)",
        "<svg onload=alert(1)>",
        "'; DROP TABLE users; --",
    ]

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_xss_in_identifier_rejected(self, payload):
        """XSS payloads must not pass identifier validation."""
        with pytest.raises(ValueError):
            validate_identifier(payload)

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_xss_in_where_clause_parameterised(self, payload):
        """XSS in values must be parameterised, not inlined into SQL."""
        clause, params = build_where_clause({"name": payload})
        assert payload not in clause
        assert payload in params


class TestPathTraversal:
    """Path traversal attempts in identifiers should be rejected."""

    @pytest.mark.parametrize("path", [
        "../../../etc/passwd",
        "..\\..\\windows\\system32",
        "file/../../secret",
        "name/../admin",
    ])
    def test_path_traversal_in_identifier(self, path):
        with pytest.raises(ValueError):
            validate_identifier(path)


class TestIntegerOverflow:
    """Pagination-style integer parameters should be validated."""

    def test_negative_in_where_clause(self):
        """Negative values are allowed as values (they're parameterised), not columns."""
        clause, params = build_where_clause({"page": -1})
        assert params == [-1]
        # The important thing is parameterisation, not value rejection

    def test_very_large_number_parameterised(self):
        clause, params = build_where_clause({"offset": 999999999999})
        assert 999999999999 in params
        assert "999999999999" not in clause


class TestPasswordStrengthValidation:
    """create_user must enforce password strength rules."""

    @pytest.mark.parametrize("weak_password", [
        "short",           # Too short
        "alllowercase12!", # No uppercase
        "ALLUPPERCASE12!", # No lowercase
        "NoDigitsHere!!!",  # No digits
        "NoSpecial1234Ab",  # No special chars
    ])
    def test_weak_passwords_rejected(self, auth, weak_password):
        with pytest.raises(AuthError):
            auth.create_user("weakuser", weak_password)

    def test_strong_password_accepted(self, auth):
        user_id = auth.create_user(
            "stronguser",
            "V3ryStr0ng!Pass#",
            systems=[("college", "student")],
        )
        assert user_id > 0


class TestDeactivatedAccount:
    """Deactivated accounts must not be able to login."""

    def test_deactivated_user_cannot_login(self, auth, auth_db):
        from education_system.shared.auth.db import connect
        conn = connect(auth_db)
        conn.execute("UPDATE users SET is_active = 0 WHERE username = 'staff1'")
        conn.commit()
        conn.close()

        with pytest.raises(AuthError, match="Invalid username or password"):
            auth.login("staff1", "staff1234")


class TestSessionExpiry:
    """Expired sessions must be rejected."""

    def test_expired_session_invalid(self, auth_db):
        from education_system.shared.auth.db import connect
        sm = SessionManager(db_path=auth_db)
        conn = connect(auth_db)
        user_id = conn.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]
        conn.close()

        token = sm.create_session(user_id)
        assert sm.validate_session(token) is not None

        # Manually expire the session
        conn = connect(auth_db)
        conn.execute(
            "UPDATE sessions SET expires_at = '2000-01-01T00:00:00' WHERE token = ?",
            (token,),
        )
        conn.commit()
        conn.close()

        assert sm.validate_session(token) is None


class TestPasswordChangeInvalidatesSessions:
    """Changing a password must invalidate all existing sessions."""

    def test_sessions_invalidated_on_password_change(self, auth, session_mgr):
        # Create a user with a strong password so we can test change_password
        user_id = auth.create_user(
            "pwchange_user", "Old$trong1Pass!",
            systems=[("college", "student")],
        )
        auth.login("pwchange_user", "Old$trong1Pass!")
        token = auth._current_token

        assert session_mgr.validate_session(token) is not None

        auth.change_password(user_id, "Old$trong1Pass!", "New$trong1Pass!")

        assert session_mgr.validate_session(token) is None
