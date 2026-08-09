"""Tests for shared.auth.password_manager — bcrypt hashing, PBKDF2 legacy, strength validation."""

import hashlib
import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

from education_system.platform.identity.auth.password_manager import (
    hash_password,
    verify_password,
    validate_password_strength,
    _verify_pbkdf2_legacy,
)
from education_system.platform.identity.auth.defaults import MIN_PASSWORD_LENGTH


# ── Bcrypt hashing & verification ─────────────────────────────────────────


class TestHashPassword:
    def test_returns_bcrypt_hash(self):
        h = hash_password("Str0ng!Pass#1")
        assert h.startswith("$2b$")

    def test_different_salts(self):
        h1 = hash_password("Str0ng!Pass#1")
        h2 = hash_password("Str0ng!Pass#1")
        assert h1 != h2  # unique salt each time

    def test_verify_round_trip(self):
        pw = "V3ry$ecure!Pass"
        h = hash_password(pw)
        assert verify_password(pw, h) is True

    def test_wrong_password_fails(self):
        h = hash_password("CorrectHorse!")
        assert verify_password("WrongHorse!", h) is False


class TestVerifyPassword:
    def test_bcrypt_valid(self):
        h = hash_password("Test1234!@Abc")
        assert verify_password("Test1234!@Abc", h) is True

    def test_bcrypt_invalid(self):
        h = hash_password("Test1234!@Abc")
        assert verify_password("wrong", h) is False

    def test_malformed_hash_returns_false(self):
        assert verify_password("anything", "not-a-hash") is False

    def test_empty_hash_returns_false(self):
        assert verify_password("anything", "") is False

    def test_none_hash_returns_false(self):
        # verify_password catches AttributeError
        assert verify_password("anything", None) is False


# ── Legacy PBKDF2-SHA256 verification ─────────────────────────────────────


class TestLegacyPBKDF2:
    @staticmethod
    def _make_legacy_hash(password: str, salt: str) -> str:
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 1_000_000, dklen=64)
        return key.hex()

    def test_valid_legacy_password(self):
        salt = "abcdef0123456789"
        pw = "legacy_pass"
        h = self._make_legacy_hash(pw, salt)
        assert verify_password(pw, h, legacy_salt=salt) is True

    def test_wrong_legacy_password(self):
        salt = "abcdef0123456789"
        h = self._make_legacy_hash("right", salt)
        assert verify_password("wrong", h, legacy_salt=salt) is False

    def test_bad_salt_returns_false(self):
        # Should not crash
        assert _verify_pbkdf2_legacy("pw", "", "badhash") is False


# ── Password strength validation ──────────────────────────────────────────


class TestValidatePasswordStrength:
    def test_valid_password(self):
        ok, msg = validate_password_strength("Str0ng!Pass#1")
        assert ok is True

    def test_too_short(self):
        ok, msg = validate_password_strength("Ab1!")
        assert ok is False
        assert str(MIN_PASSWORD_LENGTH) in msg

    def test_no_uppercase(self):
        ok, msg = validate_password_strength("alllowercase12!!")
        assert ok is False
        assert "uppercase" in msg.lower()

    def test_no_lowercase(self):
        ok, msg = validate_password_strength("ALLUPPERCASE12!!")
        assert ok is False
        assert "lowercase" in msg.lower()

    def test_no_digit(self):
        ok, msg = validate_password_strength("NoDigitsHere!!!!")
        assert ok is False
        assert "digit" in msg.lower()

    def test_no_special_char(self):
        ok, msg = validate_password_strength("NoSpecial1234Ab")
        assert ok is False
        assert "special" in msg.lower()

    def test_exactly_min_length(self):
        pw = "Abcdefgh1!23"  # 12 chars
        assert len(pw) == MIN_PASSWORD_LENGTH
        ok, _ = validate_password_strength(pw)
        assert ok is True

    def test_empty_password(self):
        ok, _ = validate_password_strength("")
        assert ok is False

    def test_very_long_password(self):
        pw = "A" * 200 + "a1!"
        ok, _ = validate_password_strength(pw)
        assert ok is True

    def test_unicode_characters(self):
        # Ü is not matched by [A-Z] regex — need ASCII uppercase too
        pw = "Ünïcödë1234A!!"
        ok, _ = validate_password_strength(pw)
        assert ok is True
