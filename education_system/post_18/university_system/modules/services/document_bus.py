"""Document Manager — canonical file-store service.

Every other GUI in the system generates documents — HR contracts,
Finance invoices, H&S risk assessments, First Aid certificates,
incident photos, transcripts, etc. Without a shared service each
domain rolls its own folder, its own ACL, its own audit trail.

This module is the single funnel:

* ``link_document(domain, ref_id, file_path, ...)`` — record a file
  against a domain object (e.g. ``("incident", 42)`` or
  ``("contract", "STAFF-99")``). Returns the new document_id.
* ``get_documents_for(domain, ref_id)`` — list every document linked
  to that object.
* ``can_access(user_id, document_id)`` — permission lookup that
  delegates to HR roles so DM doesn't duplicate the ACL model (#11).
* Publishes ``EVENT_DOCUMENT_CHANGED`` on every write so subscribers
  (chatbot index, evidence panels) refresh automatically.

Soft-fails everywhere — a missing optional column or HR outage must
never block a legitimate write or read.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from typing import Any

from education_system.post_18.university_system.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _hash_file(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return None


def _publish(event: str, **payload: Any) -> None:
    try:
        from education_system.post_18.university_system.modules.domain.academics.gui._event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("dm bus publish failed: %s", exc)


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def link_document(
    domain: str,
    ref_id: str | int,
    *,
    file_path: str,
    document_name: str | None = None,
    document_type: str | None = None,
    owner_id: int | str | None = None,
    uploaded_by: str | None = None,
    expiry_date: str | None = None,
    notes: str | None = None,
) -> int | None:
    """Record a document against ``(domain, ref_id)`` in the canonical
    ``documents`` table. Returns the new document_id.

    ``domain`` is a free-text key like ``'incident'``, ``'contract'``,
    ``'invoice'``, ``'risk_assessment'``. ``ref_id`` is the foreign id
    inside that domain. Reading the same pair via
    :func:`get_documents_for` is the reverse operation.

    No file copy happens — DM stores the path. Callers are expected
    to have placed the file somewhere durable already.
    """
    if not file_path:
        return None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_hash = _hash_file(file_path)
    file_size = None
    try:
        file_size = os.path.getsize(file_path)
    except Exception:
        pass
    name = document_name or os.path.basename(file_path)
    doc_id: int | None = None

    try:
        with get_connection() as conn:
            cur = conn.execute(
                """INSERT INTO documents
                   (source_type, owner_id, reference_type, reference_id,
                    document_type, document_name, file_path, file_hash,
                    file_size, original_filename, upload_date,
                    expiry_date, notes, uploaded_by,
                    verification_status, version_number, workflow_status,
                    is_current_version, status,
                    created_at, updated_at)
                   VALUES ('linked', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           'Pending', 1, 'submitted', 1, 'active', ?, ?)""",
                (owner_id, domain, str(ref_id),
                 document_type or domain, name, file_path,
                 file_hash, file_size, os.path.basename(file_path), now,
                 expiry_date, notes, uploaded_by,
                 now, now),
            )
            doc_id = cur.lastrowid
            conn.commit()
    except Exception as exc:
        logger.warning("link_document(%s, %s) failed: %s", domain, ref_id, exc)
        return None

    _publish(
        "dm.document.changed",
        document_id=doc_id, domain=domain, ref_id=str(ref_id),
        action="linked", uploaded_by=uploaded_by, name=name,
    )
    return doc_id


def publish_document_changed(*, document_id: int | None = None,
                             action: str = "updated",
                             domain: str | None = None,
                             ref_id: str | None = None,
                             **extra: Any) -> None:
    """Manual hook for existing DM writers (upload.py, versions.py, etc.)
    that already do their own INSERT. Lets them broadcast on the bus
    without rewriting their commit path.
    """
    _publish(
        "dm.document.changed",
        document_id=document_id, action=action,
        domain=domain, ref_id=ref_id, **extra,
    )


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------

def get_documents_for(domain: str, ref_id: str | int) -> list[dict[str, Any]]:
    """Return every document linked to ``(domain, ref_id)``."""
    if not domain or ref_id is None:
        return []
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT document_id, document_name, document_type, "
                "       file_path, upload_date, expiry_date, "
                "       uploaded_by, verification_status, file_size "
                "FROM documents "
                "WHERE reference_type = ? AND reference_id = ? "
                "  AND COALESCE(status, 'active') = 'active' "
                "ORDER BY upload_date DESC",
                (domain, str(ref_id)),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("get_documents_for(%s, %s) failed: %s",
                       domain, ref_id, exc)
        return []


def has_document(domain: str, ref_id: str | int,
                 *, document_type: str | None = None) -> bool:
    """Cheap existence check for the HR onboarding gate (#9) and similar."""
    docs = get_documents_for(domain, ref_id)
    if document_type is None:
        return bool(docs)
    return any((d.get("document_type") or "").lower() ==
               document_type.lower() for d in docs)


# ---------------------------------------------------------------------------
# Access control via HR roles (#11)
# ---------------------------------------------------------------------------

# Roles that get implicit read access to every document, regardless of
# the document's owner. Tweak in one place; HR's role tags propagate.
_GLOBAL_READ_ROLES = {"admin", "hr", "registrar", "compliance"}


def can_access(user_id: int | str, document_id: int) -> bool:
    """Authoritative read-access check.

    Algorithm:
      1. The document's owner can always read it.
      2. Users whose ``users.role`` is in ``_GLOBAL_READ_ROLES`` can read
         everything (so HR / admin / registrar dashboards work).
      3. Otherwise, deny.

    Soft-fails open ONLY for the owner check on a missing document —
    every unknown identity is denied.
    """
    if user_id is None or document_id is None:
        return False
    try:
        with get_connection() as conn:
            doc = conn.execute(
                "SELECT owner_id, uploaded_by FROM documents "
                "WHERE document_id = ?",
                (int(document_id),),
            ).fetchone()
            if not doc:
                return False
            if str(doc["owner_id"] or "") == str(user_id):
                return True
            if str(doc["uploaded_by"] or "") == str(user_id):
                return True
            # Role lookup. Try by id first, then by username.
            row = conn.execute(
                "SELECT role FROM users WHERE id = ? OR username = ? LIMIT 1",
                (user_id, user_id),
            ).fetchone()
            role = (row[0] or "").strip().lower() if row else ""
            return role in _GLOBAL_READ_ROLES
    except Exception as exc:
        logger.warning("can_access(%s, %s) failed: %s",
                       user_id, document_id, exc)
        return False


__all__ = [
    "link_document", "publish_document_changed",
    "get_documents_for", "has_document",
    "can_access",
]
