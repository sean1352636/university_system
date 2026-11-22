"""Shared plumbing for admissions casework: who may act, the audit trail,
and files attached to an application.

The conditions/documents checklist, the postgraduate requirements and the
sponsor record all need the same three things, so they live here once:

* :func:`can_manage` / :func:`require_manager` - the admissions-decision
  permission (``approve_applications``) or an admin role, the same test the
  handover board uses for contextual flags.
* :func:`audit` - one row in ``admission_casework_audit`` (shown on the
  application's panel) mirrored to the platform audit log.
* :func:`store_document` - a file copied under the university upload
  directory and recorded in the unified ``documents`` table against the
  application, the same table ``ApplicationManager.upload_document`` writes.
  :func:`document_path` resolves it again through ``stored_files.resolve``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.boundary_errors import (
    AdmissionsBoundaryError,
)

logger = logging.getLogger(__name__)

#: The permission that marks a member of admissions staff.
MANAGE_PERMISSION = "approve_applications"
_PRIVILEGED_ROLES = frozenset({"admin", "superadmin"})

#: Files an applicant, referee or member of staff may attach.
ALLOWED_EXTENSIONS = frozenset({
    ".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".jpg", ".jpeg", ".png",
})
MAX_FILE_BYTES = 20 * 1024 * 1024

_AUDIT_SYSTEM = "university"

_AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS admission_casework_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    actor TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id)
        REFERENCES admission_applications(application_id) ON DELETE CASCADE
)
"""


# ── Who is acting ───────────────────────────────────────────────────

def _user(viewer: Any) -> dict:
    if isinstance(viewer, dict):
        return viewer
    user = getattr(viewer, "current_user", None)
    return user if isinstance(user, dict) else {}


def actor_name(viewer: Any) -> str:
    """The username behind ``viewer`` (an auth object or user dict)."""
    if isinstance(viewer, str):
        return viewer
    user = _user(viewer)
    return str(user.get("username") or user.get("name") or "")


def role_of(viewer: Any) -> str:
    return str(_user(viewer).get("role") or "").lower()


def is_admin(viewer: Any) -> bool:
    return role_of(viewer) in _PRIVILEGED_ROLES


def can_manage(viewer: Any) -> bool:
    """Admissions staff: the decision permission, or an admin role."""
    if viewer is None or isinstance(viewer, str):
        return False
    if is_admin(viewer):
        return True
    if MANAGE_PERMISSION in (_user(viewer).get("permissions") or []):
        return True
    checker = getattr(viewer, "has_permission", None)
    if callable(checker):
        try:
            return bool(checker(MANAGE_PERMISSION))
        except Exception:
            logger.debug("has_permission failed closed", exc_info=True)
    return False


def require_manager(viewer: Any) -> str:
    """The acting username, or a refusal for anyone not admissions staff."""
    if not can_manage(viewer):
        raise AdmissionsBoundaryError(
            "Only admissions staff (approve_applications) can do this")
    name = actor_name(viewer)
    if not name:
        raise AdmissionsBoundaryError("The acting user could not be identified")
    return name


# ── Audit ───────────────────────────────────────────────────────────

def ensure_audit(conn) -> None:
    conn.execute(_AUDIT_DDL)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_admission_casework_audit_app "
        "ON admission_casework_audit(application_id, audit_id)")


def audit(conn, application_id: int, action: str, actor: str, *,
          target_type: str = "", target_id: Any = "",
          detail: dict | str | None = None) -> None:
    """Record one casework action on ``conn`` (inside the caller's
    transaction) and mirror it to the platform audit log."""
    ensure_audit(conn)
    text = json.dumps(detail, default=str) if isinstance(detail, dict) \
        else str(detail or "")
    conn.execute(
        """INSERT INTO admission_casework_audit
             (application_id, action, target_type, target_id, actor, detail)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (int(application_id), action, target_type, str(target_id or ""),
         actor, text),
    )
    _platform_audit(application_id, action, actor, target_type, target_id,
                    detail)


def _platform_audit(application_id, action, actor, target_type, target_id,
                    detail) -> None:
    """Mirror to the tamper-evident platform log. A failure there is logged,
    never allowed to undo the casework row already written."""
    try:
        from education_system.platform.governance.audit import (
            AuditAction,
            AuditLogger,
        )
        AuditLogger(_AUDIT_SYSTEM).log(
            AuditAction.UPDATE,
            username=actor,
            target_type=f"admission_{target_type or 'application'}",
            target_id=str(target_id or application_id),
            details={"application_id": application_id, "action": action,
                     "detail": detail},
        )
    except Exception:
        logger.exception("Platform audit mirror failed for %s on application %s",
                         action, application_id)


def audit_trail(application_id: int) -> list[dict]:
    with get_connection() as conn:
        ensure_audit(conn)
        return [dict(r) for r in conn.execute(
            "SELECT * FROM admission_casework_audit WHERE application_id = ? "
            "ORDER BY audit_id DESC", (int(application_id),)).fetchall()]


# ── Application lookups ────────────────────────────────────────────

def application_row(conn, application_id: int):
    row = conn.execute(
        """SELECT a.*, p.first_name, p.last_name, p.email
             FROM admission_applications a
             LEFT JOIN admission_prospects p ON p.prospect_id = a.prospect_id
            WHERE a.application_id = ?""",
        (int(application_id),),
    ).fetchone()
    if row is None:
        raise AdmissionsBoundaryError(f"Application ID {application_id} does not exist.")
    return row


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── Files ───────────────────────────────────────────────────────────

def _upload_root() -> Path:
    from education_system import paths
    return Path(paths.UNIVERSITY_UPLOAD_DIR) / "admissions"


def _safe_name(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name or "file").name).strip("._")
    return stem[:120] or "file"


def _checked_bytes(source_path: str | None, data: bytes | None,
                   filename: str) -> tuple[bytes, str]:
    if source_path:
        path = Path(source_path).expanduser()
        if not path.is_file():
            raise AdmissionsBoundaryError(f"File not found: {source_path}")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise AdmissionsBoundaryError("Files larger than 20 MB cannot be attached")
        data = path.read_bytes()
        filename = filename or path.name
    if data is None:
        raise AdmissionsBoundaryError("No file was supplied")
    if len(data) > MAX_FILE_BYTES:
        raise AdmissionsBoundaryError("Files larger than 20 MB cannot be attached")
    if not data:
        raise AdmissionsBoundaryError("The file is empty")
    if Path(filename or "").suffix.lower() not in ALLOWED_EXTENSIONS:
        raise AdmissionsBoundaryError(
            "Only " + ", ".join(sorted(ALLOWED_EXTENSIONS)) + " files can be attached")
    return data, filename


def store_document(conn, application_id: int, *, document_type: str,
                   uploaded_by: str, source_path: str | None = None,
                   data: bytes | None = None, filename: str = "",
                   document_name: str = "", verified: bool = False) -> int:
    """Copy a file into the admissions upload area and record it.

    Runs on the caller's connection so the document row commits (or rolls
    back) with whatever it is evidence for. The file is written first; a
    rolled-back row leaves an orphan file, never a row without a file.
    """
    data, filename = _checked_bytes(source_path, data, filename)
    folder = _upload_root() / str(int(application_id))
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{uuid.uuid4().hex[:12]}_{_safe_name(filename)}"
    target.write_bytes(data)
    stamp = now()
    cur = conn.execute(
        """INSERT INTO documents
             (source_type, owner_type, reference_type, reference_id,
              document_type, document_name, file_path, file_size, file_hash,
              original_filename, upload_date, verification_status,
              verification_date, verified_by, uploaded_by, created_at)
           VALUES ('application', 'applicant', 'application', ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(int(application_id)), document_type,
            document_name or Path(filename).name, str(target), len(data),
            hashlib.sha256(data).hexdigest(), Path(filename).name, stamp,
            "verified" if verified else "pending",
            stamp if verified else None, uploaded_by if verified else None,
            uploaded_by, stamp,
        ),
    )
    return int(cur.lastrowid)


def application_documents(application_id: int) -> list[dict]:
    """Every file on the application, newest first."""
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT document_id, document_type, document_name,
                      original_filename, file_path, file_size, upload_date,
                      verification_status, verified_by, uploaded_by
                 FROM documents
                WHERE reference_type = 'application' AND reference_id = ?
                ORDER BY document_id DESC""",
            (str(int(application_id)),),
        ).fetchall()]


def document_path(document_id: int) -> Path | None:
    """The document's file where it lives now, or ``None`` if it is gone."""
    from education_system.systems.university.infrastructure.stored_files import resolve
    with get_connection() as conn:
        row = conn.execute("SELECT file_path FROM documents WHERE document_id = ?",
                           (int(document_id),)).fetchone()
    if row is None or not row["file_path"]:
        return None
    path = resolve(row["file_path"])
    return path if path.exists() else None


__all__ = [
    "ALLOWED_EXTENSIONS", "MANAGE_PERMISSION", "actor_name", "application_documents",
    "application_row", "audit", "audit_trail", "can_manage", "document_path",
    "ensure_audit", "is_admin", "require_manager", "role_of", "store_document",
]
