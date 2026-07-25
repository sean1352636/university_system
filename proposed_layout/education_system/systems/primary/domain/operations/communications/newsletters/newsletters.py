"""Newsletters data layer.

One row per newsletter issue. Newsletters move through three states:

    draft     — being written, freely editable
    published — sent out; published_on is stamped
    archived  — retired (older issues kept for the record)

When an issue is published it is locked from edits until reverted to
draft. ``issue_number`` is optional but when present must be unique
within a given ``academic_year``.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

STATUSES: tuple[str, ...] = ("draft", "published", "archived")
STATUS_LABELS: dict[str, str] = {
    "draft":     "Draft — editable",
    "published": "Published — locked",
    "archived":  "Archived — retired",
}

# Free-text audience labels are accepted, but a known set is canonicalised
# for filtering. ``year_R`` / ``year_1`` etc. are also accepted.
AUDIENCE_CHOICES: tuple[str, ...] = (
    "whole_school", "parents", "staff", "governors", "year_group",
)
AUDIENCE_LABELS: dict[str, str] = {
    "whole_school": "Whole school",
    "parents":      "Parents / carers",
    "staff":        "Staff",
    "governors":    "Governors",
    "year_group":   "Year group (specify in target_year_group)",
}

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}(-\d{2}|-\d{4})?$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS newsletters (
    newsletter_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT NOT NULL,
    issue_number      INTEGER,
    academic_year     TEXT NOT NULL,
    issue_date        TEXT,
    audience          TEXT NOT NULL DEFAULT 'whole_school',
    target_year_group TEXT,
    body              TEXT,
    authored_by       TEXT,
    status            TEXT NOT NULL DEFAULT 'draft',
    published_on      TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_news_year   ON newsletters(academic_year);
CREATE INDEX IF NOT EXISTS idx_news_status ON newsletters(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_news_year_issue
    ON newsletters(academic_year, issue_number)
    WHERE issue_number IS NOT NULL;
"""


@dataclass
class Newsletter:
    newsletter_id: int
    title: str
    issue_number: int | None
    academic_year: str
    issue_date: str | None
    audience: str
    target_year_group: str | None
    body: str | None
    authored_by: str | None
    status: str
    published_on: str | None
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def is_draft(self) -> bool:
        return self.status == "draft"

    @property
    def is_published(self) -> bool:
        return self.status == "published"

    @property
    def is_archived(self) -> bool:
        return self.status == "archived"


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise newsletters table")
        raise
    logger.info("Primary newsletters table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Newsletter:
    return Newsletter(
        newsletter_id=r["newsletter_id"],
        title=r["title"],
        issue_number=r["issue_number"],
        academic_year=r["academic_year"],
        issue_date=r["issue_date"],
        audience=r["audience"],
        target_year_group=r["target_year_group"],
        body=r["body"],
        authored_by=r["authored_by"],
        status=r["status"],
        published_on=r["published_on"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    if len(title) > 200:
        raise ValidationError("Title must be 200 characters or fewer")
    out["title"] = title
    iss_raw = data.get("issue_number")
    if iss_raw in (None, ""):
        out["issue_number"] = None
    else:
        try:
            iss = int(iss_raw)
        except (TypeError, ValueError) as e:
            raise ValidationError("Issue number must be an integer") from e
        if iss < 1 or iss > 9999:
            raise ValidationError("Issue number must be between 1 and 9999")
        out["issue_number"] = iss
    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025-26)")
    if not _ACADEMIC_YEAR_RE.match(ay):
        raise ValidationError("Academic year must look like 2025 or 2025-26")
    out["academic_year"] = ay
    issue_date = (data.get("issue_date") or "").strip()
    if issue_date and not _DOB_RE.match(issue_date):
        raise ValidationError("Issue date must be YYYY-MM-DD")
    out["issue_date"] = issue_date or None
    audience = (data.get("audience") or "whole_school").strip().lower() or "whole_school"
    if audience not in AUDIENCE_CHOICES:
        raise ValidationError(
            f"Audience must be one of {', '.join(AUDIENCE_CHOICES)}")
    out["audience"] = audience
    tyg = (data.get("target_year_group") or "").strip()
    if audience == "year_group":
        if not tyg:
            raise ValidationError(
                "Target year group is required when audience is year_group")
        if tyg not in YEAR_GROUPS:
            raise ValidationError(
                f"Target year group must be one of {', '.join(YEAR_GROUPS)}")
        out["target_year_group"] = tyg
    else:
        out["target_year_group"] = tyg or None
    out["body"]        = (data.get("body") or "").strip() or None
    out["authored_by"] = (data.get("authored_by") or "").strip() or None
    status = (data.get("status") or "draft").strip().lower() or "draft"
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    pub_on = (data.get("published_on") or "").strip()
    if pub_on and not _DOB_RE.match(pub_on):
        raise ValidationError("Published-on date must be YYYY-MM-DD")
    out["published_on"] = pub_on or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> Newsletter:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            if payload["issue_number"] is not None:
                dup = conn.execute(
                    "SELECT newsletter_id FROM newsletters "
                    "WHERE academic_year = ? AND issue_number = ?",
                    (payload["academic_year"], payload["issue_number"]),
                ).fetchone()
                if dup:
                    raise ValidationError(
                        f"Issue {payload['issue_number']} for "
                        f"{payload['academic_year']} already exists "
                        f"(#{dup['newsletter_id']})")
            cur = conn.execute(
                """INSERT INTO newsletters
                       (title, issue_number, academic_year, issue_date,
                        audience, target_year_group, body, authored_by,
                        status, published_on, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["title"], payload["issue_number"],
                 payload["academic_year"], payload["issue_date"],
                 payload["audience"], payload["target_year_group"],
                 payload["body"], payload["authored_by"],
                 payload["status"], payload["published_on"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        logger.exception("Integrity error creating newsletter")
        raise ValidationError(f"Could not create newsletter — {e}") from e
    except sqlite3.Error:
        logger.exception("Failed to create newsletter")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created newsletter #%d %r (%s, status=%s)",
                rec.newsletter_id, rec.title, rec.academic_year, rec.status)
    return rec


def get(newsletter_id: int) -> Newsletter | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM newsletters WHERE newsletter_id = ?",
                (newsletter_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get newsletter(%s) failed", newsletter_id)
        raise
    return _row(r) if r else None


def update(newsletter_id: int, data: dict[str, Any]) -> Newsletter:
    init_db()
    existing = get(newsletter_id)
    if existing is None:
        raise ValidationError(f"No newsletter #{newsletter_id}")
    if existing.is_published:
        raise ValidationError(
            "Newsletter is published — revert to draft before editing")
    merged = {
        "title":             data.get("title", existing.title),
        "issue_number":      data.get("issue_number", existing.issue_number),
        "academic_year":     data.get("academic_year", existing.academic_year),
        "issue_date":        data.get("issue_date", existing.issue_date),
        "audience":          data.get("audience", existing.audience),
        "target_year_group": data.get("target_year_group",
                                      existing.target_year_group),
        "body":              data.get("body", existing.body),
        "authored_by":       data.get("authored_by", existing.authored_by),
        "status":            data.get("status", existing.status),
        "published_on":      data.get("published_on", existing.published_on),
        "notes":             data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    try:
        with _connect() as conn:
            if payload["issue_number"] is not None:
                dup = conn.execute(
                    "SELECT newsletter_id FROM newsletters "
                    "WHERE academic_year = ? AND issue_number = ? "
                    "AND newsletter_id <> ?",
                    (payload["academic_year"], payload["issue_number"],
                     newsletter_id),
                ).fetchone()
                if dup:
                    raise ValidationError(
                        f"Issue {payload['issue_number']} for "
                        f"{payload['academic_year']} already exists "
                        f"(#{dup['newsletter_id']})")
            conn.execute(
                """UPDATE newsletters SET
                       title = ?, issue_number = ?, academic_year = ?,
                       issue_date = ?, audience = ?, target_year_group = ?,
                       body = ?, authored_by = ?, status = ?,
                       published_on = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE newsletter_id = ?""",
                (payload["title"], payload["issue_number"],
                 payload["academic_year"], payload["issue_date"],
                 payload["audience"], payload["target_year_group"],
                 payload["body"], payload["authored_by"],
                 payload["status"], payload["published_on"],
                 payload["notes"], newsletter_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("Integrity error updating newsletter #%d",
                         newsletter_id)
        raise ValidationError(f"Could not update newsletter — {e}") from e
    except sqlite3.Error:
        logger.exception("Failed to update newsletter #%d", newsletter_id)
        raise
    rec = get(newsletter_id)
    assert rec is not None
    logger.info("Updated newsletter #%d", newsletter_id)
    return rec


def publish(newsletter_id: int,
            *, published_on: str | None = None) -> Newsletter:
    init_db()
    existing = get(newsletter_id)
    if existing is None:
        raise ValidationError(f"No newsletter #{newsletter_id}")
    if existing.is_published:
        return existing
    if existing.is_archived:
        raise ValidationError(
            "Newsletter is archived — revert to draft first")
    if published_on:
        published_on = published_on.strip()
        if not _DOB_RE.match(published_on):
            raise ValidationError("Published-on date must be YYYY-MM-DD")
    try:
        with _connect() as conn:
            pub_date = published_on or conn.execute(
                "SELECT date('now')").fetchone()[0]
            conn.execute(
                "UPDATE newsletters SET status = 'published', "
                "published_on = ?, updated_at = datetime('now') "
                "WHERE newsletter_id = ?",
                (pub_date, newsletter_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to publish newsletter #%d", newsletter_id)
        raise
    rec = get(newsletter_id)
    assert rec is not None
    logger.info("Published newsletter #%d on %s",
                newsletter_id, rec.published_on)
    return rec


def revert_to_draft(newsletter_id: int) -> Newsletter:
    init_db()
    existing = get(newsletter_id)
    if existing is None:
        raise ValidationError(f"No newsletter #{newsletter_id}")
    if existing.is_draft:
        return existing
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE newsletters SET status = 'draft', "
                "published_on = NULL, updated_at = datetime('now') "
                "WHERE newsletter_id = ?",
                (newsletter_id,),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to revert newsletter #%d", newsletter_id)
        raise
    rec = get(newsletter_id)
    assert rec is not None
    logger.info("Reverted newsletter #%d to draft", newsletter_id)
    return rec


def archive(newsletter_id: int) -> Newsletter:
    init_db()
    existing = get(newsletter_id)
    if existing is None:
        raise ValidationError(f"No newsletter #{newsletter_id}")
    if existing.is_archived:
        return existing
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE newsletters SET status = 'archived', "
                "updated_at = datetime('now') WHERE newsletter_id = ?",
                (newsletter_id,),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to archive newsletter #%d", newsletter_id)
        raise
    rec = get(newsletter_id)
    assert rec is not None
    logger.info("Archived newsletter #%d", newsletter_id)
    return rec


def delete(newsletter_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM newsletters WHERE newsletter_id = ?",
                (newsletter_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete newsletter #%d", newsletter_id)
        raise
    if deleted:
        logger.info("Deleted newsletter #%d", newsletter_id)
    return deleted


def list_newsletters(
    *, academic_year: str | None = None,
    status: str | None = None,
    audience: str | None = None,
    target_year_group: str | None = None,
    search: str | None = None,
) -> list[Newsletter]:
    init_db()
    if status is not None and status not in STATUSES:
        raise ValidationError(
            f"Status filter must be one of {', '.join(STATUSES)}")
    if audience is not None and audience not in AUDIENCE_CHOICES:
        raise ValidationError(
            f"Audience filter must be one of {', '.join(AUDIENCE_CHOICES)}")
    if target_year_group is not None and target_year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
    where: list[str] = []
    params: list[Any] = []
    if academic_year:
        where.append("academic_year = ?")
        params.append(academic_year.strip())
    if status:
        where.append("status = ?")
        params.append(status)
    if audience:
        where.append("audience = ?")
        params.append(audience)
    if target_year_group:
        where.append("target_year_group = ?")
        params.append(target_year_group)
    if search:
        q = f"%{search.strip()}%"
        where.append("(title LIKE ? OR body LIKE ? OR authored_by LIKE ?)")
        params.extend([q, q, q])
    sql = "SELECT * FROM newsletters"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY academic_year DESC, "
            "COALESCE(issue_date, '') DESC, issue_number DESC, newsletter_id DESC")
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_newsletters failed")
        raise
    return [_row(r) for r in rows]


def summary() -> dict[str, Any]:
    init_db()
    try:
        with _connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM newsletters").fetchone()[0]
            counts = {
                r["status"]: r["n"]
                for r in conn.execute(
                    "SELECT status, COUNT(*) AS n FROM newsletters "
                    "GROUP BY status"
                ).fetchall()
            }
            distinct_years = conn.execute(
                "SELECT COUNT(DISTINCT academic_year) FROM newsletters"
            ).fetchone()[0]
    except sqlite3.Error:
        logger.exception("newsletter summary failed")
        raise
    return {
        "total": total,
        "by_status": {s: counts.get(s, 0) for s in STATUSES},
        "academic_years": distinct_years,
    }


def known_years() -> list[str]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT academic_year FROM newsletters "
                "ORDER BY academic_year DESC"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("known_years failed")
        raise
    return [r["academic_year"] for r in rows]


def next_issue_number(academic_year: str) -> int:
    """Suggest the next free issue number for an academic year."""
    init_db()
    ay = (academic_year or "").strip()
    if not ay:
        raise ValidationError("Academic year is required")
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT COALESCE(MAX(issue_number), 0) AS m "
                "FROM newsletters WHERE academic_year = ?",
                (ay,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("next_issue_number(%s) failed", ay)
        raise
    return int(r["m"]) + 1
