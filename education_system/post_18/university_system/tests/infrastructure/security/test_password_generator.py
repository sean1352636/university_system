"""
Comprehensive tests for password_generator module.

Tests cover:
- generate_secure_password() with all parameter combinations
- Character set composition and exclusion
- Minimum length enforcement
- Ambiguous character exclusion
- generate_simple_password() convenience function
- generate_passphrase() word-based generation
- generate_temp_password() temporary passwords
- check_password_strength() scoring logic
"""

import string
import pytest
from unittest.mock import patch

from education_system.post_18.university_system.infrastructure.security.password_generator import (
    generate_secure_password,
    generate_simple_password,
    generate_passphrase,
    generate_temp_password,
    check_password_strength,
    LOWERCASE,
    UPPERCASE,
    DIGITS,
    SPECIAL,
    SPECIAL_SAFE,
    secure_password,
    simple_password,
    temp_password,
    passphrase,
)


# ---------------------------------------------------------------------------
# generate_secure_password - basic behavior
# ---------------------------------------------------------------------------

class TestGenerateSecurePasswordBasic:
    def test_default_length(self):
        pw = generate_secure_password()
        assert len(pw) == 16

    def test_custom_length(self):
        pw = generate_secure_password(length=20)
        assert len(pw) == 20

    def test_minimum_length_8(self):
        pw = generate_secure_password(length=8)
        assert len(pw) == 8

    def test_length_too_short_raises(self):
        with pytest.raises(ValueError, match="at least 8"):
            generate_secure_password(length=7)

    def test_length_1_raises(self):
        with pytest.raises(ValueError):
            generate_secure_password(length=1)

    def test_returns_string(self):
        assert isinstance(generate_secure_password(), str)

    def test_passwords_are_different(self):
        passwords = {generate_secure_password() for _ in range(20)}
        # All 20 should be unique (astronomically unlikely to collide)
        assert len(passwords) == 20


# ---------------------------------------------------------------------------
# Character set inclusion
# ---------------------------------------------------------------------------

class TestCharacterSets:
    def test_includes_uppercase(self):
        # Generate many passwords; at least one char should be uppercase
        pw = generate_secure_password(length=50, include_uppercase=True, exclude_ambiguous=False)
        assert any(c in UPPERCASE for c in pw)

    def test_excludes_uppercase(self):
        pw = generate_secure_password(length=50, include_uppercase=False, exclude_ambiguous=False)
        assert not any(c in UPPERCASE for c in pw)

    def test_includes_digits(self):
        pw = generate_secure_password(length=50, include_digits=True, exclude_ambiguous=False)
        assert any(c in DIGITS for c in pw)

    def test_excludes_digits(self):
        pw = generate_secure_password(length=50, include_digits=False, exclude_ambiguous=False)
        assert not any(c in DIGITS for c in pw)

    def test_includes_special_safe(self):
        pw = generate_secure_password(
            length=50, include_special=True, safe_special_only=True
        )
        assert any(c in SPECIAL_SAFE for c in pw)

    def test_includes_special_full(self):
        pw = generate_secure_password(
            length=50, include_special=True, safe_special_only=False, exclude_ambiguous=False
        )
        assert any(c in SPECIAL for c in pw)

    def test_excludes_special(self):
        pw = generate_secure_password(length=50, include_special=False, exclude_ambiguous=False)
        assert not any(c in SPECIAL for c in pw)


# ---------------------------------------------------------------------------
# Ambiguous character exclusion
# ---------------------------------------------------------------------------

class TestAmbiguousCharExclusion:
    def test_exclude_ambiguous_default(self):
        # Generate a long password many times and check none contain ambiguous chars
        ambiguous = set("0O1lI")
        for _ in range(20):
            pw = generate_secure_password(length=50, exclude_ambiguous=True)
            assert not any(c in ambiguous for c in pw), f"Found ambiguous char in: {pw}"

    def test_include_ambiguous_when_disabled(self):
        # When not excluding ambiguous, over many tries some should appear
        ambiguous = set("0O1lI")
        found = False
        for _ in range(50):
            pw = generate_secure_password(length=100, exclude_ambiguous=False)
            if any(c in ambiguous for c in pw):
                found = True
                break
        assert found, "Expected to find ambiguous chars when exclusion disabled"


# ---------------------------------------------------------------------------
# Required character guarantees
# ---------------------------------------------------------------------------

class TestRequiredCharacters:
    def test_always_has_lowercase(self):
        for _ in range(20):
            pw = generate_secure_password(length=8, exclude_ambiguous=False)
            lower_set = set(LOWERCASE)
            assert any(c in lower_set for c in pw)

    def test_always_has_uppercase_when_enabled(self):
        for _ in range(20):
            pw = generate_secure_password(length=8, include_uppercase=True, exclude_ambiguous=False)
            assert any(c in UPPERCASE for c in pw)

    def test_always_has_digit_when_enabled(self):
        for _ in range(20):
            pw = generate_secure_password(length=8, include_digits=True, exclude_ambiguous=False)
            assert any(c in DIGITS for c in pw)

    def test_always_has_special_when_enabled(self):
        for _ in range(20):
            pw = generate_secure_password(length=8, include_special=True)
            assert any(c in SPECIAL_SAFE for c in pw)


# ---------------------------------------------------------------------------
# generate_simple_password
# ---------------------------------------------------------------------------

class TestGenerateSimplePassword:
    def test_default_length(self):
        pw = generate_simple_password()
        assert len(pw) == 12

    def test_custom_length(self):
        pw = generate_simple_password(length=16)
        assert len(pw) == 16

    def test_no_special_chars(self):
        for _ in range(20):
            pw = generate_simple_password()
            assert not any(c in SPECIAL for c in pw)

    def test_has_letters_and_digits(self):
        pw = generate_simple_password(length=50)
        assert any(c.isalpha() for c in pw)
        assert any(c.isdigit() for c in pw)


# ---------------------------------------------------------------------------
# generate_passphrase
# ---------------------------------------------------------------------------

class TestGeneratePassphrase:
    def test_default_word_count(self):
        phrase = generate_passphrase()
        words = phrase.split("-")
        assert len(words) == 4

    def test_custom_word_count(self):
        phrase = generate_passphrase(word_count=6)
        words = phrase.split("-")
        assert len(words) == 6

    def test_custom_separator(self):
        phrase = generate_passphrase(separator="_")
        assert "_" in phrase
        words = phrase.split("_")
        assert len(words) == 4

    def test_minimum_words_raises(self):
        with pytest.raises(ValueError, match="at least 4"):
            generate_passphrase(word_count=3)

    def test_words_are_alpha(self):
        phrase = generate_passphrase()
        for word in phrase.split("-"):
            assert word.isalpha()

    def test_passphrases_vary(self):
        phrases = {generate_passphrase() for _ in range(20)}
        assert len(phrases) > 1


# ---------------------------------------------------------------------------
# generate_temp_password
# ---------------------------------------------------------------------------

class TestGenerateTempPassword:
    def test_length_12(self):
        pw = generate_temp_password()
        assert len(pw) == 12

    def test_has_all_character_types(self):
        pw = generate_temp_password()
        # Excluding ambiguous, so check filtered sets
        assert any(c.islower() for c in pw)
        assert any(c.isupper() for c in pw)
        assert any(c.isdigit() for c in pw)
        assert any(c in SPECIAL_SAFE for c in pw)


# ---------------------------------------------------------------------------
# check_password_strength
# ---------------------------------------------------------------------------

class TestCheckPasswordStrength:
    def test_strong_password(self):
        result = check_password_strength("Str0ng!Pass#word16")
        assert result["level"] == "strong"
        assert result["score"] >= 80

    def test_short_password(self):
        result = check_password_strength("Ab1!")
        assert result["score"] < 80
        assert "Use at least 8 characters" in result["suggestions"]

    def test_common_password_score_zero(self):
        result = check_password_strength("password")
        assert result["score"] == 0
        assert result["level"] == "very weak"

    def test_only_lowercase(self):
        result = check_password_strength("abcdefghijklmnop")
        assert "Add uppercase letters" in result["suggestions"]
        assert "Add numbers" in result["suggestions"]
        assert "Add special characters" in result["suggestions"]

    def test_medium_password(self):
        result = check_password_strength("Abcdefgh1")
        assert result["level"] in ("medium", "weak")

    def test_returns_dict_keys(self):
        result = check_password_strength("test")
        assert "score" in result
        assert "level" in result
        assert "suggestions" in result

    def test_score_capped_at_100(self):
        result = check_password_strength("Abcdefgh1!@#$%^&*()_+XYZxyz")
        assert result["score"] <= 100

    def test_very_weak_level(self):
        result = check_password_strength("abc")
        assert result["level"] == "very weak"


# ---------------------------------------------------------------------------
# Convenience aliases
# ---------------------------------------------------------------------------

class TestConvenienceAliases:
    def test_secure_password_alias(self):
        assert secure_password is generate_secure_password

    def test_simple_password_alias(self):
        assert simple_password is generate_simple_password

    def test_temp_password_alias(self):
        assert temp_password is generate_temp_password

    def test_passphrase_alias(self):
        assert passphrase is generate_passphrase
