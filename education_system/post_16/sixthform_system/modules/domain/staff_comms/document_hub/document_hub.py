"""Document Hub data layer for Sixth Form System.

Central registry of versioned documents (policies, handbooks,
forms, prospectuses, schemes of work, etc.) with category /
audience scoping, status workflow, and review cycle tracking.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system.post_16.sixthform_system.core import paths as _paths

logger = logging.getLogger(__name__)

CATEGORIES: tuple[str, ...] = (
    "Policy",
    "Procedure",
    "Handbook",
    "Form",
    "Prospectus",
    "Scheme of Work",
    "Curriculum",
    "Assessment",
    "Examination",
    "Safeguarding",
    "Health & Safety",
    "Finance",
    "HR",
    "Governance",
    "Report",
    "Letter Template",
    "Marketing",
    "Other",
)
DEFAULT_CATEGORY = "Policy"

AUDIENCES: tuple[str, ...] = (
    "All",
    "Students",
    "Staff",
    "Parents / Carers",
    "Governors",
    "External",
    "Senior Leadership",
    "Department",
    "Tutors",
    "Inspectors",
)
DEFAULT_AUDIENCE = "All"

ACCESS_LEVELS: tuple[str, ...] = (
    "Public",
    "Internal",
    "Restricted",
    "Confidential",
)
DEFAULT_ACCESS = "Internal"

STATUSES: tuple[str, ...] = (
    "Draft",
    "Under Review",
    "Approved",
    "Published",
    "Superseded",
    "Withdrawn",
    "Archived",
)
DEFAULT_STATUS = "Draft"


class ValidationError(Exception):
    pass


@dataclass
class Document:
    document_id: int
    title: str
    description: str | None
    category: str
    audience: str
    access_level: str
    version: str
    file_ref: str | None
    file_format: str | None
    file_size_kb: int | None
    author: str | None
    owner_department: str | None
    approved_by: str | None
    keywords: str | None
    status: str
    issued_on: str | None
    review_on: str | None
    expires_on: str | None
    supersedes_id: int | None
    linked_to: str | None
    download_count: int
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_current(self) -> bool:
        return self.status in ("Approved", "Published")

    @property
    def is_overdue_review(self) -> bool:
        if not self.review_on or not self.is_current:
            return False
        return self.review_on < _dt.date.today().isoformat()

    @property
    def is_expired(self) -> bool:
        if not self.expires_on:
            return False
        return self.expires_on < _dt.date.today().isoformat()

    @property
    def keyword_list(self) -> list[str]:
        if not self.keywords:
            return []
        return [k.strip() for k in self.keywords.split(",")
                  if k.strip()]


@dataclass
class DocumentHubSummary:
    total: int = 0
    drafts: int = 0
    under_review: int = 0
    approved: int = 0
    published: int = 0
    superseded: int = 0
    archived: int = 0
    overdue_review: int = 0
    expired_unprocessed: int = 0
    confidential: int = 0
    total_downloads: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_audience: dict[str, int] = field(default_factory=dict)
    by_access: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.DOCUMENT_HUB_DB)
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
            CREATE TABLE IF NOT EXISTS documents (
              document_id      INTEGER PRIMARY KEY AUTOINCREMENT,
              title            TEXT NOT NULL,
              description      TEXT,
              category         TEXT NOT NULL,
              audience         TEXT NOT NULL,
              access_level     TEXT NOT NULL,
              version          TEXT NOT NULL,
              file_ref         TEXT,
              file_format      TEXT,
              file_size_kb     INTEGER,
              author           TEXT,
              owner_department TEXT,
              approved_by      TEXT,
              keywords         TEXT,
              status           TEXT NOT NULL,
              issued_on        TEXT,
              review_on        TEXT,
              expires_on       TEXT,
              supersedes_id    INTEGER REFERENCES documents(document_id) ON DELETE SET NULL,
              linked_to        TEXT,
              download_count   INTEGER NOT NULL DEFAULT 0,
              notes            TEXT,
              created_on       TEXT NOT NULL,
              updated_on       TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_documents_cat
              ON documents(category);
            CREATE INDEX IF NOT EXISTS ix_documents_status
              ON documents(status);
            CREATE INDEX IF NOT EXISTS ix_documents_audience
              ON documents(audience);
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
    out["title"] = (out.get("title") or "").strip()
    if not out["title"]:
        raise ValidationError("Title is required")

    cat = (out.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

    aud = (out.get("audience") or DEFAULT_AUDIENCE).strip()
    if aud not in AUDIENCES:
        raise ValidationError(
            f"Audience must be one of: {', '.join(AUDIENCES)}")
    out["audience"] = aud

    access = (out.get("access_level") or DEFAULT_ACCESS).strip()
    if access not in ACCESS_LEVELS:
        raise ValidationError(
            f"Access level must be one of: "
            f"{', '.join(ACCESS_LEVELS)}")
    out["access_level"] = access

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["version"] = (out.get("version") or "1.0").strip()
    if not out["version"]:
        out["version"] = "1.0"

    _check_date("Issued on",  out.get("issued_on"))
    _check_date("Review on",  out.get("review_on"))
    _check_date("Expires on", out.get("expires_on"))

    if (out.get("issued_on") and out.get("review_on")
            and out["review_on"] < out["issued_on"]):
        raise ValidationError(
            "Review date cannot be before issue date")
    if (out.get("issued_on") and out.get("expires_on")
            and out["expires_on"] < out["issued_on"]):
        raise ValidationError(
            "Expiry date cannot be before issue date")

    sup = out.get("supersedes_id")
    if sup in (None, "", 0):
        out["supersedes_id"] = None
    else:
        try:
            out["supersedes_id"] = int(sup)
        except (TypeError, ValueError):
            raise ValidationError(
                "Supersedes id must be an integer")

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

    for k in ("description", "file_ref", "file_format",
               "author", "owner_department", "approved_by",
               "keywords", "linked_to", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("issued_on", "review_on", "expires_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None
                    if isinstance(v, str) else v)
    return out


def _row(r: sqlite3.Row) -> Document:
    return Document(
        document_id=r["document_id"],
        title=r["title"],
        description=r["description"],
        category=r["category"],
        audience=r["audience"],
        access_level=r["access_level"],
        version=r["version"],
        file_ref=r["file_ref"],
        file_format=r["file_format"],
        file_size_kb=r["file_size_kb"],
        author=r["author"],
        owner_department=r["owner_department"],
        approved_by=r["approved_by"],
        keywords=r["keywords"],
        status=r["status"],
        issued_on=r["issued_on"],
        review_on=r["review_on"],
        expires_on=r["expires_on"],
        supersedes_id=r["supersedes_id"],
        linked_to=r["linked_to"],
        download_count=r["download_count"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


# ── CRUD ──────────────────────────────────────────────────

def create_document(payload: dict[str, Any]) -> Document:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO documents (
              title, description, category, audience,
              access_level, version, file_ref, file_format,
              file_size_kb, author, owner_department,
              approved_by, keywords, status, issued_on,
              review_on, expires_on, supersedes_id,
              linked_to, download_count, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["title"], p["description"], p["category"],
            p["audience"], p["access_level"], p["version"],
            p["file_ref"], p["file_format"], p["file_size_kb"],
            p["author"], p["owner_department"],
            p["approved_by"], p["keywords"], p["status"],
            p["issued_on"], p["review_on"], p["expires_on"],
            p["supersedes_id"], p["linked_to"],
            p["download_count"], p["notes"],
            now, now,
        ))
        doc_id = cur.lastrowid
    return get_document(doc_id)  # type: ignore[return-value]


def update_document(document_id: int,
                          payload: dict[str, Any]) -> Document:
    init_db()
    if get_document(document_id) is None:
        raise ValidationError(
            f"No document with id {document_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE documents SET
              title=?, description=?, category=?, audience=?,
              access_level=?, version=?, file_ref=?,
              file_format=?, file_size_kb=?, author=?,
              owner_department=?, approved_by=?, keywords=?,
              status=?, issued_on=?, review_on=?, expires_on=?,
              supersedes_id=?, linked_to=?, download_count=?,
              notes=?, updated_on=?
            WHERE document_id=?
        """, (
            p["title"], p["description"], p["category"],
            p["audience"], p["access_level"], p["version"],
            p["file_ref"], p["file_format"], p["file_size_kb"],
            p["author"], p["owner_department"],
            p["approved_by"], p["keywords"], p["status"],
            p["issued_on"], p["review_on"], p["expires_on"],
            p["supersedes_id"], p["linked_to"],
            p["download_count"], p["notes"],
            now, document_id,
        ))
    return get_document(document_id)  # type: ignore[return-value]


def delete_document(document_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM documents WHERE document_id=?",
            (document_id,))
        return cur.rowcount > 0


def get_document(document_id: int) -> Document | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM documents WHERE document_id=?",
            (document_id,)).fetchone()
    return _row(r) if r else None


def list_documents(*,
                       category: str | None = None,
                       audience: str | None = None,
                       access_level: str | None = None,
                       status: str | None = None,
                       current_only: bool = False,
                       overdue_review_only: bool = False,
                       title_like: str | None = None,
                       keyword_like: str | None = None,
                       author_like: str | None = None,
                       ) -> list[Document]:
    init_db()
    sql = "SELECT * FROM documents WHERE 1=1"
    params: list[Any] = []
    if category:
        sql += " AND category=?"
        params.append(category)
    if audience:
        sql += " AND audience=?"
        params.append(audience)
    if access_level:
        sql += " AND access_level=?"
        params.append(access_level)
    if status:
        sql += " AND status=?"
        params.append(status)
    if current_only:
        sql += " AND status IN ('Approved','Published')"
    if overdue_review_only:
        today = _dt.date.today().isoformat()
        sql += (" AND status IN ('Approved','Published')"
                  " AND review_on IS NOT NULL"
                  " AND review_on < ?")
        params.append(today)
    if title_like:
        sql += " AND title LIKE ?"
        params.append(f"%{title_like}%")
    if keyword_like:
        sql += " AND keywords LIKE ?"
        params.append(f"%{keyword_like}%")
    if author_like:
        sql += " AND author LIKE ?"
        params.append(f"%{author_like}%")
    sql += " ORDER BY category, title, version DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


# ── Workflow ──────────────────────────────────────────────

def _to_dict(d: Document) -> dict[str, Any]:
    return {
        "title": d.title,
        "description": d.description,
        "category": d.category,
        "audience": d.audience,
        "access_level": d.access_level,
        "version": d.version,
        "file_ref": d.file_ref,
        "file_format": d.file_format,
        "file_size_kb": d.file_size_kb,
        "author": d.author,
        "owner_department": d.owner_department,
        "approved_by": d.approved_by,
        "keywords": d.keywords,
        "status": d.status,
        "issued_on": d.issued_on,
        "review_on": d.review_on,
        "expires_on": d.expires_on,
        "supersedes_id": d.supersedes_id,
        "linked_to": d.linked_to,
        "download_count": d.download_count,
        "notes": d.notes,
    }


def submit_for_review(document_id: int) -> Document:
    d = get_document(document_id)
    if d is None:
        raise ValidationError(
            f"No document with id {document_id}")
    return update_document(document_id,
                                 {**_to_dict(d),
                                   "status": "Under Review"})


def approve(document_id: int, *,
                approved_by: str | None = None) -> Document:
    d = get_document(document_id)
    if d is None:
        raise ValidationError(
            f"No document with id {document_id}")
    data = _to_dict(d)
    data["status"] = "Approved"
    if approved_by:
        data["approved_by"] = approved_by
    return update_document(document_id, data)


def publish(document_id: int, *,
                issued_on: str | None = None) -> Document:
    d = get_document(document_id)
    if d is None:
        raise ValidationError(
            f"No document with id {document_id}")
    data = _to_dict(d)
    data["status"] = "Published"
    data["issued_on"] = (issued_on
                                or data.get("issued_on")
                                or _dt.date.today().isoformat())
    return update_document(document_id, data)


def withdraw(document_id: int) -> Document:
    d = get_document(document_id)
    if d is None:
        raise ValidationError(
            f"No document with id {document_id}")
    return update_document(document_id,
                                 {**_to_dict(d),
                                   "status": "Withdrawn"})


def archive(document_id: int) -> Document:
    d = get_document(document_id)
    if d is None:
        raise ValidationError(
            f"No document with id {document_id}")
    return update_document(document_id,
                                 {**_to_dict(d),
                                   "status": "Archived"})


def supersede(old_document_id: int, *,
                   new_version: str,
                   carry_over: bool = True) -> Document:
    """Mark the old document Superseded and create a Draft copy
    under `new_version`. Returns the new draft."""
    old = get_document(old_document_id)
    if old is None:
        raise ValidationError(
            f"No document with id {old_document_id}")
    new_version = (new_version or "").strip()
    if not new_version:
        raise ValidationError("New version is required")
    if new_version == old.version:
        raise ValidationError(
            "New version must differ from current version")
    new_data = _to_dict(old) if carry_over else {
        "title": old.title,
        "category": old.category,
        "audience": old.audience,
        "access_level": old.access_level,
        "version": new_version,
        "status": "Draft",
        "supersedes_id": old_document_id,
        "download_count": 0,
    }
    new_data["version"] = new_version
    new_data["status"] = "Draft"
    new_data["supersedes_id"] = old_document_id
    new_data["download_count"] = 0
    new_data["issued_on"] = None
    new_doc = create_document(new_data)
    update_document(old_document_id,
                          {**_to_dict(old),
                            "status": "Superseded"})
    return new_doc


def set_status(document_id: int,
                    new_status: str) -> Document:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    d = get_document(document_id)
    if d is None:
        raise ValidationError(
            f"No document with id {document_id}")
    return update_document(document_id,
                                 {**_to_dict(d),
                                   "status": new_status})


def increment_downloads(document_id: int, *,
                                  by: int = 1) -> Document:
    d = get_document(document_id)
    if d is None:
        raise ValidationError(
            f"No document with id {document_id}")
    data = _to_dict(d)
    data["download_count"] = d.download_count + max(by, 0)
    return update_document(document_id, data)


def auto_archive_expired() -> int:
    """Archive Approved/Published documents whose expires_on has
    passed. Returns the number archived."""
    init_db()
    today = _dt.date.today().isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT document_id FROM documents "
            "WHERE expires_on IS NOT NULL "
            "  AND expires_on < ? "
            "  AND status IN ('Approved','Published')",
            (today,)).fetchall()
    count = 0
    for r in rows:
        archive(r["document_id"])
        count += 1
    return count


# ── Summary ─────────────────────────────────────────────

def summary() -> DocumentHubSummary:
    rows = list_documents()
    out = DocumentHubSummary(total=len(rows))
    if not rows:
        return out
    today = _dt.date.today().isoformat()
    for d in rows:
        if d.status == "Draft":
            out.drafts += 1
        elif d.status == "Under Review":
            out.under_review += 1
        elif d.status == "Approved":
            out.approved += 1
        elif d.status == "Published":
            out.published += 1
        elif d.status == "Superseded":
            out.superseded += 1
        elif d.status == "Archived":
            out.archived += 1
        if d.is_overdue_review:
            out.overdue_review += 1
        if (d.expires_on and d.expires_on < today
                and d.status in ("Approved", "Published")):
            out.expired_unprocessed += 1
        if d.access_level == "Confidential":
            out.confidential += 1
        out.total_downloads += d.download_count
        out.by_category[d.category] = (
            out.by_category.get(d.category, 0) + 1)
        out.by_audience[d.audience] = (
            out.by_audience.get(d.audience, 0) + 1)
        out.by_access[d.access_level] = (
            out.by_access.get(d.access_level, 0) + 1)
        out.by_status[d.status] = (
            out.by_status.get(d.status, 0) + 1)
    return out


__all__ = [
    "CATEGORIES", "DEFAULT_CATEGORY",
    "AUDIENCES", "DEFAULT_AUDIENCE",
    "ACCESS_LEVELS", "DEFAULT_ACCESS",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "Document", "DocumentHubSummary",
    "init_db",
    "create_document", "update_document", "delete_document",
    "get_document", "list_documents",
    "submit_for_review", "approve", "publish", "withdraw",
    "archive", "supersede", "set_status",
    "increment_downloads", "auto_archive_expired",
    "summary",
]
