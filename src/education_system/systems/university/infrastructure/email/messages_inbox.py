"""Deliver a lightweight in-app message into a user's inbox.

Event notifiers (schedule / exam changes) used to mirror their email into
the standalone ``notifications`` table. That table has been retired, so the
in-app mirror now lands in the unified inbox — a row in the ``messages``
table — where it shows up under the "University" source in the Notifications
Hub and the email Messages tab.

Best-effort by design: a failure here must never block the underlying
schedule/exam write, so every path swallows and logs instead of raising.
"""

import logging

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


def _resolve_user_id(cursor, recipient_ref):
    """Map a recipient reference to a ``users.id``.

    Accepts a ``student_id``, a ``username``, or an already-numeric
    ``users.id`` (as int or digit string). Returns the id or ``None``.
    """
    ref = str(recipient_ref).strip()
    if not ref:
        return None
    cursor.execute("SELECT id FROM users WHERE student_id = ? LIMIT 1", (ref,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (ref,))
    row = cursor.fetchone()
    if row:
        return row[0]
    if ref.isdigit():
        cursor.execute("SELECT id FROM users WHERE id = ? LIMIT 1", (int(ref),))
        row = cursor.fetchone()
        if row:
            return row[0]
    return None


def _system_sender_id(cursor):
    """Resolve a sender id for system-generated messages (first admin)."""
    cursor.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else None


def _valid_sender(cursor, sender_id):
    """``sender_id`` when it is a university profile, else the system sender.
    An unknown id (e.g. a central auth id from the other id space) would
    leave a dangling reference that a profile created later would inherit."""
    if sender_id is not None:
        cursor.execute("SELECT id FROM users WHERE id = ?", (sender_id,))
        found = cursor.fetchone()
        if found:
            return found[0]
    return _system_sender_id(cursor)


def deliver_inbox_message_on(conn, recipient_ref, subject, body, sender_id=None):
    """:func:`deliver_inbox_message` inside the caller's transaction.

    For notices that must land with the change that caused them (and roll
    back with it). Returns the message id, or ``None`` when the recipient has
    no account. Database errors propagate to the caller.
    """
    cur = conn.cursor()
    recipient_id = _resolve_user_id(cur, recipient_ref)
    if recipient_id is None:
        return None
    sender = _valid_sender(cur, sender_id)
    cur.execute(
        "INSERT INTO messages "
        "(sender_id, recipient_id, subject, message, content, is_read, sent_at) "
        "VALUES (?, ?, ?, ?, ?, 0, datetime('now'))",
        (sender, recipient_id, subject, body, body),
    )
    return cur.lastrowid


def deliver_inbox_message(recipient_ref, subject, body, sender_id=None):
    """Insert an unread message into ``messages`` for ``recipient_ref``.

    ``recipient_ref`` may be a student_id, a username, or a numeric users.id.
    Returns the new message id, or ``None`` if the recipient can't be resolved
    or the write fails. Never raises.
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            recipient_id = _resolve_user_id(cur, recipient_ref)
            if recipient_id is None:
                logger.debug("inbox delivery skipped: no user for ref=%r", recipient_ref)
                return None
            sender = _valid_sender(cur, sender_id)
            cur.execute(
                "INSERT INTO messages "
                "(sender_id, recipient_id, subject, message, content, is_read, sent_at) "
                "VALUES (?, ?, ?, ?, ?, 0, datetime('now'))",
                (sender, recipient_id, subject, body, body),
            )
            return cur.lastrowid
    except Exception as exc:
        logger.debug("inbox delivery failed for ref=%r: %s", recipient_ref, exc)
        return None
