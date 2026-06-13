"""Domain layer for the Email / Messaging centre (Nursery System).

Owns the ``email_messages`` table — the setting's outbound/inbound email log.
It mirrors the "Email / Messaging" feature the other systems carry
(``primarysch_system`` ``messages``): a single log of messages with a
from/to address pair, a direction, channel, category, priority and status, plus
optional links to a child on roll and the staff member who handled it.

Unlike ``messaging`` (Parent Messaging), a message here is addressed by email
address rather than always tied to a child, so newsletters, admissions enquiries
and supplier mail all fit the same log.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``email_centre_cli.py``, Tk GUI in ``email_centre_views.py``. The table is
created on demand inside the shared ``nursery.db`` (``CREATE TABLE IF NOT
EXISTS``), matching how the other ported modules manage their own tables.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from education_system.nursery_system.core.database import connect

logger = logging.getLogger(__name__)

FEATURE_NAME = "Email / Messaging"
CATEGORY = "Parents & Communication"

ID_PREFIX = "NEM"
ID_DIGITS = 4

DIRECTIONS = ("Outgoing", "Incoming")
CHANNELS = ("Email", "SMS", "App", "Letter")
CATEGORIES = (
    "General",
    "Admissions",
    "Funding",
    "Safeguarding",
    "Newsletter",
    "Reminder",
)
PRIORITIES = ("Low", "Normal", "High")
STATUSES = ("Draft", "Sent", "Received", "Failed")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS email_messages (
    message_id    TEXT PRIMARY KEY,
    direction     TEXT NOT NULL,
    channel       TEXT NOT NULL,
    category      TEXT NOT NULL,
    priority      TEXT NOT NULL,
    status        TEXT NOT NULL,
    subject       TEXT NOT NULL,
    body          TEXT,
    from_name     TEXT,
    from_address  TEXT,
    to_name       TEXT,
    to_address    TEXT,
    pupil_id      TEXT,
    staff_id      TEXT,
    tags          TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    sent_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_email_status    ON email_messages(status);
CREATE INDEX IF NOT EXISTS idx_email_direction ON email_messages(direction);
CREATE INDEX IF NOT EXISTS idx_email_pupil     ON email_messages(pupil_id);
"""


class ValidationError(ValueError):
    """Raised for invalid email-message input."""


@dataclass
class EmailMessage:
    message_id: str
    direction: str
    channel: str
    category: str
    priority: str
    status: str
    subject: str
    body: str | None
    from_name: str | None
    from_address: str | None
    to_name: str | None
    to_address: str | None
    pupil_id: str | None
    staff_id: str | None
    tags: str | None
    created_at: str | None
    sent_at: str | None
    # Joined display fields (not stored).
    child_name: str | None = None
    staff_name: str | None = None


_DB_READY = False


def init_db() -> None:
    """Create the email-messages table (idempotent)."""
    global _DB_READY
    if _DB_READY:
        return
    try:
        with connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to initialise email_messages table")
        raise
    _DB_READY = True


_SELECT = """
SELECT e.*,
       TRIM(COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, ''))
           AS child_name,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS staff_name
FROM email_messages e
LEFT JOIN pupils p ON p.pupil_id = e.pupil_id
LEFT JOIN staff s ON s.staff_id = e.staff_id
"""


def _row(r: sqlite3.Row) -> EmailMessage:
    keys = r.keys()
    return EmailMessage(
        message_id=r["message_id"],
        direction=r["direction"],
        channel=r["channel"],
        category=r["category"],
        priority=r["priority"],
        status=r["status"],
        subject=r["subject"],
        body=r["body"],
        from_name=r["from_name"],
        from_address=r["from_address"],
        to_name=r["to_name"],
        to_address=r["to_address"],
        pupil_id=r["pupil_id"],
        staff_id=r["staff_id"],
        tags=r["tags"],
        created_at=r["created_at"] if "created_at" in keys else None,
        sent_at=r["sent_at"] if "sent_at" in keys else None,
        child_name=(r["child_name"] or None) if "child_name" in keys else None,
        staff_name=(r["staff_name"] or None) if "staff_name" in keys else None,
    )


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: Any) -> str | None:
    v = ("" if value is None else str(value)).strip()
    return v or None


def _one_of(value: Any, allowed: tuple[str, ...], label: str, default: str) -> str:
    v = ("" if value is None else str(value)).strip() or default
    if v not in allowed:
        raise ValidationError(f"{label} must be one of: " + ", ".join(allowed))
    return v


def _email(value: Any, label: str) -> str | None:
    v = _opt(value)
    if v and not _EMAIL_RE.match(v):
        raise ValidationError(f"{label} is not a valid email address")
    return v


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["direction"] = _one_of(data.get("direction"), DIRECTIONS, "Direction",
                               "Outgoing")
    out["channel"] = _one_of(data.get("channel"), CHANNELS, "Channel", "Email")
    out["category"] = _one_of(data.get("category"), CATEGORIES, "Category",
                              "General")
    out["priority"] = _one_of(data.get("priority"), PRIORITIES, "Priority",
                              "Normal")
    out["status"] = _one_of(data.get("status"), STATUSES, "Status", "Draft")

    subject = (data.get("subject") or "").strip()
    if not subject:
        raise ValidationError("Subject is required")
    out["subject"] = subject

    out["body"] = _opt(data.get("body"))
    out["from_name"] = _opt(data.get("from_name"))
    out["from_address"] = _email(data.get("from_address"), "From address")
    out["to_name"] = _opt(data.get("to_name"))
    out["to_address"] = _email(data.get("to_address"), "To address")
    out["pupil_id"] = _opt(data.get("pupil_id"))
    out["staff_id"] = _opt(data.get("staff_id"))
    out["tags"] = _opt(data.get("tags"))

    # An outgoing email must have somewhere to go.
    if out["direction"] == "Outgoing" and out["channel"] == "Email" \
            and not out["to_address"]:
        raise ValidationError("An outgoing email needs a To address")
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_message_id() -> str:
    init_db()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT message_id FROM email_messages").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing email-message ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        mid = f"{ID_PREFIX}{n}"
        if mid not in existing:
            return mid
    raise RuntimeError("Could not allocate a unique email-message id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_messages(*, direction: str | None = None,
                  status: str | None = None) -> list[EmailMessage]:
    init_db()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if direction:
        clauses.append("e.direction = ?")
        params.append(direction)
    if status:
        clauses.append("e.status = ?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY COALESCE(e.sent_at, e.created_at) DESC, e.message_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_messages failed")
        raise
    return [_row(r) for r in rows]


def get_message(message_id: str) -> EmailMessage | None:
    init_db()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE e.message_id = ?", (message_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_message(%s) failed", message_id)
        raise
    return _row(row) if row else None


def search_messages(query: str) -> list[EmailMessage]:
    init_db()
    like = f"%{(query or '').strip()}%"
    sql = _SELECT + """
        WHERE e.subject LIKE ?
           OR e.body LIKE ?
           OR e.to_address LIKE ?
           OR e.to_name LIKE ?
           OR e.from_address LIKE ?
           OR e.message_id LIKE ?
        ORDER BY COALESCE(e.sent_at, e.created_at) DESC, e.message_id DESC
    """
    try:
        with connect() as conn:
            rows = conn.execute(sql, [like] * 6).fetchall()
    except sqlite3.Error:
        logger.exception("search_messages failed")
        raise
    return [_row(r) for r in rows]


def list_pupil_choices() -> list[tuple[str, str]]:
    init_db()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, parent_email FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_pupil_choices failed")
        raise
    return [(r["pupil_id"],
             f"{r['first_name']} {r['last_name']} ({r['pupil_id']})") for r in rows]


def recipient_directory() -> list[dict[str, Any]]:
    """Unified list of everyone the Compose dialog can target.

    Mirrors the other systems' recipient picker: parents (one per child on
    roll, addressed via their parent/carer email) followed by staff. Each entry
    carries the fields needed to auto-fill a message row when picked:
    ``label`` (shown in the dropdown), ``to_name``, ``to_address``,
    ``pupil_id``, ``staff_id`` and a ``kind`` used for the routing chip.
    """
    init_db()
    entries: list[dict[str, Any]] = []
    try:
        with connect() as conn:
            pupils = conn.execute(
                "SELECT pupil_id, first_name, last_name, room, parent_name, "
                "parent_email FROM pupils WHERE status = 'active' "
                "ORDER BY last_name, first_name").fetchall()
            staff = conn.execute(
                "SELECT staff_id, first_name, last_name, role, email FROM staff "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("recipient_directory failed")
        raise

    for p in pupils:
        child = f"{p['first_name']} {p['last_name']}"
        carer = p["parent_name"] or f"Parent of {child}"
        email = p["parent_email"] or ""
        room = f" — {p['room']}" if p["room"] else ""
        entries.append({
            "kind": "Parent",
            "label": f"{carer} (parent of {child}){room}"
                     + (f" — {email}" if email else " — no email on file"),
            "to_name": carer,
            "to_address": email,
            "pupil_id": p["pupil_id"],
            "staff_id": "",
        })
    for s in staff:
        name = f"{s['first_name']} {s['last_name']}"
        entries.append({
            "kind": "Staff",
            "label": f"{name} ({s['role']}) — {s['email']}",
            "to_name": name,
            "to_address": s["email"] or "",
            "pupil_id": "",
            "staff_id": s["staff_id"],
        })
    return entries


def pupil_parent_email(pupil_id: str) -> tuple[str | None, str | None]:
    """Return ``(parent_name, parent_email)`` for a child, for prefilling."""
    init_db()
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT parent_name, parent_email FROM pupils WHERE pupil_id = ?",
                (pupil_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("pupil_parent_email(%s) failed", pupil_id)
        raise
    if row is None:
        return (None, None)
    return (row["parent_name"], row["parent_email"])


# ── Writes ───────────────────────────────────────────────────────────────────

def create_message(data: dict[str, Any]) -> EmailMessage:
    init_db()
    payload = _validate(data)
    if payload["status"] == "Sent" and not data.get("sent_at"):
        payload["sent_at"] = _now()
    else:
        payload["sent_at"] = _opt(data.get("sent_at"))
    mid = generate_message_id()
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO email_messages (
                    message_id, direction, channel, category, priority, status,
                    subject, body, from_name, from_address, to_name, to_address,
                    pupil_id, staff_id, tags, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (mid, payload["direction"], payload["channel"],
                 payload["category"], payload["priority"], payload["status"],
                 payload["subject"], payload["body"], payload["from_name"],
                 payload["from_address"], payload["to_name"],
                 payload["to_address"], payload["pupil_id"], payload["staff_id"],
                 payload["tags"], payload["sent_at"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("INSERT failed for email-message id=%s", mid)
        raise ValidationError(f"Could not create message — {e}") from e
    m = get_message(mid)
    assert m is not None
    logger.info("Created email message %s ('%s', %s)",
                mid, m.subject, m.status)
    return m


def update_message(message_id: str, data: dict[str, Any]) -> EmailMessage:
    init_db()
    payload = _validate(data)
    if get_message(message_id) is None:
        raise ValidationError(f"No email message with id {message_id}")
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE email_messages SET
                    direction = ?, channel = ?, category = ?, priority = ?,
                    status = ?, subject = ?, body = ?, from_name = ?,
                    from_address = ?, to_name = ?, to_address = ?, pupil_id = ?,
                    staff_id = ?, tags = ?
                WHERE message_id = ?
                """,
                (payload["direction"], payload["channel"], payload["category"],
                 payload["priority"], payload["status"], payload["subject"],
                 payload["body"], payload["from_name"], payload["from_address"],
                 payload["to_name"], payload["to_address"], payload["pupil_id"],
                 payload["staff_id"], payload["tags"], message_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No email message with id {message_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for email-message id=%s", message_id)
        raise ValidationError(f"Could not update message — {e}") from e
    m = get_message(message_id)
    assert m is not None
    logger.info("Updated email message %s", message_id)
    return m


def send_message(message_id: str) -> EmailMessage:
    """Mark a draft as Sent and stamp ``sent_at`` (the demo's 'deliver')."""
    init_db()
    existing = get_message(message_id)
    if existing is None:
        raise ValidationError(f"No email message with id {message_id}")
    if existing.direction != "Outgoing":
        raise ValidationError("Only outgoing messages can be sent")
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE email_messages SET status = 'Sent', sent_at = ? "
                "WHERE message_id = ?", (_now(), message_id))
            conn.commit()
    except sqlite3.Error:
        logger.exception("send_message(%s) failed", message_id)
        raise
    m = get_message(message_id)
    assert m is not None
    logger.info("Sent email message %s to %s", message_id, m.to_address or "-")
    return m


def delete_message(message_id: str) -> bool:
    init_db()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM email_messages WHERE message_id = ?", (message_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting email-message id=%s", message_id)
        raise
    if deleted:
        logger.info("Deleted email message %s", message_id)
    return deleted


@dataclass
class Summary:
    total: int
    sent: int
    drafts: int
    incoming: int
    failed: int


def summary() -> Summary:
    init_db()
    try:
        with connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'Sent' THEN 1 ELSE 0 END) AS sent,
                    SUM(CASE WHEN status = 'Draft' THEN 1 ELSE 0 END) AS drafts,
                    SUM(CASE WHEN direction = 'Incoming' THEN 1 ELSE 0 END)
                        AS incoming,
                    SUM(CASE WHEN status = 'Failed' THEN 1 ELSE 0 END) AS failed
                FROM email_messages
                """).fetchone()
    except sqlite3.Error:
        logger.exception("summary failed")
        raise
    return Summary(
        total=row["total"] or 0,
        sent=row["sent"] or 0,
        drafts=row["drafts"] or 0,
        incoming=row["incoming"] or 0,
        failed=row["failed"] or 0,
    )
