"""Assignment notices over the unified inbox.

The standalone ``notifications`` / ``notification_preferences`` tables were
retired (``init_db`` drops them at every start). An assignment notice is now
an ordinary ``messages`` row, so it shows up in the Notifications Hub, and each
person's per-type settings live under one key of
``user_preferences.preferences_json``.

``recipient`` may be a student id, a username or a ``users.id``.
"""

import json
import logging
import re
from datetime import datetime

from education_system.platform.kernel.database.sql_safety import escape_like

logger = logging.getLogger(__name__)

PREF_KEY = "assignment_notifications"
DEFAULT_PREF = {
    "enabled": True,
    "email": True,
    "sms": False,
    "in_app": True,
    "push": False,
    "advance_notice_days": 1,
}

# The command line and the window name the same settings differently.
_TYPE_ALIASES = {
    "assignment_created": "new_assignment",
    "assignment_due": "due_reminder",
    "grade_posted": "grade_released",
    "grade_notification": "grade_released",
    "extension_approved": "extension_update",
    "extension_rejected": "extension_update",
    "peer_review_assigned": "peer_review",
}

# messages has no type column; the subject carries the same information.
_KIND_RULES = (
    ("error", re.compile(r"reject|denied|declin|fail", re.I)),
    ("warning", re.compile(r"due|overdue|late|reminder|deadline|warning", re.I)),
    ("success", re.compile(r"approv|grant|releas|available|graded|accept", re.I)),
)

_NOT_DELETED = "COALESCE(is_deleted_by_recipient, 0) = 0"


def notice_kind(subject):
    """info / warning / success / error, derived from the subject."""
    for kind, pattern in _KIND_RULES:
        if pattern.search(subject or ""):
            return kind
    return "info"


def resolve_user_id(conn, recipient):
    if recipient is None:
        return None
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        _resolve_user_id,
    )
    return _resolve_user_id(conn.cursor(), recipient)


def session_user_id(conn, auth):
    """``users.id`` of the signed-in person, resolved by username: the session
    may carry the central auth.db id, which is a different id space."""
    user = getattr(auth, "current_user", None) if auth else None
    if not isinstance(user, dict):
        return None
    for ref in (user.get("username"), user.get("student_id"), user.get("id")):
        found = resolve_user_id(conn, ref)
        if found is not None:
            return found
    return None


# ---------------------------------------------------------------- preferences

def _pref_blob(conn, user_id):
    row = conn.execute(
        "SELECT preferences_json FROM user_preferences WHERE user_id = ?",
        (str(user_id),),
    ).fetchone()
    if not row or not row[0]:
        return {}
    try:
        blob = json.loads(row[0])
    except (ValueError, TypeError):
        logger.warning("user_preferences.preferences_json for %s is not JSON", user_id)
        return {}
    return blob if isinstance(blob, dict) else {}


def all_prefs(conn, user_id):
    """{notification type: settings} that this person has saved."""
    saved = _pref_blob(conn, user_id).get(PREF_KEY)
    if not isinstance(saved, dict):
        return {}
    return {kind: {**DEFAULT_PREF, **vals} for kind, vals in saved.items()
            if isinstance(vals, dict)}


def get_pref(conn, user_id, notification_type):
    kind = _TYPE_ALIASES.get(notification_type, notification_type)
    return all_prefs(conn, user_id).get(kind, dict(DEFAULT_PREF))


def set_pref(conn, user_id, notification_type, **values):
    """Merge ``values`` into one type's settings; other JSON keys are kept."""
    notification_type = _TYPE_ALIASES.get(notification_type, notification_type)
    blob = _pref_blob(conn, user_id)
    saved = blob.get(PREF_KEY) if isinstance(blob.get(PREF_KEY), dict) else {}
    merged = {**DEFAULT_PREF, **saved.get(notification_type, {}), **values}
    saved[notification_type] = merged
    blob[PREF_KEY] = saved
    conn.execute(
        "INSERT INTO user_preferences (user_id, preferences_json) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET preferences_json = excluded.preferences_json",
        (str(user_id), json.dumps(blob)),
    )
    return merged


def email_address_if_wanted(conn, recipient, notification_type):
    """The recipient's e-mail, or None when they have none or opted out."""
    user_id = resolve_user_id(conn, recipient)
    if user_id is None:
        return None
    pref = get_pref(conn, user_id, notification_type)
    if not (pref["enabled"] and pref["email"]):
        return None
    row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    return row[0] if row and row[0] else None


# -------------------------------------------------------------------- notices

def deliver(conn, recipient, subject, body, notification_type="info", assignment_id=None):
    """Add a notice to the recipient's inbox inside the caller's transaction.

    Returns the message id; None when the recipient has no account or has
    switched this type of notice off.
    """
    user_id = resolve_user_id(conn, recipient)
    if user_id is None:
        return None
    pref = get_pref(conn, user_id, notification_type)
    if not (pref["enabled"] and pref["in_app"]):
        return None
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message_on,
    )
    message_id = deliver_inbox_message_on(conn, user_id, subject, body)
    if message_id and assignment_id is not None and conn.execute(
            "SELECT 1 FROM assignments WHERE id = ?", (assignment_id,)).fetchone():
        conn.execute("UPDATE messages SET assignment_id = ? WHERE id = ?",
                     (assignment_id, message_id))
    return message_id


def list_notices(conn, user_id, kind="all", status="all", search=""):
    """Newest first: (id, subject, body, kind, is_read, sent_at, assignment_id)."""
    sql = ("SELECT id, subject, COALESCE(content, message, ''), COALESCE(is_read, 0), "
           "sent_at, assignment_id FROM messages "
           f"WHERE recipient_id = ? AND {_NOT_DELETED} AND COALESCE(is_archived, 0) = 0")
    params = [user_id]
    if status == "unread":
        sql += " AND COALESCE(is_read, 0) = 0"
    elif status == "read":
        sql += " AND is_read = 1"
    if search:
        term = f"%{escape_like(search)}%"
        sql += " AND (subject LIKE ? ESCAPE '\\' OR COALESCE(content, message, '') LIKE ? ESCAPE '\\')"
        params += [term, term]
    sql += " ORDER BY sent_at DESC, id DESC"
    notices = [(r[0], r[1], r[2], notice_kind(r[1]), r[3], r[4], r[5])
               for r in conn.execute(sql, params).fetchall()]
    return notices if kind == "all" else [n for n in notices if n[3] == kind]


def get_notice(conn, message_id, user_id):
    row = conn.execute(
        "SELECT id, subject, COALESCE(content, message, ''), COALESCE(is_read, 0), "
        "sent_at, assignment_id FROM messages "
        f"WHERE id = ? AND recipient_id = ? AND {_NOT_DELETED}",
        (message_id, user_id),
    ).fetchone()
    if not row:
        return None
    return (row[0], row[1], row[2], notice_kind(row[1]), row[3], row[4], row[5])


def set_read(conn, message_id, user_id, is_read=True):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if is_read else None
    return conn.execute(
        "UPDATE messages SET is_read = ?, read_at = ? WHERE id = ? AND recipient_id = ?",
        (1 if is_read else 0, stamp, message_id, user_id),
    ).rowcount


def delete_notice(conn, message_id, user_id):
    """Hide it from this recipient (a message also belongs to its sender)."""
    return conn.execute(
        "UPDATE messages SET is_deleted_by_recipient = 1 WHERE id = ? AND recipient_id = ?",
        (message_id, user_id),
    ).rowcount


def mark_all_read(conn, user_id):
    return conn.execute(
        "UPDATE messages SET is_read = 1, read_at = ? "
        f"WHERE recipient_id = ? AND COALESCE(is_read, 0) = 0 AND {_NOT_DELETED}",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id),
    ).rowcount


def clear_read(conn, user_id):
    return conn.execute(
        "UPDATE messages SET is_deleted_by_recipient = 1 "
        f"WHERE recipient_id = ? AND is_read = 1 AND {_NOT_DELETED}",
        (user_id,),
    ).rowcount


def purge_deleted(conn, cutoff):
    """Remove read messages older than ``cutoff`` that both sides have deleted.
    Live mail is never touched: the inbox is shared with staff messaging."""
    return conn.execute(
        "DELETE FROM messages WHERE sent_at < ? AND is_read = 1 "
        "AND is_deleted_by_recipient = 1 AND is_deleted_by_sender = 1",
        (cutoff,),
    ).rowcount
