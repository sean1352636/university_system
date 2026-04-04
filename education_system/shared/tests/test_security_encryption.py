"""Tests for shared.security.encryption — key helpers and FieldEncryptor."""

import os
import pytest

from education_system.shared.security.encryption import (
    generate_key,
    load_key,
    save_key,
    is_encrypted,
    FieldEncryptor,
)


class TestKeyHelpers:
    """Test generate_key, load_key, save_key."""

    def test_generate_key_returns_string(self):
        key = generate_key()
        assert isinstance(key, str)
        assert len(key) > 0

    def test_load_key_from_env(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", "test-key-value")
        assert load_key() == "test-key-value"

    def test_load_key_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        assert load_key() is None

    def test_save_key_writes_file(self, tmp_path):
        filepath = str(tmp_path / "key.txt")
        key = save_key(filepath)
        assert os.path.exists(filepath)
        with open(filepath) as f:
            assert f.read() == key


class TestIsEncrypted:
    """Test the is_encrypted detection function."""

    def test_encrypted_string_detected(self):
        assert is_encrypted("ENC:abc123") is True

    def test_plain_string_not_detected(self):
        assert is_encrypted("hello world") is False

    def test_non_string_not_detected(self):
        assert is_encrypted(42) is False
        assert is_encrypted(None) is False


class TestFieldEncryptor:
    """Test FieldEncryptor roundtrip encrypt/decrypt."""

    @pytest.fixture
    def encryptor(self):
        key = generate_key()
        return FieldEncryptor(key)

    def test_is_available(self, encryptor):
        assert encryptor.is_available is True

    def test_encrypt_produces_prefixed_string(self, encryptor):
        ct = encryptor.encrypt("secret")
        assert ct.startswith("ENC:")

    def test_roundtrip(self, encryptor):
        original = "sensitive data 123"
        encrypted = encryptor.encrypt(original)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == original

    def test_decrypt_plaintext_passthrough(self, encryptor):
        assert encryptor.decrypt("not encrypted") == "not encrypted"

    def test_encrypt_field_none_passthrough(self, encryptor):
        assert encryptor.encrypt_field(None) is None

    def test_decrypt_field_none_passthrough(self, encryptor):
        assert encryptor.decrypt_field(None) is None

    def test_encrypt_field_roundtrip(self, encryptor):
        encrypted = encryptor.encrypt_field("hello")
        assert is_encrypted(encrypted)
        assert encryptor.decrypt_field(encrypted) == "hello"

    def test_unavailable_encryptor_passthrough(self):
        enc = FieldEncryptor(key=None)
        assert enc.is_available is False
        assert enc.encrypt("plain") == "plain"
        assert enc.decrypt("plain") == "plain"
