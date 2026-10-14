"""Digital signatures on learning plans and documents.

Signatures are only ever added. Re-signing after an edit writes a new
row; the lapsed one stays, so the history shows that a signatory agreed
to an earlier version and then to this one.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.records.signatures import Signature
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
)


def _map(row: Any) -> Signature:
    return Signature(
        signature_id=row["signature_id"],
        entity_type=row["entity_type"],
        entity_id=row["entity_id"],
        signatory_role=row["signatory_role"],
        signed_by=row["signed_by"],
        statement=row["statement"],
        content_hash=row["content_hash"],
        apprentice_id=col(row, "apprentice_id"),
        signer_role=col(row, "signer_role"),
        signed_at=col(row, "signed_at", ""),
    )


def create(
    *,
    entity_type: str,
    entity_id: int,
    signatory_role: str,
    signed_by: str,
    statement: str,
    content_hash: str,
    apprentice_id: int | None = None,
    signer_role: str | None = None,
) -> int:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO signatures
                   (entity_type, entity_id, apprentice_id, signatory_role, signed_by,
                    signer_role, statement, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (entity_type, entity_id, apprentice_id, signatory_role, signed_by,
             signer_role, statement, content_hash),
        )
        return int(cur.lastrowid)


def get(signature_id: int) -> Signature | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM signatures WHERE signature_id = ?", (signature_id,)
        ).fetchone()
    return _map(row) if row else None


def list_signatures(
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    entity_ids: list[int] | None = None,
    apprentice_id: int | None = None,
    signed_by: str | None = None,
) -> list[Signature]:
    """Oldest first, so the last one per signatory is their latest."""
    init_db()
    qb = QueryBuilder()
    qb.add_if(entity_type, "entity_type = ?", entity_type)
    qb.add_if(entity_id is not None, "entity_id = ?", entity_id)
    if entity_ids is not None:
        if not entity_ids:
            return []
        qb.add_in("entity_id", list(entity_ids))
    qb.add_if(apprentice_id, "apprentice_id = ?", apprentice_id)
    qb.add_if(signed_by, "signed_by = ?", signed_by)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM signatures {qb.where} ORDER BY signed_at, signature_id",
            qb.args,
        ).fetchall()
    return [_map(r) for r in rows]
