"""Notices & Bulletins data layer for the Sixth Form System.

One row per notice. Notices have a lifecycle:

    Draft → Published → Archived
                 ↑          ↓
                 └─ (unarchive)

A *currently visible* notice is one that is Published, has
``publish_from <= today``, and either has no ``publish_until`` or
``publish_until >= today``. Pinned notices sort first, then by
priority, then most-recent ``publish_from``.

Notices have a soft link to a staff member as the author. If that
staff row is deleted, the author_staff_id is cleared (SET NULL).
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import date as _date
from typing import Any
from education_system.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.NOTICES_DB

CATEGORIES: tuple[str, ...] = (
    "General", "Academic", "Pastoral", "UCAS", "Careers",
    "Exams", "Trips", "Sports", "Clubs & Societies",
    "Safeguarding", "Closure / Weather", "Timetable Change",
    "Cover", "IT", "Library", "Other",
)
DEFAULT_CATEGORY: str = "General"

AUDIENCES: tuple[str, ...] = (
    "All", "Year 12 Students", "Year 13 Students",
    "All Students", "Tutors", "Heads of Year",
    "All Staff", "Year 12 Parents", "Year 13 Parents",
    "All Parents", "Sixth Form Office",
)
DEFAULT_AUDIENCE: str = "All"

PRIORITIES: tuple[str, ...] = ("Low", "Normal", "High", "Urgent")
DEFAULT_PRIORITY: str = "Normal"
_PRIORITY_RANK = {p: i for i, p in enumerate(reversed(PRIORITIES))}

STATUSES: tuple[str, ...] = ("Draft", "Published", "Archived")
DEFAULT_STATUS: str = "Draft"

MAX_TITLE_LEN: int = 200

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notices (
    notice_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    body             TEXT NOT NULL,
    category         TEXT NOT NULL DEFAULT 'General',
    audience         TEXT NOT NULL DEFAULT 'All',
    priority         TEXT NOT NULL DEFAULT 'Normal',
    status           TEXT NOT NULL DEFAULT 'Draft',
    author_staff_id  TEXT,
    publish_from     TEXT,
    publish_until    TEXT,
    pinned           INTEGER NOT NULL DEFAULT 0,
    view_count       INTEGER NOT NULL DEFAULT 0,
    attachments_note TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (author_staff_id) REFERENCES staff(staff_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_notice_status   ON notices(status);
CREATE INDEX IF NOT EXISTS idx_notice_category ON notices(category);
CREATE INDEX IF NOT EXISTS idx_notice_audience ON notices(audience);
CREATE INDEX IF NOT EXISTS idx_notice_pinned   ON notices(pinned);
CREATE INDEX IF NOT EXISTS idx_notice_from     ON notices(publish_from);
"""


@dataclass
class Notice:
    notice_id: int
    title: str
    body: str
    category: str
    audience: str
    priority: str
    status: str
    author_staff_id: str | None
    publish_from: str | None
    publish_until: str | None
    pinned: bool
    view_count: int
    attachments_note: str | None
    created_at: str
    updated_at: str

    def is_visible_on(self, when: str) -> bool:
        if self.status != "Published":
            return False
        if self.publish_from and self.publish_from > when:
            return False
        if self.publish_until and self.publish_until < when:
            return False
        return True

    @property
    def is_visible_today(self) -> bool:
        return self.is_visible_on(_date.today().isoformat())


@dataclass
class NoticeRow:
    notice: Notice
    author_name: str | None


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    from education_system.sixthform_system.modules.domain.staff import staff as _staff
    _staff.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Notices schema ready at %s", DB_PATH)


def _row(r: sqlite3.Row) -> Notice:
    return Notice(
        notice_id=r["notice_id"], title=r["title"], body=r["body"],
        category=r["category"], audience=r["audience"],
        priority=r["priority"], status=r["status"],
        author_staff_id=r["author_staff_id"],
        publish_from=r["publish_from"], publish_until=r["publish_until"],
        pinned=bool(r["pinned"]), view_count=r["view_count"],
        attachments_note=r["attachments_note"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_date(v: Any, label: str, *,
                    required: bool = False) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_author(v: Any) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    sid = str(v).strip().upper()
    from education_system.sixthform_system.modules.domain.staff import staff as _staff
    if _staff.get_staff(sid) is None:
        raise ValidationError(f"No staff with id {sid}")
    return sid


def _validate_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    title = _require(d.get("title"), "Title").strip()
    if len(title) > MAX_TITLE_LEN:
        raise ValidationError(
            f"Title must be {MAX_TITLE_LEN} characters or fewer")
    out["title"] = title
    out["body"] = _require(d.get("body"), "Body").strip()

    cat = (d.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

    aud = (d.get("audience") or DEFAULT_AUDIENCE).strip()
    if aud not in AUDIENCES:
        raise ValidationError(
            f"Audience must be one of: {', '.join(AUDIENCES)}")
    out["audience"] = aud

    pri = (d.get("priority") or DEFAULT_PRIORITY).strip()
    if pri not in PRIORITIES:
        raise ValidationError(
            f"Priority must be one of: {', '.join(PRIORITIES)}")
    out["priority"] = pri

    status = (d.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["author_staff_id"] = _validate_author(d.get("author_staff_id"))
    out["publish_from"]    = _validate_date(d.get("publish_from"),
                                              "Publish from")
    out["publish_until"]   = _validate_date(d.get("publish_until"),
                                              "Publish until")
    if out["publish_from"] and out["publish_until"] \
            and out["publish_until"] < out["publish_from"]:
        raise ValidationError("Publish-until cannot be before publish-from")

    if status == "Published" and not out["publish_from"]:
        out["publish_from"] = _date.today().isoformat()

    out["pinned"] = bool(d.get("pinned"))
    out["attachments_note"] = (
        d.get("attachments_note") or "").strip() or None
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_notice(d: dict[str, Any]) -> Notice:
    init_db()
    try:
        p = _validate_payload(d)
    except ValidationError as e:
        logger.warning("create_notice validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO notices
                 (title, body, category, audience, priority, status,
                  author_staff_id, publish_from, publish_until,
                  pinned, view_count, attachments_note,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?,
                       datetime('now'), datetime('now'))""",
            (p["title"], p["body"], p["category"], p["audience"],
             p["priority"], p["status"], p["author_staff_id"],
             p["publish_from"], p["publish_until"],
             int(p["pinned"]), p["attachments_note"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_notice(new_id)
    assert out is not None
    logger.info("Created notice #%d %r (%s/%s)",
                new_id, p["title"], p["category"], p["status"])
    return out


def get_notice(notice_id: int) -> Notice | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM notices WHERE notice_id = ?",
            (notice_id,)).fetchone()
        return _row(r) if r else None


def list_notices(
    *,
    category: str | None = None,
    audience: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    author_staff_id: str | None = None,
    pinned_only: bool = False,
    published_only: bool = False,
    active_on: str | None = None,
) -> list[Notice]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if category:
        if category not in CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    if audience:
        if audience not in AUDIENCES:
            raise ValidationError(
                f"Audience must be one of: {', '.join(AUDIENCES)}")
        clauses.append("audience = ?")
        args.append(audience)
    if priority:
        if priority not in PRIORITIES:
            raise ValidationError(
                f"Priority must be one of: {', '.join(PRIORITIES)}")
        clauses.append("priority = ?")
        args.append(priority)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if author_staff_id:
        clauses.append("author_staff_id = ?")
        args.append(author_staff_id.strip().upper())
    if pinned_only:
        clauses.append("pinned = 1")
    if published_only:
        clauses.append("status = 'Published'")
    if active_on:
        d = _validate_date(active_on, "active_on", required=True)
        clauses.append("status = 'Published'")
        clauses.append("(publish_from IS NULL OR publish_from <= ?)")
        clauses.append("(publish_until IS NULL OR publish_until >= ?)")
        args.extend([d, d])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM notices {where} "
           "ORDER BY pinned DESC, "
           "CASE priority WHEN 'Urgent' THEN 0 "
           "              WHEN 'High'   THEN 1 "
           "              WHEN 'Normal' THEN 2 "
           "              ELSE 3 END, "
           "COALESCE(publish_from, created_at) DESC, notice_id DESC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def list_notices_with_detail(**kwargs) -> list[NoticeRow]:
    rows = list_notices(**kwargs)
    if not rows:
        return []
        from education_system.sixthform_system.modules.domain.staff import staff as _staff
    names = {t.staff_id: t.full_name for t in _staff.list_staff()}
    return [NoticeRow(notice=n,
                       author_name=(names.get(n.author_staff_id)
                                       if n.author_staff_id else None))
            for n in rows]


def feed(audience: str | None = None,
          *, when: str | None = None) -> list[Notice]:
    """Notices visible to a given audience right now (or on `when`).

    Audience match is exact OR the notice is for "All". (We don't try
    to model 'parents implies all parents' etc — keep it simple.)
    """
    when = when or _date.today().isoformat()
    rows = list_notices(active_on=when)
    if audience is None:
        return rows
    if audience not in AUDIENCES:
        raise ValidationError(
            f"Audience must be one of: {', '.join(AUDIENCES)}")
    return [n for n in rows if n.audience == audience
            or n.audience == "All"]


def search_notices(q: str) -> list[Notice]:
    init_db()
    q = (q or "").strip()
    if not q:
        return list_notices()
    like = f"%{q}%"
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM notices
                WHERE title LIKE ? OR body LIKE ? OR category LIKE ?
                ORDER BY pinned DESC,
                          COALESCE(publish_from, created_at) DESC""",
            (like, like, like),
        ).fetchall()
    return [_row(r) for r in rows]


def update_notice(notice_id: int, d: dict[str, Any]) -> Notice:
    init_db()
    existing = get_notice(notice_id)
    if existing is None:
        raise ValidationError(f"No notice with id {notice_id}")
    merged = {
        "title":            d.get("title", existing.title),
        "body":             d.get("body", existing.body),
        "category":         d.get("category", existing.category),
        "audience":         d.get("audience", existing.audience),
        "priority":         d.get("priority", existing.priority),
        "status":           d.get("status", existing.status),
        "author_staff_id":  d.get("author_staff_id",
                                    existing.author_staff_id),
        "publish_from":     d.get("publish_from",
                                    existing.publish_from),
        "publish_until":    d.get("publish_until",
                                    existing.publish_until),
        "pinned":           d.get("pinned", existing.pinned),
        "attachments_note": d.get("attachments_note",
                                    existing.attachments_note),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE notices SET
                  title=?, body=?, category=?, audience=?, priority=?,
                  status=?, author_staff_id=?, publish_from=?,
                  publish_until=?, pinned=?, attachments_note=?,
                  updated_at=datetime('now')
               WHERE notice_id=?""",
            (p["title"], p["body"], p["category"], p["audience"],
             p["priority"], p["status"], p["author_staff_id"],
             p["publish_from"], p["publish_until"],
             int(p["pinned"]), p["attachments_note"], notice_id),
        )
        conn.commit()
    out = get_notice(notice_id)
    assert out is not None
    logger.info("Updated notice #%d (status=%s)", notice_id, out.status)
    return out


def set_status(notice_id: int, status: str) -> Notice:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_notice(notice_id, {"status": status})


def publish(notice_id: int,
             publish_from: str | None = None,
             publish_until: str | None = None) -> Notice:
    d: dict[str, Any] = {"status": "Published"}
    if publish_from is not None:
        d["publish_from"] = publish_from
    if publish_until is not None:
        d["publish_until"] = publish_until
    return update_notice(notice_id, d)


def archive(notice_id: int) -> Notice:
    return set_status(notice_id, "Archived")


def set_pinned(notice_id: int, pinned: bool) -> Notice:
    return update_notice(notice_id, {"pinned": pinned})


def increment_view(notice_id: int) -> Notice | None:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE notices SET view_count=view_count+1 "
            "WHERE notice_id=?", (notice_id,))
        conn.commit()
        if cur.rowcount == 0:
            return None
    return get_notice(notice_id)


def delete_notice(notice_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM notices WHERE notice_id=?", (notice_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted notice #%d", notice_id)
            return True
        return False


# ── Maintenance ──────────────────────────────────────────────────

def auto_archive_expired(*, when: str | None = None) -> int:
    """Move expired Published notices to Archived. Returns rows affected."""
    init_db()
    today = when or _date.today().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """UPDATE notices SET status='Archived',
                                    updated_at=datetime('now')
                WHERE status='Published'
                  AND publish_until IS NOT NULL
                  AND publish_until < ?""", (today,))
        conn.commit()
        n = cur.rowcount
    if n:
        logger.info("Auto-archived %d expired notice(s)", n)
    return n


# ── Summary ──────────────────────────────────────────────────────

@dataclass
class Summary:
    total: int
    drafts: int
    published: int
    archived: int
    visible_today: int
    pinned: int
    urgent_visible: int
    by_category: dict[str, int]
    by_audience: dict[str, int]
    by_priority: dict[str, int]
    expiring_within: int    # publish_until within N days
    top_viewed: list[tuple[int, str, int]]   # (id, title, views)


def summary(*, expiring_window_days: int = 7) -> Summary:
    import datetime as _dt
    init_db()
    today = _dt.date.today()
    today_s = today.isoformat()
    cutoff = (today + _dt.timedelta(days=expiring_window_days)).isoformat()

    rows = list_notices()
    by_cat = {c: 0 for c in CATEGORIES}
    by_aud = {a: 0 for a in AUDIENCES}
    by_pri = {p: 0 for p in PRIORITIES}
    drafts = published = archived = visible = pinned = urgent_vis = 0
    expiring = 0
    for n in rows:
        by_cat[n.category] = by_cat.get(n.category, 0) + 1
        by_aud[n.audience] = by_aud.get(n.audience, 0) + 1
        by_pri[n.priority] = by_pri.get(n.priority, 0) + 1
        if n.status == "Draft":
            drafts += 1
        elif n.status == "Published":
            published += 1
        elif n.status == "Archived":
            archived += 1
        if n.is_visible_on(today_s):
            visible += 1
            if n.pinned:
                pinned += 1
            if n.priority == "Urgent":
                urgent_vis += 1
            if n.publish_until and today_s <= n.publish_until <= cutoff:
                expiring += 1

    top = sorted(rows, key=lambda x: -x.view_count)[:5]
    top_viewed = [(n.notice_id, n.title, n.view_count) for n in top]

    return Summary(
        total=len(rows), drafts=drafts, published=published,
        archived=archived, visible_today=visible, pinned=pinned,
        urgent_visible=urgent_vis,
        by_category=by_cat, by_audience=by_aud, by_priority=by_pri,
        expiring_within=expiring, top_viewed=top_viewed,
    )
