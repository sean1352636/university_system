"""Tamper-evident academic credential issuance and verification.

Credentials are signed with HMAC-SHA256 over a canonical JSON payload.  The
payload and proof metadata are stored with the credential so verification can
detect modification of either the signed payload or the relational columns.
This is an institution-hosted verification ledger; external-chain anchoring is
an optional integration, not a prerequisite for cryptographic verification.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Callable, Mapping

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.infrastructure.database.remaining_features_schema import (
    BLOCKCHAIN_SCHEMA,
)

PROOF_TYPE = "EducationCredentialHmacSha256V1"
Record = Mapping[str, Any]
NetworkPublisher = Callable[[Mapping[str, Any]], Mapping[str, Any] | str]
RecordResolver = Callable[[str, str], Record]


class CredentialConfigurationError(RuntimeError):
    """Raised when credential signing is not configured safely."""


class CredentialNotFoundError(LookupError):
    """Raised when a requested credential does not exist."""


@dataclass(frozen=True)
class CredentialPayload:
    student_id: str
    credential_type: str
    credential_name: str
    issue_date: str
    issuer: str
    blockchain_address: str | None = None
    ipfs_hash: str | None = None
    claims: dict[str, Any] | None = None


def _signing_key(explicit_key: str | bytes | None = None) -> bytes:
    value = (
        explicit_key
        or os.getenv("CREDENTIAL_SIGNING_KEY")
        or os.getenv("API_SECRET_KEY")
        or os.getenv("JWT_SECRET_KEY")
    )
    if value is None:
        raise CredentialConfigurationError(
            "CREDENTIAL_SIGNING_KEY (or a persistent API/JWT secret) must be "
            "configured to issue or verify credentials"
        )
    key = value.encode("utf-8") if isinstance(value, str) else value
    if len(key) < 32:
        raise CredentialConfigurationError(
            "CREDENTIAL_SIGNING_KEY must contain at least 32 bytes"
        )
    return key


def canonical_payload(payload: CredentialPayload | Mapping[str, Any]) -> bytes:
    values = asdict(payload) if isinstance(payload, CredentialPayload) else dict(payload)
    return json.dumps(
        values,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sign_payload(
    payload: CredentialPayload | Mapping[str, Any],
    *,
    signing_key: str | bytes | None = None,
) -> str:
    return hmac.new(
        _signing_key(signing_key),
        canonical_payload(payload),
        hashlib.sha256,
    ).hexdigest()


def record_digest(record: Record) -> str:
    """Return a stable digest of a registrar-owned academic record."""
    return hashlib.sha256(canonical_payload(record)).hexdigest()


def ensure_credential_schema() -> None:
    with transaction() as conn:
        conn.executescript(BLOCKCHAIN_SCHEMA)


def issue_credential(
    *,
    student_id: str,
    credential_type: str,
    credential_name: str,
    issuer: str,
    issue_date: str | None = None,
    blockchain_address: str | None = None,
    ipfs_hash: str | None = None,
    claims: Mapping[str, Any] | None = None,
    signing_key: str | bytes | None = None,
    authoritative_record: Record | None = None,
    record_type: str | None = None,
    record_id: str | int | None = None,
    verification_networks: Mapping[str, NetworkPublisher] | None = None,
) -> dict[str, Any]:
    required = {
        "student_id": student_id,
        "credential_type": credential_type,
        "credential_name": credential_name,
        "issuer": issuer,
    }
    missing = [name for name, value in required.items() if not str(value).strip()]
    if missing:
        raise ValueError(f"Missing required credential fields: {', '.join(missing)}")

    if authoritative_record is not None and (not record_type or record_id is None):
        raise ValueError("record_type and record_id are required for an authoritative record")
    bound_claims = dict(claims) if claims else {}
    if authoritative_record is not None:
        bound_claims["academic_record"] = {
            "type": str(record_type),
            "id": str(record_id),
            "sha256": record_digest(authoritative_record),
        }
    payload = CredentialPayload(
        student_id=str(student_id).strip(),
        credential_type=str(credential_type).strip().lower(),
        credential_name=str(credential_name).strip(),
        issue_date=issue_date or date.today().isoformat(),
        issuer=str(issuer).strip(),
        blockchain_address=blockchain_address or None,
        ipfs_hash=ipfs_hash or None,
        claims=bound_claims or None,
    )
    proof = sign_payload(payload, signing_key=signing_key)
    metadata = json.dumps(
        {"credential": asdict(payload), "proof": {"type": PROOF_TYPE}},
        sort_keys=True,
    )

    ensure_credential_schema()
    with transaction() as conn:
        cursor = conn.execute(
            """INSERT INTO blockchain_credentials
               (student_id, credential_type, credential_name, issue_date,
                blockchain_hash, blockchain_address, ipfs_hash, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.student_id,
                payload.credential_type,
                payload.credential_name,
                payload.issue_date,
                proof,
                payload.blockchain_address,
                payload.ipfs_hash,
                metadata,
            ),
        )
        credential_id = int(cursor.lastrowid)
        if authoritative_record is not None:
            conn.execute(
                """INSERT INTO credential_academic_records
                   (credential_id, record_type, record_id, record_hash)
                   VALUES (?, ?, ?, ?)""",
                (credential_id, str(record_type), str(record_id), record_digest(authoritative_record)),
            )
    credential = get_credential(credential_id)
    for network_name, publisher in (verification_networks or {}).items():
        publish_to_verification_network(credential_id, network_name, publisher)
    return credential


def issue_academic_record_credential(
    *, record_type: str, record_id: str | int, authoritative_record: Record, **fields: Any
) -> dict[str, Any]:
    """Issue a credential cryptographically bound to an authoritative record."""
    return issue_credential(
        authoritative_record=authoritative_record,
        record_type=record_type,
        record_id=record_id,
        **fields,
    )


def get_credential(credential_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM blockchain_credentials WHERE credential_id = ?",
            (credential_id,),
        ).fetchone()
    if row is None:
        raise CredentialNotFoundError(f"Credential {credential_id} not found")
    return dict(row)


def verify_credential(
    *,
    credential_id: int | None = None,
    credential_hash: str | None = None,
    verifier_name: str | None = None,
    verifier_email: str | None = None,
    verification_method: str = "api",
    signing_key: str | bytes | None = None,
    authoritative_record: Record | None = None,
    network_verifiers: Mapping[str, Callable[[Mapping[str, Any]], bool]] | None = None,
    record_resolver: RecordResolver | None = None,
    initialize_schema: bool = True,
) -> dict[str, Any]:
    if credential_id is None and not credential_hash:
        raise ValueError("credential_id or credential_hash is required")
    if initialize_schema:
        ensure_credential_schema()
    column, value = (
        ("credential_id", credential_id)
        if credential_id is not None
        else ("blockchain_hash", credential_hash)
    )
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT * FROM blockchain_credentials WHERE {column} = ?", (value,)
        ).fetchone()
    if row is None:
        return {"valid": False, "reason": "not_found"}

    record = dict(row)
    try:
        metadata = json.loads(record.get("metadata") or "{}")
        payload_data = metadata["credential"]
        proof_type = metadata["proof"]["type"]
        expected = sign_payload(payload_data, signing_key=signing_key)
        row_matches = all(
            str(record.get(field) or "") == str(payload_data.get(field) or "")
            for field in (
                "student_id",
                "credential_type",
                "credential_name",
                "issue_date",
                "blockchain_address",
                "ipfs_hash",
            )
        )
        integrity = (
            proof_type == PROOF_TYPE
            and row_matches
            and hmac.compare_digest(str(record["blockchain_hash"]), expected)
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        integrity = False

    with get_connection() as conn:
        source = conn.execute(
            "SELECT * FROM credential_academic_records WHERE credential_id = ?",
            (record["credential_id"],),
        ).fetchone()
        attestations = conn.execute(
            "SELECT * FROM credential_network_attestations WHERE credential_id = ?",
            (record["credential_id"],),
        ).fetchall()
    source_result: dict[str, Any] | None = dict(source) if source else None
    if source_result is not None and authoritative_record is None and record_resolver:
        authoritative_record = record_resolver(
            source_result["record_type"], source_result["record_id"]
        )
    if source_result is not None and authoritative_record is not None:
        source_result["current_hash"] = record_digest(authoritative_record)
        source_result["matches"] = hmac.compare_digest(
            source_result["record_hash"], source_result["current_hash"]
        )
        integrity = integrity and source_result["matches"]
    network_results = []
    for item in attestations:
        attestation = dict(item)
        verifier = (network_verifiers or {}).get(attestation["network_name"])
        attestation["verified"] = verifier(attestation) if verifier else None
        if verifier and not attestation["verified"]:
            integrity = False
        network_results.append(attestation)

    revoked = bool(record.get("is_revoked"))
    valid = integrity and not revoked
    if integrity and verifier_name:
        with transaction() as conn:
            conn.execute(
                """INSERT INTO credential_verifications
                   (credential_id, verifier_name, verifier_email, verification_method)
                   VALUES (?, ?, ?, ?)""",
                (
                    record["credential_id"],
                    verifier_name,
                    verifier_email,
                    verification_method,
                ),
            )
    return {
        "valid": valid,
        "integrity": integrity,
        "revoked": revoked,
        "reason": "valid" if valid else "revoked" if revoked and integrity else "tampered",
        "credential": record,
        "authoritative_record": source_result,
        "network_attestations": network_results,
    }


def publish_to_verification_network(
    credential_id: int, network_name: str, publisher: NetworkPublisher
) -> dict[str, Any]:
    """Publish a proof envelope and persist the external network receipt."""
    if not network_name.strip():
        raise ValueError("network_name is required")
    credential = get_credential(credential_id)
    envelope = {
        "credential_id": credential_id,
        "credential_hash": credential["blockchain_hash"],
        "metadata": json.loads(credential.get("metadata") or "{}"),
        "revoked": bool(credential.get("is_revoked")),
    }
    try:
        response = publisher(envelope)
        receipt = dict(response) if isinstance(response, Mapping) else {"external_id": str(response)}
    except Exception as exc:
        receipt = {"status": "failed", "error": exc.__class__.__name__}
    status = str(receipt.get("status") or "published")
    external_id = receipt.get("external_id") or receipt.get("id")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO credential_network_attestations
               (credential_id, network_name, external_id, status, receipt)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(credential_id, network_name) DO UPDATE SET
                 external_id=excluded.external_id, status=excluded.status,
                 receipt=excluded.receipt, published_at=CURRENT_TIMESTAMP""",
            (credential_id, network_name.strip(), external_id, status,
             json.dumps(receipt, sort_keys=True)),
        )
    return receipt


def revoke_credential(
    credential_id: int,
    *,
    reason: str,
    revoked_by: int | None = None,
    signing_key: str | bytes | None = None,
) -> dict[str, Any]:
    if not reason.strip():
        raise ValueError("A revocation reason is required")
    credential = get_credential(credential_id)
    if credential.get("is_revoked"):
        return credential
    revocation_payload = {
        "credential_id": credential_id,
        "credential_hash": credential["blockchain_hash"],
        "reason": reason.strip(),
        "revoked_by": revoked_by,
    }
    revocation_hash = sign_payload(revocation_payload, signing_key=signing_key)
    with transaction() as conn:
        conn.execute(
            "UPDATE blockchain_credentials SET is_revoked = 1 WHERE credential_id = ?",
            (credential_id,),
        )
        conn.execute(
            """INSERT INTO revoked_credentials
               (credential_id, reason, revoked_by, blockchain_revocation_hash)
               VALUES (?, ?, ?, ?)""",
            (credential_id, reason.strip(), revoked_by, revocation_hash),
        )
    return get_credential(credential_id)


__all__ = [
    "CredentialConfigurationError",
    "CredentialNotFoundError",
    "CredentialPayload",
    "canonical_payload",
    "ensure_credential_schema",
    "get_credential",
    "issue_credential",
    "issue_academic_record_credential",
    "publish_to_verification_network",
    "record_digest",
    "revoke_credential",
    "sign_payload",
    "verify_credential",
]
