"""Chatbot fallback inbox.

When a backend gate (finance hold, library overdue, scheduling
conflict, incident logged) fires while the user is not in front of
the chatbot, we still want them to learn about it the next time
they open it. This module is a tiny queue:

* ``queue_message_for(user_id, message, source)`` — push.
* ``pop_messages_for(user_id, mark_read=True)`` — pull pending.

Bootstraps its own table on first call.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from education_system.post_18.university_system.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chatbot_pending_messages (
    msg_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    source     TEXT NOT NULL,
    message    TEXT NOT NULL,
    payload    TEXT,
    is_read    INTEGER NOT NULL DEFAULT 0,
    queued_at  TEXT NOT NULL,
    read_at    TEXT
)
"""

_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_chatbot_pending_user "
    "ON chatbot_pending_messages(user_id, is_read)",
)


def _ensure(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)
    for sql in _INDEX_SQL:
        conn.execute(sql)


def queue_message_for(user_id: str | int, message: str,
                      *, source: str = "system",
                      payload: str | None = None) -> int | None:
    """Push a contextual message for ``user_id`` to read on next chatbot open."""
    if not user_id or not message:
        return None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg_id: int | None = None
    try:
        with get_connection() as conn:
            _ensure(conn)
            cur = conn.execute(
                "INSERT INTO chatbot_pending_messages "
                "(user_id, source, message, payload, queued_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (str(user_id), source, message, payload, now),
            )
            conn.commit()
            msg_id = cur.lastrowid
    except Exception as exc:
        logger.warning("queue_message_for(%s) failed: %s", user_id, exc)
        return None

    # Mirror to email when the user has opted in (default-on). Same
    # notification, two channels, single config — purely best-effort.
    try:
        from education_system.post_18.university_system.modules.services.email_bus import (
            mirror_inbox_to_email,
        )
        mirror_inbox_to_email(user_id, message, source=source)
    except Exception:
        pass
    return msg_id


def pop_messages_for(user_id: str | int,
                     *, mark_read: bool = True,
                     limit: int = 20) -> list[dict[str, Any]]:
    """Return the user's pending messages and (optionally) mark them read."""
    if not user_id:
        return []
    out: list[dict[str, Any]] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            _ensure(conn)
            rows = conn.execute(
                "SELECT msg_id, source, message, payload, queued_at "
                "FROM chatbot_pending_messages "
                "WHERE user_id = ? AND is_read = 0 "
                "ORDER BY queued_at LIMIT ?",
                (str(user_id), int(limit)),
            ).fetchall()
            ids = [r["msg_id"] for r in rows]
            for r in rows:
                out.append(dict(r))
            if mark_read and ids:
                conn.execute(
                    f"UPDATE chatbot_pending_messages "
                    f"SET is_read = 1, read_at = ? "
                    f"WHERE msg_id IN ({','.join('?' for _ in ids)})",
                    (now, *ids),
                )
                conn.commit()
    except Exception as exc:
        logger.warning("pop_messages_for(%s) failed: %s", user_id, exc)
    return out


__all__ = ["queue_message_for", "pop_messages_for"]
