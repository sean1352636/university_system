from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

from education_system.systems.university.domain.finance.blockchain.services import (
    CredentialConfigurationError,
    issue_credential,
    publish_to_verification_network,
    revoke_credential,
    verify_credential,
)
from education_system.systems.university.domain.finance.blockchain.services import (
    credential_service as service,
)


@pytest.fixture()
def credential_db(tmp_path, monkeypatch):
    path = tmp_path / "credentials.db"

    def connect():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def transact():
        conn = connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    monkeypatch.setattr(service, "get_connection", connect)
    monkeypatch.setattr(service, "transaction", transact)
    return path


def test_issue_verify_tamper_and_revoke_lifecycle(credential_db):
    key = "test-signing-key-with-at-least-thirty-two-bytes"
    credential = issue_credential(
        student_id="S100",
        credential_type="Degree",
        credential_name="BSc Computer Science",
        issuer="Example University",
        issue_date="2026-07-01",
        signing_key=key,
    )

    verified = verify_credential(
        credential_hash=credential["blockchain_hash"], signing_key=key
    )
    assert verified["valid"] is True
    assert verified["integrity"] is True

    conn = sqlite3.connect(credential_db)
    conn.execute(
        "UPDATE blockchain_credentials SET credential_name = ? WHERE credential_id = ?",
        ("Altered Degree", credential["credential_id"]),
    )
    conn.commit()
    conn.close()
    tampered = verify_credential(
        credential_id=credential["credential_id"], signing_key=key
    )
    assert tampered["valid"] is False
    assert tampered["reason"] == "tampered"

    # Restore the signed column before exercising revocation.
    conn = sqlite3.connect(credential_db)
    conn.execute(
        "UPDATE blockchain_credentials SET credential_name = ? WHERE credential_id = ?",
        ("BSc Computer Science", credential["credential_id"]),
    )
    conn.commit()
    conn.close()
    revoke_credential(
        credential["credential_id"],
        reason="Issued in error",
        revoked_by=7,
        signing_key=key,
    )
    revoked = verify_credential(
        credential_id=credential["credential_id"], signing_key=key
    )
    assert revoked["valid"] is False
    assert revoked["integrity"] is True
    assert revoked["reason"] == "revoked"


def test_signing_key_is_mandatory(credential_db, monkeypatch):
    monkeypatch.delenv("CREDENTIAL_SIGNING_KEY", raising=False)
    with pytest.raises(CredentialConfigurationError):
        issue_credential(
            student_id="S100",
            credential_type="degree",
            credential_name="BSc",
            issuer="Example University",
        )


def test_authoritative_record_and_external_network_are_verified(credential_db):
    key = "test-signing-key-with-at-least-thirty-two-bytes"
    source = {"award_id": 41, "classification": "First", "released": True}
    published = []

    def publisher(envelope):
        published.append(envelope)
        return {"id": "external-123", "status": "confirmed"}

    credential = issue_credential(
        student_id="S100",
        credential_type="degree",
        credential_name="BSc Computer Science",
        issuer="Example University",
        signing_key=key,
        authoritative_record=source,
        record_type="ratified_award",
        record_id=41,
        verification_networks={"hesa": publisher},
    )
    assert published[0]["credential_hash"] == credential["blockchain_hash"]

    valid = verify_credential(
        credential_id=credential["credential_id"],
        signing_key=key,
        authoritative_record=source,
        network_verifiers={"hesa": lambda receipt: receipt["external_id"] == "external-123"},
    )
    assert valid["valid"] is True
    assert valid["authoritative_record"]["matches"] is True
    assert valid["network_attestations"][0]["verified"] is True

    changed = dict(source, classification="Second")
    invalid = verify_credential(
        credential_id=credential["credential_id"],
        signing_key=key,
        authoritative_record=changed,
    )
    assert invalid["valid"] is False
    assert invalid["reason"] == "tampered"


def test_network_receipt_can_be_added_after_issuance(credential_db):
    key = "test-signing-key-with-at-least-thirty-two-bytes"
    credential = issue_credential(
        student_id="S100", credential_type="transcript",
        credential_name="Official transcript", issuer="Example University",
        signing_key=key,
    )
    receipt = publish_to_verification_network(
        credential["credential_id"], "europass", lambda _: "urn:credential:1"
    )
    assert receipt["external_id"] == "urn:credential:1"


def test_network_failure_is_persisted_without_losing_credential(credential_db):
    key = "test-signing-key-with-at-least-thirty-two-bytes"

    def unavailable(_):
        raise TimeoutError("network unavailable")

    credential = issue_credential(
        student_id="S100", credential_type="degree", credential_name="BSc",
        issuer="Example University", signing_key=key,
        verification_networks={"external": unavailable},
    )
    result = verify_credential(credential_id=credential["credential_id"], signing_key=key)
    assert result["valid"] is True
    assert result["network_attestations"][0]["status"] == "failed"


def test_authoritative_record_can_be_resolved_during_verification(credential_db):
    key = "test-signing-key-with-at-least-thirty-two-bytes"
    source = {"award_id": 9, "status": "ratified"}
    credential = issue_credential(
        student_id="S100", credential_type="degree", credential_name="BSc",
        issuer="Example University", signing_key=key,
        authoritative_record=source, record_type="award", record_id=9,
    )
    result = verify_credential(
        credential_id=credential["credential_id"], signing_key=key,
        record_resolver=lambda kind, identifier: source,
    )
    assert result["valid"] is True
    assert result["authoritative_record"]["matches"] is True
