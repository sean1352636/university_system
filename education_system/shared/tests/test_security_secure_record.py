"""Tests for shared.security.secure_record — record-level encrypt/decrypt helpers."""

import pytest

from education_system.shared.security.encryption import generate_key, FieldEncryptor, is_encrypted
from education_system.shared.security.secure_record import (
    encrypt_record,
    decrypt_record,
    encrypt_records,
    decrypt_records,
    has_encrypted_fields,
    get_encrypted_field_names,
)


@pytest.fixture
def encryptor():
    """FieldEncryptor with a fresh key."""
    return FieldEncryptor(generate_key())


SAMPLE_RECORD = {
    "student_id": "STU001",
    "first_name": "Alice",
    "email_address": "alice@example.com",
    "medical_notes": "Asthma",
    "date_of_birth": "2010-05-15",
    "grade": "A",
}


class TestEncryptDecryptRecord:
    """Test roundtrip on individual records."""

    def test_encrypt_marks_sensitive_fields(self, encryptor):
        result = encrypt_record(SAMPLE_RECORD, encryptor)
        assert is_encrypted(result["email_address"])
        assert is_encrypted(result["medical_notes"])
        assert is_encrypted(result["date_of_birth"])

    def test_encrypt_leaves_non_sensitive_fields(self, encryptor):
        result = encrypt_record(SAMPLE_RECORD, encryptor)
        assert result["student_id"] == "STU001"
        assert result["first_name"] == "Alice"
        assert result["grade"] == "A"

    def test_roundtrip(self, encryptor):
        encrypted = encrypt_record(SAMPLE_RECORD, encryptor)
        decrypted = decrypt_record(encrypted, encryptor)
        assert decrypted["email_address"] == "alice@example.com"
        assert decrypted["medical_notes"] == "Asthma"
        assert decrypted["date_of_birth"] == "2010-05-15"

    def test_none_values_preserved(self, encryptor):
        rec = {"email_address": None, "first_name": "Bob"}
        result = encrypt_record(rec, encryptor)
        assert result["email_address"] is None

    def test_unavailable_encryptor_passthrough(self):
        enc = FieldEncryptor(key=None)
        result = encrypt_record(SAMPLE_RECORD, enc)
        assert result["email_address"] == "alice@example.com"


class TestBatchRecords:
    """Test encrypt_records / decrypt_records on lists."""

    def test_encrypt_records(self, encryptor):
        records = [SAMPLE_RECORD, {**SAMPLE_RECORD, "student_id": "STU002"}]
        encrypted = encrypt_records(records, encryptor)
        assert len(encrypted) == 2
        assert all(is_encrypted(r["email_address"]) for r in encrypted)

    def test_decrypt_records_roundtrip(self, encryptor):
        records = [SAMPLE_RECORD]
        encrypted = encrypt_records(records, encryptor)
        decrypted = decrypt_records(encrypted, encryptor)
        assert decrypted[0]["medical_notes"] == "Asthma"


class TestHasEncryptedFields:
    """Test has_encrypted_fields and get_encrypted_field_names."""

    def test_plain_record_has_no_encrypted(self):
        assert has_encrypted_fields(SAMPLE_RECORD) is False

    def test_encrypted_record_detected(self, encryptor):
        encrypted = encrypt_record(SAMPLE_RECORD, encryptor)
        assert has_encrypted_fields(encrypted) is True

    def test_get_encrypted_field_names(self, encryptor):
        encrypted = encrypt_record(SAMPLE_RECORD, encryptor)
        names = get_encrypted_field_names(encrypted)
        assert "email_address" in names
        assert "medical_notes" in names
        assert "first_name" not in names

    def test_get_encrypted_field_names_plain(self):
        assert get_encrypted_field_names(SAMPLE_RECORD) == []
