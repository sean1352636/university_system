"""Domain layer for Parent Messaging (Nursery System).

Owns the ``parent_messages`` table — the two-way message log between the
setting and parents / carers. Records outgoing messages sent by staff (via App,
Email, SMS, Phone, or In-person) and incoming messages received from parents,
together with the status of each message (draft / sent / read / replied).

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``messaging_cli.py``, Tk GUI in ``messaging_views.py``.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Parent Messaging"
CATEGORY = "Parents & Communication"

ID_PREFIX = "NMS"
ID_DIGITS = 3

DIRECTIONS = ("outgoing", "incoming")
CHANNELS = ("App", "Email", "SMS", "Phone", "In person")
STATUSES = ("draft", "sent", "read", "replied")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid parent-message input."""


@dataclass
class Message:
    message_id: str
    pupil_id: str
    direction: str
    channel: str | None
    subject: str
    body: str | None
    message_date: str | None
    staff_id: str | None
    status: str
    created_at: str | None
    child_name: str | None = None
    room: str | None = None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for parent messaging")
        raise


_SELECT = """
SELECT pm.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS staff_name
FROM parent_messages pm
LEFT JOIN pupils p ON p.pupil_id = pm.pupil_id
LEFT JOIN staff s ON s.staff_id = pm.staff_id
"""


def _row(r: sqlite3.Row) -> Message:
    keys = r.keys()
    return Message(
        message_id=r["message_id"],
        pupil_id=r["pupil_id"],
        direction=r["direction"],
        channel=r["channel"],
        subject=r["subject"],
        body=r["body"],
        message_date=r["message_date"],
        staff_id=r["staff_id"],
        status=r["status"],
        created_at=r["created_at"] if "created_at" in keys else None,
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        staff_name=(r["staff_name"] or None) if "staff_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    direction = (data.get("direction") or "outgoing").strip()
    if direction not in DIRECTIONS:
        raise ValidationError(
            "Direction must be one of: " + ", ".join(DIRECTIONS))
    out["direction"] = direction

    channel = (data.get("channel") or "").strip()
    if channel and channel not in CHANNELS:
        raise ValidationError(
            "Channel must be one of: " + ", ".join(CHANNELS))
    out["channel"] = channel or None

    subject = (data.get("subject") or "").strip()
    if not subject:
        raise ValidationError("Subject is required")
    out["subject"] = subject

    out["body"] = _opt(data.get("body"))
    out["message_date"] = _opt_date(data.get("message_date"), "Message date")
    out["staff_id"] = _opt(data.get("staff_id"))

    status = (data.get("status") or "sent").strip()
    if status not in STATUSES:
        raise ValidationError(
            "Status must be one of: " + ", ".join(STATUSES))
    out["status"] = status

    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_message_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT message_id FROM parent_messages").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing parent-message ids")
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
    raise RuntimeError("Could not allocate a unique parent-message id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_messages(*, pupil_id: str | None = None) -> list[Message]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE pm.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY pm.message_date DESC, pm.message_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_messages failed")
        raise
    return [_row(r) for r in rows]


def get_message(message_id: str) -> Message | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE pm.message_id = ?", (message_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_message(%s) failed", message_id)
        raise
    return _row(row) if row else None


def list_pupil_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_pupil_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"],
                    f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out


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


# ── Writes ───────────────────────────────────────────────────────────────────

def create_message(data: dict[str, Any]) -> Message:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    mid = generate_message_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO parent_messages (
                    message_id, pupil_id, direction, channel, subject, body,
                    message_date, staff_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (mid, payload["pupil_id"], payload["direction"],
                 payload["channel"], payload["subject"], payload["body"],
                 payload["message_date"], payload["staff_id"],
                 payload["status"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for parent-message id=%s", mid)
        raise ValidationError(f"Could not create message — {e}") from e
    m = get_message(mid)
    assert m is not None
    logger.info("Created parent message %s for pupil %s", mid, payload["pupil_id"])
    return m


def update_message(message_id: str, data: dict[str, Any]) -> Message:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_message(message_id)
    if existing is None:
        raise ValidationError(f"No parent message with id {message_id}")
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE parent_messages SET
                    direction = ?, channel = ?, subject = ?, body = ?,
                    message_date = ?, staff_id = ?, status = ?
                WHERE message_id = ?
                """,
                (payload["direction"], payload["channel"], payload["subject"],
                 payload["body"], payload["message_date"], payload["staff_id"],
                 payload["status"], message_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No parent message with id {message_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for parent-message id=%s", message_id)
        raise ValidationError(f"Could not update message — {e}") from e
    m = get_message(message_id)
    assert m is not None
    logger.info("Updated parent message %s", message_id)
    return m


def delete_message(message_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM parent_messages WHERE message_id = ?", (message_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting parent-message id=%s", message_id)
        raise
    if deleted:
        logger.info("Deleted parent message %s", message_id)
    return deleted
