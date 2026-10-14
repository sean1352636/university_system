"""Uploaded record documents: metadata, versions and approval.

The bytes live in ``infrastructure.storage.document_store``; this module
holds only the rows. Scoping filters mirror ``access.apprentice_filters``
so a service can splat an actor's scope straight in:

* ``tutor_id`` — documents of apprentices on that tutor's caseload;
* ``employer_id`` — the employer's own documents *and* those of
  apprentices they employ;
* ``apprentice_id`` — one apprentice's documents.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.records.documents import Document
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_bool,
    to_int,
)

_FIELDS = (
    "apprentice_id", "employer_id", "category", "title", "original_filename",
    "stored_name", "size_bytes", "sha256", "version", "series_id", "supersedes",
    "checklist_key", "uploaded_by", "uploaded_role", "expiry_date",
    "approval_status", "approved_by", "approved_at", "rejection_reason",
)

# The fields that may change after upload. Everything else describes the
# file as it arrived; a different file is a new version, not an edit.
_MUTABLE_FIELDS = (
    "title", "expiry_date", "checklist_key",
    "approval_status", "approved_by", "approved_at", "rejection_reason",
)

_SELECT = """
    SELECT d.*,
           (a.given_name || ' ' || a.family_name) AS apprentice_name,
           COALESCE(e.name, ae.name) AS employer_name,
           EXISTS (SELECT 1 FROM documents n WHERE n.supersedes = d.document_id)
               AS superseded
      FROM documents d
      LEFT JOIN apprentices a ON a.apprentice_id = d.apprentice_id
      LEFT JOIN employers e   ON e.employer_id = d.employer_id
      LEFT JOIN employers ae  ON ae.employer_id = a.employer_id
"""


def _map(row: Any) -> Document:
    return Document(
        document_id=row["document_id"],
        category=row["category"],
        title=row["title"],
        original_filename=row["original_filename"],
        stored_name=row["stored_name"],
        size_bytes=to_int(col(row, "size_bytes")),
        sha256=row["sha256"],
        uploaded_by=row["uploaded_by"],
        uploaded_role=row["uploaded_role"],
        apprentice_id=col(row, "apprentice_id"),
        employer_id=col(row, "employer_id"),
        version=to_int(col(row, "version"), 1),
        series_id=col(row, "series_id"),
        supersedes=col(row, "supersedes"),
        checklist_key=col(row, "checklist_key"),
        uploaded_at=col(row, "uploaded_at", ""),
        expiry_date=col(row, "expiry_date"),
        approval_status=col(row, "approval_status", "Pending"),
        approved_by=col(row, "approved_by"),
        approved_at=col(row, "approved_at"),
        rejection_reason=col(row, "rejection_reason"),
        apprentice_name=col(row, "apprentice_name"),
        employer_name=col(row, "employer_name"),
        is_superseded=to_bool(col(row, "superseded")),
    )


def get(document_id: int) -> Document | None:
    init_db()
    with connect() as conn:
        row = conn.execute(f"{_SELECT} WHERE d.document_id = ?", (document_id,)).fetchone()
    return _map(row) if row else None


def list_documents(
    *,
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    tutor_id: int | None = None,
    apprentice_ids: list[int] | None = None,
    category: str | None = None,
    categories: list[str] | tuple[str, ...] | None = None,
    approval_status: str | None = None,
    checklist_key: str | None = None,
    series_id: int | None = None,
    apprentice_only: bool = False,
    current_only: bool = True,
    expiring_before: str | None = None,
    search: str | None = None,
    limit: int | None = None,
) -> list[Document]:
    """Documents matching every filter given; the latest versions by default.

    ``expiring_before`` (an ISO date) keeps documents with an expiry date
    on or before it — pass today plus the warning window to get both the
    expired and the expiring.
    """
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "d.apprentice_id = ?", apprentice_id)
    qb.add_if(employer_id, "(d.employer_id = ? OR a.employer_id = ?)", employer_id, employer_id)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    if apprentice_ids is not None:
        # An empty list means "none of them", not "no filter".
        if not apprentice_ids:
            return []
        qb.add_in("d.apprentice_id", list(apprentice_ids))
    qb.add_if(category, "d.category = ?", category)
    qb.add_in("d.category", list(categories) if categories else None)
    qb.add_if(approval_status, "d.approval_status = ?", approval_status)
    qb.add_if(checklist_key, "d.checklist_key = ?", checklist_key)
    qb.add_if(series_id, "d.series_id = ?", series_id)
    qb.add_if(apprentice_only, "d.apprentice_id IS NOT NULL")
    qb.add_if(
        current_only,
        "NOT EXISTS (SELECT 1 FROM documents n WHERE n.supersedes = d.document_id)",
    )
    qb.add_if(
        expiring_before, "d.expiry_date IS NOT NULL AND d.expiry_date <= ?", expiring_before
    )
    if search and search.strip():
        term = f"%{search.strip()}%"
        qb.add("(d.title LIKE ? OR d.original_filename LIKE ?)", term, term)
    sql = f"{_SELECT} {qb.where} ORDER BY d.category, d.title, d.version DESC, d.document_id"
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_map(r) for r in rows]


def list_versions(series_id: int) -> list[Document]:
    """Every version of one document, newest first."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            f"{_SELECT} WHERE d.series_id = ? ORDER BY d.version DESC", (series_id,)
        ).fetchall()
    return [_map(r) for r in rows]


def create(payload: dict[str, Any]) -> int:
    """Insert one version. Version 1 becomes the head of its own series."""
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO documents ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        document_id = int(cur.lastrowid)
        if payload.get("series_id") is None:
            conn.execute(
                "UPDATE documents SET series_id = ? WHERE document_id = ?",
                (document_id, document_id),
            )
        return document_id


def update(document_id: int, payload: dict[str, Any]) -> None:
    """Change the supplied mutable fields only; anything else is ignored."""
    init_db()
    columns = [f for f in _MUTABLE_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE documents SET {assignments} WHERE document_id = ?",
            [*(payload[c] for c in columns), document_id],
        )
