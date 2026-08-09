"""Domain layer for Newsletters (Nursery System).

Owns the ``newsletters`` table — setting-wide bulletins sent to parents.
Newsletters are NOT attached to a child; they are addressed to the whole
setting or a specific room audience.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``newsletters_cli.py``, Tk GUI in ``newsletters_views.py``.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Newsletters"
CATEGORY = "Parents & Communication"

ID_PREFIX = "NNL"
ID_DIGITS = 3

AUDIENCES = (
    "Whole setting",
    "Baby Room",
    "Toddler Room",
    "Preschool Room",
)
STATUSES = ("draft", "published")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid newsletter input."""


@dataclass
class Newsletter:
    newsletter_id: str
    title: str
    issue_date: str | None
    audience: str | None
    body: str | None
    author: str | None
    status: str
    published_date: str | None
    created_at: str | None
    author_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for newsletters")
        raise


_SELECT = """
SELECT n.*,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS author_name
FROM newsletters n
LEFT JOIN staff s ON s.staff_id = n.author
"""


def _row(r: sqlite3.Row) -> Newsletter:
    keys = r.keys()
    return Newsletter(
        newsletter_id=r["newsletter_id"],
        title=r["title"],
        issue_date=r["issue_date"],
        audience=r["audience"],
        body=r["body"],
        author=r["author"],
        status=r["status"],
        published_date=r["published_date"],
        created_at=r["created_at"],
        author_name=(r["author_name"] or None) if "author_name" in keys else None,
    )


# ── Validation ────────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    out["title"] = title

    out["issue_date"] = _opt_date(data.get("issue_date"), "Issue date")

    audience = (data.get("audience") or "").strip()
    if audience and audience not in AUDIENCES:
        raise ValidationError(
            "Audience must be one of: " + ", ".join(AUDIENCES))
    out["audience"] = audience or None

    out["body"] = _opt(data.get("body"))
    out["author"] = _opt(data.get("author"))

    status = (data.get("status") or "draft").strip()
    if status not in STATUSES:
        raise ValidationError("Status must be one of: " + ", ".join(STATUSES))
    out["status"] = status

    out["published_date"] = _opt_date(data.get("published_date"), "Published date")
    return out


# ── ID allocation ─────────────────────────────────────────────────────────────

def generate_newsletter_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT newsletter_id FROM newsletters").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing newsletter ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        nid = f"{ID_PREFIX}{n}"
        if nid not in existing:
            return nid
    raise RuntimeError("Could not allocate a unique newsletter id")


# ── Reads ─────────────────────────────────────────────────────────────────────

def list_newsletters() -> list[Newsletter]:
    _ensure_schema()
    sql = (
        _SELECT
        + " ORDER BY COALESCE(n.issue_date, '') DESC, n.newsletter_id DESC"
    )
    try:
        with connect() as conn:
            rows = conn.execute(sql).fetchall()
    except sqlite3.Error:
        logger.exception("list_newsletters failed")
        raise
    return [_row(r) for r in rows]


def get_newsletter(newsletter_id: str) -> Newsletter | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE n.newsletter_id = ?",
                (newsletter_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_newsletter(%s) failed", newsletter_id)
        raise
    return _row(row) if row else None


def list_staff_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name FROM staff "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    return [(r["staff_id"], f"{r['first_name']} {r['last_name']} ({r['staff_id']})")
            for r in rows]


# ── Writes ────────────────────────────────────────────────────────────────────

def create_newsletter(data: dict[str, Any]) -> Newsletter:
    _ensure_schema()
    payload = _validate(data)
    nid = generate_newsletter_id()
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO newsletters (
                    newsletter_id, title, issue_date, audience, body,
                    author, status, published_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (nid, payload["title"], payload["issue_date"],
                 payload["audience"], payload["body"],
                 payload["author"], payload["status"],
                 payload["published_date"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("INSERT failed for newsletter id=%s", nid)
        raise ValidationError(f"Could not create newsletter — {e}") from e
    n = get_newsletter(nid)
    assert n is not None
    logger.info("Created newsletter %s", nid)
    return n


def update_newsletter(newsletter_id: str, data: dict[str, Any]) -> Newsletter:
    _ensure_schema()
    payload = _validate(data)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE newsletters SET
                    title = ?, issue_date = ?, audience = ?, body = ?,
                    author = ?, status = ?, published_date = ?
                WHERE newsletter_id = ?
                """,
                (payload["title"], payload["issue_date"],
                 payload["audience"], payload["body"],
                 payload["author"], payload["status"],
                 payload["published_date"], newsletter_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(
                    f"No newsletter with id {newsletter_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for newsletter id=%s", newsletter_id)
        raise ValidationError(f"Could not update newsletter — {e}") from e
    n = get_newsletter(newsletter_id)
    assert n is not None
    logger.info("Updated newsletter %s", newsletter_id)
    return n


def delete_newsletter(newsletter_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM newsletters WHERE newsletter_id = ?",
                (newsletter_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting newsletter id=%s",
                         newsletter_id)
        raise
    if deleted:
        logger.info("Deleted newsletter %s", newsletter_id)
    return deleted


def publish_newsletter(newsletter_id: str,
                       published_date: str | None = None) -> Newsletter:
    """Set status to 'published' and stamp published_date.

    If *published_date* is provided it is used; otherwise the existing
    published_date is kept, or issue_date is used as a fallback.
    """
    _ensure_schema()
    existing = get_newsletter(newsletter_id)
    if existing is None:
        raise ValidationError(f"No newsletter with id {newsletter_id}")
    # Resolve the date to stamp
    if published_date:
        date_to_set: str | None = _opt_date(published_date, "Published date")
    else:
        date_to_set = existing.published_date or existing.issue_date
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE newsletters
                SET status = 'published', published_date = ?
                WHERE newsletter_id = ?
                """,
                (date_to_set, newsletter_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(
                    f"No newsletter with id {newsletter_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("PUBLISH failed for newsletter id=%s", newsletter_id)
        raise ValidationError(f"Could not publish newsletter — {e}") from e
    n = get_newsletter(newsletter_id)
    assert n is not None
    logger.info("Published newsletter %s", newsletter_id)
    return n
