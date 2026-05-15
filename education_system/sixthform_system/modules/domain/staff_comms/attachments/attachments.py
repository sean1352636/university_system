"""Attachments data layer for Sixth Form System.

Per-record file references attached to any linked entity
(student, staff, behaviour incident, notice, etc.). The actual
file lives on disk or external storage; this module tracks the
metadata, an opaque `file_ref`, and ownership / access flags.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system.sixthform_system.core import paths as _paths

logger = logging.getLogger(__name__)

ENTITY_TYPES: tuple[str, ...] = (
    "Student",
    "Staff",
    "Parent",
    "Notice",
    "Announcement",
    "Behaviour",
    "Safeguarding",
    "Health",
    "First Aid",
    "Visit",
    "Trip",
    "Course",
    "Subject",
    "Assignment",
    "Homework",
    "Exam Result",
    "UCAS",
    "Reference",
    "Personal Statement",
    "Bursary",
    "Finance",
    "HR",
    "Complaint",
    "Document",
    "Other",
)
DEFAULT_ENTITY_TYPE = "Student"

CATEGORIES: tuple[str, ...] = (
    "Evidence",
    "Photo",
    "Form",
    "Letter",
    "Report",
    "Certificate",
    "Identification",
    "Medical",
    "Consent",
    "Receipt",
    "Invoice",
    "Contract",
    "Reference",
    "Scan",
    "Audio",
    "Video",
    "Other",
)
DEFAULT_CATEGORY = "Other"

VISIBILITY: tuple[str, ...] = (
    "Internal",
    "Restricted",
    "Confidential",
    "Public",
)
DEFAULT_VISIBILITY = "Internal"

STATUSES: tuple[str, ...] = (
    "Active",
    "Quarantined",
    "Archived",
    "Deleted",
)
DEFAULT_STATUS = "Active"


class ValidationError(Exception):
    pass


@dataclass
class Attachment:
    attachment_id: int
    entity_type: str
    entity_id: str
    title: str
    description: str | None
    category: str
    visibility: str
    file_ref: str
    file_name: str | None
    file_format: str | None
    file_size_kb: int | None
    mime_type: str | None
    checksum: str | None
    uploaded_by: str | None
    uploaded_on: str
    tagged_keywords: str | None
    status: str
    contains_pii: bool
    consent_recorded: bool
    retention_until: str | None
    download_count: int
    last_accessed_on: str | None
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_active(self) -> bool:
        return self.status == "Active"

    @property
    def is_expired_retention(self) -> bool:
        if not self.retention_until:
            return False
        return self.retention_until < _dt.date.today().isoformat()

    @property
    def keyword_list(self) -> list[str]:
        if not self.tagged_keywords:
            return []
        return [k.strip() for k in self.tagged_keywords.split(",")
                  if k.strip()]


@dataclass
class AttachmentsSummary:
    total: int = 0
    active: int = 0
    quarantined: int = 0
    archived: int = 0
    deleted: int = 0
    confidential: int = 0
    contains_pii: int = 0
    retention_expired: int = 0
    total_size_kb: int = 0
    total_downloads: int = 0
    distinct_entities: int = 0
    by_entity_type: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    by_visibility: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_format: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.ATTACHMENTS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS attachments (
              attachment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
              entity_type        TEXT NOT NULL,
              entity_id          TEXT NOT NULL,
              title              TEXT NOT NULL,
              description        TEXT,
              category           TEXT NOT NULL,
              visibility         TEXT NOT NULL,
              file_ref           TEXT NOT NULL,
              file_name          TEXT,
              file_format        TEXT,
              file_size_kb       INTEGER,
              mime_type          TEXT,
              checksum           TEXT,
              uploaded_by        TEXT,
              uploaded_on        TEXT NOT NULL,
              tagged_keywords    TEXT,
              status             TEXT NOT NULL,
              contains_pii       INTEGER NOT NULL DEFAULT 0,
              consent_recorded   INTEGER NOT NULL DEFAULT 0,
              retention_until    TEXT,
              download_count     INTEGER NOT NULL DEFAULT 0,
              last_accessed_on   TEXT,
              notes              TEXT,
              created_on         TEXT NOT NULL,
              updated_on         TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_attachments_entity
              ON attachments(entity_type, entity_id);
            CREATE INDEX IF NOT EXISTS ix_attachments_status
              ON attachments(status);
            CREATE INDEX IF NOT EXISTS ix_attachments_category
              ON attachments(category);
        """)


def _check_date(label: str, value: str | None) -> None:
    if not value:
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(
            f"{label} must be YYYY-MM-DD")


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)

    et = (out.get("entity_type") or DEFAULT_ENTITY_TYPE).strip()
    if et not in ENTITY_TYPES:
        raise ValidationError(
            f"Entity type must be one of: "
            f"{', '.join(ENTITY_TYPES)}")
    out["entity_type"] = et

    out["entity_id"] = (out.get("entity_id") or "").strip()
    if not out["entity_id"]:
        raise ValidationError("Entity id is required")

    out["title"] = (out.get("title") or "").strip()
    if not out["title"]:
        raise ValidationError("Title is required")

    cat = (out.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

    vis = (out.get("visibility") or DEFAULT_VISIBILITY).strip()
    if vis not in VISIBILITY:
        raise ValidationError(
            f"Visibility must be one of: "
            f"{', '.join(VISIBILITY)}")
    out["visibility"] = vis

    out["file_ref"] = (out.get("file_ref") or "").strip()
    if not out["file_ref"]:
        raise ValidationError(
            "File reference is required")

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    _check_date("Uploaded on",      out.get("uploaded_on"))
    _check_date("Retention until",  out.get("retention_until"))
    _check_date("Last accessed on", out.get("last_accessed_on"))

    fsz = out.get("file_size_kb")
    if fsz in (None, ""):
        out["file_size_kb"] = None
    else:
        try:
            out["file_size_kb"] = int(fsz)
        except (TypeError, ValueError):
            raise ValidationError(
                "File size (kB) must be an integer")
        if out["file_size_kb"] < 0:
            raise ValidationError(
                "File size (kB) must be >= 0")

    dc = out.get("download_count")
    if dc in (None, ""):
        out["download_count"] = 0
    else:
        try:
            out["download_count"] = int(dc)
        except (TypeError, ValueError):
            raise ValidationError(
                "Download count must be an integer")
        if out["download_count"] < 0:
            raise ValidationError(
                "Download count must be >= 0")

    out["uploaded_on"] = (
        (out.get("uploaded_on") or "").strip()
        or _dt.date.today().isoformat())

    for k in ("description", "file_name", "file_format",
               "mime_type", "checksum", "uploaded_by",
               "tagged_keywords", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("retention_until", "last_accessed_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None
                    if isinstance(v, str) else v)
    for k in ("contains_pii", "consent_recorded"):
        out[k] = bool(out.get(k))
    return out


def _row(r: sqlite3.Row) -> Attachment:
    return Attachment(
        attachment_id=r["attachment_id"],
        entity_type=r["entity_type"],
        entity_id=r["entity_id"],
        title=r["title"],
        description=r["description"],
        category=r["category"],
        visibility=r["visibility"],
        file_ref=r["file_ref"],
        file_name=r["file_name"],
        file_format=r["file_format"],
        file_size_kb=r["file_size_kb"],
        mime_type=r["mime_type"],
        checksum=r["checksum"],
        uploaded_by=r["uploaded_by"],
        uploaded_on=r["uploaded_on"],
        tagged_keywords=r["tagged_keywords"],
        status=r["status"],
        contains_pii=bool(r["contains_pii"]),
        consent_recorded=bool(r["consent_recorded"]),
        retention_until=r["retention_until"],
        download_count=r["download_count"],
        last_accessed_on=r["last_accessed_on"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


# ── CRUD ──────────────────────────────────────────────────

def create_attachment(payload: dict[str, Any]) -> Attachment:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO attachments (
              entity_type, entity_id, title, description,
              category, visibility, file_ref, file_name,
              file_format, file_size_kb, mime_type, checksum,
              uploaded_by, uploaded_on, tagged_keywords,
              status, contains_pii, consent_recorded,
              retention_until, download_count,
              last_accessed_on, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["entity_type"], p["entity_id"], p["title"],
            p["description"], p["category"], p["visibility"],
            p["file_ref"], p["file_name"], p["file_format"],
            p["file_size_kb"], p["mime_type"], p["checksum"],
            p["uploaded_by"], p["uploaded_on"],
            p["tagged_keywords"], p["status"],
            1 if p["contains_pii"] else 0,
            1 if p["consent_recorded"] else 0,
            p["retention_until"], p["download_count"],
            p["last_accessed_on"], p["notes"],
            now, now,
        ))
        att_id = cur.lastrowid
    return get_attachment(att_id)  # type: ignore[return-value]


def update_attachment(attachment_id: int,
                            payload: dict[str, Any]) -> Attachment:
    init_db()
    if get_attachment(attachment_id) is None:
        raise ValidationError(
            f"No attachment with id {attachment_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE attachments SET
              entity_type=?, entity_id=?, title=?,
              description=?, category=?, visibility=?,
              file_ref=?, file_name=?, file_format=?,
              file_size_kb=?, mime_type=?, checksum=?,
              uploaded_by=?, uploaded_on=?, tagged_keywords=?,
              status=?, contains_pii=?, consent_recorded=?,
              retention_until=?, download_count=?,
              last_accessed_on=?, notes=?, updated_on=?
            WHERE attachment_id=?
        """, (
            p["entity_type"], p["entity_id"], p["title"],
            p["description"], p["category"], p["visibility"],
            p["file_ref"], p["file_name"], p["file_format"],
            p["file_size_kb"], p["mime_type"], p["checksum"],
            p["uploaded_by"], p["uploaded_on"],
            p["tagged_keywords"], p["status"],
            1 if p["contains_pii"] else 0,
            1 if p["consent_recorded"] else 0,
            p["retention_until"], p["download_count"],
            p["last_accessed_on"], p["notes"],
            now, attachment_id,
        ))
    return get_attachment(attachment_id)  # type: ignore[return-value]


def delete_attachment(attachment_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attachments WHERE attachment_id=?",
            (attachment_id,))
        return cur.rowcount > 0


def get_attachment(attachment_id: int) -> Attachment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attachments WHERE attachment_id=?",
            (attachment_id,)).fetchone()
    return _row(r) if r else None


def list_attachments(*,
                          entity_type: str | None = None,
                          entity_id: str | None = None,
                          category: str | None = None,
                          visibility: str | None = None,
                          status: str | None = None,
                          active_only: bool = False,
                          pii_only: bool = False,
                          retention_expired_only: bool = False,
                          title_like: str | None = None,
                          keyword_like: str | None = None,
                          uploaded_by_like: str | None = None,
                          ) -> list[Attachment]:
    init_db()
    sql = "SELECT * FROM attachments WHERE 1=1"
    params: list[Any] = []
    if entity_type:
        sql += " AND entity_type=?"
        params.append(entity_type)
    if entity_id:
        sql += " AND entity_id=?"
        params.append(entity_id)
    if category:
        sql += " AND category=?"
        params.append(category)
    if visibility:
        sql += " AND visibility=?"
        params.append(visibility)
    if status:
        sql += " AND status=?"
        params.append(status)
    if active_only:
        sql += " AND status='Active'"
    if pii_only:
        sql += " AND contains_pii=1"
    if retention_expired_only:
        today = _dt.date.today().isoformat()
        sql += (" AND retention_until IS NOT NULL"
                  " AND retention_until < ?"
                  " AND status='Active'")
        params.append(today)
    if title_like:
        sql += " AND title LIKE ?"
        params.append(f"%{title_like}%")
    if keyword_like:
        sql += " AND tagged_keywords LIKE ?"
        params.append(f"%{keyword_like}%")
    if uploaded_by_like:
        sql += " AND uploaded_by LIKE ?"
        params.append(f"%{uploaded_by_like}%")
    sql += (" ORDER BY uploaded_on DESC,"
              " attachment_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def attachments_for(entity_type: str,
                            entity_id: str
                            ) -> list[Attachment]:
    return list_attachments(entity_type=entity_type,
                                  entity_id=entity_id)


# ── Workflow ──────────────────────────────────────────────

def _to_dict(a: Attachment) -> dict[str, Any]:
    return {
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "title": a.title,
        "description": a.description,
        "category": a.category,
        "visibility": a.visibility,
        "file_ref": a.file_ref,
        "file_name": a.file_name,
        "file_format": a.file_format,
        "file_size_kb": a.file_size_kb,
        "mime_type": a.mime_type,
        "checksum": a.checksum,
        "uploaded_by": a.uploaded_by,
        "uploaded_on": a.uploaded_on,
        "tagged_keywords": a.tagged_keywords,
        "status": a.status,
        "contains_pii": a.contains_pii,
        "consent_recorded": a.consent_recorded,
        "retention_until": a.retention_until,
        "download_count": a.download_count,
        "last_accessed_on": a.last_accessed_on,
        "notes": a.notes,
    }


def quarantine(attachment_id: int) -> Attachment:
    a = get_attachment(attachment_id)
    if a is None:
        raise ValidationError(
            f"No attachment with id {attachment_id}")
    return update_attachment(attachment_id,
                                    {**_to_dict(a),
                                      "status": "Quarantined"})


def restore(attachment_id: int) -> Attachment:
    a = get_attachment(attachment_id)
    if a is None:
        raise ValidationError(
            f"No attachment with id {attachment_id}")
    return update_attachment(attachment_id,
                                    {**_to_dict(a),
                                      "status": "Active"})


def archive(attachment_id: int) -> Attachment:
    a = get_attachment(attachment_id)
    if a is None:
        raise ValidationError(
            f"No attachment with id {attachment_id}")
    return update_attachment(attachment_id,
                                    {**_to_dict(a),
                                      "status": "Archived"})


def soft_delete(attachment_id: int) -> Attachment:
    a = get_attachment(attachment_id)
    if a is None:
        raise ValidationError(
            f"No attachment with id {attachment_id}")
    return update_attachment(attachment_id,
                                    {**_to_dict(a),
                                      "status": "Deleted"})


def set_status(attachment_id: int,
                    new_status: str) -> Attachment:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    a = get_attachment(attachment_id)
    if a is None:
        raise ValidationError(
            f"No attachment with id {attachment_id}")
    return update_attachment(attachment_id,
                                    {**_to_dict(a),
                                      "status": new_status})


def record_access(attachment_id: int, *,
                       by: int = 1) -> Attachment:
    a = get_attachment(attachment_id)
    if a is None:
        raise ValidationError(
            f"No attachment with id {attachment_id}")
    data = _to_dict(a)
    data["download_count"] = a.download_count + max(by, 0)
    data["last_accessed_on"] = _dt.date.today().isoformat()
    return update_attachment(attachment_id, data)


def purge_expired_retention(*,
                                       hard_delete: bool = False
                                       ) -> int:
    """Soft-delete (or hard-delete) active attachments whose
    retention window has expired. Returns the number affected."""
    init_db()
    today = _dt.date.today().isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT attachment_id FROM attachments "
            "WHERE retention_until IS NOT NULL "
            "  AND retention_until < ? "
            "  AND status='Active'",
            (today,)).fetchall()
    count = 0
    for r in rows:
        if hard_delete:
            delete_attachment(r["attachment_id"])
        else:
            soft_delete(r["attachment_id"])
        count += 1
    return count


# ── Summary ─────────────────────────────────────────────

def summary() -> AttachmentsSummary:
    rows = list_attachments()
    out = AttachmentsSummary(total=len(rows))
    if not rows:
        return out
    today = _dt.date.today().isoformat()
    entities: set[tuple[str, str]] = set()
    for a in rows:
        entities.add((a.entity_type, a.entity_id))
        if a.status == "Active":
            out.active += 1
        elif a.status == "Quarantined":
            out.quarantined += 1
        elif a.status == "Archived":
            out.archived += 1
        elif a.status == "Deleted":
            out.deleted += 1
        if a.visibility == "Confidential":
            out.confidential += 1
        if a.contains_pii:
            out.contains_pii += 1
        if (a.retention_until and a.retention_until < today
                and a.status == "Active"):
            out.retention_expired += 1
        if a.file_size_kb:
            out.total_size_kb += a.file_size_kb
        out.total_downloads += a.download_count
        out.by_entity_type[a.entity_type] = (
            out.by_entity_type.get(a.entity_type, 0) + 1)
        out.by_category[a.category] = (
            out.by_category.get(a.category, 0) + 1)
        out.by_visibility[a.visibility] = (
            out.by_visibility.get(a.visibility, 0) + 1)
        out.by_status[a.status] = (
            out.by_status.get(a.status, 0) + 1)
        fmt = a.file_format or "—"
        out.by_format[fmt] = out.by_format.get(fmt, 0) + 1
    out.distinct_entities = len(entities)
    return out


__all__ = [
    "ENTITY_TYPES", "DEFAULT_ENTITY_TYPE",
    "CATEGORIES", "DEFAULT_CATEGORY",
    "VISIBILITY", "DEFAULT_VISIBILITY",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "Attachment", "AttachmentsSummary",
    "init_db",
    "create_attachment", "update_attachment",
    "delete_attachment", "get_attachment",
    "list_attachments", "attachments_for",
    "quarantine", "restore", "archive", "soft_delete",
    "set_status", "record_access",
    "purge_expired_retention",
    "summary",
]
