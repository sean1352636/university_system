"""Email / Messaging log for the Sixth Form System.

This module is a **log**, not an SMTP gateway — it records every
communication the school sends or receives (email, SMS, letter,
phone, in-person, portal). Use it to:

* compose drafts and "send" them (which simply flips status to Sent
  and stamps ``sent_at``);
* log incoming messages from parents/students;
* group related messages with a ``thread_id`` (auto-generated for a
  new thread; passed to ``reply()`` to continue an existing one);
* bulk-send: one message body to many students/contacts/staff,
  recorded as one row per recipient sharing a thread.

Soft links:
* ``student_id`` (who the message is about, optional)
* ``staff_id`` (who handled it on our side, optional)
* ``parent_contact_id`` (the specific parent contact, optional)

All three use ``ON DELETE SET NULL`` so we keep the historical log
even when those records are removed.
"""

from __future__ import annotations

import logging
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from education_system.post_16.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.MESSAGES_DB

DIRECTIONS: tuple[str, ...] = ("Outgoing", "Incoming")
DEFAULT_DIRECTION: str = "Outgoing"

CHANNELS: tuple[str, ...] = (
    "Email", "SMS", "Letter", "Phone Call",
    "In-Person Meeting", "Portal", "Other",
)
DEFAULT_CHANNEL: str = "Email"

STATUSES: tuple[str, ...] = (
    "Draft", "Queued", "Sent", "Delivered", "Failed",
    "Read", "Replied", "Received",
)
DEFAULT_STATUS: str = "Draft"
TERMINAL_STATUSES: tuple[str, ...] = (
    "Sent", "Delivered", "Failed", "Read", "Replied", "Received")
SENT_STATUSES: tuple[str, ...] = (
    "Sent", "Delivered", "Read", "Replied")

PRIORITIES: tuple[str, ...] = ("Low", "Normal", "High", "Urgent")
DEFAULT_PRIORITY: str = "Normal"

CATEGORIES: tuple[str, ...] = (
    "General", "Academic", "Attendance", "Behaviour",
    "Pastoral", "Safeguarding", "UCAS", "Careers",
    "Exams", "Finance", "Trips", "Library", "Closure / Weather",
    "Other",
)
DEFAULT_CATEGORY: str = "General"

MAX_SUBJECT_LEN: int = 200
THREAD_PREFIX: str = "TH-"

_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?)?$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    message_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id         TEXT NOT NULL,
    direction         TEXT NOT NULL DEFAULT 'Outgoing',
    channel           TEXT NOT NULL DEFAULT 'Email',
    category          TEXT NOT NULL DEFAULT 'General',
    priority          TEXT NOT NULL DEFAULT 'Normal',
    status            TEXT NOT NULL DEFAULT 'Draft',
    subject           TEXT NOT NULL,
    body              TEXT NOT NULL,
    from_name         TEXT,
    from_address      TEXT,
    to_name           TEXT,
    to_address        TEXT,
    cc_address        TEXT,
    student_id        TEXT,
    staff_id          TEXT,
    parent_contact_id INTEGER,
    alumni_id         INTEGER,
    sent_at           TEXT,
    received_at       TEXT,
    attachments_note  TEXT,
    tags              TEXT,
    notes             TEXT,
    reply_to_message_id INTEGER,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE SET NULL,
    FOREIGN KEY (staff_id)   REFERENCES staff(staff_id)
        ON DELETE SET NULL,
    FOREIGN KEY (parent_contact_id) REFERENCES parent_contacts(contact_id)
        ON DELETE SET NULL,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE SET NULL,
    FOREIGN KEY (reply_to_message_id) REFERENCES messages(message_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_msg_thread     ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_msg_direction  ON messages(direction);
CREATE INDEX IF NOT EXISTS idx_msg_status     ON messages(status);
CREATE INDEX IF NOT EXISTS idx_msg_student    ON messages(student_id);
CREATE INDEX IF NOT EXISTS idx_msg_staff      ON messages(staff_id);
CREATE INDEX IF NOT EXISTS idx_msg_sent_at    ON messages(sent_at);
"""

# Added after the initial release — applied with ALTER TABLE on
# existing databases.
_MESSAGES_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("alumni_id", "INTEGER"),
)


@dataclass
class Message:
    message_id: int
    thread_id: str
    direction: str
    channel: str
    category: str
    priority: str
    status: str
    subject: str
    body: str
    from_name: str | None
    from_address: str | None
    to_name: str | None
    to_address: str | None
    cc_address: str | None
    student_id: str | None
    staff_id: str | None
    parent_contact_id: int | None
    alumni_id: int | None
    sent_at: str | None
    received_at: str | None
    attachments_note: str | None
    tags: str | None
    notes: str | None
    reply_to_message_id: int | None
    created_at: str
    updated_at: str

    @property
    def is_sent(self) -> bool:
        return self.status in SENT_STATUSES

    @property
    def is_draft(self) -> bool:
        return self.status == "Draft"

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]


@dataclass
class Thread:
    thread_id: str
    subject: str
    message_count: int
    last_at: str
    last_direction: str
    last_status: str


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.parent_contacts import parent_contacts
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import staff
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.parent_contacts import parent_contacts as _pc
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import staff as _staff
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    _staff.init_db()
    _pc.init_db()
    # Ensure the alumni table exists so the FK target is present.
    try:
        from education_system.post_16.sixthform_system.modules.domain.students.alumni \
            import alumni as _alumni
        _alumni.init_db()
    except Exception:
        logger.debug("alumni module not available at init_db",
                      exc_info=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        existing = {row[1] for row in conn.execute(
            "PRAGMA table_info(messages)").fetchall()}
        for col, decl in _MESSAGES_NEW_COLUMNS:
            if col not in existing:
                conn.execute(
                    f"ALTER TABLE messages ADD COLUMN {col} {decl}")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_msg_alumni "
            "ON messages(alumni_id)")
    logger.debug("Messages schema ready at %s", DB_PATH)

    _DB_READY = True


def _get_alumni_id(r: sqlite3.Row) -> int | None:
    """Read alumni_id from a row safely (column missing on pre-migration DBs)."""
    try:
        return r["alumni_id"]
    except (IndexError, KeyError):
        return None


def _row(r: sqlite3.Row) -> Message:
    return Message(
        message_id=r["message_id"], thread_id=r["thread_id"],
        direction=r["direction"], channel=r["channel"],
        category=r["category"], priority=r["priority"],
        status=r["status"], subject=r["subject"], body=r["body"],
        from_name=r["from_name"], from_address=r["from_address"],
        to_name=r["to_name"], to_address=r["to_address"],
        cc_address=r["cc_address"],
        student_id=r["student_id"], staff_id=r["staff_id"],
        parent_contact_id=r["parent_contact_id"],
        alumni_id=_get_alumni_id(r),
        sent_at=r["sent_at"], received_at=r["received_at"],
        attachments_note=r["attachments_note"], tags=r["tags"],
        notes=r["notes"],
        reply_to_message_id=r["reply_to_message_id"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Helpers ───────────────────────────────────────────────────────

def new_thread_id() -> str:
    return f"{THREAD_PREFIX}{secrets.token_hex(4).upper()}"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_email(v: Any, label: str) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    s = str(v).strip()
    if not _EMAIL_RE.match(s):
        raise ValidationError(f"{label} is not a valid email address")
    return s.lower()


def _validate_datetime(v: Any, label: str) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    s = str(v).strip()
    if not _DATETIME_RE.match(s):
        raise ValidationError(
            f"{label} must be YYYY-MM-DD or YYYY-MM-DD HH:MM[:SS]")
    return s


def _validate_student(v: Any) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    sid = str(v).strip()
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_staff(v: Any) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    sid = str(v).strip().upper()
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import staff as _staff
    if _staff.get_staff(sid) is None:
        raise ValidationError(f"No staff with id {sid}")
    return sid


def _validate_contact(v: Any) -> int | None:
    if v in (None, ""):
        return None
    try:
        cid = int(v)
    except (TypeError, ValueError):
        raise ValidationError("Parent contact id must be a number") from None
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.parent_contacts import (
        parent_contacts as _pc,
    )
    if _pc.get_contact(cid) is None:
        raise ValidationError(f"No parent contact with id {cid}")
    return cid


def _validate_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    direction = (d.get("direction") or DEFAULT_DIRECTION).strip()
    if direction not in DIRECTIONS:
        raise ValidationError(
            f"Direction must be one of: {', '.join(DIRECTIONS)}")
    out["direction"] = direction

    channel = (d.get("channel") or DEFAULT_CHANNEL).strip()
    if channel not in CHANNELS:
        raise ValidationError(
            f"Channel must be one of: {', '.join(CHANNELS)}")
    out["channel"] = channel

    cat = (d.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

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

    subject = _require(d.get("subject"), "Subject").strip()
    if len(subject) > MAX_SUBJECT_LEN:
        raise ValidationError(
            f"Subject must be {MAX_SUBJECT_LEN} characters or fewer")
    out["subject"] = subject
    out["body"]    = _require(d.get("body"), "Body").strip()

    out["from_name"]    = (d.get("from_name") or "").strip() or None
    out["to_name"]      = (d.get("to_name") or "").strip() or None
    out["from_address"] = _validate_email(d.get("from_address"),
                                             "From address") \
        if channel in ("Email", "Portal") \
        else ((d.get("from_address") or "").strip() or None)
    out["to_address"]   = _validate_email(d.get("to_address"),
                                             "To address") \
        if channel in ("Email", "Portal") \
        else ((d.get("to_address") or "").strip() or None)
    out["cc_address"]   = (d.get("cc_address") or "").strip() or None

    out["student_id"]        = _validate_student(d.get("student_id"))
    out["staff_id"]          = _validate_staff(d.get("staff_id"))
    out["parent_contact_id"] = _validate_contact(
        d.get("parent_contact_id"))
    aid = d.get("alumni_id")
    if aid in (None, ""):
        out["alumni_id"] = None
    else:
        try:
            out["alumni_id"] = int(aid)
        except (TypeError, ValueError):
            raise ValidationError("Alumni id must be a number") from None

    out["sent_at"]     = _validate_datetime(d.get("sent_at"), "Sent at")
    out["received_at"] = _validate_datetime(d.get("received_at"),
                                              "Received at")

    out["attachments_note"] = (
        d.get("attachments_note") or "").strip() or None
    out["tags"]  = (d.get("tags") or "").strip() or None
    out["notes"] = (d.get("notes") or "").strip() or None

    # Light cross-field rules:
    if direction == "Outgoing" and status in ("Received",):
        raise ValidationError(
            "Outgoing messages cannot have status 'Received'")
    if direction == "Incoming" and status == "Queued":
        raise ValidationError(
            "Incoming messages cannot be 'Queued'")
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_message(d: dict[str, Any]) -> Message:
    init_db()
    try:
        p = _validate_payload(d)
    except ValidationError as e:
        logger.warning("create_message validation failed: %s", e)
        raise

    thread_id = (d.get("thread_id") or "").strip() or new_thread_id()
    reply_to = d.get("reply_to_message_id")
    if reply_to is not None and reply_to != "":
        try:
            reply_to = int(reply_to)
        except (TypeError, ValueError):
            raise ValidationError("reply_to_message_id must be a number") \
                from None
        parent = get_message(reply_to)
        if parent is None:
            raise ValidationError(
                f"Reply target #{reply_to} does not exist")
        # If replying, inherit the thread.
        thread_id = parent.thread_id
    else:
        reply_to = None

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO messages
                 (thread_id, direction, channel, category, priority,
                  status, subject, body, from_name, from_address,
                  to_name, to_address, cc_address, student_id, staff_id,
                  parent_contact_id, alumni_id, sent_at, received_at,
                  attachments_note, tags, notes,
                  reply_to_message_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (thread_id, p["direction"], p["channel"], p["category"],
             p["priority"], p["status"], p["subject"], p["body"],
             p["from_name"], p["from_address"], p["to_name"],
             p["to_address"], p["cc_address"],
             p["student_id"], p["staff_id"], p["parent_contact_id"],
             p["alumni_id"], p["sent_at"], p["received_at"],
             p["attachments_note"], p["tags"], p["notes"], reply_to),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_message(new_id)
    assert out is not None
    logger.info(
        "Created message #%d (%s/%s, %s, thread=%s)",
        new_id, p["direction"], p["channel"], p["status"], thread_id)
    return out


def get_message(message_id: int) -> Message | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM messages WHERE message_id = ?",
            (message_id,)).fetchone()
        return _row(r) if r else None


def list_messages(
    *,
    direction: str | None = None,
    channel: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    student_id: str | None = None,
    staff_id: str | None = None,
    alumni_id: int | None = None,
    thread_id: str | None = None,
    drafts_only: bool = False,
    unsent_only: bool = False,
    sent_only: bool = False,
) -> list[Message]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if direction:
        if direction not in DIRECTIONS:
            raise ValidationError(
                f"Direction must be one of: {', '.join(DIRECTIONS)}")
        clauses.append("direction = ?")
        args.append(direction)
    if channel:
        if channel not in CHANNELS:
            raise ValidationError(
                f"Channel must be one of: {', '.join(CHANNELS)}")
        clauses.append("channel = ?")
        args.append(channel)
    if category:
        if category not in CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
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
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if staff_id:
        clauses.append("staff_id = ?")
        args.append(staff_id.strip().upper())
    if alumni_id is not None:
        clauses.append("alumni_id = ?")
        args.append(int(alumni_id))
    if thread_id:
        clauses.append("thread_id = ?")
        args.append(thread_id.strip())
    if drafts_only:
        clauses.append("status = 'Draft'")
    if unsent_only:
        clauses.append("status IN ('Draft', 'Queued')")
    if sent_only:
        ph = ",".join("?" * len(SENT_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(SENT_STATUSES)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM messages {where} "
           "ORDER BY COALESCE(sent_at, received_at, created_at) DESC, "
           "message_id DESC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def search_messages(q: str) -> list[Message]:
    init_db()
    q = (q or "").strip()
    if not q:
        return list_messages()
    like = f"%{q}%"
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM messages
                WHERE subject LIKE ? OR body LIKE ?
                   OR to_name LIKE ? OR from_name LIKE ?
                   OR to_address LIKE ? OR from_address LIKE ?
                   OR tags LIKE ?
                ORDER BY COALESCE(sent_at, received_at, created_at) DESC""",
            (like, like, like, like, like, like, like),
        ).fetchall()
    return [_row(r) for r in rows]


def update_message(message_id: int, d: dict[str, Any]) -> Message:
    init_db()
    existing = get_message(message_id)
    if existing is None:
        raise ValidationError(f"No message with id {message_id}")
    merged = {
        "direction":         d.get("direction", existing.direction),
        "channel":           d.get("channel", existing.channel),
        "category":          d.get("category", existing.category),
        "priority":          d.get("priority", existing.priority),
        "status":            d.get("status", existing.status),
        "subject":           d.get("subject", existing.subject),
        "body":              d.get("body", existing.body),
        "from_name":         d.get("from_name", existing.from_name),
        "from_address":      d.get("from_address",
                                     existing.from_address),
        "to_name":           d.get("to_name", existing.to_name),
        "to_address":        d.get("to_address", existing.to_address),
        "cc_address":        d.get("cc_address", existing.cc_address),
        "student_id":        d.get("student_id", existing.student_id),
        "staff_id":          d.get("staff_id", existing.staff_id),
        "parent_contact_id": d.get("parent_contact_id",
                                     existing.parent_contact_id),
        "alumni_id":         d.get("alumni_id", existing.alumni_id),
        "sent_at":           d.get("sent_at", existing.sent_at),
        "received_at":       d.get("received_at",
                                     existing.received_at),
        "attachments_note":  d.get("attachments_note",
                                     existing.attachments_note),
        "tags":              d.get("tags", existing.tags),
        "notes":             d.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE messages SET
                  direction=?, channel=?, category=?, priority=?, status=?,
                  subject=?, body=?, from_name=?, from_address=?,
                  to_name=?, to_address=?, cc_address=?, student_id=?,
                  staff_id=?, parent_contact_id=?, alumni_id=?,
                  sent_at=?, received_at=?,
                  attachments_note=?, tags=?, notes=?,
                  updated_at=datetime('now')
               WHERE message_id=?""",
            (p["direction"], p["channel"], p["category"], p["priority"],
             p["status"], p["subject"], p["body"], p["from_name"],
             p["from_address"], p["to_name"], p["to_address"],
             p["cc_address"], p["student_id"], p["staff_id"],
             p["parent_contact_id"], p["alumni_id"],
             p["sent_at"], p["received_at"],
             p["attachments_note"], p["tags"], p["notes"], message_id),
        )
        conn.commit()
    out = get_message(message_id)
    assert out is not None
    logger.info("Updated message #%d (status=%s)", message_id, out.status)
    return out


def send_message(message_id: int) -> Message:
    """Flip a Draft/Queued message to Sent and stamp sent_at."""
    init_db()
    existing = get_message(message_id)
    if existing is None:
        raise ValidationError(f"No message with id {message_id}")
    if existing.direction != "Outgoing":
        raise ValidationError("Only Outgoing messages can be sent")
    if existing.status not in ("Draft", "Queued", "Failed"):
        raise ValidationError(
            f"Message #{message_id} is already {existing.status}")
    return update_message(message_id, {
        "status": "Sent",
        "sent_at": existing.sent_at or _now(),
    })


def mark_failed(message_id: int, reason: str | None = None) -> Message:
    existing = get_message(message_id)
    if existing is None:
        raise ValidationError(f"No message with id {message_id}")
    notes = existing.notes or ""
    if reason:
        notes = (notes + "\n" if notes else "") + f"[FAILED] {reason}"
    return update_message(message_id, {"status": "Failed", "notes": notes})


def set_status(message_id: int, status: str) -> Message:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_message(message_id, {"status": status})


def delete_message(message_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM messages WHERE message_id = ?", (message_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted message #%d", message_id)
            return True
        return False


# ── Threads ──────────────────────────────────────────────────────

def thread(thread_id: str) -> list[Message]:
    return list_messages(thread_id=thread_id)[::-1]  # oldest first


def list_threads(*, student_id: str | None = None,
                  staff_id: str | None = None) -> list[Thread]:
    """Group messages into threads with a tiny summary per thread."""
    msgs = list_messages(student_id=student_id, staff_id=staff_id)
    bucket: dict[str, list[Message]] = {}
    for m in msgs:
        bucket.setdefault(m.thread_id, []).append(m)
    out: list[Thread] = []
    for tid, items in bucket.items():
        items_sorted = sorted(
            items,
            key=lambda x: (x.sent_at or x.received_at or x.created_at),
            reverse=True)
        latest = items_sorted[0]
        out.append(Thread(
            thread_id=tid,
            subject=latest.subject,
            message_count=len(items),
            last_at=(latest.sent_at or latest.received_at
                      or latest.created_at),
            last_direction=latest.direction,
            last_status=latest.status,
        ))
    out.sort(key=lambda t: t.last_at, reverse=True)
    return out


def reply(message_id: int, d: dict[str, Any]) -> Message:
    """Compose a reply (new message inheriting thread + flipping
    direction). Pass new subject/body/etc in `d`; the rest is
    inherited where useful."""
    parent = get_message(message_id)
    if parent is None:
        raise ValidationError(f"No message with id {message_id}")
    flipped_dir = "Incoming" if parent.direction == "Outgoing" \
        else "Outgoing"
    base = {
        "thread_id": parent.thread_id,
        "reply_to_message_id": parent.message_id,
        "direction": d.get("direction") or flipped_dir,
        "channel":   d.get("channel") or parent.channel,
        "category":  d.get("category") or parent.category,
        "priority":  d.get("priority") or parent.priority,
        "status":    d.get("status") or DEFAULT_STATUS,
        "subject":   d.get("subject")
                     or (parent.subject if parent.subject.startswith("Re:")
                         else f"Re: {parent.subject}"),
        "body":      d.get("body", ""),
        "from_name": d.get("from_name", parent.to_name),
        "to_name":   d.get("to_name", parent.from_name),
        "from_address": d.get("from_address", parent.to_address),
        "to_address":   d.get("to_address", parent.from_address),
        "student_id":   d.get("student_id", parent.student_id),
        "staff_id":     d.get("staff_id", parent.staff_id),
        "parent_contact_id": d.get("parent_contact_id",
                                     parent.parent_contact_id),
    }
    # Allow overrides for anything the caller already passed in.
    for k, v in d.items():
        base.setdefault(k, v)
    return create_message(base)


# ── Bulk send ────────────────────────────────────────────────────

@dataclass
class BulkResult:
    thread_id: str
    created: list[Message]
    failed: list[tuple[str, str]]   # (recipient_label, reason)


def bulk_send(
    *,
    subject: str,
    body: str,
    student_ids: list[str] | None = None,
    contact_ids: list[int] | None = None,
    staff_ids: list[str] | None = None,
    alumni_recipients: list[tuple[int, str, str]] | None = None,
    channel: str = DEFAULT_CHANNEL,
    category: str = DEFAULT_CATEGORY,
    priority: str = DEFAULT_PRIORITY,
    status: str = "Sent",
    sender_staff_id: str | None = None,
    from_name: str | None = None,
    from_address: str | None = None,
    attachments_note: str | None = None,
    tags: str | None = None,
) -> BulkResult:
    """Create one outgoing message per recipient, all sharing a thread.

    If `status='Sent'`, sent_at is stamped to 'now' on each row.
    """
    init_db()
    student_ids = student_ids or []
    contact_ids = contact_ids or []
    staff_ids   = staff_ids or []
    alumni_recipients = alumni_recipients or []
    if not (student_ids or contact_ids or staff_ids
              or alumni_recipients):
        raise ValidationError("No recipients selected")

    tid = new_thread_id()
    sent_at = _now() if status in SENT_STATUSES else None
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.parent_contacts import parent_contacts as _pc
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import staff as _staff
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students

    out: list[Message] = []
    failed: list[tuple[str, str]] = []

    base = {
        "thread_id":   tid,
        "direction":   "Outgoing",
        "channel":     channel,
        "category":    category,
        "priority":    priority,
        "status":      status,
        "subject":     subject,
        "body":        body,
        "from_name":   from_name,
        "from_address": from_address,
        "staff_id":    sender_staff_id,
        "sent_at":     sent_at,
        "attachments_note": attachments_note,
        "tags":        tags,
    }

    for sid in student_ids:
        s = _students.get_student(sid)
        if s is None:
            failed.append((f"student {sid}", "no such student"))
            continue
        try:
            m = create_message({**base,
                                 "student_id": sid,
                                 "to_name": s.full_name,
                                 "to_address": s.email})
            out.append(m)
        except ValidationError as e:
            failed.append((f"student {sid}", str(e)))

    for cid in contact_ids:
        c = _pc.get_contact(cid)
        if c is None:
            failed.append((f"contact #{cid}", "no such contact"))
            continue
        try:
            m = create_message({
                **base,
                "student_id": c.student_id,
                "parent_contact_id": cid,
                "to_name": c.full_name,
                "to_address": c.email or "",
            })
            out.append(m)
        except ValidationError as e:
            failed.append((f"contact #{cid}", str(e)))

    for sid in staff_ids:
        st = _staff.get_staff(sid)
        if st is None:
            failed.append((f"staff {sid}", "no such staff"))
            continue
        try:
            m = create_message({**base,
                                 "to_name": st.full_name,
                                 "to_address": st.email})
            out.append(m)
        except ValidationError as e:
            failed.append((f"staff {sid}", str(e)))

    for aid, name, addr in alumni_recipients:
        try:
            m = create_message({
                **base,
                "alumni_id":  int(aid),
                "to_name":    name,
                "to_address": addr,
            })
            out.append(m)
        except ValidationError as e:
            failed.append((f"alumnus #{aid}", str(e)))

    logger.info("Bulk send thread %s: %d created, %d failed",
                tid, len(out), len(failed))
    return BulkResult(thread_id=tid, created=out, failed=failed)


# ── Summary ──────────────────────────────────────────────────────

@dataclass
class Summary:
    total: int
    drafts: int
    queued: int
    sent: int
    incoming: int
    outgoing: int
    failed: int
    threads: int
    by_channel: dict[str, int]
    by_category: dict[str, int]
    by_priority: dict[str, int]
    by_status: dict[str, int]


def summary() -> Summary:
    init_db()
    rows = list_messages()
    by_ch = {c: 0 for c in CHANNELS}
    by_cat = {c: 0 for c in CATEGORIES}
    by_pri = {p: 0 for p in PRIORITIES}
    by_st = {s: 0 for s in STATUSES}
    drafts = queued = sent = failed = incoming = outgoing = 0
    for m in rows:
        by_ch[m.channel] = by_ch.get(m.channel, 0) + 1
        by_cat[m.category] = by_cat.get(m.category, 0) + 1
        by_pri[m.priority] = by_pri.get(m.priority, 0) + 1
        by_st[m.status] = by_st.get(m.status, 0) + 1
        if m.status == "Draft":
            drafts += 1
        elif m.status == "Queued":
            queued += 1
        elif m.status in SENT_STATUSES:
            sent += 1
        elif m.status == "Failed":
            failed += 1
        if m.direction == "Incoming":
            incoming += 1
        else:
            outgoing += 1
    threads = len({m.thread_id for m in rows})
    return Summary(
        total=len(rows), drafts=drafts, queued=queued, sent=sent,
        incoming=incoming, outgoing=outgoing, failed=failed,
        threads=threads,
        by_channel=by_ch, by_category=by_cat,
        by_priority=by_pri, by_status=by_st,
    )
