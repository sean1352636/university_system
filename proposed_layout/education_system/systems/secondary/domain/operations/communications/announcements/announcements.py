"""Announcements data layer for Secondary School System.

Site-wide announcements / news / banners. Distinct from the
`notices` module which carries formal school-wide bulletin items;
announcements are more dynamic (status banners, breaking news,
celebrations, urgent communications) with audience targeting,
pin / banner flags, scheduled publish + auto-expiry.

Single table.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.systems.secondary.infrastructure import paths as _paths

logger = logging.getLogger(__name__)

CATEGORIES: tuple[str, ...] = (
    "General",
    "Whole-School",
    "Safeguarding",
    "Examinations",
    "Sport",
    "Trips & Visits",
    "Achievements",
    "Wellbeing",
    "Whole School",
    "Year 12",
    "Year 13",
    "Parents",
    "Staff",
    "Emergency",
    "Weather",
    "IT / Systems",
    "Other",
)
DEFAULT_CATEGORY = "General"

AUDIENCES: tuple[str, ...] = (
    "students",
    "staff",
    "parents",
    "governors",
    "public",
    "alumni",
    "visitors",
)
DEFAULT_AUDIENCES = ("students", "staff")

PRIORITIES: tuple[int, ...] = (1, 2, 3, 4, 5)
_PRIORITY_LABELS = {
    1: "Low",
    2: "Normal",
    3: "Important",
    4: "High",
    5: "Urgent",
}


def priority_label(p: int | None) -> str:
    if p is None:
        return "—"
    return _PRIORITY_LABELS.get(p, "Unknown")


STATUSES: tuple[str, ...] = (
    "Draft",
    "Scheduled",
    "Published",
    "Expired",
    "Archived",
    "Withdrawn",
)
DEFAULT_STATUS = "Draft"


class ValidationError(Exception):
    pass


@dataclass
class Announcement:
    announcement_id: int
    title: str
    body: str | None
    summary: str | None
    category: str
    priority: int
    audiences: str
    pinned: bool
    banner: bool
    author: str | None
    publish_on: str | None
    expires_on: str | None
    published_on: str | None
    requires_acknowledgement: bool
    comments_enabled: bool
    view_count: int
    attachments_ref: str | None
    linked_to: str | None
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def audience_list(self) -> list[str]:
        if not self.audiences:
            return []
        return [a.strip() for a in self.audiences.split(",")
                  if a.strip()]

    @property
    def is_published(self) -> bool:
        return self.status == "Published"

    @property
    def is_live(self) -> bool:
        """Currently visible to its audience."""
        if not self.is_published:
            return False
        today = _dt.date.today().isoformat()
        if self.publish_on and self.publish_on > today:
            return False
        if self.expires_on and self.expires_on < today:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        if not self.expires_on or self.status == "Archived":
            return False
        return self.expires_on < _dt.date.today().isoformat()

    @property
    def is_scheduled_future(self) -> bool:
        if not self.publish_on:
            return False
        return self.publish_on > _dt.date.today().isoformat()

    @property
    def priority_label(self) -> str:
        return priority_label(self.priority)


@dataclass
class AnnouncementsSummary:
    total: int = 0
    drafts: int = 0
    scheduled: int = 0
    published: int = 0
    live_now: int = 0
    expired_unarchived: int = 0
    pinned: int = 0
    banners: int = 0
    urgent_count: int = 0
    total_views: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_priority: dict[int, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_audience: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.ANNOUNCEMENTS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT,
                summary TEXT,
                category TEXT NOT NULL,
                priority INTEGER NOT NULL,
                audiences TEXT NOT NULL,
                pinned INTEGER NOT NULL DEFAULT 0,
                banner INTEGER NOT NULL DEFAULT 0,
                author TEXT,
                publish_on TEXT,
                expires_on TEXT,
                published_on TEXT,
                requires_acknowledgement INTEGER NOT NULL DEFAULT 0,
                comments_enabled INTEGER NOT NULL DEFAULT 0,
                view_count INTEGER NOT NULL DEFAULT 0,
                attachments_ref TEXT,
                linked_to TEXT,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _validate_audiences(value: Any) -> list[str]:
    if value is None:
        return list(DEFAULT_AUDIENCES)
    if isinstance(value, str):
        parts = [a.strip() for a in value.split(",")
                   if a.strip()]
    elif isinstance(value, (list, tuple)):
        parts = [str(a).strip() for a in value
                   if str(a).strip()]
    else:
        raise ValidationError(
            "Audiences must be a list or comma-separated string")
    if not parts:
        raise ValidationError("At least one audience is required")
    for a in parts:
        if a not in AUDIENCES:
            raise ValidationError(
                f"Audience {a!r} must be one of: "
                f"{', '.join(AUDIENCES)}")
    return parts


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

    try:
        pr = int(out.get("priority") or 2)
    except (TypeError, ValueError):
        raise ValidationError("Priority must be 1-5")
    if pr not in PRIORITIES:
        raise ValidationError("Priority must be 1-5")
    out["priority"] = pr

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    _check_date("Publish on",   out.get("publish_on"))
    _check_date("Expires on",   out.get("expires_on"))
    _check_date("Published on", out.get("published_on"))
    if (out.get("publish_on") and out.get("expires_on")
            and out["expires_on"] < out["publish_on"]):
        raise ValidationError(
            "Expires on must be on or after publish on")

    audiences = _validate_audiences(out.get("audiences"))
    out["audiences"] = ",".join(audiences)

    for k in ("body", "summary", "author",
               "attachments_ref", "linked_to", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("publish_on", "expires_on", "published_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    for k in ("pinned", "banner", "requires_acknowledgement",
               "comments_enabled"):
        out[k] = bool(out.get(k))

    vc = out.get("view_count")
    if vc in (None, ""):
        out["view_count"] = 0
    else:
        try:
            out["view_count"] = int(vc)
        except (TypeError, ValueError):
            raise ValidationError(
                "View count must be an integer")
        if out["view_count"] < 0:
            raise ValidationError("View count must be >= 0")
    return out


def _row(r: sqlite3.Row) -> Announcement:
    return Announcement(
        announcement_id=r["announcement_id"],
        title=r["title"],
        body=r["body"],
        summary=r["summary"],
        category=r["category"],
        priority=r["priority"],
        audiences=r["audiences"],
        pinned=bool(r["pinned"]),
        banner=bool(r["banner"]),
        author=r["author"],
        publish_on=r["publish_on"],
        expires_on=r["expires_on"],
        published_on=r["published_on"],
        requires_acknowledgement=bool(
            r["requires_acknowledgement"]),
        comments_enabled=bool(r["comments_enabled"]),
        view_count=r["view_count"],
        attachments_ref=r["attachments_ref"],
        linked_to=r["linked_to"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_announcement(payload: dict[str, Any]) -> Announcement:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO announcements (
              title, body, summary, category, priority,
              audiences, pinned, banner, author,
              publish_on, expires_on, published_on,
              requires_acknowledgement, comments_enabled,
              view_count, attachments_ref, linked_to,
              status, notes, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["title"], p["body"], p["summary"],
            p["category"], p["priority"], p["audiences"],
            1 if p["pinned"] else 0,
            1 if p["banner"] else 0,
            p["author"], p["publish_on"], p["expires_on"],
            p["published_on"],
            1 if p["requires_acknowledgement"] else 0,
            1 if p["comments_enabled"] else 0,
            p["view_count"], p["attachments_ref"],
            p["linked_to"], p["status"], p["notes"],
            now, now,
        ))
        new_id = cur.lastrowid
    return get_announcement(new_id)


def update_announcement(announcement_id: int,
                            payload: dict[str, Any]
                            ) -> Announcement:
    init_db()
    if get_announcement(announcement_id) is None:
        raise ValidationError(
            f"No announcement with id {announcement_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE announcements SET
              title=?, body=?, summary=?, category=?, priority=?,
              audiences=?, pinned=?, banner=?, author=?,
              publish_on=?, expires_on=?, published_on=?,
              requires_acknowledgement=?, comments_enabled=?,
              view_count=?, attachments_ref=?, linked_to=?,
              status=?, notes=?, updated_on=?
            WHERE announcement_id=?
        """, (
            p["title"], p["body"], p["summary"],
            p["category"], p["priority"], p["audiences"],
            1 if p["pinned"] else 0,
            1 if p["banner"] else 0,
            p["author"], p["publish_on"], p["expires_on"],
            p["published_on"],
            1 if p["requires_acknowledgement"] else 0,
            1 if p["comments_enabled"] else 0,
            p["view_count"], p["attachments_ref"],
            p["linked_to"], p["status"], p["notes"],
            now, announcement_id,
        ))
    return get_announcement(announcement_id)


def delete_announcement(announcement_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM announcements WHERE announcement_id=?",
            (announcement_id,))
        return cur.rowcount > 0


def get_announcement(announcement_id: int) -> Announcement | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM announcements "
            "WHERE announcement_id=?",
            (announcement_id,)).fetchone()
        return _row(r) if r else None


def list_announcements(*,
                            category: str | None = None,
                            status: str | None = None,
                            priority: int | None = None,
                            priority_min: int | None = None,
                            audience: str | None = None,
                            author_like: str | None = None,
                            title_like: str | None = None,
                            published_only: bool = False,
                            live_only: bool = False,
                            pinned_only: bool = False,
                            banner_only: bool = False,
                            scheduled_only: bool = False,
                            expired_unarchived: bool = False,
                            date_from: str | None = None,
                            date_to: str | None = None,
                            ) -> list[Announcement]:
    init_db()
    sql = "SELECT * FROM announcements WHERE 1=1"
    params: list[Any] = []
    if category:
        sql += " AND category=?"
        params.append(category)
    if status:
        sql += " AND status=?"
        params.append(status)
    if priority is not None:
        sql += " AND priority=?"
        params.append(priority)
    if priority_min is not None:
        sql += " AND priority >= ?"
        params.append(priority_min)
    if audience:
        if audience not in AUDIENCES:
            raise ValidationError(
                f"Audience must be one of: "
                f"{', '.join(AUDIENCES)}")
        sql += " AND audiences LIKE ?"
        params.append(f"%{audience}%")
    if author_like:
        sql += " AND author LIKE ?"
        params.append(f"%{author_like}%")
    if title_like:
        sql += " AND title LIKE ?"
        params.append(f"%{title_like}%")
    if published_only:
        sql += " AND status='Published'"
    if pinned_only:
        sql += " AND pinned=1"
    if banner_only:
        sql += " AND banner=1"
    if scheduled_only:
        sql += " AND status='Scheduled'"
    today = _dt.date.today().isoformat()
    if live_only:
        sql += (" AND status='Published'"
                  " AND (publish_on IS NULL OR publish_on <= ?)"
                  " AND (expires_on IS NULL OR expires_on >= ?)")
        params.extend([today, today])
    if expired_unarchived:
        sql += (" AND expires_on IS NOT NULL"
                  " AND expires_on < ?"
                  " AND status NOT IN ('Archived','Withdrawn')")
        params.append(today)
    if date_from:
        _check_date("From", date_from)
        sql += (" AND (publish_on >= ? OR "
                  " (publish_on IS NULL AND created_on >= ?))")
        params.extend([date_from, date_from])
    if date_to:
        _check_date("To", date_to)
        sql += (" AND (publish_on <= ? OR "
                  " (publish_on IS NULL AND created_on <= ?))")
        params.extend([date_to, date_to])
    sql += (" ORDER BY pinned DESC, priority DESC,"
              " COALESCE(publish_on, created_on) DESC,"
              " announcement_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


# ── Workflow ──────────────────────────────────────────────

def _to_dict(a: Announcement) -> dict[str, Any]:
    return {
        "title": a.title,
        "body": a.body,
        "summary": a.summary,
        "category": a.category,
        "priority": a.priority,
        "audiences": a.audiences,
        "pinned": a.pinned,
        "banner": a.banner,
        "author": a.author,
        "publish_on": a.publish_on,
        "expires_on": a.expires_on,
        "published_on": a.published_on,
        "requires_acknowledgement": a.requires_acknowledgement,
        "comments_enabled": a.comments_enabled,
        "view_count": a.view_count,
        "attachments_ref": a.attachments_ref,
        "linked_to": a.linked_to,
        "status": a.status,
        "notes": a.notes,
    }


def publish(announcement_id: int, *,
                published_on: str | None = None) -> Announcement:
    a = get_announcement(announcement_id)
    if a is None:
        raise ValidationError(
            f"No announcement with id {announcement_id}")
    data = _to_dict(a)
    data["status"] = "Published"
    data["published_on"] = (published_on
                                 or _dt.date.today().isoformat())
    return update_announcement(announcement_id, data)


def schedule(announcement_id: int, *,
                  publish_on: str) -> Announcement:
    _check_date("Publish on", publish_on)
    a = get_announcement(announcement_id)
    if a is None:
        raise ValidationError(
            f"No announcement with id {announcement_id}")
    data = _to_dict(a)
    data["publish_on"] = publish_on
    data["status"] = "Scheduled"
    return update_announcement(announcement_id, data)


def withdraw(announcement_id: int) -> Announcement:
    a = get_announcement(announcement_id)
    if a is None:
        raise ValidationError(
            f"No announcement with id {announcement_id}")
    return update_announcement(announcement_id,
                                     {**_to_dict(a),
                                       "status": "Withdrawn"})


def archive(announcement_id: int) -> Announcement:
    a = get_announcement(announcement_id)
    if a is None:
        raise ValidationError(
            f"No announcement with id {announcement_id}")
    return update_announcement(announcement_id,
                                     {**_to_dict(a),
                                       "status": "Archived"})


def expire(announcement_id: int) -> Announcement:
    a = get_announcement(announcement_id)
    if a is None:
        raise ValidationError(
            f"No announcement with id {announcement_id}")
    return update_announcement(announcement_id,
                                     {**_to_dict(a),
                                       "status": "Expired"})


def toggle_pin(announcement_id: int) -> Announcement:
    a = get_announcement(announcement_id)
    if a is None:
        raise ValidationError(
            f"No announcement with id {announcement_id}")
    return update_announcement(announcement_id,
                                     {**_to_dict(a),
                                       "pinned": not a.pinned})


def toggle_banner(announcement_id: int) -> Announcement:
    a = get_announcement(announcement_id)
    if a is None:
        raise ValidationError(
            f"No announcement with id {announcement_id}")
    return update_announcement(announcement_id,
                                     {**_to_dict(a),
                                       "banner": not a.banner})


def increment_views(announcement_id: int,
                          n: int = 1) -> Announcement:
    a = get_announcement(announcement_id)
    if a is None:
        raise ValidationError(
            f"No announcement with id {announcement_id}")
    return update_announcement(announcement_id,
                                     {**_to_dict(a),
                                       "view_count":
                                       a.view_count + max(0, n)})


def set_status(announcement_id: int,
                    new_status: str) -> Announcement:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    a = get_announcement(announcement_id)
    if a is None:
        raise ValidationError(
            f"No announcement with id {announcement_id}")
    return update_announcement(announcement_id,
                                     {**_to_dict(a),
                                       "status": new_status})


def auto_expire() -> int:
    """Move expired Published announcements to Expired status.
    Returns rows updated."""
    init_db()
    today = _dt.date.today().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE announcements SET status='Expired',"
            " updated_on=? "
            "WHERE status='Published'"
            " AND expires_on IS NOT NULL"
            " AND expires_on < ?",
            (_dt.datetime.now().isoformat(timespec="seconds"),
             today))
        return cur.rowcount


# ── Summary ─────────────────────────────────────────────

def summary() -> AnnouncementsSummary:
    rows = list_announcements()
    out = AnnouncementsSummary(total=len(rows))
    if not rows:
        return out
    today = _dt.date.today().isoformat()
    for a in rows:
        if a.status == "Draft":
            out.drafts += 1
        elif a.status == "Scheduled":
            out.scheduled += 1
        elif a.status == "Published":
            out.published += 1
            if a.is_live:
                out.live_now += 1
        if (a.expires_on and a.expires_on < today
                and a.status not in ("Archived", "Withdrawn",
                                              "Expired")):
            out.expired_unarchived += 1
        if a.pinned:
            out.pinned += 1
        if a.banner:
            out.banners += 1
        if a.priority >= 4:
            out.urgent_count += 1
        out.total_views += a.view_count
        out.by_category[a.category] = (
            out.by_category.get(a.category, 0) + 1)
        out.by_priority[a.priority] = (
            out.by_priority.get(a.priority, 0) + 1)
        out.by_status[a.status] = (
            out.by_status.get(a.status, 0) + 1)
        for aud in a.audience_list:
            out.by_audience[aud] = (
                out.by_audience.get(aud, 0) + 1)
    return out


__all__ = [
    "CATEGORIES", "DEFAULT_CATEGORY",
    "AUDIENCES", "DEFAULT_AUDIENCES",
    "PRIORITIES", "priority_label",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "Announcement", "AnnouncementsSummary",
    "init_db",
    "create_announcement", "update_announcement",
    "delete_announcement", "get_announcement",
    "list_announcements",
    "publish", "schedule", "withdraw", "archive",
    "expire", "toggle_pin", "toggle_banner",
    "increment_views", "set_status", "auto_expire",
    "summary",
]
