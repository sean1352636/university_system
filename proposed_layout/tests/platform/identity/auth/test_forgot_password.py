"""Tests for ForgotPasswordService — security question reset flow.

Covers: correct/wrong answers, rate limiting (per-user/IP/global), lockout,
enumeration prevention, answer policy validation, question management,
audit logging, legacy rehash, entropy checks, retention cleanup, and
integration tests for the full recovery path.
"""

import hashlib
import sqlite3
import pytest

from education_system.platform.identity.auth.schema import (
    initialise_auth_db,
    _hash_answer,
    _verify_answer,
    rehash_answer_if_legacy,
    validate_answer,
    cleanup_sq_tables,
    check_weak_defaults,
    SECURITY_QUESTIONS,
    MIN_ANSWER_LENGTH,
)
from education_system.platform.identity.auth.password_manager import hash_password, verify_password
from education_system.platform.identity.auth.forgot_password import (
    ForgotPasswordService,
    MAX_SQ_ATTEMPTS,
)
from education_system.platform.identity.auth.exceptions import AuthError


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    """Create a temporary auth DB with schema + a test user with security Qs."""
    path = str(tmp_path / "auth.db")
    initialise_auth_db(path)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    # Create test user
    pw = hash_password("OldPassword@123")
    conn.execute(
        "INSERT INTO users (username, password_hash, display_name, email) "
        "VALUES (?, ?, ?, ?)",
        ("testuser", pw, "Test User", "test@example.com"),
    )
    user_id = conn.execute("SELECT id FROM users WHERE username='testuser'").fetchone()["id"]

    # Add security questions (bcrypt hashed)
    for q, a in [
        ("What is your pet's name?", "fluffy"),
        ("What city were you born in?", "oxford"),
        ("What is your favourite colour?", "blue"),
    ]:
        conn.execute(
            "INSERT INTO security_questions (user_id, question, answer_hash) "
            "VALUES (?, ?, ?)",
            (user_id, q, _hash_answer(a)),
        )

    conn.commit()
    conn.close()
    return path


@pytest.fixture
def svc(db):
    return ForgotPasswordService(db)


# ── Answer hashing ───────────────────────────────────────────────────────────

class TestAnswerHashing:
    def test_bcrypt_round_trip(self):
        h = _hash_answer("Fluffy")
        assert _verify_answer("fluffy", h)  # case-insensitive
        assert _verify_answer("FLUFFY", h)
        assert _verify_answer(" Fluffy ", h)  # whitespace stripped

    def test_wrong_answer(self):
        h = _hash_answer("fluffy")
        assert not _verify_answer("fido", h)

    def test_legacy_sha256_compat(self):
        """Answers stored as SHA-256 before the upgrade should still verify."""
        import hashlib
        legacy = hashlib.sha256("fluffy".encode()).hexdigest()
        assert _verify_answer("fluffy", legacy)
        assert not _verify_answer("wrong", legacy)


# ── Answer policy ────────────────────────────────────────────────────────────

class TestAnswerValidation:
    def test_too_short(self):
        ok, msg = validate_answer("a")
        assert not ok
        assert "at least" in msg.lower()

    def test_banned_answer(self):
        ok, msg = validate_answer("password")
        assert not ok
        assert "common" in msg.lower()

    def test_valid_answer(self):
        ok, msg = validate_answer("fluffy")
        assert ok
        assert msg == ""


# ── Question lookup ──────────────────────────────────────────────────────────

class TestGetQuestions:
    def test_returns_questions(self, svc):
        qs = svc.get_questions_for_user("testuser")
        assert len(qs) == 3
        assert all("id" in q and "question" in q for q in qs)

    def test_unknown_user_generic_error(self, svc):
        with pytest.raises(AuthError, match="Unable to verify"):
            svc.get_questions_for_user("nonexistent")

    def test_user_without_questions_generic_error(self, db):
        # Create user with no questions
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name) "
            "VALUES (?, ?, ?)",
            ("noquestions", hash_password("Test@12345678"), "No Q User"),
        )
        conn.commit()
        conn.close()

        svc = ForgotPasswordService(db)
        with pytest.raises(AuthError, match="Unable to verify"):
            svc.get_questions_for_user("noquestions")


# ── Verification + reset ─────────────────────────────────────────────────────

class TestVerifyAndReset:
    def test_correct_answers_resets_password(self, svc, db):
        qs = svc.get_questions_for_user("testuser")
        answers = {}
        correct = {"What is your pet's name?": "fluffy",
                    "What city were you born in?": "oxford",
                    "What is your favourite colour?": "blue"}
        for q in qs:
            answers[q["id"]] = correct[q["question"]]

        result = svc.verify_answers_and_reset("testuser", answers)
        assert "temp_password" in result
        assert result["username"] == "testuser"

        # Temp password should work for login
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT password_hash, password_changed_at FROM users WHERE username='testuser'").fetchone()
        conn.close()
        assert verify_password(result["temp_password"], row["password_hash"])
        assert row["password_changed_at"] is None  # forces change

    def test_wrong_answer_generic_error(self, svc):
        qs = svc.get_questions_for_user("testuser")
        answers = {q["id"]: "wrong" for q in qs}

        with pytest.raises(AuthError, match="Unable to verify"):
            svc.verify_answers_and_reset("testuser", answers)

    def test_empty_answer_generic_error(self, svc):
        qs = svc.get_questions_for_user("testuser")
        answers = {q["id"]: "" for q in qs}

        with pytest.raises(AuthError, match="Unable to verify"):
            svc.verify_answers_and_reset("testuser", answers)

    def test_unknown_user_generic_error(self, svc):
        with pytest.raises(AuthError, match="Unable to verify"):
            svc.verify_answers_and_reset("nonexistent", {1: "a", 2: "b", 3: "c"})


# ── Brute-force / rate limiting ──────────────────────────────────────────────

class TestRateLimiting:
    def test_lockout_after_max_attempts(self, svc):
        qs = svc.get_questions_for_user("testuser")
        bad_answers = {q["id"]: "wrong" for q in qs}

        for _ in range(MAX_SQ_ATTEMPTS):
            with pytest.raises(AuthError):
                svc.verify_answers_and_reset("testuser", bad_answers)

        # Next attempt should be rate-limited
        with pytest.raises(AuthError, match="Too many failed attempts"):
            svc.verify_answers_and_reset("testuser", bad_answers)

    def test_success_still_works_before_lockout(self, svc):
        qs = svc.get_questions_for_user("testuser")
        bad_answers = {q["id"]: "wrong" for q in qs}
        correct = {"What is your pet's name?": "fluffy",
                    "What city were you born in?": "oxford",
                    "What is your favourite colour?": "blue"}
        good_answers = {q["id"]: correct[q["question"]] for q in qs}

        # Fail a few times but stay under limit
        for _ in range(MAX_SQ_ATTEMPTS - 1):
            with pytest.raises(AuthError):
                svc.verify_answers_and_reset("testuser", bad_answers)

        # Should still accept correct answers
        result = svc.verify_answers_and_reset("testuser", good_answers)
        assert "temp_password" in result


# ── Question management ──────────────────────────────────────────────────────

class TestSetSecurityQuestions:
    def test_set_questions(self, db):
        conn = sqlite3.connect(db)
        uid = conn.execute("SELECT id FROM users WHERE username='testuser'").fetchone()[0]
        conn.close()

        svc = ForgotPasswordService(db)
        svc.set_security_questions(uid, [
            ("New Q1?", "answer1"),
            ("New Q2?", "answer2"),
            ("New Q3?", "answer3"),
        ])
        assert svc.has_security_questions("testuser")

    def test_minimum_3_required(self, db):
        svc = ForgotPasswordService(db)
        with pytest.raises(AuthError, match="3 security questions"):
            svc.set_security_questions(1, [("Q?", "answer1"), ("Q2?", "answer2")])

    def test_banned_answer_rejected(self, db):
        conn = sqlite3.connect(db)
        uid = conn.execute("SELECT id FROM users WHERE username='testuser'").fetchone()[0]
        conn.close()

        svc = ForgotPasswordService(db)
        with pytest.raises(AuthError, match="common"):
            svc.set_security_questions(uid, [
                ("Q1?", "password"),  # banned
                ("Q2?", "answer2"),
                ("Q3?", "answer3"),
            ])

    def test_short_answer_rejected(self, db):
        conn = sqlite3.connect(db)
        uid = conn.execute("SELECT id FROM users WHERE username='testuser'").fetchone()[0]
        conn.close()

        svc = ForgotPasswordService(db)
        with pytest.raises(AuthError, match="at least"):
            svc.set_security_questions(uid, [
                ("Q1?", "x"),  # too short
                ("Q2?", "answer2"),
                ("Q3?", "answer3"),
            ])


# ── Audit logging ────────────────────────────────────────────────────────────

class TestAuditLogging:
    def test_successful_reset_logged(self, svc, db):
        qs = svc.get_questions_for_user("testuser")
        correct = {"What is your pet's name?": "fluffy",
                    "What city were you born in?": "oxford",
                    "What is your favourite colour?": "blue"}
        answers = {q["id"]: correct[q["question"]] for q in qs}
        svc.verify_answers_and_reset("testuser", answers)

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        events = conn.execute(
            "SELECT event_type FROM security_audit_log WHERE username='testuser' "
            "ORDER BY id"
        ).fetchall()
        conn.close()

        types = [e["event_type"] for e in events]
        assert "sq_lookup_success" in types
        assert "sq_reset_success" in types

    def test_failed_verify_logged(self, svc, db):
        qs = svc.get_questions_for_user("testuser")
        with pytest.raises(AuthError):
            svc.verify_answers_and_reset("testuser", {q["id"]: "wrong" for q in qs})

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        events = conn.execute(
            "SELECT event_type FROM security_audit_log WHERE username='testuser' "
            "AND event_type='sq_verify_failed'"
        ).fetchall()
        conn.close()
        assert len(events) >= 1

    def test_unknown_user_lookup_logged(self, svc, db):
        with pytest.raises(AuthError):
            svc.get_questions_for_user("ghost")

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        events = conn.execute(
            "SELECT event_type FROM security_audit_log WHERE username='ghost'"
        ).fetchall()
        conn.close()
        assert any(e["event_type"] == "sq_lookup_unknown_user" for e in events)


# ── Security questions list ──────────────────────────────────────────────────

class TestSecurityQuestionsList:
    def test_minimum_question_count(self):
        assert len(SECURITY_QUESTIONS) >= 10

    def test_no_duplicates(self):
        assert len(SECURITY_QUESTIONS) == len(set(SECURITY_QUESTIONS))


# ── Entropy / policy checks ─────────────────────────────────────────────────

class TestEntropyValidation:
    def test_repeated_char_rejected(self):
        ok, msg = validate_answer("aaaa")
        assert not ok
        assert "distinct" in msg.lower()

    def test_repeated_digit_rejected(self):
        ok, msg = validate_answer("1111")
        assert not ok

    def test_min_length_is_at_least_4(self):
        assert MIN_ANSWER_LENGTH >= 4

    def test_3_char_answer_rejected(self):
        ok, _ = validate_answer("cat")
        assert not ok

    def test_4_char_diverse_answer_accepted(self):
        ok, msg = validate_answer("fish")
        assert ok


# ── Legacy SHA-256 auto-rehash ───────────────────────────────────────────────

class TestLegacyRehash:
    def test_rehash_returns_bcrypt(self):
        legacy = hashlib.sha256("fluffy".encode()).hexdigest()
        new_hash = rehash_answer_if_legacy("fluffy", legacy)
        assert new_hash is not None
        assert new_hash.startswith("$2")
        assert _verify_answer("fluffy", new_hash)

    def test_no_rehash_for_bcrypt(self):
        bcrypt_hash = _hash_answer("fluffy")
        assert rehash_answer_if_legacy("fluffy", bcrypt_hash) is None

    def test_no_rehash_for_wrong_answer(self):
        legacy = hashlib.sha256("fluffy".encode()).hexdigest()
        assert rehash_answer_if_legacy("wrong", legacy) is None

    def test_rehash_on_successful_verify(self, db):
        """Legacy answers should be auto-rehashed to bcrypt on successful reset."""
        # Replace one answer with a legacy SHA-256 hash
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        uid = conn.execute("SELECT id FROM users WHERE username='testuser'").fetchone()["id"]
        q = conn.execute(
            "SELECT id FROM security_questions WHERE user_id=? LIMIT 1", (uid,)
        ).fetchone()
        legacy_hash = hashlib.sha256("fluffy".encode()).hexdigest()
        conn.execute(
            "UPDATE security_questions SET answer_hash=? WHERE id=?",
            (legacy_hash, q["id"]),
        )
        conn.commit()
        conn.close()

        # Perform successful reset
        svc = ForgotPasswordService(db)
        qs = svc.get_questions_for_user("testuser")
        correct = {"What is your pet's name?": "fluffy",
                    "What city were you born in?": "oxford",
                    "What is your favourite colour?": "blue"}
        answers = {q["id"]: correct[q["question"]] for q in qs}
        svc.verify_answers_and_reset("testuser", answers)

        # Verify the hash was upgraded to bcrypt
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT answer_hash FROM security_questions WHERE id=?", (q["id"],)
        ).fetchone()
        conn.close()
        assert row["answer_hash"].startswith("$2")


# ── Per-IP rate limiting ─────────────────────────────────────────────────────

class TestIPRateLimiting:
    def test_ip_recorded_in_attempts(self, svc, db):
        qs = svc.get_questions_for_user("testuser")
        bad = {q["id"]: "wrong" for q in qs}
        with pytest.raises(AuthError):
            svc.verify_answers_and_reset("testuser", bad, ip_address="10.0.0.1")

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT ip_address FROM sq_verification_attempts WHERE username='testuser' LIMIT 1"
        ).fetchone()
        conn.close()
        assert row["ip_address"] == "10.0.0.1"


# ── Retention cleanup ────────────────────────────────────────────────────────

class TestRetentionCleanup:
    def test_cleanup_removes_old_attempts(self, db):
        conn = sqlite3.connect(db)
        # Insert an old attempt (200 days ago)
        conn.execute(
            "INSERT INTO sq_verification_attempts (username, success, created_at) "
            "VALUES (?, 0, datetime('now', '-200 days'))",
            ("testuser",),
        )
        # Insert a recent attempt
        conn.execute(
            "INSERT INTO sq_verification_attempts (username, success) VALUES (?, 0)",
            ("testuser",),
        )
        conn.commit()
        conn.close()

        cleanup_sq_tables(db)

        conn = sqlite3.connect(db)
        cnt = conn.execute("SELECT COUNT(*) FROM sq_verification_attempts").fetchone()[0]
        conn.close()
        assert cnt == 1  # only the recent one survives

    def test_cleanup_removes_old_audit_entries(self, db):
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO security_audit_log (event_type, username, created_at) "
            "VALUES ('test', 'u', datetime('now', '-400 days'))"
        )
        conn.execute(
            "INSERT INTO security_audit_log (event_type, username) VALUES ('test', 'u')"
        )
        conn.commit()
        conn.close()

        cleanup_sq_tables(db)

        conn = sqlite3.connect(db)
        cnt = conn.execute("SELECT COUNT(*) FROM security_audit_log").fetchone()[0]
        conn.close()
        assert cnt == 1


# ── Weak defaults check ─────────────────────────────────────────────────────

class TestWeakDefaults:
    def test_check_weak_defaults_on_seeded_db(self, tmp_path):
        """Seeded DB should report weak default accounts."""
        import os
        db = str(tmp_path / "seeded.db")
        initialise_auth_db(db)
        # Force seeding by simulating fresh DB
        from education_system.platform.identity.auth.schema import seed_default_users
        seed_default_users(db)
        weak = check_weak_defaults(db)
        assert len(weak) > 0
        assert "superadmin" in weak


# ── Integration: full recovery path ──────────────────────────────────────────

class TestFullRecoveryPath:
    """End-to-end integration test covering the complete forgot-password flow:
    username lookup → security questions → answer verification → temp password →
    login with temp password → forced password change.
    """

    def test_full_recovery_flow(self, db):
        from education_system.platform.identity.auth.core import UserAuth

        svc = ForgotPasswordService(db)

        # Step 1: look up questions
        qs = svc.get_questions_for_user("testuser")
        assert len(qs) == 3

        # Step 2: verify answers and reset
        correct = {"What is your pet's name?": "fluffy",
                    "What city were you born in?": "oxford",
                    "What is your favourite colour?": "blue"}
        answers = {q["id"]: correct[q["question"]] for q in qs}
        result = svc.verify_answers_and_reset("testuser", answers, ip_address="127.0.0.1")

        assert "temp_password" in result
        temp_pw = result["temp_password"]

        # Step 3: login with temp password should succeed and flag password_expired
        auth = UserAuth(db)
        user_info = auth.login("testuser", temp_pw)
        assert user_info["password_expired"] is True

        # Step 4: change password
        auth.change_password(user_info["id"], temp_pw, "NewSecure@Pass99")

        # Step 5: login with new password, should not be expired
        auth2 = UserAuth(db)
        user_info2 = auth2.login("testuser", "NewSecure@Pass99")
        assert user_info2["password_expired"] is False

    def test_recovery_with_wrong_answers_then_correct(self, db):
        """User fails once, then succeeds — both events audited."""
        svc = ForgotPasswordService(db)
        qs = svc.get_questions_for_user("testuser")
        bad = {q["id"]: "wrong" for q in qs}
        correct = {"What is your pet's name?": "fluffy",
                    "What city were you born in?": "oxford",
                    "What is your favourite colour?": "blue"}
        good = {q["id"]: correct[q["question"]] for q in qs}

        with pytest.raises(AuthError):
            svc.verify_answers_and_reset("testuser", bad)

        result = svc.verify_answers_and_reset("testuser", good)
        assert "temp_password" in result

        # Verify audit trail has both failure and success
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        events = [
            r["event_type"] for r in conn.execute(
                "SELECT event_type FROM security_audit_log WHERE username='testuser' ORDER BY id"
            ).fetchall()
        ]
        conn.close()
        assert "sq_verify_failed" in events
        assert "sq_reset_success" in events
