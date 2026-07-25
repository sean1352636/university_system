"""Utility for encrypting/decrypting sensitive fields in record dicts."""

from education_system.platform.governance.security.data_classification import SENSITIVE_FIELDS
from education_system.platform.governance.security.encryption import FieldEncryptor, is_encrypted


def encrypt_record(record: dict, encryptor: FieldEncryptor) -> dict:
    """Encrypt sensitive fields in a record dict. Returns new dict."""
    if not encryptor.is_available:
        return record
    result = dict(record)
    for key, value in result.items():
        if key in SENSITIVE_FIELDS and value is not None and not is_encrypted(str(value)):
            result[key] = encryptor.encrypt_field(value)
    return result


def decrypt_record(record: dict, encryptor: FieldEncryptor) -> dict:
    """Decrypt sensitive fields in a record dict. Returns new dict."""
    if not encryptor.is_available:
        return record
    result = dict(record)
    for key, value in result.items():
        if key in SENSITIVE_FIELDS and value is not None:
            result[key] = encryptor.decrypt_field(value)
    return result


def encrypt_records(records: list, encryptor: FieldEncryptor) -> list:
    return [encrypt_record(r, encryptor) for r in records]


def decrypt_records(records: list, encryptor: FieldEncryptor) -> list:
    return [decrypt_record(r, encryptor) for r in records]


def has_encrypted_fields(record: dict) -> bool:
    return any(is_encrypted(str(v)) for v in record.values() if v is not None)


def get_encrypted_field_names(record: dict) -> list:
    return [k for k, v in record.items() if v is not None and is_encrypted(str(v))]
