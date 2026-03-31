"""Tests for ForgotPasswordService — security question reset flow.

Covers: correct/wrong answers, rate limiting, lockout, enumeration
prevention, answer policy validation, question management, and
audit logging.
"""

import sqlite3
import pytest

from education_system.shared.auth.schema import (
    initialise_auth_db,
    _hash_answer,
    _verify_answer,
    validate_answer,
    SECURITY_QUESTIONS,
)
from education_system.shared.auth.password_manager import hash_password, verify_password
from education_system.shared.auth.forgot_password import (
    ForgotPasswordService,
    MAX_SQ_ATTEMPTS,
)
from education_system.shared.auth.exceptions import AuthError


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
            svc.set_security_questions(1, [("Q?", "A"), ("Q2?", "A2")])

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
