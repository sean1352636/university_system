"""Notifications data layer for Sixth Form System.

Per-recipient targeted notifications. Distinct from messages
(which are conversations) and announcements (broadcast). One row
per (recipient, notification) — when broadcasting, the caller
creates one row per intended recipient.

`recipient_id` is free-text (soft pointer to a student / staff /
parent identifier). No FK so notifications survive recipient
deletion (useful for audit).
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

RECIPIENT_TYPES: tuple[str, ...] = (
    "Student",
    "Staff",
    "Parent",
    "Tutor",
    "Group",
    "Other",
)
DEFAULT_RECIPIENT_TYPE = "Student"

NOTIFICATION_TYPES: tuple[str, ...] = (
    "System",
    "Action Required",
    "Reminder",
    "Info",
    "Alert",
    "Warning",
    "Achievement",
    "Deadline",
    "Approval",
    "Comment",
    "Mention",
    "Birthday",
    "Welcome",
    "Safeguarding",
    "Attendance",
    "Behaviour",
    "Other",
)
DEFAULT_NOTIFICATION_TYPE = "Info"

CHANNELS: tuple[str, ...] = (
    "In-App",
    "Email",
    "SMS",
    "Push",
    "Multiple",
)
DEFAULT_CHANNEL = "In-App"

PRIORITIES: tuple[int, ...] = (1, 2, 3, 4, 5)
_PRIORITY_LABELS = {
    1: "Low", 2: "Normal", 3: "Important",
    4: "High", 5: "Urgent",
}


def priority_label(p: int | None) -> str:
    if p is None:
        return "—"
    return _PRIORITY_LABELS.get(p, "Unknown")


STATUSES: tuple[str, ...] = (
    "Draft",
    "Scheduled",
    "Sent",
    "Delivered",
    "Read",
    "Acknowledged",
    "Dismissed",
    "Failed",
    "Expired",
)
DEFAULT_STATUS = "Draft"


class ValidationError(Exception):
    pass


@dataclass
class Notification:
    notification_id: int
    recipient_type: str
    recipient_id: str
    recipient_name: str | None
    title: str
    body: str | None
    notification_type: str
    priority: int
    channel: str
    icon: str | None
    url: str | None
    linked_to: str | None
    requires_action: bool
    action_label: str | None
    action_url: str | None
    action_completed: bool
    sent_by: str | None
    scheduled_for: str | None
    sent_at: str | None
    delivered_at: str | None
    read_at: str | None
    acknowledged_at: str | None
    dismissed_at: str | None
    expires_on: str | None
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    @property
    def is_pending(self) -> bool:
        return self.status in ("Draft", "Scheduled")

    @property
    def is_active(self) -> bool:
        return self.status in ("Sent", "Delivered",
                                       "Read", "Acknowledged")

    @property
    def is_expired(self) -> bool:
        if not self.expires_on:
            return False
        return self.expires_on < _dt.date.today().isoformat()

    @property
    def needs_action(self) -> bool:
        return (self.requires_action
                  and not self.action_completed
                  and self.is_active)

    @property
    def priority_label(self) -> str:
        return priority_label(self.priority)


@dataclass
class NotificationsSummary:
    total: int = 0
    unread: int = 0
    pending: int = 0
    sent: int = 0
    scheduled: int = 0
    needs_action: int = 0
    expired_unprocessed: int = 0
    urgent_unread: int = 0
    distinct_recipients: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_priority: dict[int, int] = field(default_factory=dict)
    by_channel: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_recipient_type: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.NOTIFICATIONS_DB)
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
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_type TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                recipient_name TEXT,
                title TEXT NOT NULL,
                body TEXT,
                notification_type TEXT NOT NULL,
                priority INTEGER NOT NULL,
                channel TEXT NOT NULL,
                icon TEXT,
                url TEXT,
                linked_to TEXT,
                requires_action INTEGER NOT NULL DEFAULT 0,
                action_label TEXT,
                action_url TEXT,
                action_completed INTEGER NOT NULL DEFAULT 0,
                sent_by TEXT,
                scheduled_for TEXT,
                sent_at TEXT,
                delivered_at TEXT,
                read_at TEXT,
                acknowledged_at TEXT,
                dismissed_at TEXT,
                expires_on TEXT,
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


def _check_datetime(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.datetime.fromisoformat(value)
    except ValueError:
        try:
            _dt.date.fromisoformat(value)
        except ValueError:
            raise ValidationError(
                f"{label} must be YYYY-MM-DD or "
                "YYYY-MM-DDTHH:MM")


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    rt = (out.get("recipient_type")
            or DEFAULT_RECIPIENT_TYPE).strip()
    if rt not in RECIPIENT_TYPES:
        raise ValidationError(
            f"Recipient type must be one of: "
            f"{', '.join(RECIPIENT_TYPES)}")
    out["recipient_type"] = rt

    out["recipient_id"] = (out.get("recipient_id") or "").strip()
    if not out["recipient_id"]:
        raise ValidationError("Recipient id is required")

    out["title"] = (out.get("title") or "").strip()
    if not out["title"]:
        raise ValidationError("Title is required")

    nt = (out.get("notification_type")
            or DEFAULT_NOTIFICATION_TYPE).strip()
    if nt not in NOTIFICATION_TYPES:
        raise ValidationError(
            f"Notification type must be one of: "
            f"{', '.join(NOTIFICATION_TYPES)}")
    out["notification_type"] = nt

    ch = (out.get("channel") or DEFAULT_CHANNEL).strip()
    if ch not in CHANNELS:
        raise ValidationError(
            f"Channel must be one of: {', '.join(CHANNELS)}")
    out["channel"] = ch

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

    _check_datetime("Scheduled for",  out.get("scheduled_for"))
    _check_datetime("Sent at",        out.get("sent_at"))
    _check_datetime("Delivered at",   out.get("delivered_at"))
    _check_datetime("Read at",        out.get("read_at"))
    _check_datetime("Acknowledged at",
                       out.get("acknowledged_at"))
    _check_datetime("Dismissed at",   out.get("dismissed_at"))
    _check_date("Expires on",         out.get("expires_on"))

    for k in ("recipient_name", "body", "icon", "url",
               "linked_to", "action_label", "action_url",
               "sent_by", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("scheduled_for", "sent_at", "delivered_at",
               "read_at", "acknowledged_at", "dismissed_at",
               "expires_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    for k in ("requires_action", "action_completed"):
        out[k] = bool(out.get(k))
    return out


def _row(r: sqlite3.Row) -> Notification:
    return Notification(
        notification_id=r["notification_id"],
        recipient_type=r["recipient_type"],
        recipient_id=r["recipient_id"],
        recipient_name=r["recipient_name"],
        title=r["title"],
        body=r["body"],
        notification_type=r["notification_type"],
        priority=r["priority"],
        channel=r["channel"],
        icon=r["icon"],
        url=r["url"],
        linked_to=r["linked_to"],
        requires_action=bool(r["requires_action"]),
        action_label=r["action_label"],
        action_url=r["action_url"],
        action_completed=bool(r["action_completed"]),
        sent_by=r["sent_by"],
        scheduled_for=r["scheduled_for"],
        sent_at=r["sent_at"],
        delivered_at=r["delivered_at"],
        read_at=r["read_at"],
        acknowledged_at=r["acknowledged_at"],
        dismissed_at=r["dismissed_at"],
        expires_on=r["expires_on"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_notification(payload: dict[str, Any]
                                 ) -> Notification:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO notifications (
              recipient_type, recipient_id, recipient_name,
              title, body, notification_type, priority,
              channel, icon, url, linked_to,
              requires_action, action_label, action_url,
              action_completed, sent_by,
              scheduled_for, sent_at, delivered_at,
              read_at, acknowledged_at, dismissed_at,
              expires_on, status, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["recipient_type"], p["recipient_id"],
            p["recipient_name"], p["title"], p["body"],
            p["notification_type"], p["priority"],
            p["channel"], p["icon"], p["url"], p["linked_to"],
            1 if p["requires_action"] else 0,
            p["action_label"], p["action_url"],
            1 if p["action_completed"] else 0,
            p["sent_by"], p["scheduled_for"], p["sent_at"],
            p["delivered_at"], p["read_at"],
            p["acknowledged_at"], p["dismissed_at"],
            p["expires_on"], p["status"], p["notes"],
            now, now,
        ))
        new_id = cur.lastrowid
    return get_notification(new_id)


def update_notification(notification_id: int,
                            payload: dict[str, Any]
                            ) -> Notification:
    init_db()
    if get_notification(notification_id) is None:
        raise ValidationError(
            f"No notification with id {notification_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE notifications SET
              recipient_type=?, recipient_id=?, recipient_name=?,
              title=?, body=?, notification_type=?, priority=?,
              channel=?, icon=?, url=?, linked_to=?,
              requires_action=?, action_label=?, action_url=?,
              action_completed=?, sent_by=?,
              scheduled_for=?, sent_at=?, delivered_at=?,
              read_at=?, acknowledged_at=?, dismissed_at=?,
              expires_on=?, status=?, notes=?, updated_on=?
            WHERE notification_id=?
        """, (
            p["recipient_type"], p["recipient_id"],
            p["recipient_name"], p["title"], p["body"],
            p["notification_type"], p["priority"],
            p["channel"], p["icon"], p["url"], p["linked_to"],
            1 if p["requires_action"] else 0,
            p["action_label"], p["action_url"],
            1 if p["action_completed"] else 0,
            p["sent_by"], p["scheduled_for"], p["sent_at"],
            p["delivered_at"], p["read_at"],
            p["acknowledged_at"], p["dismissed_at"],
            p["expires_on"], p["status"], p["notes"],
            now, notification_id,
        ))
    return get_notification(notification_id)


def delete_notification(notification_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM notifications "
            "WHERE notification_id=?", (notification_id,))
        return cur.rowcount > 0


def get_notification(notification_id: int) -> Notification | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM notifications "
            "WHERE notification_id=?",
            (notification_id,)).fetchone()
        return _row(r) if r else None


def list_notifications(*,
                            recipient_type: str | None = None,
                            recipient_id: str | None = None,
                            notification_type: str | None = None,
                            channel: str | None = None,
                            status: str | None = None,
                            priority: int | None = None,
                            priority_min: int | None = None,
                            unread_only: bool = False,
                            needs_action_only: bool = False,
                            urgent_only: bool = False,
                            pending_only: bool = False,
                            sent_by_like: str | None = None,
                            title_like: str | None = None,
                            date_from: str | None = None,
                            date_to: str | None = None,
                            ) -> list[Notification]:
    init_db()
    sql = "SELECT * FROM notifications WHERE 1=1"
    params: list[Any] = []
    if recipient_type:
        sql += " AND recipient_type=?"
        params.append(recipient_type)
    if recipient_id:
        sql += " AND recipient_id=?"
        params.append(recipient_id)
    if notification_type:
        sql += " AND notification_type=?"
        params.append(notification_type)
    if channel:
        sql += " AND channel=?"
        params.append(channel)
    if status:
        sql += " AND status=?"
        params.append(status)
    if priority is not None:
        sql += " AND priority=?"
        params.append(priority)
    if priority_min is not None:
        sql += " AND priority >= ?"
        params.append(priority_min)
    if unread_only:
        sql += (" AND read_at IS NULL"
                  " AND status IN "
                  "('Sent','Delivered','Acknowledged')")
    if needs_action_only:
        sql += (" AND requires_action=1"
                  " AND action_completed=0"
                  " AND status IN "
                  "('Sent','Delivered','Read','Acknowledged')")
    if urgent_only:
        sql += (" AND priority >= 4"
                  " AND read_at IS NULL"
                  " AND status IN ('Sent','Delivered')")
    if pending_only:
        sql += " AND status IN ('Draft','Scheduled')"
    if sent_by_like:
        sql += " AND sent_by LIKE ?"
        params.append(f"%{sent_by_like}%")
    if title_like:
        sql += " AND title LIKE ?"
        params.append(f"%{title_like}%")
    if date_from:
        _check_date("From", date_from)
        sql += (" AND (sent_at >= ? OR"
                  " (sent_at IS NULL AND created_on >= ?))")
        params.extend([date_from, date_from])
    if date_to:
        _check_date("To", date_to)
        sql += (" AND (sent_at <= ? OR"
                  " (sent_at IS NULL AND created_on <= ?))")
        params.extend([date_to, date_to])
    sql += (" ORDER BY priority DESC,"
              " COALESCE(sent_at, created_on) DESC,"
              " notification_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def notifications_for(recipient_type: str,
                            recipient_id: str
                            ) -> list[Notification]:
    return list_notifications(
        recipient_type=recipient_type,
        recipient_id=recipient_id)


def unread_count_for(recipient_type: str,
                            recipient_id: str) -> int:
    return len(list_notifications(
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        unread_only=True))


# ── Workflow ──────────────────────────────────────────────

def _to_dict(n: Notification) -> dict[str, Any]:
    return {
        "recipient_type": n.recipient_type,
        "recipient_id": n.recipient_id,
        "recipient_name": n.recipient_name,
        "title": n.title,
        "body": n.body,
        "notification_type": n.notification_type,
        "priority": n.priority,
        "channel": n.channel,
        "icon": n.icon,
        "url": n.url,
        "linked_to": n.linked_to,
        "requires_action": n.requires_action,
        "action_label": n.action_label,
        "action_url": n.action_url,
        "action_completed": n.action_completed,
        "sent_by": n.sent_by,
        "scheduled_for": n.scheduled_for,
        "sent_at": n.sent_at,
        "delivered_at": n.delivered_at,
        "read_at": n.read_at,
        "acknowledged_at": n.acknowledged_at,
        "dismissed_at": n.dismissed_at,
        "expires_on": n.expires_on,
        "status": n.status,
        "notes": n.notes,
    }


def schedule(notification_id: int, *,
                  scheduled_for: str) -> Notification:
    _check_datetime("Scheduled for", scheduled_for)
    n = get_notification(notification_id)
    if n is None:
        raise ValidationError(
            f"No notification with id {notification_id}")
    data = _to_dict(n)
    data["scheduled_for"] = scheduled_for
    data["status"] = "Scheduled"
    return update_notification(notification_id, data)


def mark_sent(notification_id: int, *,
                  sent_at: str | None = None) -> Notification:
    n = get_notification(notification_id)
    if n is None:
        raise ValidationError(
            f"No notification with id {notification_id}")
    data = _to_dict(n)
    data["sent_at"] = (sent_at
                          or _dt.datetime.now().isoformat(
                              timespec="seconds"))
    data["status"] = "Sent"
    return update_notification(notification_id, data)


def mark_delivered(notification_id: int, *,
                         delivered_at: str | None = None
                         ) -> Notification:
    n = get_notification(notification_id)
    if n is None:
        raise ValidationError(
            f"No notification with id {notification_id}")
    data = _to_dict(n)
    data["delivered_at"] = (delivered_at
                                  or _dt.datetime.now().isoformat(
                                      timespec="seconds"))
    if data["status"] == "Sent":
        data["status"] = "Delivered"
    return update_notification(notification_id, data)


def mark_read(notification_id: int, *,
                  read_at: str | None = None) -> Notification:
    n = get_notification(notification_id)
    if n is None:
        raise ValidationError(
            f"No notification with id {notification_id}")
    data = _to_dict(n)
    data["read_at"] = (read_at
                          or _dt.datetime.now().isoformat(
                              timespec="seconds"))
    if data["status"] in ("Sent", "Delivered"):
        data["status"] = "Read"
    return update_notification(notification_id, data)


def acknowledge(notification_id: int, *,
                     ack_at: str | None = None
                     ) -> Notification:
    n = get_notification(notification_id)
    if n is None:
        raise ValidationError(
            f"No notification with id {notification_id}")
    data = _to_dict(n)
    data["acknowledged_at"] = (ack_at
                                     or _dt.datetime.now().isoformat(
                                         timespec="seconds"))
    if not data["read_at"]:
        data["read_at"] = data["acknowledged_at"]
    data["status"] = "Acknowledged"
    return update_notification(notification_id, data)


def dismiss(notification_id: int, *,
                dismissed_at: str | None = None
                ) -> Notification:
    n = get_notification(notification_id)
    if n is None:
        raise ValidationError(
            f"No notification with id {notification_id}")
    data = _to_dict(n)
    data["dismissed_at"] = (dismissed_at
                                  or _dt.datetime.now().isoformat(
                                      timespec="seconds"))
    data["status"] = "Dismissed"
    return update_notification(notification_id, data)


def mark_action_completed(notification_id: int
                                  ) -> Notification:
    n = get_notification(notification_id)
    if n is None:
        raise ValidationError(
            f"No notification with id {notification_id}")
    return update_notification(notification_id,
                                       {**_to_dict(n),
                                         "action_completed": True})


def mark_failed(notification_id: int) -> Notification:
    n = get_notification(notification_id)
    if n is None:
        raise ValidationError(
            f"No notification with id {notification_id}")
    return update_notification(notification_id,
                                       {**_to_dict(n),
                                         "status": "Failed"})


def set_status(notification_id: int,
                    new_status: str) -> Notification:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    n = get_notification(notification_id)
    if n is None:
        raise ValidationError(
            f"No notification with id {notification_id}")
    return update_notification(notification_id,
                                       {**_to_dict(n),
                                         "status": new_status})


def auto_expire() -> int:
    """Move expired notifications to Expired status.
    Returns rows updated."""
    init_db()
    today = _dt.date.today().isoformat()
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE notifications SET status='Expired',"
            " updated_on=? "
            "WHERE expires_on IS NOT NULL"
            " AND expires_on < ?"
            " AND status NOT IN "
            "('Dismissed','Acknowledged','Expired','Failed')",
            (now, today))
        return cur.rowcount


# ── Broadcast helper ─────────────────────────────────────

def broadcast(*,
                  recipients: list[tuple[str, str, str | None]],
                  title: str,
                  body: str | None = None,
                  notification_type: str = DEFAULT_NOTIFICATION_TYPE,
                  priority: int = 2,
                  channel: str = DEFAULT_CHANNEL,
                  sent_by: str | None = None,
                  status: str = "Draft",
                  expires_on: str | None = None,
                  linked_to: str | None = None,
                  ) -> list[Notification]:
    """Create one notification row per recipient.

    `recipients` is a list of (recipient_type, recipient_id,
    recipient_name) tuples.
    """
    out: list[Notification] = []
    for rt, rid, rname in recipients:
        out.append(create_notification({
            "recipient_type": rt,
            "recipient_id": rid,
            "recipient_name": rname,
            "title": title,
            "body": body,
            "notification_type": notification_type,
            "priority": priority,
            "channel": channel,
            "sent_by": sent_by,
            "status": status,
            "expires_on": expires_on,
            "linked_to": linked_to,
        }))
    return out


# ── Summary ─────────────────────────────────────────────

def summary() -> NotificationsSummary:
    rows = list_notifications()
    out = NotificationsSummary(total=len(rows))
    if not rows:
        return out
    today = _dt.date.today().isoformat()
    recipients: set[tuple[str, str]] = set()
    for n in rows:
        recipients.add((n.recipient_type, n.recipient_id))
        if (n.read_at is None and n.status
                in ("Sent", "Delivered", "Acknowledged")):
            out.unread += 1
        if n.is_pending:
            out.pending += 1
        if n.status == "Scheduled":
            out.scheduled += 1
        if n.status in ("Sent", "Delivered",
                              "Read", "Acknowledged"):
            out.sent += 1
        if n.needs_action:
            out.needs_action += 1
        if (n.priority >= 4 and n.read_at is None
                and n.status in ("Sent", "Delivered")):
            out.urgent_unread += 1
        if (n.expires_on and n.expires_on < today
                and n.status not in (
                    "Dismissed", "Acknowledged",
                    "Expired", "Failed")):
            out.expired_unprocessed += 1
        out.by_type[n.notification_type] = (
            out.by_type.get(n.notification_type, 0) + 1)
        out.by_priority[n.priority] = (
            out.by_priority.get(n.priority, 0) + 1)
        out.by_channel[n.channel] = (
            out.by_channel.get(n.channel, 0) + 1)
        out.by_status[n.status] = (
            out.by_status.get(n.status, 0) + 1)
        out.by_recipient_type[n.recipient_type] = (
            out.by_recipient_type.get(n.recipient_type, 0) + 1)
    out.distinct_recipients = len(recipients)
    return out


__all__ = [
    "RECIPIENT_TYPES", "DEFAULT_RECIPIENT_TYPE",
    "NOTIFICATION_TYPES", "DEFAULT_NOTIFICATION_TYPE",
    "CHANNELS", "DEFAULT_CHANNEL",
    "PRIORITIES", "priority_label",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "Notification", "NotificationsSummary",
    "init_db",
    "create_notification", "update_notification",
    "delete_notification", "get_notification",
    "list_notifications", "notifications_for",
    "unread_count_for",
    "schedule", "mark_sent", "mark_delivered",
    "mark_read", "acknowledge", "dismiss",
    "mark_action_completed", "mark_failed",
    "set_status", "auto_expire",
    "broadcast",
    "summary",
]
